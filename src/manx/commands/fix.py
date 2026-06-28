"""manx fix "<报错信息>"：解释报错并给安全排查步骤。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from manx.commands.base import Context
from manx.render import DIM

_DATA = Path(__file__).parent.parent / "data" / "errors.json"


@lru_cache(maxsize=1)
def _entries() -> List[dict]:
    try:
        return json.loads(_DATA.read_text(encoding="utf-8")).get("entries", [])
    except (OSError, json.JSONDecodeError):
        return []


def _match(message: str) -> Optional[dict]:
    msg = message.lower()
    best = None
    best_len = 0
    for entry in _entries():
        for needle in entry.get("match", []):
            if needle.lower() in msg and len(needle) > best_len:
                best = entry
                best_len = len(needle)
    return best


def _render(ctx: Context, entry: dict) -> List[str]:
    r = ctx.renderer
    lines: List[str] = [r.heading(entry["title"]), ""]
    if entry.get("causes"):
        lines.append("常见原因：")
        for i, c in enumerate(entry["causes"], 1):
            lines.append(f"  {i}. {c}")
        lines.append("")
    if entry.get("steps"):
        lines.append("安全排查：")
        for i, s in enumerate(entry["steps"], 1):
            lines.append(f"  {i}. {s}")
    if entry.get("warn"):
        lines.append("")
        lines.append(r.c("注意：" + entry["warn"], "\033[33m"))
    return lines


def _build_prompt(ctx: Context, message: str) -> str:
    return (
        f"用户在终端遇到报错：\n  {message}\n\n"
        f"【系统上下文】\n{ctx.sysinfo.as_prompt_context()}\n\n"
        "请向 Linux 新手解释：1) 这个报错是什么意思；2) 常见原因；3) 安全的排查步骤（命令单独成行）。\n"
        "要求：先给只读的诊断命令（ls/whoami/ss/systemctl status/journalctl 等），"
        "不要让新手贸然执行删除、chmod 777、kill 等危险操作。简洁、终端友好。"
    )


def run(ctx: Context, message: str) -> int:
    r = ctx.renderer
    entry = _match(message)

    if ctx.as_json:
        payload = {
            "error": message,
            "matched": entry["title"] if entry else None,
            "causes": entry.get("causes", []) if entry else [],
            "steps": entry.get("steps", []) if entry else [],
            "warn": entry.get("warn") if entry else None,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    # 内置高频错误优先（更准、可控）；命中后可再用 LLM 补充，但默认用内置
    if entry and not ctx.llm_enabled():
        r.emit(_render(ctx, entry))
        return 0
    if entry and ctx.llm_enabled():
        # 命中内置：仍以内置为主，附 LLM 细化（保证安全步骤稳定）
        text = ctx.ask_llm(_build_prompt(ctx, message))
        if text:
            r.emit(text.splitlines())
        else:
            r.emit(_render(ctx, entry))
        return 0

    if ctx.llm_enabled():
        text = ctx.ask_llm(_build_prompt(ctx, message))
        if text:
            r.emit(text.splitlines())
            return 0

    r.emit([
        r.c("这条报错不在内置高频错误库里，也没有启用 LLM。", "\033[33m"),
        "",
        "通用排查思路：",
        "  1. 完整复制报错信息搜索关键词",
        "  2. 确认当前用户和路径：whoami；pwd",
        "  3. 相关服务看状态与日志：systemctl status <服务>；journalctl -u <服务> -n 100",
        "",
        r.c("配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 后，manx 能解释更多报错。", DIM),
    ])
    return 1
