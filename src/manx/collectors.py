"""本机资料采集层：执行只读命令获取 man / --help / builtin help / type。

要求：超时控制、输出长度限制、错误处理、缓存。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from typing import List, Optional

# shell builtin（外部不一定有同名可执行文件，需用 `help` 查）
SHELL_BUILTINS = {
    "cd", "pwd", "echo", "type", "help", "alias", "export", "source", ".",
    "set", "unset", "read", "test", "[", "exit", "return", "true", "false",
    "kill", "jobs", "fg", "bg", "wait", "trap", "ulimit", "umask", "history",
}

_TIMEOUT = 6
_MAX_CHARS = 16000  # 单个文档片段上限，避免把整本 man 灌进上下文


def _run(cmd: List[str], timeout: int = _TIMEOUT) -> Optional[str]:
    env = dict(os.environ)
    env["MANPAGER"] = "cat"
    env["PAGER"] = "cat"
    env["MANWIDTH"] = "80"
    env["LC_ALL"] = env.get("LC_ALL", "C")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            env=env,
            text=True,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    out = proc.stdout or ""
    if not out.strip():
        return None
    return out


def _clean_man(text: str) -> str:
    # man 输出可能含退格加粗序列 (x\bx)，去掉
    import re
    text = re.sub(r".\x08", "", text)
    return text


@dataclass
class DocBundle:
    """某个命令在本机收集到的全部资料。"""

    name: str
    exists: bool = False
    is_builtin: bool = False
    type_desc: str = ""        # `type cmd`
    path: str = ""             # which
    whatis: str = ""           # 一句话简介
    man: str = ""              # man 正文（截断）
    help_text: str = ""        # --help 或 builtin help

    @property
    def has_local_doc(self) -> bool:
        return bool(self.man or self.help_text or self.whatis)


def is_builtin(name: str) -> bool:
    if name in SHELL_BUILTINS:
        return True
    out = _run(["bash", "-c", f"type -t {shlex_quote(name)}"])
    return bool(out and out.strip() == "builtin")


def shlex_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)


@lru_cache(maxsize=128)
def command_exists(name: str) -> bool:
    if shutil.which(name):
        return True
    return is_builtin(name)


@lru_cache(maxsize=128)
def collect_doc(name: str) -> DocBundle:
    """收集单个命令的本机资料（带缓存）。"""
    bundle = DocBundle(name=name)

    path = shutil.which(name)
    builtin = is_builtin(name)
    bundle.exists = bool(path) or builtin
    bundle.is_builtin = builtin and not path
    bundle.path = path or ""

    # type
    t = _run(["bash", "-c", f"type {shlex_quote(name)} 2>&1"])
    if t:
        bundle.type_desc = t.strip().splitlines()[0][:200]

    # whatis（一句话）
    w = _run(["whatis", name])
    if w:
        bundle.whatis = w.strip().splitlines()[0][:200]

    if bundle.is_builtin:
        h = _run(["bash", "-c", f"help {shlex_quote(name)} 2>&1"])
        if h:
            bundle.help_text = h[:_MAX_CHARS]
        return bundle

    # man
    m = _run(["man", name])
    if m:
        bundle.man = _clean_man(m)[:_MAX_CHARS]

    # --help（很多命令支持；失败无所谓）
    h = _run([name, "--help"]) or _run(["bash", "-c", f"{shlex_quote(name)} --help 2>&1"])
    if h:
        bundle.help_text = h[:_MAX_CHARS]

    return bundle


def find_option_doc(bundle: DocBundle, option: str) -> Optional[str]:
    """在 man/help 文本中尝试定位某个参数的说明行。返回匹配片段或 None。"""
    text = bundle.man or bundle.help_text
    if not text:
        return None
    opt = option.strip()
    lines = text.splitlines()
    hits: List[str] = []
    # 归一化：-z / --gzip
    needles = {opt}
    if opt.startswith("--"):
        needles.add(opt.split("=", 1)[0])
    for i, line in enumerate(lines):
        stripped = line.strip()
        # 参数说明通常以 - 开头
        if _line_mentions_option(stripped, needles):
            block = [line]
            # 收集紧跟的缩进续行
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j]
                if nxt.strip() and (nxt.startswith(" ") or nxt.startswith("\t")) and not nxt.strip().startswith("-"):
                    block.append(nxt)
                else:
                    break
            hits.append("\n".join(block).rstrip())
            if len(hits) >= 3:
                break
    if hits:
        return "\n".join(hits)
    return None


def _line_mentions_option(line: str, needles) -> bool:
    import re
    for n in needles:
        # 词边界匹配，避免 -r 命中 --recursive
        pat = re.escape(n)
        if re.search(rf"(^|[\s,(]){pat}([\s,=\[\)]|$)", line):
            if line.lstrip().startswith("-") or "," in line[:30]:
                return True
    return False
