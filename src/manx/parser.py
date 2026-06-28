"""命令解析层：把一行命令拆成可分析的结构。

MVP 采用轻量解析（不接完整 Bash AST），识别：
管道 | 、重定向 > >> 、sudo、短参数组合、长参数、路径、通配符、命令替换 $()。
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Segment:
    """一条由管道分隔的子命令。"""

    raw: str
    sudo: bool = False
    command: str = ""
    args: List[str] = field(default_factory=list)
    options: List[str] = field(default_factory=list)       # 展开后的单个选项：-x -z -f --recursive（供风险引擎按字母判断）
    raw_options: List[str] = field(default_factory=list)    # 原样选项 token：-xzf -name --recursive（供结构展示）
    operands: List[str] = field(default_factory=list)       # 非选项参数（路径/值）
    redirects: List[str] = field(default_factory=list)

    def has_option(self, opt: str) -> bool:
        return opt in self.options


@dataclass
class ParsedCommand:
    raw: str
    segments: List[Segment] = field(default_factory=list)
    has_pipe: bool = False
    has_command_substitution: bool = False
    has_glob: bool = False
    pipe_to_shell: bool = False   # curl ... | bash 之类

    @property
    def commands(self) -> List[str]:
        return [s.command for s in self.segments if s.command]


_REDIRECT_RE = re.compile(r"^\d*>>?$|^<$|^&>$|^\d*>&\d*$")
_SHELL_RUNNERS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}


def _split_pipes(line: str) -> List[str]:
    """按未被引号包裹的 | 切分（忽略 ||）。"""
    parts: List[str] = []
    buf = ""
    quote = ""
    i = 0
    while i < len(line):
        ch = line[i]
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == "|":
            if i + 1 < len(line) and line[i + 1] == "|":  # || 逻辑或，MVP 不深入
                buf += "||"
                i += 2
                continue
            parts.append(buf)
            buf = ""
        else:
            buf += ch
        i += 1
    if buf.strip():
        parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def _explode_options(token: str) -> List[str]:
    """把 -xzf 展开成 -x -z -f；长参数保持整体。"""
    if token.startswith("--"):
        return [token]
    if token.startswith("-") and len(token) > 1 and token != "-":
        body = token[1:]
        # 把组合短参拆成单个选项字母，例如 -xzf -> -x -z -f
        return [f"-{c}" for c in body if c.isalpha()]
    return []


def parse_segment(raw: str) -> Segment:
    seg = Segment(raw=raw.strip())
    try:
        tokens = shlex.split(raw, comments=False)
    except ValueError:
        tokens = raw.split()

    if not tokens:
        return seg

    # sudo（可能带 -u 等，MVP 简单处理：跳过 sudo 及其纯选项）
    idx = 0
    while idx < len(tokens) and tokens[idx] in ("sudo", "doas"):
        seg.sudo = True
        idx += 1
        # 跳过 sudo 自身的选项（-u user, -E 等）
        while idx < len(tokens) and tokens[idx].startswith("-"):
            opt = tokens[idx]
            idx += 1
            if opt in ("-u", "--user", "-g", "--group"):
                idx += 1  # 跳过其值
    tokens = tokens[idx:]
    if not tokens:
        return seg

    seg.command = tokens[0]
    rest = tokens[1:]

    expect_redirect_target = False
    for tok in rest:
        if expect_redirect_target:
            seg.redirects.append(tok)
            expect_redirect_target = False
            continue
        if _REDIRECT_RE.match(tok):
            seg.redirects.append(tok)
            expect_redirect_target = True
            continue
        seg.args.append(tok)
        if tok.startswith("--"):
            base = tok.split("=", 1)[0]
            seg.options.append(base)
            seg.raw_options.append(base)
        elif tok.startswith("-") and len(tok) > 1:
            # 既保留原 token（-xzf / -name），又展开成单字母供风险引擎判断
            seg.raw_options.append(tok)
            seg.options.extend(_explode_options(tok))
        else:
            seg.operands.append(tok)
    return seg


def parse(line: str) -> ParsedCommand:
    line = line.strip()
    pc = ParsedCommand(raw=line)
    pc.has_command_substitution = bool(re.search(r"\$\(|`", line))
    pc.has_glob = bool(re.search(r"(^|\s)[^\s]*[*?]", line)) or "*" in line

    parts = _split_pipes(line)
    pc.has_pipe = len(parts) > 1
    for p in parts:
        pc.segments.append(parse_segment(p))

    # 管道执行远程脚本：上游是 curl/wget，下游是 shell
    if pc.has_pipe:
        cmds = pc.commands
        if any(c in ("curl", "wget", "fetch") for c in cmds) and any(
            c in _SHELL_RUNNERS for c in cmds
        ):
            pc.pipe_to_shell = True

    return pc
