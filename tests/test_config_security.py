from __future__ import annotations

import base64
import logging

import pytest

from snipeit_copilot_mcp.config import ConfigError, load_settings
from snipeit_copilot_mcp.logging import JsonFormatter, redact
from snipeit_copilot_mcp.security import decode_base64, path_segment, safe_filename


def test_https_required_for_non_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNIPEIT_URL", "http://snipe.example")
    with pytest.raises(ConfigError):
        load_settings()


def test_loopback_http_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNIPEIT_URL", "http://127.0.0.1:8080")
    assert load_settings().snipeit_url == "http://127.0.0.1:8080"


def test_http_shared_token_requires_separate_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.delenv("SNIPEIT_MCP_TOKEN", raising=False)
    with pytest.raises(ConfigError):
        load_settings(require_credentials=True)


def test_http_shared_token_cannot_equal_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    value = "x" * 40
    monkeypatch.setenv("MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("SNIPEIT_TOKEN", value)
    monkeypatch.setenv("SNIPEIT_MCP_TOKEN", value)
    with pytest.raises(ConfigError):
        load_settings(require_credentials=True)


def test_insecure_tls_is_two_step(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNIPEIT_VERIFY_TLS", "false")
    with pytest.raises(ConfigError):
        load_settings()


def test_invalid_allowed_tool_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNIPEIT_ALLOWED_TOOLS", "assets_search,")
    with pytest.raises(ConfigError):
        load_settings()


@pytest.mark.parametrize(
    "value",
    [
        "http://evil.example/callback",
        "https://good.example/callback?code=leak",
        "https://user:pass@good.example/callback",
        "https://foo.*.example/callback",
        "https://good.example/../callback",
    ],
)
def test_unsafe_oauth_redirect_rejected(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("SNIPEIT_OAUTH_ALLOWED_REDIRECT_URIS", value)
    with pytest.raises(ConfigError):
        load_settings()


def test_safe_oauth_redirect_patterns(monkeypatch: pytest.MonkeyPatch) -> None:
    value = "https://global.consent.azure-apim.net/redirect,https://*.consent.azure-apim.net/redirect"
    monkeypatch.setenv("SNIPEIT_OAUTH_ALLOWED_REDIRECT_URIS", value)
    assert load_settings().oauth_allowed_redirect_uris == tuple(value.split(","))


@pytest.mark.parametrize("value", ["../secret", "a/b", "a\\b", ".", "..", "bad\x00name"])
def test_unsafe_filename(value: str) -> None:
    with pytest.raises(Exception):
        safe_filename(value)


@pytest.mark.parametrize("value", ["../1", "a/b", "%2fusers", "..", "bad\nvalue"])
def test_unsafe_path_segment(value: str) -> None:
    with pytest.raises(Exception):
        path_segment(value)


def test_base64_bounds() -> None:
    encoded = base64.b64encode(b"abcd").decode()
    assert decode_base64(encoded, 4) == b"abcd"
    with pytest.raises(Exception):
        decode_base64(encoded, 3)


def test_secret_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNIPEIT_TOKEN", "super-secret-value")
    text = redact("Authorization: Bearer super-secret-value password=hunter2 access_token=abc")
    assert "super-secret-value" not in text
    assert "hunter2" not in text
    assert "access_token=abc" not in text


def test_formatter_does_not_emit_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNIPEIT_TOKEN", "super-secret-value")
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "token super-secret-value", (), None)
    assert "super-secret-value" not in JsonFormatter().format(record)
