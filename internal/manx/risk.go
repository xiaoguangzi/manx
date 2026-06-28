package manx

import (
	"fmt"
	"strings"
)

var levelNames = map[int]string{0: "无风险", 1: "低", 2: "中", 3: "高", 4: "极高"}
var levelEN = map[int]string{0: "none", 1: "low", 2: "medium", 3: "high", 4: "critical"}

var systemDirs = []string{"/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/boot", "/var", "/dev", "/proc", "/sys", "/opt", "/root"}

var readonlyCommands = setOf("ls", "pwd", "cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep",
	"find", "stat", "file", "wc", "sort", "uniq", "cut", "tr", "echo", "printf",
	"ps", "top", "htop", "ss", "netstat", "lsof", "df", "du", "free", "uptime",
	"whoami", "id", "uname", "hostname", "date", "env", "which", "type", "whatis",
	"apropos", "man", "whereis", "history", "tree", "readlink", "basename", "dirname",
	"diff", "cmp", "md5sum", "sha256sum", "ip", "ping", "dig", "nslookup", "host",
	"systemctl", "journalctl")

var mutatingCommands = setOf("rm", "mv", "cp", "chmod", "chown", "chgrp", "ln", "mkdir", "rmdir", "touch",
	"dd", "mkfs", "fdisk", "parted", "mount", "umount", "kill", "pkill", "killall",
	"tee", "truncate", "shred", "sed")

type RiskFinding struct {
	Level          int      `json:"risk_level"`
	Reasons        []string `json:"reasons"`
	DangerousParts []string `json:"dangerous_parts"`
	SafePreview    string   `json:"safe_preview,omitempty"`
	Advice         []string `json:"advice"`
}

func (r RiskFinding) LevelName() string {
	if name, ok := levelNames[r.Level]; ok {
		return name
	}
	return "未知"
}

func (r RiskFinding) LevelEN() string {
	if name, ok := levelEN[r.Level]; ok {
		return name
	}
	return "unknown"
}

func (r *RiskFinding) bump(level int, reason, part string) {
	if level > r.Level {
		r.Level = level
	}
	if reason != "" && !contains(r.Reasons, reason) {
		r.Reasons = append(r.Reasons, reason)
	}
	if part != "" && !contains(r.DangerousParts, part) {
		r.DangerousParts = append(r.DangerousParts, part)
	}
}

func AssessLine(line string) RiskFinding {
	return Assess(Parse(line))
}

func Assess(pc ParsedCommand) RiskFinding {
	var result RiskFinding
	if pc.PipeToShell {
		result.bump(3, "把远程下载的内容直接管道给 shell 执行（curl|bash 模式），无法预先审查脚本", "| bash")
		result.addAdvice("先下载再看：curl -fsSLO <URL>，用 less 查看内容，确认安全后再 bash <脚本>")
	}
	for _, s := range pc.Segments {
		sf := AssessSegment(s)
		if sf.Level > result.Level {
			result.Level = sf.Level
		}
		result.Reasons = appendUnique(result.Reasons, sf.Reasons...)
		result.DangerousParts = appendUnique(result.DangerousParts, sf.DangerousParts...)
		result.Advice = appendUnique(result.Advice, sf.Advice...)
		if result.SafePreview == "" {
			result.SafePreview = sf.SafePreview
		}
	}
	return result
}

func AssessSegment(s Segment) RiskFinding {
	var f RiskFinding
	cmd := s.Command
	switch {
	case cmd == "rm":
		assessRM(&f, s)
	case cmd == "chmod" || cmd == "chown" || cmd == "chgrp":
		assessChmodChown(&f, s)
	case cmd == "dd" || cmd == "mkfs" || strings.HasPrefix(cmd, "mkfs.") || cmd == "fdisk" || cmd == "parted" || cmd == "mount" || cmd == "umount":
		assessDisk(&f, s)
	case cmd == "systemctl":
		assessService(&f, s)
	case cmd == "kill" || cmd == "pkill" || cmd == "killall":
		assessKill(&f, s)
	case cmd == "iptables" || cmd == "ip6tables" || cmd == "nft" || cmd == "ufw" || cmd == "firewall-cmd":
		f.bump(3, fmt.Sprintf("%s 修改防火墙规则，配置错误可能把自己挡在门外（尤其远程 SSH）", cmd), cmd)
		f.addAdvice("远程操作防火墙前，先准备好恢复方案，避免断开后无法连回")
	case cmd == "apt" || cmd == "apt-get" || cmd == "dnf" || cmd == "yum" || cmd == "pacman" || cmd == "zypper" || cmd == "brew" || cmd == "apk" || cmd == "dpkg" || cmd == "rpm":
		assessPackage(&f, s)
	case cmd == "mv" || cmd == "cp":
		if !s.HasOption("-n") && !s.HasOption("--no-clobber") {
			f.bump(2, fmt.Sprintf("%s 可能覆盖同名的既有文件", cmd), "")
			f.addAdvice("加 -n 可避免覆盖，或加 -i 在覆盖前确认")
		} else {
			f.bump(1, fmt.Sprintf("%s 文件操作", cmd), "")
		}
	case cmd == "shred" || cmd == "truncate":
		f.bump(3, fmt.Sprintf("%s 会销毁/清空文件内容，不可恢复", cmd), cmd)
	case cmd == "tee":
		if s.Sudo {
			if sysdir := targetsSystemDir(s); sysdir != "" {
				f.bump(3, fmt.Sprintf("sudo tee 写入系统文件 %s", sysdir), sysdir)
			}
		}
		if f.Level == 0 {
			f.bump(2, "tee 会写入/覆盖文件", "")
		}
	case cmd == "mkdir" || cmd == "rmdir" || cmd == "touch" || cmd == "ln":
		f.bump(1, fmt.Sprintf("%s 普通用户范围内的文件操作", cmd), "")
	case readonlyCommands[cmd]:
		f.bump(0, "", "")
	case mutatingCommands[cmd]:
		f.bump(2, fmt.Sprintf("%s 可能修改文件", cmd), "")
	default:
		f.bump(0, "", "")
	}

	if s.Sudo && f.Level >= 1 {
		f.bump(3, "使用 sudo，会以管理员（root）权限执行，影响面更大", "")
	} else if s.Sudo {
		f.Reasons = appendUnique(f.Reasons, "使用了 sudo（此处为只读查询，风险有限）")
	}

	if cmd == "find" {
		if contains(s.Args, "-delete") || s.HasOption("--delete") {
			f.bump(3, "find -delete 会真实删除匹配到的文件", "-delete")
			f.SafePreview = strings.ReplaceAll(s.Raw, "-delete", "-print")
			f.addAdvice("先把 -delete 换成 -print 预览匹配结果，确认后再删除")
		}
		if idx := indexOf(s.Args, "-exec"); idx >= 0 && idx+1 < len(s.Args) {
			after := s.Args[idx+1]
			if after == "rm" || after == "rmdir" || after == "shred" {
				f.bump(3, fmt.Sprintf("find -exec %s 会对每个匹配文件执行删除", after), "-exec")
			}
		}
	}

	return f
}

func assessRM(f *RiskFinding, s Segment) {
	recursive := s.HasOption("-r") || s.HasOption("-R") || s.HasOption("--recursive")
	force := s.HasOption("-f") || s.HasOption("--force")
	sysdir := targetsSystemDir(s)
	wide := homeOrCwdWide(s)
	switch {
	case recursive && force && (sysdir == "/" || sysdir == "/*" || wide == "~" || wide == "$HOME" || wide == "/"):
		f.bump(4, "rm -rf 作用于根/家目录/通配，可能删除大量不可恢复文件", s.Raw)
	case recursive && sysdir != "":
		f.bump(4, "递归删除系统目录 "+sysdir, sysdir)
	case recursive:
		f.bump(3, "rm -r 会递归删除整个目录树", "-r")
	case wide != "":
		f.bump(3, "删除目标含通配/家目录 "+wide+"，范围可能比预期大", wide)
	default:
		f.bump(2, "rm 会删除文件，删除后通常不可恢复", "")
	}
	if force {
		f.Reasons = appendUnique(f.Reasons, "-f 跳过确认，不会提示")
	}
	if len(s.Operands) > 0 {
		f.SafePreview = "ls -la " + strings.Join(firstN(s.Operands, 3), " ")
	} else {
		f.SafePreview = "ls -la"
	}
	f.addAdvice("先用 ls / find -print 预览要删除的内容，确认无误再执行")
}

func assessChmodChown(f *RiskFinding, s Segment) {
	recursive := s.HasOption("-R") || s.HasOption("--recursive")
	sysdir := targetsSystemDir(s)
	is777 := containsAny(s.Operands, "777", "0777", "a+rwx")
	switch {
	case recursive && sysdir != "":
		f.bump(4, "递归修改系统目录 "+sysdir+" 的权限/属主，可能破坏系统与安全边界", sysdir)
		f.addAdvice("不要递归修改系统目录。先定位你真正遇到的 Permission denied 文件")
	case recursive && is777:
		f.bump(3, "递归 chmod 777 会让所有人可读写执行，存在安全风险", "777")
	case recursive:
		f.bump(3, "-R 会递归影响所有子目录和文件", "")
	case is777:
		f.bump(2, "777 给所有用户读写执行权限，通常不必要", "")
	default:
		f.bump(2, "修改文件权限/属主", "")
	}
	if s.Command == "chmod" && is777 {
		f.addAdvice("脚本要可执行用 chmod +x 即可，不要用 777")
	}
}

func assessDisk(f *RiskFinding, s Segment) {
	raw := s.Raw
	if strings.Contains(raw, "of=/dev/") || s.Command == "mkfs" || strings.HasPrefix(s.Command, "mkfs.") {
		f.bump(4, "直接写入块设备 / 格式化，会清空磁盘上的数据", s.Command)
		f.addAdvice("反复确认目标设备路径（/dev/sdX）后再操作，否则可能清空整块盘")
	} else if s.Command == "fdisk" || s.Command == "parted" {
		level := 3
		for _, op := range s.Operands {
			if strings.HasPrefix(op, "/dev/") {
				level = 4
			}
		}
		f.bump(level, "分区工具，误操作会破坏磁盘分区表", s.Command)
	} else if s.Command == "mount" || s.Command == "umount" {
		f.bump(3, "挂载/卸载文件系统，可能影响数据访问", "")
	}
}

func assessService(f *RiskFinding, s Segment) {
	sub := firstNonOption(s.Operands)
	switch sub {
	case "stop", "restart", "disable", "mask", "kill":
		f.bump(3, "systemctl "+sub+" 会改变服务运行状态", sub)
		f.addAdvice("操作前先看状态：systemctl status <服务名>")
	case "start", "enable", "reload":
		f.bump(2, "systemctl "+sub+" 会改变服务状态", "")
	default:
		f.bump(0, "", "")
	}
}

func assessKill(f *RiskFinding, s Segment) {
	if s.Command == "pkill" || s.Command == "killall" {
		f.bump(3, s.Command+" 按名字批量结束进程，可能误杀同名进程", s.Command)
		f.addAdvice("先用 pgrep / ps aux | grep 确认要结束的进程")
		return
	}
	nine := s.HasOption("-9") || contains(s.Operands, "9") || contains(s.Args, "-KILL")
	reason := "kill 会结束进程"
	if nine {
		reason += "，-9 强制结束、进程无法清理"
	}
	f.bump(2, reason, "")
	f.addAdvice("先确认进程是什么再结束，必要时优先普通 kill（默认 TERM）")
}

func assessPackage(f *RiskFinding, s Segment) {
	sub := firstNonOption(s.Operands)
	removers := setOf("remove", "purge", "autoremove", "uninstall", "erase", "-R", "-Rns")
	installers := setOf("install", "add", "-S", "-Sy", "-Syu", "update", "upgrade", "dist-upgrade")
	readers := setOf("search", "list", "show", "info", "policy", "-Q", "-Qi", "-Ss")
	blob := append([]string{sub}, s.RawOptions...)
	if anyInSet(blob, removers) {
		part := sub
		if part == "" {
			part = s.Command
		}
		f.bump(3, s.Command+" 卸载软件包，可能连带删除依赖、影响其他程序", part)
		f.addAdvice("卸载前看清会移除哪些包（注意 autoremove / 依赖连带）")
	} else if anyInSet(blob, installers) {
		f.bump(2, s.Command+" 会安装/升级软件包，修改系统", "")
	} else if anyInSet(blob, readers) {
		f.bump(0, "", "")
	} else {
		f.bump(2, s.Command+" 包管理操作", "")
	}
}

func targetsSystemDir(s Segment) string {
	for _, op := range s.Operands {
		norm := strings.TrimRight(op, "/")
		if norm == "" {
			norm = "/"
		}
		if op == "/" || op == "/*" || contains(systemDirs, norm) {
			return op
		}
		for _, d := range systemDirs {
			if d != "/" && (op == d || strings.HasPrefix(op, d+"/")) {
				return op
			}
		}
	}
	return ""
}

func homeOrCwdWide(s Segment) string {
	for _, op := range s.Operands {
		switch op {
		case "~", "$HOME", ".", "*", "./*", "~/*", "$HOME/*":
			return op
		}
	}
	return ""
}

func (r *RiskFinding) addAdvice(s string) {
	r.Advice = appendUnique(r.Advice, s)
}
