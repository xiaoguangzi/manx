package manx

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

type LLMClient struct {
	Provider string
	Model    string
	APIKey   string
	BaseURL  string
	Timeout  time.Duration
}

func NewLLMClient(opts Options) (LLMClient, bool) {
	if opts.NoLLM {
		return LLMClient{}, false
	}
	provider := normalizeProvider(firstEnv("MANX_LLM_PROVIDER"))
	if provider == "" || provider == "auto" {
		switch {
		case os.Getenv("ANTHROPIC_API_KEY") != "":
			provider = "anthropic"
		case os.Getenv("OPENAI_API_KEY") != "":
			provider = "openai"
		case os.Getenv("MANX_API_KEY") != "" && os.Getenv("MANX_BASE_URL") != "":
			provider = "openai-compatible"
		case os.Getenv("MANX_API_KEY") != "":
			provider = "openai-compatible"
		default:
			return LLMClient{}, false
		}
	}
	if provider == "none" || provider == "off" {
		return LLMClient{}, false
	}
	c := LLMClient{Provider: provider, Timeout: 30 * time.Second}
	switch provider {
	case "anthropic":
		c.APIKey = firstEnv("MANX_API_KEY", "ANTHROPIC_API_KEY")
		c.Model = firstEnv("MANX_MODEL", "ANTHROPIC_MODEL")
		if c.Model == "" {
			c.Model = "claude-3-5-haiku-latest"
		}
		c.BaseURL = firstEnv("MANX_BASE_URL", "ANTHROPIC_BASE_URL")
		if c.BaseURL == "" {
			c.BaseURL = "https://api.anthropic.com/v1/messages"
		}
	case "openai":
		c.APIKey = firstEnv("MANX_API_KEY", "OPENAI_API_KEY")
		c.Model = firstEnv("MANX_MODEL", "OPENAI_MODEL")
		if c.Model == "" {
			c.Model = "gpt-4o-mini"
		}
		c.BaseURL = strings.TrimRight(firstEnv("MANX_BASE_URL", "OPENAI_BASE_URL"), "/")
		if c.BaseURL == "" {
			c.BaseURL = "https://api.openai.com/v1"
		}
	case "openai-compatible":
		c.Provider = "openai"
		c.APIKey = firstEnv("MANX_API_KEY", "OPENAI_COMPATIBLE_API_KEY")
		c.Model = firstEnv("MANX_MODEL", "OPENAI_COMPATIBLE_MODEL")
		c.BaseURL = strings.TrimRight(firstEnv("MANX_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL"), "/")
		if c.Model == "" || c.BaseURL == "" {
			return LLMClient{}, false
		}
	default:
		if firstEnv("MANX_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL") == "" {
			return LLMClient{}, false
		}
		c.Provider = "openai"
		c.APIKey = firstEnv("MANX_API_KEY", providerEnvKey(provider), "OPENAI_COMPATIBLE_API_KEY")
		c.Model = firstEnv("MANX_MODEL", "OPENAI_COMPATIBLE_MODEL")
		c.BaseURL = strings.TrimRight(firstEnv("MANX_BASE_URL", "OPENAI_COMPATIBLE_BASE_URL"), "/")
		if c.Model == "" || c.APIKey == "" {
			return LLMClient{}, false
		}
	}
	return c, c.APIKey != ""
}

func normalizeProvider(provider string) string {
	p := strings.ToLower(strings.TrimSpace(provider))
	switch p {
	case "compatible", "openai-compatible", "openai_compatible", "openai compatible",
		"third-party", "thirdparty", "custom",
		"deepseek", "qwen", "dashscope", "kimi", "moonshot", "zhipu", "glm", "siliconflow":
		return "openai-compatible"
	default:
		return p
	}
}

func providerEnvKey(provider string) string {
	if provider == "" {
		return ""
	}
	var b strings.Builder
	for _, ch := range provider {
		switch {
		case ch >= 'a' && ch <= 'z':
			b.WriteRune(ch - 'a' + 'A')
		case ch >= 'A' && ch <= 'Z':
			b.WriteRune(ch)
		case ch >= '0' && ch <= '9':
			b.WriteRune(ch)
		default:
			b.WriteRune('_')
		}
	}
	return b.String() + "_API_KEY"
}

func (c LLMClient) Ask(system, prompt string) (string, error) {
	prompt = Redact(prompt)
	system = Redact(system)
	ctx, cancel := context.WithTimeout(context.Background(), c.Timeout)
	defer cancel()
	switch c.Provider {
	case "anthropic":
		return c.askAnthropic(ctx, system, prompt)
	case "openai":
		return c.askOpenAI(ctx, system, prompt)
	default:
		return "", errors.New("unsupported LLM provider")
	}
}

func (c LLMClient) askAnthropic(ctx context.Context, system, prompt string) (string, error) {
	body := map[string]any{
		"model":      c.Model,
		"max_tokens": 900,
		"system":     system,
		"messages": []map[string]string{
			{"role": "user", "content": prompt},
		},
	}
	var resp struct {
		Content []struct {
			Type string `json:"type"`
			Text string `json:"text"`
		} `json:"content"`
		Error *struct {
			Message string `json:"message"`
		} `json:"error"`
	}
	if err := c.postJSON(ctx, c.BaseURL, map[string]string{
		"x-api-key":         c.APIKey,
		"anthropic-version": "2023-06-01",
	}, body, &resp); err != nil {
		return "", err
	}
	if resp.Error != nil {
		return "", errors.New(resp.Error.Message)
	}
	var parts []string
	for _, p := range resp.Content {
		if p.Text != "" {
			parts = append(parts, p.Text)
		}
	}
	return strings.TrimSpace(strings.Join(parts, "\n")), nil
}

func (c LLMClient) askOpenAI(ctx context.Context, system, prompt string) (string, error) {
	body := map[string]any{
		"model": c.Model,
		"messages": []map[string]string{
			{"role": "system", "content": system},
			{"role": "user", "content": prompt},
		},
		"temperature": 0.2,
	}
	var resp struct {
		Choices []struct {
			Message struct {
				Content string `json:"content"`
			} `json:"message"`
		} `json:"choices"`
		Error *struct {
			Message string `json:"message"`
		} `json:"error"`
	}
	if err := c.postJSON(ctx, c.BaseURL+"/chat/completions", map[string]string{
		"Authorization": "Bearer " + c.APIKey,
	}, body, &resp); err != nil {
		return "", err
	}
	if resp.Error != nil {
		return "", errors.New(resp.Error.Message)
	}
	if len(resp.Choices) == 0 {
		return "", errors.New("empty LLM response")
	}
	return strings.TrimSpace(resp.Choices[0].Message.Content), nil
}

func (c LLMClient) postJSON(ctx context.Context, url string, headers map[string]string, body any, out any) error {
	raw, err := json.Marshal(body)
	if err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(raw))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	res, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer res.Body.Close()
	data, err := io.ReadAll(io.LimitReader(res.Body, 2<<20))
	if err != nil {
		return err
	}
	if res.StatusCode < 200 || res.StatusCode >= 300 {
		return fmt.Errorf("LLM HTTP %d: %s", res.StatusCode, limitText(string(data), 600))
	}
	return json.Unmarshal(data, out)
}

func firstEnv(keys ...string) string {
	for _, k := range keys {
		if v := strings.TrimSpace(os.Getenv(k)); v != "" {
			return v
		}
	}
	return ""
}

func llmSystem(mode string) string {
	return "你是 manx，一个面向 Linux 新手的命令解释助手。回答必须简洁、终端友好、中文优先。只根据提供的本机文档和规则引擎结论回答；不确定就明说。风险等级只能采用规则引擎给出的等级，不能自行调高或调低。当前模式：" + mode
}
