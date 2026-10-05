from __future__ import annotations

import pytest

from snipeit_copilot_mcp.config import Settings


@pytest.fixture(autouse=True)
def configured_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SNIPEIT_URL", "https://snipe.example")
    monkeypatch.setenv("SNIPEIT_TOKEN", "upstream-test-token")
    monkeypatch.setenv("MCP_TRANSPORT", "stdio")
    monkeypatch.delenv("SNIPEIT_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("SNIPEIT_OAUTH_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("SNIPEIT_ALLOWED_TOOLS", raising=False)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        snipeit_url="https://snipe.example",
        snipeit_token="upstream-test-token",
        oauth_client_id="",
        oauth_client_secret="",
        oauth_base_url="",
        oauth_redirect_path="/auth/callback",
        oauth_allowed_redirect_uris=(),
        oauth_jwt_signing_key="",
        mcp_transport="stdio",
        mcp_host="127.0.0.1",
        mcp_port=8000,
        mcp_token="",
        allowed_tools=(),
        ca_bundle="",
        verify_tls=True,
        timeout=1,
        upload_timeout=2,
        download_timeout=2,
        long_timeout=3,
        max_upload_bytes=1024 * 1024,
        max_download_bytes=1024 * 1024,
        max_json_bytes=1024 * 1024,
        log_level="INFO",
    )

