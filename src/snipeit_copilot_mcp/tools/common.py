"""Shared action validation, extraction, and tool error handling."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from ..errors import SnipeITError, error_result, invalid

logger = logging.getLogger(__name__)
T = TypeVar("T")


def action(value: str, allowed: set[str], tool: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise invalid(f"{tool} action must be one of: {', '.join(sorted(allowed))}")
    return normalized


def resource(value: str, allowed: set[str], label: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise invalid(f"{label} must be one of: {', '.join(sorted(allowed))}")
    return normalized


def payload_json(value: str, label: str = "data_json") -> dict[str, Any]:
    if not value.strip():
        return {}
    if len(value.encode()) > 1024 * 1024:
        raise invalid(f"{label} exceeds the size limit")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise invalid(f"{label} must be a JSON object") from exc
    if not isinstance(parsed, dict):
        raise invalid(f"{label} must be a JSON object")
    return parsed


def compact(values: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value not in {"", 0, None}}


def result_item(payload: dict[str, Any]) -> object:
    for key in ("payload", "item", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def success_item(item: dict[str, object], message: str = "Operation completed") -> dict[str, object]:
    return {"success": True, "message": message, "item": item}


def success_list(items: list[dict[str, object]], meta: dict[str, object], message: str = "") -> dict[str, object]:
    result: dict[str, object] = {"success": True, "items": items, **meta}
    if message:
        result["message"] = message
    return result


async def guarded(operation: Callable[[], Awaitable[dict[str, object]]]) -> dict[str, object]:
    try:
        return await operation()
    except SnipeITError as exc:
        return error_result(exc)
    except (ValueError, TypeError) as exc:
        return error_result(SnipeITError("validation_failed", str(exc)[:1000]))
    except Exception as exc:  # fail closed without returning secrets or paths
        logger.exception("Unhandled tool failure: %s", type(exc).__name__)
        return error_result(SnipeITError("internal_error", "An unexpected internal error occurred"))
