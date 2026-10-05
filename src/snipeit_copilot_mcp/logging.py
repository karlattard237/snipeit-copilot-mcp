"""Structured JSON logging with credential redaction."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

_SECRETS = ("SNIPEIT_TOKEN", "SNIPEIT_MCP_TOKEN", "SNIPEIT_OAUTH_CLIENT_SECRET", "SNIPEIT_OAUTH_JWT_SIGNING_KEY")
_PATTERNS = (
    re.compile(r"(?i)Bearer\s+[^\s,;]+"),
    re.compile(r"(?i)(authorization|client_secret|password|access_token|refresh_token)(\s*[:=]\s*)[^\s,;&]+"),
)


def redact(value: object) -> str:
    text = str(value)
    for name in _SECRETS:
        secret = os.getenv(name, "")
        if secret:
            text = text.replace(secret, "<redacted>")
    text = _PATTERNS[0].sub("Bearer <redacted>", text)
    text = _PATTERNS[1].sub(lambda m: f"{m.group(1)}{m.group(2)}<redacted>", text)
    return text


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
        }
        for name in ("correlation_id", "tool", "operation", "endpoint_family", "status", "duration_ms", "auth_mode"):
            value = getattr(record, name, None)
            if value is not None:
                payload[name] = redact(value)
        if record.exc_info:
            payload["exception"] = redact(record.exc_info[0].__name__ if record.exc_info[0] else "Exception")
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    selected = level if level in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"} else "INFO"
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, selected))

