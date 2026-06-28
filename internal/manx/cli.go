package manx

import (
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"runtime"
	"sort"
	"strings"
)

const Version = "1.0.0"

type Options struct {
	Mode   string
	JSON   bool
	Full   bool
	Color  string
	Help   bool
	Ver    bool
	NoLLM  bool
	Output io.Writer
}

const usage = `manx - 把 Linux 命令讲成人话（LLM 主路径，本地风险规则兜底）

用法：
  manx <命令>                    结合本机文档解释一个命令，如 manx tar
  manx explain "<整条命令>"       解释整条命令并标注风险
  manx ask "<想做什么>"           根据自然语言推荐命令
  manx fix "<报错信息>"           解释报错并给排查步骤
  manx option <命令> <参数>        解释某个参数，如 manx option tar -z

模式：  --beginner(默认) --short --pro
输出：  --json --full --no-llm --color=auto|always|never
其他：  --version -h/--help

LLM：设置 MANX_API_KEY/OPENAI_API_KEY/ANTHROPIC_API_KEY。
第三方 OpenAI-compatible 服务：设置 MANX_LLM_PROVIDER=openai-compatible、MANX_BASE_URL、MANX_MODEL。
`

func Run(argv []string) int {
	positional, opts := splitFlags(argv)
	if opts.Output == nil {
		opts.Output = os.Stdout
	}
	r := Renderer{Color: opts.Color, MaxLines: 80, Out: opts.Output}
	if opts.Full {
		r.MaxLines = 0
	}
	if opts.Mode == "" {
		opts.Mode = "beginner"
	}

	if opts.Ver {
		fmt.Fprintf(opts.Output, "manx %s\n", Version)
		return 0
	}
	if opts.Help || len(positional) == 0 || positional[0] == "help" {
		fmt.Fprint(opts.Output, usage)
		return 0
	}

	head := positional[0]
	rest := positional[1:]
	switch head {
	case "explain":
		if len(rest) == 0 {
			fmt.Fprintln(opts.Output, `用法：manx explain "<整条命令>"`)
			return 2
		}
		return runExplain(r, opts, strings.Join(rest, " "))
	case "ask":
		if len(rest) == 0 {
			fmt.Fprintln(opts.Output, `用法：manx ask "<想做什么>"`)
			return 2
		}
		return runAsk(r, opts, strings.Join(rest, " "))
	case "fix":
		if len(rest) == 0 {
			fmt.Fprintln(opts.Output, `用法：manx fix "<报错信息>"`)
			return 2
		}
		return runFix(r, opts, strings.Join(rest, " "))
	case "option":
		if len(rest) < 2 {
			fmt.Fprintln(opts.Output, "用法：manx option <命令> <参数>，如 manx option tar -z")
			return 2
		}
		return runOption(r, opts, rest[0], rest[1])
	default:
		return runCommand(r, opts, head)
	}
}

func splitFlags(argv []string) ([]string, Options) {
	var pos []string
	opts := Options{Color: "auto"}
	for _, a := range argv {
		switch {
		case a == "--short":
			opts.Mode = "short"
		case a == "--pro":
			opts.Mode = "pro"
		case a == "--beginner":
			opts.Mode = "beginner"
		case a == "--json":
			opts.JSON = true
		case a == "--full":
			opts.Full = true
		case a == "--no-llm" || a == "--offline":
			opts.NoLLM = true
		case a == "--color":
			opts.Color = "always"
		case strings.HasPrefix(a, "--color="):
			opts.Color = strings.TrimPrefix(a, "--color=")
		case a == "-h" || a == "--help":
			opts.Help = true
		case a == "-V" || a == "--version":
			opts.Ver = true
		default:
			pos = append(pos, a)
		}
	}
	return pos, opts
}

func runCommand(r Renderer, opts Options, name string) int {
	llm, ok := requireLLM(r, opts)
	if !ok {
		return 1
	}
	doc := CollectDoc(name)
	text, err := llm.Ask(llmSystem(opts.Mode), commandPrompt(name, doc))
	return emitLLMAnswer(r, opts, text, err)
}

func runExplain(r Renderer, opts Options, line string) int {
	pc := Parse(line)
	finding := Assess(pc)
	if opts.JSON {
		primary := ""
		if len(pc.Segments) > 0 {
			primary = pc.Segments[0].Command
		}
		return emitJSON(r.Out, map[string]any{
			"command":         primary,
			"raw":             line,
			"summary":         shortSummary(pc),
			"risk":            finding.LevelEN(),
			"risk_level":      finding.Level,
			"dangerous_parts": finding.DangerousParts,
			"reasons":         finding.Reasons,
			"safe_preview":    finding.SafePreview,
			"recommendation":  firstAdvice(finding),
			"has_pipe":        pc.HasPipe,
			"pipe_to_shell":   pc.PipeToShell,
		})
	}
	if llm, ok := NewLLMClient(opts); ok {
		text, err := llm.Ask(llmSystem(opts.Mode), explainPrompt(line, pc, finding))
		if err == nil && text != "" {
			lines := strings.Split(text, "\n")
			lines = append(lines, "", r.Dim("────────────────────────────"))
			lines = append(lines, renderRiskBlock(r, finding)...)
			r.Emit(lines)
			return 0
		}
		if !opts.NoLLM {
			r.Emit([]string{r.Warn("LLM 调用失败：" + err.Error()), ""})
		}
	}

	lines := []string{
		r.Warn("未启用 LLM，仅输出本地解析和风险规则。"),
		"",
		"命令：" + r.Cmd(line),
		"",
		r.Heading("结构："),
	}
	for _, seg := range pc.Segments {
		if seg.Command == "" {
			continue
		}
		if seg.Sudo {
			lines = append(lines, "  sudo               以管理员（root）权限执行")
		}
		lines = append(lines, fmt.Sprintf("  %-18s command", seg.Command))
		for _, opt := range seg.RawOptions {
			lines = append(lines, fmt.Sprintf("  %-18s option", opt))
		}
		for _, op := range seg.Operands {
			lines = append(lines, fmt.Sprintf("  %-18s operand", op))
		}
	}
	lines = append(lines, "")
	lines = append(lines, renderRiskBlock(r, finding)...)
	r.Emit(lines)
	return 0
}

func runAsk(r Renderer, opts Options, question string) int {
	llm, ok := requireLLM(r, opts)
	if !ok {
		return 1
	}
	text, err := llm.Ask(llmSystem(opts.Mode), askPrompt(question))
	return emitLLMAnswer(r, opts, text, err)
}

func runFix(r Renderer, opts Options, message string) int {
	llm, ok := requireLLM(r, opts)
	if !ok {
		return 1
	}
	text, err := llm.Ask(llmSystem(opts.Mode), fixPrompt(message))
	return emitLLMAnswer(r, opts, text, err)
}

func runOption(r Renderer, opts Options, name, opt string) int {
	llm, ok := requireLLM(r, opts)
	if !ok {
		return 1
	}
	doc := CollectDoc(name)
	snippet := FindOptionDoc(doc, opt)
	text, err := llm.Ask(llmSystem(opts.Mode), optionPrompt(name, opt, snippet, doc))
	return emitLLMAnswer(r, opts, text, err)
}

func requireLLM(r Renderer, opts Options) (LLMClient, bool) {
	llm, ok := NewLLMClient(opts)
	if ok {
		return llm, true
	}
	r.Emit([]string{
		r.Warn("这个命令需要 LLM。"),
		"",
		"配置方式：",
		"  export MANX_LLM_PROVIDER=openai-compatible",
		"  export MANX_BASE_URL=https://你的服务商/v1",
		"  export MANX_API_KEY=...",
		"  export MANX_MODEL=...",
		"",
		"官方 OpenAI/Anthropic 也支持：OPENAI_API_KEY 或 ANTHROPIC_API_KEY。",
	})
	return LLMClient{}, false
}

func emitLLMAnswer(r Renderer, opts Options, text string, err error) int {
	if err != nil {
		if opts.JSON {
			return emitJSON(r.Out, map[string]any{"error": err.Error()})
		}
		r.Emit([]string{r.Warn("LLM 调用失败：" + err.Error())})
		return 1
	}
	if opts.JSON {
		return emitJSON(r.Out, map[string]any{"answer": text})
	}
	r.Emit(strings.Split(strings.TrimSpace(text), "\n"))
	return 0
}

func commandPrompt(name string, doc DocBundle) string {
	var b strings.Builder
	fmt.Fprintf(&b, "用户想了解命令：%s\n\n", name)
	b.WriteString("请结合本机文档解释这个命令：用途、最常用用法、关键参数、新手容易误解的点、风险。不要复制 man 原文，不要编造不存在的参数。\n")
	if doc.TypeDesc != "" {
		b.WriteString("\n【type 结果】\n" + doc.TypeDesc + "\n")
	}
	if doc.Whatis != "" {
		b.WriteString("\n【whatis】\n" + doc.Whatis + "\n")
	}
	if doc.HelpText != "" {
		b.WriteString("\n【--help 片段】\n" + doc.HelpText + "\n")
	}
	if doc.ManText != "" {
		b.WriteString("\n【man 片段】\n" + doc.ManText + "\n")
	}
	if !doc.HasLocalDoc() {
		b.WriteString("\n本机没有找到可用文档。请明确说明资料不足，不要编造。\n")
	}
	return b.String()
}

func explainPrompt(line string, pc ParsedCommand, finding RiskFinding) string {
	var b strings.Builder
	fmt.Fprintf(&b, "请向 Linux 新手解释这条命令：\n  %s\n\n", line)
	b.WriteString("要求：先一句话说明它会做什么；再逐段解释命令、参数、路径/对象；最后使用规则引擎给出的风险等级解释风险。不要编造选项。\n")
	b.WriteString("\n【解析结构】\n")
	b.WriteString(mustJSON(pc))
	b.WriteString("\n\n【规则引擎风险结论（权威，不可改写等级）】\n")
	b.WriteString(mustJSON(map[string]any{
		"risk":            finding.LevelEN(),
		"risk_level":      finding.Level,
		"risk_name":       finding.LevelName(),
		"reasons":         finding.Reasons,
		"dangerous_parts": finding.DangerousParts,
		"safe_preview":    finding.SafePreview,
		"advice":          finding.Advice,
	}))
	b.WriteString("\n")
	seen := map[string]bool{}
	for _, seg := range pc.Segments {
		if seg.Command == "" || seen[seg.Command] {
			continue
		}
		seen[seg.Command] = true
		doc := CollectDoc(seg.Command)
		if doc.HelpText != "" {
			b.WriteString("\n【" + seg.Command + " --help 片段】\n" + limitText(doc.HelpText, 2500) + "\n")
		} else if doc.ManText != "" {
			b.WriteString("\n【" + seg.Command + " man 片段】\n" + limitText(doc.ManText, 2500) + "\n")
		}
	}
	return b.String()
}

func askPrompt(question string) string {
	var b strings.Builder
	fmt.Fprintf(&b, "用户用自然语言描述了一个 Linux 任务：%s\n\n", question)
	b.WriteString("请推荐 1 个最合适、对新手安全、本机大概率可用的命令，并逐项解释参数。涉及删除/覆盖/格式化/改权限时，必须先给只读预览命令，不要把危险命令作为第一答案。\n")
	b.WriteString("\n当前环境：" + SystemSummary() + "\n")
	return b.String()
}

func fixPrompt(message string) string {
	var b strings.Builder
	fmt.Fprintf(&b, "用户在终端遇到报错：\n  %s\n\n", message)
	b.WriteString("请向 Linux 新手解释：这个报错是什么意思、常见原因、安全排查步骤。优先给只读诊断命令，不要让新手贸然执行 rm、chmod 777、kill 等危险操作。\n")
	return b.String()
}

func optionPrompt(name, opt, snippet string, doc DocBundle) string {
	var b strings.Builder
	fmt.Fprintf(&b, "解释命令 %s 的参数 %s，面向 Linux 新手。\n\n", name, opt)
	if snippet != "" {
		b.WriteString("【本机文档中关于该参数的片段】\n")
		b.WriteString(snippet + "\n")
		b.WriteString("\n请给出：含义、1-2 个常见组合示例、相关注意点。命令单独成行，不要编造其他选项。\n")
	} else {
		b.WriteString("本机文档里没有确认这个参数。请明确告诉用户没有找到，可能是版本差异，建议运行 `" + name + " --help`，不要编造。\n")
	}
	if doc.TypeDesc != "" {
		b.WriteString("\n【type 结果】\n" + doc.TypeDesc + "\n")
	}
	return b.String()
}

func shortSummary(pc ParsedCommand) string {
	if len(pc.Segments) == 0 {
		return ""
	}
	seg := pc.Segments[0]
	if len(seg.Operands) > 0 {
		return seg.Command + "（作用于 " + strings.Join(firstN(seg.Operands, 3), ", ") + "）"
	}
	return seg.Command
}

func firstAdvice(f RiskFinding) string {
	if len(f.Advice) > 0 {
		return f.Advice[0]
	}
	return "确认后再执行"
}

func commandExists(name string) bool {
	if name == "" {
		return false
	}
	if _, err := exec.LookPath(name); err == nil {
		return true
	}
	switch name {
	case "cd", "help", "type", "alias", "export", "unset", "history":
		return true
	}
	return false
}

func emitJSON(w io.Writer, payload any) int {
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "  ")
	if err := enc.Encode(payload); err != nil {
		fmt.Fprintln(w, err)
		return 1
	}
	return 0
}

func mustJSON(v any) string {
	raw, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return fmt.Sprint(v)
	}
	return string(raw)
}

func SystemSummary() string {
	keys := []string{"GOOS", "GOARCH"}
	values := map[string]string{"GOOS": runtime.GOOS, "GOARCH": runtime.GOARCH}
	sort.Strings(keys)
	var parts []string
	for _, k := range keys {
		parts = append(parts, k+"="+values[k])
	}
	return strings.Join(parts, " ")
}
