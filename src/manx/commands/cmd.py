"""manx <cmd>：命令新手解释。"""

from __future__ import annotations

import json
from typing import List, Optional

from manx import cards, collectors
from manx.commands.base import Context, mode_instruction
from manx.render import DIM


def _render_card_offline(ctx: Context, card: cards.Card, doc: collectors.DocBundle) -> List[str]:
    r = ctx.renderer
    lines: List[str] = []
    lines.append(f"{r.cmd(card.command)}：{card.purpose}")
    lines.append("")

    if ctx.mode != "pro":
        lines.append(r.heading("最常用："))
        for ex in card.common_tasks:
            lines.append("  " + r.cmd(ex.cmd))
            if ex.desc and ctx.mode != "short":
                lines.append("    " + r.c(ex.desc, DIM))
        lines.append("")
    else:
        lines.append(r.heading("常用组合："))
        for ex in card.common_tasks:
            lines.append("  " + r.cmd(ex.cmd))
        lines.append("")

    lines.append(r.heading("常用参数："))
    for opt in card.common_options:
        lines.append(f"  {opt.option:<22} {opt.meaning}")

    if ctx.mode != "short" and card.common_mistakes:
        lines.append("")
        lines.append(r.heading("新手坑："))
        for m in card.common_mistakes:
            lines.append(f"  - {m}")

    if card.risks:
        lines.append("")
        lines.append(r.heading("风险："))
        for rk in card.risks:
            lines.append(f"  - {rk}")

    if ctx.mode == "beginner" and card.next_steps:
        lines.append("")
        lines.append(r.heading("下一步："))
        for n in card.next_steps:
            lines.append(f"  - {n}")

    if not doc.exists:
        lines.append("")
        lines.append(r.c(f"提示：本机似乎没有安装 {card.command}。", DIM))
    return lines


def _build_llm_prompt(ctx: Context, name: str, card: Optional[cards.Card], doc: collectors.DocBundle) -> str:
    parts: List[str] = []
    parts.append(f"用户想了解命令：{name}\n")
    parts.append(mode_instruction(ctx.mode))
    parts.append("\n【系统上下文】\n" + ctx.sysinfo.as_prompt_context())
    if doc.type_desc:
        parts.append(f"\n【type 结果】\n{doc.type_desc}")
    if card:
        parts.append("\n【内置命令卡片（权威，可直接采用）】\n" + json.dumps(
            {
                "purpose": card.purpose,
                "common_tasks": [{"cmd": e.cmd, "desc": e.desc} for e in card.common_tasks],
                "common_options": [{"option": o.option, "meaning": o.meaning} for o in card.common_options],
                "common_mistakes": card.common_mistakes,
                "risks": card.risks,
            },
            ensure_ascii=False,
        ))
    snippet = doc.man or doc.help_text
    if snippet:
        parts.append(f"\n【本机 man/--help 片段（截断，作为事实依据）】\n{snippet[:6000]}")
    if not card and not snippet:
        parts.append("\n注意：本机没有该命令的文档，也没有内置卡片。如果你不确定，请明说找不到资料，不要编造参数。")
    parts.append("\n请输出面向 Linux 新手、终端友好的命令说明。只用提供的资料，不要编造选项。")
    return "\n".join(parts)


def run(ctx: Context, name: str) -> int:
    r = ctx.renderer
    card = cards.get_card(name)
    doc = collectors.collect_doc(name)

    if ctx.as_json:
        payload = {
            "command": name,
            "exists": doc.exists,
            "is_builtin": doc.is_builtin,
            "has_card": card is not None,
            "purpose": card.purpose if card else (doc.whatis or ""),
            "common_tasks": [{"cmd": e.cmd, "desc": e.desc} for e in card.common_tasks] if card else [],
            "common_options": [{"option": o.option, "meaning": o.meaning} for o in card.common_options] if card else [],
            "risks": card.risks if card else [],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    if not doc.exists and not card:
        r.emit([
            r.c(f"本机没有找到命令 {name}，也没有内置卡片。", "\033[33m"),
            "",
            "可以尝试：",
            "  - 确认拼写是否正确",
            f"  - 用包管理器搜索：{_install_hint(ctx, name)}",
            "  - 我不会编造它的参数。",
        ])
        return 1

    # 优先尝试 LLM（结合本机 man/help + 卡片），失败则离线卡片渲染
    llm_text = None
    if ctx.llm_enabled() and (doc.has_local_doc or card):
        llm_text = ctx.ask_llm(_build_llm_prompt(ctx, name, card, doc))

    if llm_text:
        r.emit(llm_text.splitlines())
        return 0

    if card:
        r.emit(_render_card_offline(ctx, card, doc))
        return 0

    # 无卡片但有本机文档：给出 whatis + 提示
    lines = []
    if doc.whatis:
        lines.append(f"{r.cmd(name)}：{doc.whatis}")
        lines.append("")
    lines.append(r.c("本机有该命令的文档，但没有内置新手卡片，也未启用 LLM。", DIM))
    lines.append("可以直接查看本机文档：")
    lines.append("  " + r.cmd(f"man {name}"))
    lines.append("  " + r.cmd(f"{name} --help"))
    lines.append("")
    lines.append(r.c("配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 后，manx 能把它讲成人话。", DIM))
    r.emit(lines)
    return 0


def _install_hint(ctx: Context, name: str) -> str:
    pm = ctx.sysinfo.primary_pkg_manager
    if pm == "apt":
        return f"sudo apt install {name}"
    if pm in ("dnf", "yum"):
        return f"sudo {pm} install {name}"
    if pm == "pacman":
        return f"sudo pacman -S {name}"
    if pm == "brew":
        return f"brew install {name}"
    if pm == "zypper":
        return f"sudo zypper install {name}"
    return f"用你的包管理器安装 {name}"
