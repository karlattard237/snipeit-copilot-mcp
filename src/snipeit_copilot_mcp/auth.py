"""Inbound shared-token and per-user Snipe-IT Passport OAuth providers."""

from __future__ import annotations

import asyncio
import json
import secrets
import ssl
import time

import httpx
from fastmcp.server.auth import TokenVerifier
from fastmcp.server.auth.auth import AccessToken
from fastmcp.server.auth.oauth_proxy import OAuthProxy

from .config import Settings


class SharedTokenVerifier(TokenVerifier):
    def __init__(self, expected: str):
        super().__init__(required_scopes=None)
        self.expected = expected

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 8192 or not secrets.compare_digest(token, self.expected):
            return None
        return AccessToken(token=token, client_id="copilot-shared-service", scopes=[], expires_at=None)


class SnipeITTokenVerifier(TokenVerifier):
    """Validate opaque Passport access tokens with Snipe-IT's users/me route."""

    def __init__(self, settings: Settings, cache_seconds: int = 30):
        super().__init__(required_scopes=None)
        self.settings = settings
        self.cache_seconds = cache_seconds
        self.cache: dict[str, tuple[float, AccessToken]] = {}
        self.lock = asyncio.Lock()

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token or len(token) > 8192 or any(c.isspace() or ord(c) < 32 for c in token):
            return None
        cached = self.cache.get(token)
        if cached and cached[0] > time.monotonic():
            return cached[1]
        verify: bool | ssl.SSLContext = self.settings.verify_tls
        if self.settings.ca_bundle:
            verify = ssl.create_default_context(cafile=self.settings.ca_bundle)
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.timeout,
                follow_redirects=False,
                trust_env=False,
                verify=verify,
            ) as client:
                response = await client.get(
                    f"{self.settings.snipeit_url}/api/v1/users/me",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json", "User-Agent": "snipeit-copilot-mcp/1.0"},
                )
            if response.status_code != 200 or len(response.content) > 1024 * 1024:
                return None
            user = json.loads(response.content)
            if not isinstance(user, dict) or not isinstance(user.get("id"), (str, int)):
                return None
        except (httpx.HTTPError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        access = AccessToken(token=token, client_id=str(user["id"]), scopes=[], expires_at=None)
        if self.cache_seconds:
            async with self.lock:
                now = time.monotonic()
                self.cache = {key: value for key, value in self.cache.items() if value[0] > now}
                if len(self.cache) >= 1024:
                    self.cache.pop(next(iter(self.cache)))
                self.cache[token] = (now + self.cache_seconds, access)
        return access


def build_auth(settings: Settings) -> TokenVerifier | OAuthProxy | None:
    if settings.oauth_enabled:
        return OAuthProxy(
            upstream_authorization_endpoint=f"{settings.snipeit_url}/oauth/authorize",
            upstream_token_endpoint=f"{settings.snipeit_url}/oauth/token",
            upstream_client_id=settings.oauth_client_id,
            upstream_client_secret=settings.oauth_client_secret,
            token_verifier=SnipeITTokenVerifier(settings),
            base_url=settings.oauth_base_url,
            redirect_path=settings.oauth_redirect_path,
            allowed_client_redirect_uris=list(settings.oauth_allowed_redirect_uris),
            jwt_signing_key=settings.oauth_jwt_signing_key,
            enable_cimd=False,
            require_authorization_consent=True,
        )
    if settings.http_enabled and settings.mcp_token:
        return SharedTokenVerifier(settings.mcp_token)
    return None
