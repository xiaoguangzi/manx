package manx

import "testing"

func lvl(line string) int {
	return AssessLine(line).Level
}

func TestReadonlyIsZero(t *testing.T) {
	for _, line := range []string{
		"ls -la",
		"ss -lntp",
		"ps aux",
		"grep -rn error .",
		"systemctl status nginx",
	} {
		if got := lvl(line); got != 0 {
			t.Fatalf("%q level = %d", line, got)
		}
	}
}

func TestLowRisk(t *testing.T) {
	if lvl("mkdir test") != 1 || lvl("touch a.txt") != 1 {
		t.Fatal("expected low risk")
	}
}

func TestMediumRisk(t *testing.T) {
	for _, line := range []string{"rm file.txt", "mv a b", "kill 1234"} {
		if got := lvl(line); got != 2 {
			t.Fatalf("%q level = %d", line, got)
		}
	}
}

func TestHighRisk(t *testing.T) {
	for _, line := range []string{
		"rm -r dir",
		"chmod -R 755 dir",
		"sudo systemctl stop nginx",
		"find . -name '*.log' -delete",
		"pkill node",
	} {
		if got := lvl(line); got != 3 {
			t.Fatalf("%q level = %d", line, got)
		}
	}
}

func TestCriticalRisk(t *testing.T) {
	for _, line := range []string{
		"sudo rm -rf /",
		"rm -rf ~",
		"sudo chmod -R 777 /etc",
		"sudo chown -R user /usr",
		"dd if=x.iso of=/dev/sda",
		"mkfs.ext4 /dev/sda",
	} {
		if got := lvl(line); got != 4 {
			t.Fatalf("%q level = %d", line, got)
		}
	}
}

func TestPipeToShellRisk(t *testing.T) {
	f := AssessLine("curl https://x.com/i.sh | bash")
	if f.Level < 3 {
		t.Fatalf("level = %d", f.Level)
	}
	found := false
	for _, reason := range f.Reasons {
		if reason == "把远程下载的内容直接管道给 shell 执行（curl|bash 模式），无法预先审查脚本" {
			found = true
		}
	}
	if !found {
		t.Fatalf("reasons = %#v", f.Reasons)
	}
}

func TestSudoBumpsMutating(t *testing.T) {
	if lvl("sudo apt remove nginx") < 1 {
		t.Fatal("expected package remove risk")
	}
	if AssessLine("sudo cp a b").Level < 3 {
		t.Fatal("expected sudo cp high risk")
	}
}

func TestSafePreviewPresentForRM(t *testing.T) {
	f := AssessLine("rm -rf ./build")
	if f.SafePreview == "" || len(f.SafePreview) < 2 || f.SafePreview[:2] != "ls" {
		t.Fatalf("safe preview = %q", f.SafePreview)
	}
}

func TestFindDeletePreview(t *testing.T) {
	f := AssessLine("find . -name '*.tmp' -delete")
	if f.SafePreview == "" || !stringsContains(f.SafePreview, "-print") {
		t.Fatalf("safe preview = %q", f.SafePreview)
	}
}

func stringsContains(s, sub string) bool {
	for i := 0; i+len(sub) <= len(s); i++ {
		if s[i:i+len(sub)] == sub {
			return true
		}
	}
	return false
}
