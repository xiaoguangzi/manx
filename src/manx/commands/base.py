"""子命令共享的运行上下文与工具函数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from manx import llm
from manx.config import Config
from manx.render import Renderer
from manx.sysinfo import SysInfo


@dataclass
class Context:
    config: Config
    sysinfo: SysInfo
    renderer: Renderer
    mode: str = "beginner"     # beginner | short | pro
    as_json: bool = False
    full: bool = False
    no_llm: bool = False

    def llm_enabled(self) -> bool:
        if self.no_llm or self.as_json:
            return False
        if self.config.llm_provider == "none":
            return False
        return llm.available(self.config.llm_provider)

    def ask_llm(self, prompt: str) -> Optional[str]:
        if not self.llm_enabled():
            return None
        res = llm.explain(prompt, self.config.llm_provider, self.config.llm_model)
        return res.text if res else None


def mode_instruction(mode: str) -> str:
    if mode == "short":
        return "用精简模式：只给一句作用 + 3~5 个最常用例子 + 关键参数列表，不超过 20 行。"
    if mode == "pro":
        return "用老手模式：直接给常用命令组合和危险参数清单，省略基础解释，紧凑输出。"
    return ("用新手模式：结构为【作用 / 最常用 / 参数 / 例子 / 常见坑 / 下一步】，"
            "解释通俗，命令单独成行方便复制。")
