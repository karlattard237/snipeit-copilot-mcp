"""Input bounds and path-component/file-name safety helpers."""

from __future__ import annotations

import base64
import binascii
import re
from urllib.parse import quote, unquote

from .errors import invalid

_SAFE_RESOURCE = re.compile(r"^[a-z][a-z0-9-]{0,63}$")


def path_segment(value: str, label: str = "identifier") -> str:
    if not value or len(value) > 1024 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise invalid(f"{label} is invalid")
    decoded = value
    for _ in range(4):
        updated = unquote(decoded)
        if updated == decoded:
            break
        decoded = updated
    if decoded in {".", ".."} or "/" in decoded or "\\" in decoded:
        raise invalid(f"{label} is not a safe path component")
    return quote(decoded, safe="")


def resource_name(value: str, allowed: set[str], label: str = "resource_type") -> str:
    if not _SAFE_RESOURCE.fullmatch(value) or value not in allowed:
        raise invalid(f"Unsupported {label}: {value}")
    return value


def safe_filename(value: str) -> str:
    if (
        not value
        or len(value) > 255
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise invalid("filename is unsafe")
    return value


def decode_base64(value: str, maximum: int) -> bytes:
    if len(value) > ((maximum + 2) // 3) * 4 + 8:
        raise invalid("base64 content exceeds the configured upload limit")
    try:
        content = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise invalid("content_base64 is not valid base64") from exc
    if len(content) > maximum:
        raise invalid("decoded content exceeds the configured upload limit")
    return content

