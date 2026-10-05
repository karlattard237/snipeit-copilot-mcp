from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import httpx
import pytest
import respx
import fastmcp
from fastmcp.server.auth.oauth_proxy import OAuthProxy

from snipeit_copilot_mcp.auth import SharedTokenVerifier, SnipeITTokenVerifier, build_auth


@pytest.mark.asyncio
async def test_shared_token_boundary(settings) -> None:
    verifier = SharedTokenVerifier("a" * 40)
    assert await verifier.verify_token("wrong") is None
    access = await verifier.verify_token("a" * 40)
    assert access is not None
    assert access.client_id == "copilot-shared-service"


@pytest.mark.asyncio
async def test_opaque_oauth_token_is_verified_upstream(settings) -> None:
    verifier = SnipeITTokenVerifier(settings)
    with respx.mock as router:
        route = router.get("https://snipe.example/api/v1/users/me").mock(
            return_value=httpx.Response(200, json={"id": 7, "username": "john"})
        )
        first = await verifier.verify_token("opaque-passport-token")
        second = await verifier.verify_token("opaque-passport-token")
    assert first is not None and first.client_id == "7"
    assert second is first
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_bad_oauth_token_is_rejected(settings) -> None:
    verifier = SnipeITTokenVerifier(settings)
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/users/me").mock(return_value=httpx.Response(401))
        assert await verifier.verify_token("expired-token") is None


def test_oauth_proxy_builds_with_current_fastmcp_api(settings, monkeypatch) -> None:
    oauth_settings = replace(
        settings,
        oauth_client_id="client-id",
        oauth_client_secret="client-secret",
        oauth_base_url="https://mcp.example.com",
        oauth_allowed_redirect_uris=("https://global.consent.azure-apim.net/redirect",),
        oauth_jwt_signing_key="z" * 40,
        mcp_transport="streamable-http",
    )
    oauth_settings.validate(require_credentials=True)
    fastmcp_home = Path(__file__).parents[1] / ".tmp" / "fastmcp-test"
    fastmcp_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(fastmcp.settings, "home", fastmcp_home)
    assert isinstance(build_auth(oauth_settings), OAuthProxy)
