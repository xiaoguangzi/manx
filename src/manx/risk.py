"""风险规则层：硬编码的危险命令识别。

PRD 6.3 / 12.1：风险识别必须由规则引擎完成，LLM 只负责解释，不负责定级。

风险分级（PRD 第 10 章）：
  0 none      只读查询
  1 low       普通用户可控操作
  2 medium    可能覆盖/删除/移动文件
  3 high      递归删除、递归改权限、sudo 改系统、停服务
  4 critical  可能破坏系统/磁盘/启动项/安全边界
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from manx.parser import ParsedCommand, Segment, parse

LEVEL_NAMES = {0: "无风险", 1: "低", 2: "中", 3: "高", 4: "极高"}
LEVEL_EN = {0: "none", 1: "low", 2: "medium", 3: "high", 4: "critical"}

# 系统关键目录（递归改权限/删除/改属主时极危险）
SYSTEM_DIRS = (
    "/", "/etc", "/usr", "/bin", "/sbin", "/lib", "/lib64", "/boot",
    "/var", "/dev", "/proc", "/sys", "/opt", "/root",
)

# 只读命令（PRD 6.2 允许自动执行的范畴 + 常见查询）
READONLY_COMMANDS = {
    "ls", "pwd", "cat", "less", "more", "head", "tail", "grep", "egrep", "fgrep",
    "find", "stat", "file", "wc", "sort", "uniq", "cut", "tr", "echo", "printf",
    "ps", "top", "htop", "ss", "netstat", "lsof", "df", "du", "free", "uptime",
    "whoami", "id", "uname", "hostname", "date", "env", "which", "type", "whatis",
    "apropos", "man", "whereis", "history", "tree", "readlink", "basename", "dirname",
    "diff", "cmp", "md5sum", "sha256sum", "ip", "ping", "dig", "nslookup", "host",
    "systemctl", "journalctl",  # 仅在只读子命令时为 0，下面会校正
}

# 修改性命令（基础风险 medium，叠加具体规则）
MUTATING_COMMANDS = {
    "rm", "mv", "cp", "chmod", "chown", "chgrp", "ln", "mkdir", "rmdir", "touch",
    "dd", "mkfs", "fdisk", "parted", "mount", "umount", "kill", "pkill", "killall",
    "tee", "truncate", "shred", "sed",
}


@dataclass
class RiskFinding:
    level: int = 0
    reasons: List[str] = field(default_factory=list)
    dangerous_parts: List[str] = field(default_factory=list)
    safe_preview: Optional[str] = None
    advice: List[str] = field(default_factory=list)

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, "未知")

    @property
    def level_en(self) -> str:
        return LEVEL_EN.get(self.level, "unknown")

    def bump(self, level: int, reason: str, part: Optional[str] = None) -> None:
        self.level = max(self.level, level)
        if reason and reason not in self.reasons:
            self.reasons.append(reason)
        if part and part not in self.dangerous_parts:
            self.dangerous_parts.append(part)


def _targets_system_dir(seg: Segment) -> Optional[str]:
    for op in seg.operands:
        norm = op.rstrip("/") or "/"
        if op in ("/", "/*") or norm in SYSTEM_DIRS:
            return op
        # /etc/... 子路径也算系统目录
        for d in SYSTEM_DIRS:
            if d != "/" and (op == d or op.startswith(d + "/")):
                return op
    return None


def _is_home_or_cwd_wide(seg: Segment) -> Optional[str]:
    for op in seg.operands:
        if op in ("~", "$HOME", ".", "*", "./*", "~/*", "$HOME/*"):
            return op
    return None


def _assess_rm(fz: "RiskFinding", s: Segment) -> None:
    recursive = s.has_option("-r") or s.has_option("-R") or s.has_option("--recursive")
    force = s.has_option("-f") or s.has_option("--force")
    sysdir = _targets_system_dir(s)
    wide = _is_home_or_cwd_wide(s)

    if recursive and force and (sysdir in ("/", "/*") or wide in ("~", "$HOME", "/")):
        fz.bump(4, "rm -rf 作用于根/家目录/通配，可能删除大量不可恢复文件", s.raw)
    elif recursive and sysdir:
        fz.bump(4, f"递归删除系统目录 {sysdir}", sysdir)
    elif recursive:
        fz.bump(3, "rm -r 会递归删除整个目录树", "-r")
    elif wide:
        fz.bump(3, f"删除目标含通配/家目录 {wide}，范围可能比预期大", wide)
    else:
        fz.bump(2, "rm 会删除文件，删除后通常不可恢复")
    if force:
        fz.reasons.append("-f 跳过确认，不会提示")
    fz.safe_preview = "ls -la " + " ".join(s.operands[:3]) if s.operands else "ls -la"
    fz.advice.append("先用 ls / find -print 预览要删除的内容，确认无误再执行")


def _assess_chmod_chown(fz: "RiskFinding", s: Segment) -> None:
    recursive = s.has_option("-R") or s.has_option("--recursive")
    sysdir = _targets_system_dir(s)
    is_777 = any(o in ("777", "0777", "a+rwx") for o in s.operands)

    if recursive and sysdir:
        fz.bump(4, f"递归修改系统目录 {sysdir} 的权限/属主，可能破坏系统与安全边界", sysdir)
        fz.advice.append("不要递归修改系统目录。先定位你真正遇到的 Permission denied 文件")
    elif recursive and is_777:
        fz.bump(3, "递归 chmod 777 会让所有人可读写执行，存在安全风险", "777")
    elif recursive:
        fz.bump(3, "-R 会递归影响所有子目录和文件")
    elif is_777:
        fz.bump(2, "777 给所有用户读写执行权限，通常不必要")
    else:
        fz.bump(2, "修改文件权限/属主")
    if s.command == "chmod" and is_777:
        fz.advice.append("脚本要可执行用 chmod +x 即可，不要用 777")


def _assess_disk(fz: "RiskFinding", s: Segment) -> None:
    raw = s.raw
    if re.search(r"\bof=/dev/", raw) or s.command in ("mkfs",) or s.command.startswith("mkfs."):
        fz.bump(4, "直接写入块设备 / 格式化，会清空磁盘上的数据", s.command)
        fz.advice.append("反复确认目标设备路径（/dev/sdX）后再操作，否则可能清空整块盘")
    elif s.command in ("fdisk", "parted"):
        targets_dev = any(o.startswith("/dev/") for o in s.operands)
        fz.bump(4 if targets_dev else 3, "分区工具，误操作会破坏磁盘分区表", s.command)
    elif s.command in ("mount", "umount"):
        fz.bump(3, "挂载/卸载文件系统，可能影响数据访问")


def _assess_service(fz: "RiskFinding", s: Segment) -> None:
    sub = next((o for o in s.operands if not o.startswith("-")), "")
    if s.command == "systemctl":
        if sub in ("stop", "restart", "disable", "mask", "kill"):
            fz.bump(3, f"systemctl {sub} 会改变服务运行状态", sub)
            fz.advice.append(f"操作前先看状态：systemctl status <服务名>")
        elif sub in ("start", "enable", "reload"):
            fz.bump(2, f"systemctl {sub} 会改变服务状态")
        else:
            fz.bump(0, "")  # status / list 等只读


def _assess_kill(fz: "RiskFinding", s: Segment) -> None:
    if s.command in ("pkill", "killall"):
        fz.bump(3, f"{s.command} 按名字批量结束进程，可能误杀同名进程", s.command)
        fz.advice.append("先用 pgrep / ps aux | grep 确认要结束的进程")
    else:
        nine = s.has_option("-9") or "9" in s.operands or "-KILL" in s.args
        fz.bump(2, "kill 会结束进程" + ("，-9 强制结束、进程无法清理" if nine else ""))
        fz.advice.append("先确认进程是什么再结束，必要时优先普通 kill（默认 TERM）")


def _assess_firewall(fz: "RiskFinding", s: Segment) -> None:
    fz.bump(3, f"{s.command} 修改防火墙规则，配置错误可能把自己挡在门外（尤其远程 SSH）", s.command)
    fz.advice.append("远程操作防火墙前，先准备好恢复方案，避免断开后无法连回")


def _assess_pkg(fz: "RiskFinding", s: Segment) -> None:
    sub = next((o for o in s.operands if not o.startswith("-")), "")
    removers = {"remove", "purge", "autoremove", "uninstall", "erase", "-R", "-Rns"}
    installers = {"install", "add", "-S", "-Sy", "-Syu", "update", "upgrade", "dist-upgrade"}
    readers = {"search", "list", "show", "info", "policy", "-Q", "-Qi", "-Ss"}
    # pacman 用选项当子命令，回退看 raw_options
    blob = (sub, *s.raw_options)
    if any(x in removers for x in blob):
        fz.bump(3, f"{s.command} 卸载软件包，可能连带删除依赖、影响其他程序", sub or s.command)
        fz.advice.append("卸载前看清会移除哪些包（注意 autoremove / 依赖连带）")
    elif any(x in installers for x in blob):
        fz.bump(2, f"{s.command} 会安装/升级软件包，修改系统")
    elif any(x in readers for x in blob):
        fz.bump(0, "")
    else:
        fz.bump(2, f"{s.command} 包管理操作")


def assess_segment(s: Segment) -> RiskFinding:
    fz = RiskFinding()
    cmd = s.command

    # 管道执行远程脚本在整条命令层处理；这里先按命令名分派
    if cmd == "rm":
        _assess_rm(fz, s)
    elif cmd in ("chmod", "chown", "chgrp"):
        _assess_chmod_chown(fz, s)
    elif cmd == "dd" or cmd == "mkfs" or cmd.startswith("mkfs.") or cmd in ("fdisk", "parted", "mount", "umount"):
        _assess_disk(fz, s)
    elif cmd == "systemctl":
        _assess_service(fz, s)
    elif cmd in ("kill", "pkill", "killall"):
        _assess_kill(fz, s)
    elif cmd in ("iptables", "ip6tables", "nft", "ufw", "firewall-cmd"):
        _assess_firewall(fz, s)
    elif cmd in ("apt", "apt-get", "dnf", "yum", "pacman", "zypper", "brew", "apk", "dpkg", "rpm"):
        _assess_pkg(fz, s)
    elif cmd in ("mv", "cp"):
        # 覆盖既有文件
        if not (s.has_option("-n") or s.has_option("--no-clobber")):
            fz.bump(2, f"{cmd} 可能覆盖同名的既有文件")
            fz.advice.append("加 -n 可避免覆盖，或加 -i 在覆盖前确认")
        else:
            fz.bump(1, f"{cmd} 文件操作")
    elif cmd in ("shred", "truncate"):
        fz.bump(3, f"{cmd} 会销毁/清空文件内容，不可恢复", cmd)
    elif cmd == "tee":
        sysdir = _targets_system_dir(s)
        if s.sudo and sysdir:
            fz.bump(3, f"sudo tee 写入系统文件 {sysdir}", sysdir)
        else:
            fz.bump(2, "tee 会写入/覆盖文件")
    elif cmd in ("mkdir", "rmdir", "touch", "ln"):
        fz.bump(1, f"{cmd} 普通用户范围内的文件操作")
    elif cmd in READONLY_COMMANDS:
        fz.bump(0, "")
    elif cmd in MUTATING_COMMANDS:
        fz.bump(2, f"{cmd} 可能修改文件")
    else:
        fz.bump(0, "")

    # sudo 叠加：以管理员权限执行，至少抬到 high（只读查询除外）
    if s.sudo and fz.level >= 1:
        fz.bump(3, "使用 sudo，会以管理员（root）权限执行，影响面更大")
    elif s.sudo:
        fz.reasons.append("使用了 sudo（此处为只读查询，风险有限）")

    # find ... -delete / -exec rm
    if cmd == "find":
        if s.has_option("--delete") or "-delete" in s.args:
            fz.bump(3, "find -delete 会真实删除匹配到的文件", "-delete")
            fz.safe_preview = s.raw.replace("-delete", "-print")
            fz.advice.append("先把 -delete 换成 -print 预览匹配结果，确认后再删除")
        if "-exec" in s.args:
            after = s.args[s.args.index("-exec") + 1] if s.args.index("-exec") + 1 < len(s.args) else ""
            if after in ("rm", "rmdir", "shred"):
                fz.bump(3, f"find -exec {after} 会对每个匹配文件执行删除", "-exec")

    return fz


def assess(pc: ParsedCommand) -> RiskFinding:
    """对整条命令（可能含管道）评估，取最高风险并合并理由。"""
    result = RiskFinding()

    # 整条命令级别：管道执行远程脚本
    if pc.pipe_to_shell:
        result.bump(3, "把远程下载的内容直接管道给 shell 执行（curl|bash 模式），无法预先审查脚本", "| bash")
        result.advice.append("先下载再看：curl -fsSLO <URL>，用 less 查看内容，确认安全后再 bash <脚本>")

    for s in pc.segments:
        sf = assess_segment(s)
        result.level = max(result.level, sf.level)
        for r in sf.reasons:
            if r and r not in result.reasons:
                result.reasons.append(r)
        for p in sf.dangerous_parts:
            if p not in result.dangerous_parts:
                result.dangerous_parts.append(p)
        for a in sf.advice:
            if a not in result.advice:
                result.advice.append(a)
        if sf.safe_preview and not result.safe_preview:
            result.safe_preview = sf.safe_preview

    return result


def assess_line(line: str) -> RiskFinding:
    return assess(parse(line))
