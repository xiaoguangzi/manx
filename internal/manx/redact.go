package manx

import "regexp"

var redactors = []*regexp.Regexp{
	regexp.MustCompile(`(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*['"]?[^'"\s]+`),
	regexp.MustCompile(`(?i)(bearer\s+)[a-z0-9._~+/=-]+`),
	regexp.MustCompile(`(?s)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----`),
	regexp.MustCompile(`sk-[A-Za-z0-9_-]{16,}`),
	regexp.MustCompile(`AKIA[0-9A-Z]{16}`),
}

func Redact(s string) string {
	for _, re := range redactors {
		s = re.ReplaceAllStringFunc(s, func(match string) string {
			if len(match) >= 7 && (match[:7] == "Bearer " || match[:7] == "bearer ") {
				return match[:7] + "[REDACTED]"
			}
			return "[REDACTED]"
		})
	}
	return s
}
