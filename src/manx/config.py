"""配置加载：~/.config/manx/config.toml + 环境变量。

为保持核心零依赖，这里实现一个极小的 TOML 子集解析器，只支持
`key = "string"` / `key = true|false` / `key = 整数`，足够覆盖本产品的配置。
环境变量优先级高于配置文件。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

DEFAULTS: Dict[str, Any] = {
    "language": "zh-CN",
    "mode": "beginner",          # beginner | short | pro
    "llm_provider": "auto",      # auto | anthropic | openai | none
    "llm_model": "",             # 留空则按 provider 取默认
    "llm_base_url": "",          # 留空用官方 base；可填第三方中转/自建网关
    "offline_first": True,
    "risk_guard": True,
    "max_output_lines": 80,
    "color": "auto",             # auto | always | never
}


def _config_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return Path(base) / "manx" / "config.toml"


def _parse_mini_toml(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        # 去掉行内注释（仅在非引号值上）
        if val and val[0] not in "\"'":
            val = val.split("#", 1)[0].strip()
        if not val:
            continue
        if val[0] in "\"'" and val[-1] == val[0]:
            out[key] = val[1:-1]
        elif val.lower() in ("true", "false"):
            out[key] = val.lower() == "true"
        elif val.lstrip("-").isdigit():
            out[key] = int(val)
        else:
            out[key] = val
    return out


@dataclass
class Config:
    language: str = DEFAULTS["language"]
    mode: str = DEFAULTS["mode"]
    llm_provider: str = DEFAULTS["llm_provider"]
    llm_model: str = DEFAULTS["llm_model"]
    llm_base_url: str = DEFAULTS["llm_base_url"]
    offline_first: bool = DEFAULTS["offline_first"]
    risk_guard: bool = DEFAULTS["risk_guard"]
    max_output_lines: int = DEFAULTS["max_output_lines"]
    color: str = DEFAULTS["color"]
    api_key: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


def load_config() -> Config:
    data: Dict[str, Any] = dict(DEFAULTS)

    path = _config_path()
    if path.is_file():
        try:
            data.update(_parse_mini_toml(path.read_text(encoding="utf-8")))
        except OSError:
            pass

    # 环境变量覆盖
    env_map = {
        "MANX_LANG": "language",
        "MANX_MODE": "mode",
        "MANX_LLM_PROVIDER": "llm_provider",
        "MANX_LLM_MODEL": "llm_model",
        "MANX_BASE_URL": "llm_base_url",
        "MANX_COLOR": "color",
    }
    for env, key in env_map.items():
        v = os.environ.get(env)
        if v:
            data[key] = v

    if os.environ.get("MANX_OFFLINE"):
        data["offline_first"] = os.environ["MANX_OFFLINE"].lower() in ("1", "true", "yes")

    cfg = Config(
        language=str(data.get("language", DEFAULTS["language"])),
        mode=str(data.get("mode", DEFAULTS["mode"])),
        llm_provider=str(data.get("llm_provider", DEFAULTS["llm_provider"])),
        llm_model=str(data.get("llm_model", DEFAULTS["llm_model"])),
        llm_base_url=str(data.get("llm_base_url", DEFAULTS["llm_base_url"])),
        offline_first=bool(data.get("offline_first", DEFAULTS["offline_first"])),
        risk_guard=bool(data.get("risk_guard", DEFAULTS["risk_guard"])),
        max_output_lines=int(data.get("max_output_lines", DEFAULTS["max_output_lines"])),
        color=str(data.get("color", DEFAULTS["color"])),
    )
    cfg.api_key = os.environ.get("MANX_API_KEY", "")
    return cfg
