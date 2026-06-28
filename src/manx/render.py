"""输出渲染层：彩色高亮、风险颜色、行数控制、窄终端适配。"""

from __future__ import annotations

import os
import shutil
import sys
from typing import List, Optional

from manx.risk import RiskFinding

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

RISK_COLOR = {0: GREEN, 1: GREEN, 2: YELLOW, 3: RED, 4: MAGENTA}


class Renderer:
    def __init__(self, color: str = "auto", max_lines: int = 80):
        self.max_lines = max_lines
        self.color_enabled = self._decide_color(color)
        self.width = min(shutil.get_terminal_size((80, 24)).columns, 100)

    @staticmethod
    def _decide_color(color: str) -> bool:
        if color == "always":
            return True
        if color == "never" or os.environ.get("NO_COLOR"):
            return False
        return sys.stdout.isatty()

    def c(self, text: str, *codes: str) -> str:
        if not self.color_enabled or not codes:
            return text
        return "".join(codes) + text + RESET

    def heading(self, text: str) -> str:
        return self.c(text, BOLD, CYAN)

    def cmd(self, text: str) -> str:
        return self.c(text, GREEN)

    def risk_label(self, finding: RiskFinding) -> str:
        color = RISK_COLOR.get(finding.level, YELLOW)
        return self.c(f"风险：{finding.level_name}", BOLD, color)

    def render_lines(self, lines: List[str]) -> str:
        if self.max_lines and len(lines) > self.max_lines:
            kept = lines[: self.max_lines - 1]
            kept.append(self.c(f"… 输出已截断（共 {len(lines)} 行，加 --full 查看全部）", DIM))
            lines = kept
        return "\n".join(lines)

    def emit(self, lines: List[str]) -> None:
        sys.stdout.write(self.render_lines(lines) + "\n")


def render_risk_block(r: Renderer, finding: RiskFinding) -> List[str]:
    """渲染风险段落。Level 0 时返回简短的“安全”说明。"""
    lines: List[str] = []
    if finding.level == 0:
        lines.append(r.c("风险：无", GREEN) + r.c("（只读查询，不会修改系统）", DIM))
        return lines

    lines.append(r.risk_label(finding))
    if finding.reasons:
        lines.append("原因：")
        for reason in finding.reasons:
            lines.append(f"  - {reason}")
    if finding.safe_preview:
        lines.append("")
        lines.append("先预览（只读，不会改动）：")
        lines.append("  " + r.cmd(finding.safe_preview))
    if finding.advice:
        lines.append("")
        lines.append("建议：")
        for a in finding.advice:
            lines.append(f"  - {a}")
    if finding.level >= 4:
        lines.append("")
        lines.append(r.c("结论：不要直接执行。请先说明你真正想解决的问题。", BOLD, MAGENTA))
    return lines
