"""manx ask "<自然语言>"：根据描述推荐本机可用的命令。"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from manx import collectors
from manx.commands.base import Context
from manx.render import DIM
from manx.risk import LEVEL_NAMES, assess_line

_DATA = Path(__file__).parent.parent / "data" / "scenarios.json"


@lru_cache(maxsize=1)
def _scenarios() -> List[dict]:
    try:
        return json.loads(_DATA.read_text(encoding="utf-8")).get("scenarios", [])
    except (OSError, json.JSONDecodeError):
        return []


def _score(question: str, scenario: dict) -> int:
    q = question.lower()
    score = 0
    for kw in scenario.get("keywords", []):
        if kw.lower() in q:
            score += 2 if not re.match(r"^[a-z]+$", kw.lower()) else 1
    return score


def _best_scenario(question: str) -> Optional[dict]:
    ranked = sorted(_scenarios(), key=lambda s: _score(question, s), reverse=True)
    if ranked and _score(question, ranked[0]) > 0:
        return ranked[0]
    return None


def _pick_command(scenario: dict) -> dict:
    """优先选择本机已安装的方案。"""
    primary = scenario["primary"]
    if all(collectors.command_exists(c) for c in primary.get("needs", [])):
        return primary
    fb = scenario.get("fallback")
    if fb and all(collectors.command_exists(c) for c in fb.get("needs", [])):
        return fb
    return primary  # 都没装也返回 primary，并在输出里提示


def _render_scenario(ctx: Context, scenario: dict) -> List[str]:
    r = ctx.renderer
    chosen = _pick_command(scenario)
    lines: List[str] = []
    is_primary = chosen is scenario["primary"]
    lines.append(r.heading("推荐命令："))
    lines.append("  " + r.cmd(chosen["cmd"]))
    if not is_primary:
        lines.append("  " + r.c(f"（本机没有 {scenario['primary']['cmd'].split()[0]}，改用上面这个等效命令）", DIM))
    lines.append("")
    # 含义块描述的是 primary 命令，仅在选用 primary 时展示，避免命令与解释对不上
    if is_primary and scenario.get("explain"):
        lines.append(r.heading("含义："))
        for e in scenario["explain"]:
            lines.append("  " + e)
        lines.append("")
    risk = scenario.get("risk", 0)
    if risk == 0:
        lines.append(r.c("风险：低", "\033[32m") + r.c("（只读查询，不会修改系统）", DIM))
    else:
        lines.append(r.c(f"风险：{LEVEL_NAMES.get(risk, '低')}", "\033[33m"))
    if scenario.get("note"):
        lines.append("")
        lines.append(r.c("提示：" + scenario["note"], DIM))
    missing = [c for c in chosen.get("needs", []) if not collectors.command_exists(c)]
    if missing:
        lines.append("")
        lines.append(r.c(f"注意：本机似乎没有 {', '.join(missing)}，命令可能无法直接运行。", "\033[33m"))
    return lines


def _build_prompt(ctx: Context, question: str) -> str:
    available = ", ".join(ctx.sysinfo.pkg_managers) or "未知"
    return (
        f"用户用自然语言描述了一个 Linux 任务：{question}\n\n"
        f"【系统上下文】\n{ctx.sysinfo.as_prompt_context()}\n\n"
        "请推荐 1 个最合适、对新手安全、本机大概率可用的命令，并逐项解释参数。要求：\n"
        "- 只推荐通用、安全的命令，不要花哨的 one-liner。\n"
        "- 如任务涉及删除/覆盖/格式化/改权限，必须先给只读预览命令，再给操作命令。\n"
        "- 不要把危险命令作为第一答案。\n"
        "- 标注风险高低。命令单独成行方便复制。\n"
        f"- 当前包管理器：{available}（据此选择安装类建议）。\n"
        "- 不确定本机是否有某命令时，说明可能需要先安装。"
    )


def run(ctx: Context, question: str) -> int:
    r = ctx.renderer
    scenario = _best_scenario(question)

    if ctx.as_json:
        if scenario:
            chosen = _pick_command(scenario)
            payload = {
                "question": question,
                "matched_scenario": scenario["title"],
                "command": chosen["cmd"],
                "risk": scenario.get("risk", 0),
                "explain": scenario.get("explain", []),
                "note": scenario.get("note"),
            }
        else:
            payload = {"question": question, "matched_scenario": None,
                       "command": None, "note": "无内置场景匹配，建议启用 LLM"}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    # LLM 优先（更灵活），但若命中内置场景且无 LLM，用场景库
    if ctx.llm_enabled():
        text = ctx.ask_llm(_build_prompt(ctx, question))
        if text:
            r.emit(text.splitlines())
            return 0

    if scenario:
        r.emit(_render_scenario(ctx, scenario))
        return 0

    r.emit([
        r.c("我没有匹配到内置场景，也没有启用 LLM。", "\033[33m"),
        "",
        "可以：",
        "  - 换一种说法再问（例如包含“端口/大文件/磁盘/日志/服务”等关键词）",
        "  - 配置 ANTHROPIC_API_KEY 或 OPENAI_API_KEY 后，manx 能自由回答更多问题",
    ])
    return 1
