package manx

import "strings"

type Segment struct {
	Raw        string
	Sudo       bool
	Command    string
	Args       []string
	Options    []string
	RawOptions []string
	Operands   []string
	Redirects  []string
}

func (s Segment) HasOption(opt string) bool {
	for _, o := range s.Options {
		if o == opt {
			return true
		}
	}
	return false
}

type ParsedCommand struct {
	Raw                    string
	Segments               []Segment
	HasPipe                bool
	HasCommandSubstitution bool
	HasGlob                bool
	PipeToShell            bool
}

func (p ParsedCommand) Commands() []string {
	var out []string
	for _, s := range p.Segments {
		if s.Command != "" {
			out = append(out, s.Command)
		}
	}
	return out
}

func Parse(line string) ParsedCommand {
	line = strings.TrimSpace(line)
	pc := ParsedCommand{
		Raw:                    line,
		HasCommandSubstitution: strings.Contains(line, "$(") || strings.Contains(line, "`"),
		HasGlob:                strings.ContainsAny(line, "*?"),
	}
	parts := splitPipes(line)
	pc.HasPipe = len(parts) > 1
	for _, part := range parts {
		pc.Segments = append(pc.Segments, ParseSegment(part))
	}
	if pc.HasPipe {
		hasDownloader := false
		hasShell := false
		for _, cmd := range pc.Commands() {
			switch cmd {
			case "curl", "wget", "fetch":
				hasDownloader = true
			case "bash", "sh", "zsh", "dash", "ksh", "fish":
				hasShell = true
			}
		}
		pc.PipeToShell = hasDownloader && hasShell
	}
	return pc
}

func ParseSegment(raw string) Segment {
	seg := Segment{Raw: strings.TrimSpace(raw)}
	tokens := shellFields(raw)
	if len(tokens) == 0 {
		return seg
	}

	idx := 0
	for idx < len(tokens) && (tokens[idx] == "sudo" || tokens[idx] == "doas") {
		seg.Sudo = true
		idx++
		for idx < len(tokens) && strings.HasPrefix(tokens[idx], "-") {
			opt := tokens[idx]
			idx++
			if opt == "-u" || opt == "--user" || opt == "-g" || opt == "--group" {
				idx++
			}
		}
	}
	tokens = tokens[idx:]
	if len(tokens) == 0 {
		return seg
	}

	seg.Command = tokens[0]
	expectRedirectTarget := false
	for _, tok := range tokens[1:] {
		if expectRedirectTarget {
			seg.Redirects = append(seg.Redirects, tok)
			expectRedirectTarget = false
			continue
		}
		if isRedirect(tok) {
			seg.Redirects = append(seg.Redirects, tok)
			expectRedirectTarget = true
			continue
		}
		seg.Args = append(seg.Args, tok)
		switch {
		case strings.HasPrefix(tok, "--"):
			base := strings.SplitN(tok, "=", 2)[0]
			seg.Options = append(seg.Options, base)
			seg.RawOptions = append(seg.RawOptions, base)
		case strings.HasPrefix(tok, "-") && len(tok) > 1:
			seg.RawOptions = append(seg.RawOptions, tok)
			seg.Options = append(seg.Options, explodeOptions(tok)...)
		default:
			seg.Operands = append(seg.Operands, tok)
		}
	}
	return seg
}

func splitPipes(line string) []string {
	var parts []string
	var b strings.Builder
	var quote rune
	runes := []rune(line)
	for i := 0; i < len(runes); i++ {
		ch := runes[i]
		if quote != 0 {
			b.WriteRune(ch)
			if ch == quote {
				quote = 0
			}
			continue
		}
		if ch == '\'' || ch == '"' {
			quote = ch
			b.WriteRune(ch)
			continue
		}
		if ch == '|' {
			if i+1 < len(runes) && runes[i+1] == '|' {
				b.WriteString("||")
				i++
				continue
			}
			part := strings.TrimSpace(b.String())
			if part != "" {
				parts = append(parts, part)
			}
			b.Reset()
			continue
		}
		b.WriteRune(ch)
	}
	if part := strings.TrimSpace(b.String()); part != "" {
		parts = append(parts, part)
	}
	return parts
}

func shellFields(s string) []string {
	var fields []string
	var b strings.Builder
	var quote rune
	escaped := false
	have := false
	for _, ch := range s {
		if escaped {
			b.WriteRune(ch)
			have = true
			escaped = false
			continue
		}
		if ch == '\\' && quote != '\'' {
			escaped = true
			have = true
			continue
		}
		if quote != 0 {
			if ch == quote {
				quote = 0
			} else {
				b.WriteRune(ch)
			}
			have = true
			continue
		}
		if ch == '\'' || ch == '"' {
			quote = ch
			have = true
			continue
		}
		if ch == ' ' || ch == '\t' || ch == '\n' {
			if have {
				fields = append(fields, b.String())
				b.Reset()
				have = false
			}
			continue
		}
		b.WriteRune(ch)
		have = true
	}
	if escaped {
		b.WriteRune('\\')
	}
	if have {
		fields = append(fields, b.String())
	}
	return fields
}

func explodeOptions(token string) []string {
	if strings.HasPrefix(token, "--") || token == "-" || !strings.HasPrefix(token, "-") {
		return nil
	}
	var opts []string
	for _, ch := range token[1:] {
		if (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') {
			opts = append(opts, "-"+string(ch))
		}
	}
	return opts
}

func isRedirect(tok string) bool {
	if tok == ">" || tok == ">>" || tok == "<" || tok == "&>" {
		return true
	}
	if strings.HasSuffix(tok, ">") || strings.HasSuffix(tok, ">>") {
		prefix := strings.TrimRight(tok, ">")
		if prefix == "" {
			return true
		}
		for _, ch := range prefix {
			if ch < '0' || ch > '9' {
				return false
			}
		}
		return true
	}
	if strings.Contains(tok, ">&") {
		return true
	}
	return false
}
