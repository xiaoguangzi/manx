"""发送给 LLM 前的敏感信息过滤（PRD 19.2）。"""

from __future__ import annotations

import re

_PATTERNS = [
    (re.compile(r"(?i)\b(api[_-]?key|token|password|passwd|secret|access[_-]?key)\s*[=:]\s*\S+"),
     r"\1=<REDACTED>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
     "<REDACTED PRIVATE KEY>"),
    (re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"), "Bearer <REDACTED>"),
    (re.compile(r"\b(sk|pk|ghp|gho|xox[baprs])-[A-Za-z0-9_\-]{12,}"), "<REDACTED_TOKEN>"),
    (re.compile(r"://[^/\s:@]+:([^/\s@]+)@"), "://<user>:<REDACTED>@"),
]


def redact(text: str) -> str:
    if not text:
        return text
    for pat, repl in _PATTERNS:
        text = pat.sub(repl, text)
    return text
