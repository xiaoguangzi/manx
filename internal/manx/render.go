package manx

import (
	"fmt"
	"io"
	"os"
	"strings"
)

type Renderer struct {
	Color    string
	MaxLines int
	Out      io.Writer
}

const (
	ansiReset = "\033[0m"
	ansiBold  = "\033[1m"
	ansiDim   = "\033[2m"
	ansiGreen = "\033[32m"
	ansiYel   = "\033[33m"
	ansiRed   = "\033[31m"
)

func (r Renderer) Emit(lines []string) {
	if r.Out == nil {
		r.Out = os.Stdout
	}
	if r.MaxLines > 0 && len(lines) > r.MaxLines {
		lines = append(lines[:r.MaxLines], r.Dim(fmt.Sprintf("... 已截断，使用 --full 查看完整输出（共 %d 行）", len(lines))))
	}
	for _, line := range lines {
		fmt.Fprintln(r.Out, line)
	}
}

func (r Renderer) Heading(s string) string { return r.paint(s, ansiBold) }
func (r Renderer) Dim(s string) string     { return r.paint(s, ansiDim) }
func (r Renderer) OK(s string) string      { return r.paint(s, ansiGreen) }
func (r Renderer) Warn(s string) string    { return r.paint(s, ansiYel) }
func (r Renderer) Danger(s string) string  { return r.paint(s, ansiRed) }

func (r Renderer) Cmd(s string) string {
	return "`" + s + "`"
}

func (r Renderer) paint(s, code string) string {
	if r.Color == "never" || r.Color == "" {
		return s
	}
	if r.Color == "auto" && !stdoutIsTerminal() {
		return s
	}
	return code + s + ansiReset
}

func renderRiskBlock(r Renderer, f RiskFinding) []string {
	var lines []string
	label := "风险：" + f.LevelName()
	switch {
	case f.Level >= 4:
		lines = append(lines, r.Danger(label))
	case f.Level >= 2:
		lines = append(lines, r.Warn(label))
	default:
		lines = append(lines, r.OK(label))
	}
	if len(f.Reasons) > 0 {
		lines = append(lines, "原因：")
		for _, reason := range f.Reasons {
			lines = append(lines, "  - "+reason)
		}
	}
	if f.SafePreview != "" {
		lines = append(lines, "", "先预览：", "  "+r.Cmd(f.SafePreview))
	}
	if len(f.Advice) > 0 {
		lines = append(lines, "", "建议：")
		for _, advice := range f.Advice {
			lines = append(lines, "  - "+advice)
		}
	}
	if len(lines) == 1 && strings.HasPrefix(label, "风险：无风险") {
		lines = append(lines, r.Dim("只读查询，不会修改系统。"))
	}
	return lines
}

func stdoutIsTerminal() bool {
	info, err := os.Stdout.Stat()
	if err != nil {
		return false
	}
	return (info.Mode() & os.ModeCharDevice) != 0
}
