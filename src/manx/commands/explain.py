"""manx explain "<command line>"：解释完整命令 + 风险。"""

from __future__ import annotations

import json
from typing import List

from manx import cards, collectors
from manx.commands.base import Context
from manx.parser import ParsedCommand, parse
from manx.render import DIM, render_risk_block
from manx.risk import RiskFinding, assess


def _explain_option_token(card, tok: str):
    """把一个原样选项 token 拆成 (显示名, 含义) 列表。

    智能区分组合短参（tar -xzf -> -x -z -f）与单横杠长参（find -name）：
    - 长参 --xxx：整体查；
    - 整体能在卡片里查到（如 find -name、-delete）：整体显示；
    - 否则若每个字母都能在卡片查到：按组合短参逐字母展开（tar -xzf）；
    - 都不行：整体显示并标注未确认（避免把 -name 拆成 -n -a -m -e）。
    """
    if tok.startswith("--"):
        return [(tok, card.option_meaning(tok) if card else None)]

    whole = card.option_meaning(tok) if card else None
    if whole:
        return [(tok, whole)]

    letters = list(tok[1:])
    if card and len(letters) > 1 and all(card.option_meaning(f"-{c}") for c in letters):
        return [(f"-{c}", card.option_meaning(f"-{c}")) for c in letters]

    return [(tok, None)]


def _structure_lines(ctx: Context, pc: ParsedCommand) -> List[str]:
    """离线时给出逐段结构解释（基于卡片里的选项含义）。"""
    r = ctx.renderer
    lines: List[str] = []
    for seg in pc.segments:
        if not seg.command:
            continue
        card = cards.get_card(seg.command)
        if seg.sudo:
            lines.append(f"  {'sudo':<18} 以管理员（root）权限执行")
        purpose = card.purpose if card else (collectors.collect_doc(seg.command).whatis or "")
        lines.append(f"  {seg.command:<18} {purpose}")
        for tok in seg.raw_options:
            for opt, meaning in _explain_option_token(card, tok):
                if meaning:
                    lines.append(f"  {opt:<18} {meaning}")
                else:
                    lines.append(f"  {opt:<18} " + r.c("（本机文档未确认此参数，可能是版本差异）", DIM))
        for op in seg.operands:
            lines.append(f"  {op:<18} 操作对象（路径/参数）")
    return lines


def _build_prompt(ctx: Context, line: str, pc: ParsedCommand, finding: RiskFinding) -> str:
    parts: List[str] = []
    parts.append(f"请向 Linux 新手解释这条命令的作用、逐段结构、执行效果：\n  {line}\n")
    parts.append("【系统上下文】\n" + ctx.sysinfo.as_prompt_context())

    # 给 LLM 提供本机文档佐证
    seen = set()
    for seg in pc.segments:
        if seg.command and seg.command not in seen:
            seen.add(seg.command)
            card = cards.get_card(seg.command)
            if card:
                parts.append(f"\n【{seg.command} 卡片】\n" + json.dumps(
                    {"purpose": card.purpose,
                     "options": [{o.option: o.meaning} for o in card.common_options]},
                    ensure_ascii=False))
            doc = collectors.collect_doc(seg.command)
            snip = doc.man or doc.help_text
            if snip:
                parts.append(f"\n【{seg.command} man/help 片段】\n{snip[:2500]}")

    # 关键：把规则引擎的风险结论交给 LLM，禁止其改写等级
    parts.append("\n【规则引擎给出的风险结论（权威，不可改写等级）】")
    parts.append(f"风险等级：{finding.level_name}（{finding.level_en}）")
    if finding.reasons:
        parts.append("原因：" + "；".join(finding.reasons))
    if finding.safe_preview:
        parts.append("建议的只读预览命令：" + finding.safe_preview)

    parts.append(
        "\n要求：先一句话说明它会做什么；再逐段结构解释；最后照搬上面的风险等级并解释为什么危险，"
        "如风险≥高则明确建议先预览/不要直接执行。不要编造选项，不要调高或调低风险等级。"
    )
    return "\n".join(parts)


def run(ctx: Context, line: str) -> int:
    r = ctx.renderer
    pc = parse(line)
    finding = assess(pc)

    if ctx.as_json:
        primary = pc.segments[0] if pc.segments else None
        payload = {
            "command": primary.command if primary else "",
            "raw": line,
            "summary": _short_summary(pc),
            "risk": finding.level_en,
            "risk_level": finding.level,
            "dangerous_parts": finding.dangerous_parts,
            "reasons": finding.reasons,
            "safe_preview": finding.safe_preview,
            "recommendation": finding.advice[0] if finding.advice else "确认后再执行",
            "has_pipe": pc.has_pipe,
            "pipe_to_shell": pc.pipe_to_shell,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    llm_text = None
    if ctx.llm_enabled():
        llm_text = ctx.ask_llm(_build_prompt(ctx, line, pc, finding))

    lines: List[str] = []
    if llm_text:
        lines.extend(llm_text.splitlines())
        # 即便 LLM 解释过，也用规则引擎的风险块兜底（确保等级权威、不被改写）
        lines.append("")
        lines.append(r.c("─" * 28, DIM))
        lines.extend(render_risk_block(r, finding))
    else:
        lines.append(f"命令：{r.cmd(line)}")
        lines.append("")
        lines.append(r.heading("结构解释："))
        lines.extend(_structure_lines(ctx, pc))
        lines.append("")
        lines.extend(render_risk_block(r, finding))

    r.emit(lines)
    return 0


def _short_summary(pc: ParsedCommand) -> str:
    if not pc.segments:
        return ""
    seg = pc.segments[0]
    card = cards.get_card(seg.command)
    base = card.purpose if card else seg.command
    if seg.operands:
        return f"{base}（作用于 {', '.join(seg.operands[:3])}）"
    return base
