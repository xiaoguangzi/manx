package manx

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestOpenAILLMClient(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer test-key" {
			t.Fatalf("missing authorization header")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []map[string]any{
				{"message": map[string]string{"content": "ok from openai"}},
			},
		})
	}))
	defer server.Close()

	t.Setenv("MANX_LLM_PROVIDER", "openai")
	t.Setenv("MANX_API_KEY", "test-key")
	t.Setenv("MANX_BASE_URL", server.URL)
	t.Setenv("MANX_MODEL", "test-model")
	client, ok := NewLLMClient(Options{})
	if !ok {
		t.Fatal("expected enabled client")
	}
	got, err := client.Ask("system", "prompt")
	if err != nil {
		t.Fatal(err)
	}
	if got != "ok from openai" {
		t.Fatalf("got %q", got)
	}
}

func TestAnthropicLLMClient(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("x-api-key") != "test-key" {
			t.Fatalf("missing api key")
		}
		if r.Header.Get("anthropic-version") == "" {
			t.Fatalf("missing anthropic version")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"content": []map[string]string{
				{"type": "text", "text": "ok from anthropic"},
			},
		})
	}))
	defer server.Close()

	t.Setenv("MANX_LLM_PROVIDER", "anthropic")
	t.Setenv("MANX_API_KEY", "test-key")
	t.Setenv("MANX_BASE_URL", server.URL)
	t.Setenv("MANX_MODEL", "test-model")
	client, ok := NewLLMClient(Options{})
	if !ok {
		t.Fatal("expected enabled client")
	}
	got, err := client.Ask("system", "prompt")
	if err != nil {
		t.Fatal(err)
	}
	if got != "ok from anthropic" {
		t.Fatalf("got %q", got)
	}
}

func TestOpenAICompatibleAlias(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer third-party-key" {
			t.Fatalf("missing authorization header")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []map[string]any{
				{"message": map[string]string{"content": "ok from compatible"}},
			},
		})
	}))
	defer server.Close()

	t.Setenv("MANX_LLM_PROVIDER", "deepseek")
	t.Setenv("MANX_API_KEY", "third-party-key")
	t.Setenv("MANX_BASE_URL", server.URL)
	t.Setenv("MANX_MODEL", "deepseek-chat")
	client, ok := NewLLMClient(Options{})
	if !ok {
		t.Fatal("expected enabled compatible client")
	}
	if client.Provider != "openai" {
		t.Fatalf("provider = %q", client.Provider)
	}
	got, err := client.Ask("system", "prompt")
	if err != nil {
		t.Fatal(err)
	}
	if got != "ok from compatible" {
		t.Fatalf("got %q", got)
	}
}

func TestOpenAICompatibleRequiresBaseURLAndModel(t *testing.T) {
	t.Setenv("MANX_LLM_PROVIDER", "openai-compatible")
	t.Setenv("MANX_API_KEY", "third-party-key")
	t.Setenv("MANX_MODEL", "some-model")
	if _, ok := NewLLMClient(Options{}); ok {
		t.Fatal("expected disabled compatible client without base URL")
	}
}

func TestUnknownProviderWithBaseURLUsesOpenAICompatible(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/chat/completions" {
			t.Fatalf("path = %s", r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer custom-key" {
			t.Fatalf("missing authorization header")
		}
		_ = json.NewEncoder(w).Encode(map[string]any{
			"choices": []map[string]any{
				{"message": map[string]string{"content": "ok from custom"}},
			},
		})
	}))
	defer server.Close()

	t.Setenv("MANX_LLM_PROVIDER", "my-provider")
	t.Setenv("MY_PROVIDER_API_KEY", "custom-key")
	t.Setenv("MANX_BASE_URL", server.URL)
	t.Setenv("MANX_MODEL", "custom-model")
	client, ok := NewLLMClient(Options{})
	if !ok {
		t.Fatal("expected enabled compatible client")
	}
	got, err := client.Ask("system", "prompt")
	if err != nil {
		t.Fatal(err)
	}
	if got != "ok from custom" {
		t.Fatalf("got %q", got)
	}
}

func TestNoLLMDisablesClient(t *testing.T) {
	t.Setenv("MANX_API_KEY", "test-key")
	if _, ok := NewLLMClient(Options{NoLLM: true}); ok {
		t.Fatal("expected disabled client")
	}
}

func TestRedact(t *testing.T) {
	got := Redact("token=abc123 password: hunter2 Authorization: Bearer secret-token")
	if got == "" || got == "token=abc123 password: hunter2 Authorization: Bearer secret-token" {
		t.Fatalf("redaction did not change text: %q", got)
	}
}

func TestMain(m *testing.M) {
	for _, key := range []string{"MANX_LLM_PROVIDER", "MANX_API_KEY", "MANX_BASE_URL", "MANX_MODEL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"} {
		_ = os.Unsetenv(key)
	}
	os.Exit(m.Run())
}
