package manx

import (
	"context"
	"os/exec"
	"regexp"
	"strings"
	"time"
)

type DocBundle struct {
	Command  string
	Exists   bool
	TypeDesc string
	Whatis   string
	HelpText string
	ManText  string
}

func (d DocBundle) HasLocalDoc() bool {
	return d.TypeDesc != "" || d.Whatis != "" || d.HelpText != "" || d.ManText != ""
}

func CollectDoc(name string) DocBundle {
	doc := DocBundle{Command: name, Exists: commandExists(name)}
	if !safeCommandName(name) {
		return doc
	}
	doc.TypeDesc = runShort(2*time.Second, "sh", "-lc", "type "+shellQuote(name))
	doc.Whatis = runShort(2*time.Second, "whatis", name)
	doc.HelpText = runShort(2*time.Second, name, "--help")
	doc.ManText = runShort(2*time.Second, "man", name)
	doc.TypeDesc = limitText(Redact(doc.TypeDesc), 1200)
	doc.Whatis = limitText(Redact(doc.Whatis), 1200)
	doc.HelpText = limitText(Redact(doc.HelpText), 5000)
	doc.ManText = limitText(Redact(doc.ManText), 8000)
	return doc
}

func FindOptionDoc(doc DocBundle, opt string) string {
	if opt == "" {
		return ""
	}
	text := doc.HelpText
	if text == "" {
		text = doc.ManText
	}
	if text == "" {
		return ""
	}
	lines := strings.Split(text, "\n")
	var out []string
	for i, line := range lines {
		if strings.Contains(line, opt) {
			start := i - 1
			if start < 0 {
				start = 0
			}
			end := i + 2
			if end > len(lines) {
				end = len(lines)
			}
			out = append(out, lines[start:end]...)
			if len(out) > 8 {
				break
			}
		}
	}
	return limitText(strings.Join(out, "\n"), 1600)
}

func runShort(timeout time.Duration, name string, args ...string) string {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	cmd := exec.CommandContext(ctx, name, args...)
	out, err := cmd.CombinedOutput()
	if err != nil && len(out) == 0 {
		return ""
	}
	return strings.TrimSpace(string(out))
}

func limitText(s string, n int) string {
	if n <= 0 || len(s) <= n {
		return s
	}
	return s[:n] + "\n...[truncated]"
}

func safeCommandName(name string) bool {
	return regexp.MustCompile(`^[A-Za-z0-9_./+-]+$`).MatchString(name)
}

func shellQuote(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'"
}
