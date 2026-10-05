"""Stable internal and MCP-facing error semantics."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SnipeITError(Exception):
    """An upstream or local failure safe to translate into a tool result."""

    code: str
    message: str
    validation_errors: list[dict[str, str]] = field(default_factory=list)
    http_status: int = 0

    def __str__(self) -> str:
        return self.message


def error_result(error: SnipeITError) -> dict[str, object]:
    """Return the standard error envelope without leaking internal details."""
    result: dict[str, object] = {
        "success": False,
        "error_code": error.code,
        "message": error.message,
    }
    if error.validation_errors:
        result["validation_errors"] = error.validation_errors
    return result


def invalid(message: str) -> SnipeITError:
    return SnipeITError("validation_failed", message)


def unsupported(message: str) -> SnipeITError:
    return SnipeITError("unsupported_feature", message)

