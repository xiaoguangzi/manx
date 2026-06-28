"""LLM 解释层（可选增强）。

PRD 12：LLM 只负责把资料讲成人话，不负责风险定级 / 是否执行 / 参数是否存在。
默认 Anthropic（Claude，本项目原生），也支持 OpenAI。无 key 时返回 None，调用方降级到离线卡片。

防幻觉：system prompt 强约束“只能基于提供的资料回答，资料不足要明说不知道”。
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

from manx.redact import redact

# 最新、最强的 Claude 模型见知识库；解释类任务用快速且便宜的 Haiku 即可。
DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """你是 manx，一个面向 Linux 新手的命令行教练。你的输出会显示在终端里。

铁律：
1. 只能基于【提供的资料】回答：本机 man/help 片段、命令知识卡片、系统上下文、用户输入、以及规则引擎给出的风险结论。
2. 资料不足时，明确说“我没有在本机文档中找到”，绝不编造参数、选项或命令。
3. 不要自己改写风险等级——风险等级由规则引擎给出，你只负责把原因讲清楚。
4. 输出要短、准、可复制。不要寒暄，不要长篇大论。命令单独成行，方便复制。
5. 优先推荐本机已安装、对新手安全、通用的命令；涉及删除/覆盖/格式化/改权限时，先给只读预览命令。
6. 默认用中文（除非用户用英文提问）。术语首次出现可中英对照，如“解包(extract)”。
"""


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str


def _resolve_base(provider: str, base_url: str) -> str:
    """决定 API base（不含具体路径）。优先级：显式传入 > 标准环境变量 > 官方默认。

    base 只到 host 或 host/v1 层级，具体路径（/messages、/chat/completions）由调用方拼接。
    用户填 `https://relay.com`、`https://relay.com/`、`https://relay.com/v1` 都能正确处理。
    """
    base = (base_url or "").strip()
    if not base:
        if provider == "anthropic":
            base = os.environ.get("ANTHROPIC_BASE_URL", "")
        else:
            base = os.environ.get("OPENAI_BASE_URL", "")
    base = base.strip().rstrip("/")
    if not base:
        return "https://api.anthropic.com" if provider == "anthropic" else "https://api.openai.com"
    return base


def _join(base: str, path: str) -> str:
    """把 base 与官方路径拼起来，避免 /v1 重复。path 形如 '/v1/messages'。"""
    base = base.rstrip("/")
    if base.endswith("/v1") and path.startswith("/v1/"):
        path = path[len("/v1"):]
    return base + path


def _provider_and_key(provider_pref: str):
    """返回 (provider, api_key)。provider_pref: auto|anthropic|openai|none。"""
    if provider_pref == "none":
        return None, None

    anthropic_key = os.environ.get("MANX_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    openai_key = os.environ.get("MANX_API_KEY") or os.environ.get("OPENAI_API_KEY")

    if provider_pref == "anthropic":
        return ("anthropic", anthropic_key) if anthropic_key else (None, None)
    if provider_pref == "openai":
        return ("openai", openai_key) if openai_key else (None, None)

    # auto：优先 anthropic
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MANX_API_KEY"):
        if os.environ.get("ANTHROPIC_API_KEY"):
            return "anthropic", os.environ["ANTHROPIC_API_KEY"]
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", os.environ["OPENAI_API_KEY"]
    if os.environ.get("MANX_API_KEY"):
        # 无法判断归属，默认按 anthropic 试
        return "anthropic", os.environ["MANX_API_KEY"]
    return None, None


def available(provider_pref: str = "auto") -> bool:
    provider, key = _provider_and_key(provider_pref)
    return bool(provider and key)


def _call_anthropic(model: str, key: str, prompt: str, base_url: str = "") -> Optional[str]:
    base = _resolve_base("anthropic", base_url)
    try:
        import anthropic  # type: ignore
    except ImportError:
        return _call_anthropic_http(model, key, prompt, base)
    try:
        # base 到 host/v1 层级；anthropic SDK 期望 base_url 不含 /v1
        sdk_base = base[:-len("/v1")] if base.endswith("/v1") else base
        client = anthropic.Anthropic(api_key=key, base_url=sdk_base)
        msg = client.messages.create(
            model=model,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception:
        return None


def _call_anthropic_http(model: str, key: str, prompt: str, base: str = "") -> Optional[str]:
    import urllib.error
    import urllib.request

    base = base or _resolve_base("anthropic", "")
    body = json.dumps({
        "model": model,
        "max_tokens": 1500,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        _join(base, "/v1/messages"),
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError):
        return None


def _call_openai(model: str, key: str, prompt: str, base_url: str = "") -> Optional[str]:
    import urllib.error
    import urllib.request

    base = _resolve_base("openai", base_url)
    body = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 1500,
    }).encode()
    req = urllib.request.Request(
        _join(base, "/v1/chat/completions"),
        data=body,
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
    except (urllib.error.URLError, json.JSONDecodeError, KeyError, TimeoutError):
        return None


def explain(prompt: str, provider_pref: str = "auto", model: str = "",
            base_url: str = "") -> Optional[LLMResult]:
    """调用 LLM。失败/无 key 返回 None。输入会先做敏感信息脱敏。

    base_url 留空时用官方 base 或标准环境变量（ANTHROPIC_BASE_URL/OPENAI_BASE_URL）。
    """
    provider, key = _provider_and_key(provider_pref)
    if not provider or not key:
        return None

    prompt = redact(prompt)

    if provider == "anthropic":
        mdl = model or DEFAULT_ANTHROPIC_MODEL
        text = _call_anthropic(mdl, key, prompt, base_url)
    else:
        mdl = model or DEFAULT_OPENAI_MODEL
        text = _call_openai(mdl, key, prompt, base_url)

    if not text:
        return None
    return LLMResult(text=text.strip(), provider=provider, model=mdl)
