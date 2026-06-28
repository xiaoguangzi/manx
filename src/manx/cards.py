"""知识卡片层：高频命令的结构化解释，离线可用。

卡片以 JSON 存储于 data/cards/<cmd>.json。结构见 PRD 11.3。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_CARD_DIR = Path(__file__).parent / "data" / "cards"


@dataclass
class Example:
    cmd: str
    desc: str = ""


@dataclass
class Option:
    option: str
    meaning: str = ""


@dataclass
class Card:
    command: str
    purpose: str = ""
    common_tasks: List[Example] = field(default_factory=list)
    common_options: List[Option] = field(default_factory=list)
    common_mistakes: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    def option_meaning(self, opt: str) -> Optional[str]:
        for o in self.common_options:
            if o.option == opt or o.option.split(",")[0].strip() == opt:
                return o.meaning
            # -r 命中 "-r, --recursive"
            parts = [p.strip() for p in o.option.split(",")]
            if opt in parts:
                return o.meaning
        return None


@lru_cache(maxsize=1)
def _index() -> Dict[str, str]:
    """命令名/别名 -> 卡片文件名。"""
    idx: Dict[str, str] = {}
    if not _CARD_DIR.is_dir():
        return idx
    for p in _CARD_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        idx[data.get("command", p.stem)] = p.name
        for a in data.get("aliases", []):
            idx[a] = p.name
    return idx


def _to_card(data: dict) -> Card:
    return Card(
        command=data.get("command", ""),
        purpose=data.get("purpose", ""),
        common_tasks=[Example(e.get("cmd", ""), e.get("desc", "")) for e in data.get("common_tasks", [])],
        common_options=[Option(o.get("option", ""), o.get("meaning", "")) for o in data.get("common_options", [])],
        common_mistakes=list(data.get("common_mistakes", [])),
        risks=list(data.get("risks", [])),
        next_steps=list(data.get("next_steps", [])),
        aliases=list(data.get("aliases", [])),
    )


@lru_cache(maxsize=128)
def get_card(name: str) -> Optional[Card]:
    fname = _index().get(name)
    if not fname:
        return None
    try:
        data = json.loads((_CARD_DIR / fname).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _to_card(data)


def available_commands() -> List[str]:
    return sorted({k for k in _index().keys()})
