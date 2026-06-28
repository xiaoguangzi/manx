package manx

func setOf(values ...string) map[string]bool {
	out := make(map[string]bool, len(values))
	for _, v := range values {
		out[v] = true
	}
	return out
}

func contains(values []string, needle string) bool {
	for _, v := range values {
		if v == needle {
			return true
		}
	}
	return false
}

func containsAny(values []string, needles ...string) bool {
	for _, n := range needles {
		if contains(values, n) {
			return true
		}
	}
	return false
}

func appendUnique(dst []string, values ...string) []string {
	for _, v := range values {
		if v != "" && !contains(dst, v) {
			dst = append(dst, v)
		}
	}
	return dst
}

func indexOf(values []string, needle string) int {
	for i, v := range values {
		if v == needle {
			return i
		}
	}
	return -1
}

func firstNonOption(values []string) string {
	for _, v := range values {
		if len(v) == 0 || v[0] != '-' {
			return v
		}
	}
	return ""
}

func anyInSet(values []string, set map[string]bool) bool {
	for _, v := range values {
		if set[v] {
			return true
		}
	}
	return false
}

func firstN(values []string, n int) []string {
	if len(values) <= n {
		return values
	}
	return values[:n]
}
