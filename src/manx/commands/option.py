"""manx option <cmd> <option>：解释某命令的某个参数（必须在本机文档/卡片中确认存在）。"""

from __future__ import annotations

import json
from typing import List, Optional

from manx import cards, collectors
from manx.commands.base import Context
from manx.render import DIM


def _verify(name: str, option: str):
    """返回 (meaning, source, doc_snippet)。meaning 来自卡片；doc_snippet 来自本机 man/help。"""
    card = cards.get_card(name)
    meaning = card.option_meaning(option) if card else None
    doc = collectors.collect_doc(name)
    snippet = collectors.find_option_doc(doc, option)
    return meaning, doc, snippet


def _build_prompt(ctx: Context, name: str, option: str, meaning: Optional[str], snippet: Optional[str]) -> str:
    parts = [f"解释命令 {name} 的参数 {option}，面向 Linux 新手。\n"]
    if meaning:
        parts.append(f"【内置卡片含义（权威）】{option}: {meaning}")
    if snippet:
        parts.append(f"【本机 man/help 中关于该参数的片段】\n{snippet}")
    if not meaning and not snippet:
        parts.append("注意：本机文档和卡片里都没有确认这个参数。请明确告诉用户没有找到，可能是版本差异，"
                     "建议运行 `" + f"{name} --help`，不要编造该参数的含义。")
    else:
        parts.append("请给出：含义、1~2 个常见组合示例、相关注意点。命令单独成行，不要编造其他选项。")
    return "\n".join(parts)


def run(ctx: Context, name: str, option: str) -> int:
    r = ctx.renderer
    meaning, doc, snippet = _verify(name, option)
    confirmed = bool(meaning or snippet)

    if ctx.as_json:
        print(json.dumps({
            "command": name,
            "option": option,
            "confirmed": confirmed,
            "meaning": meaning,
            "doc_snippet": snippet,
        }, ensure_ascii=False, indent=2))
        return 0

    if ctx.llm_enabled():
        text = ctx.ask_llm(_build_prompt(ctx, name, option, meaning, snippet))
        if text:
            r.emit(text.splitlines())
            return 0

    # 离线渲染
    lines: List[str] = []
    if not confirmed:
        lines.append(r.c(f"注意：我没有在本机文档中确认 {name} 的参数 {option}。", "\033[33m"))
        lines.append("可能是版本差异，建议运行：")
        lines.append("  " + r.cmd(f"{name} --help"))
        if not doc.exists:
            lines.append("")
            lines.append(r.c(f"（本机似乎没有安装 {name}）", DIM))
        r.emit(lines)
        return 1

    lines.append(f"{r.cmd(name + ' ' + option)}：{meaning or '见下方本机文档片段'}")
    if snippet:
        lines.append("")
        lines.append(r.heading("本机文档："))
        for s in snippet.splitlines():
            lines.append("  " + s.strip())
    # 给点卡片里的相关示例
    card = cards.get_card(name)
    if card:
        rel = [e for e in card.common_tasks if option in e.cmd]
        if rel:
            lines.append("")
            lines.append(r.heading("常见组合："))
            for e in rel[:3]:
                lines.append("  " + r.cmd(e.cmd) + ("  " + r.c(e.desc, DIM) if e.desc else ""))
    r.emit(lines)
    return 0
