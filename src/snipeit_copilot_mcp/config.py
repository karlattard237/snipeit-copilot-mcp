"""Validated environment configuration for transport, auth, and limits."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from .errors import SnipeITError


class ConfigError(SnipeITError):
    def __init__(self, message: str):
        super().__init__("configuration_error", message)


def _integer(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if not minimum <= value <= maximum:
        raise ConfigError(f"{name} must be between {minimum} and {maximum}")
    return value


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} must be true or false")


def _service_url(name: str, value: str, *, allow_path: bool = False) -> str:
    value = value.strip().rstrip("/")
    if not value or len(value) > 2048 or any(ord(c) < 32 or c.isspace() for c in value):
        raise ConfigError(f"{name} is not a valid URL")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise ConfigError(f"{name} is not a valid URL") from exc
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigError(f"{name} must be an HTTP or HTTPS URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError(f"{name} must not contain credentials, a query, or a fragment")
    if not allow_path and parsed.path not in {"", "/"}:
        raise ConfigError(f"{name} must not contain a path")
    if "\\" in parsed.path or any(part in {".", ".."} for part in parsed.path.split("/")):
        raise ConfigError(f"{name} contains an unsafe path")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ConfigError(f"{name} must use HTTPS except on loopback")
    return value


def _csv(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    if not raw.strip():
        return ()
    values = tuple(value.strip() for value in raw.split(","))
    if any(not value for value in values):
        raise ConfigError(f"{name} contains an empty entry")
    return tuple(dict.fromkeys(values))


def _redirect_uris(name: str) -> tuple[str, ...]:
    """Validate exact HTTPS callbacks or a single left-most hostname wildcard."""
    values = _csv(name)
    for value in values:
        if len(value) > 2048 or any(ord(c) < 32 or c.isspace() for c in value):
            raise ConfigError(f"{name} contains an invalid redirect URI")
        try:
            parsed = urlsplit(value)
            _ = parsed.port
        except ValueError as exc:
            raise ConfigError(f"{name} contains an invalid redirect URI") from exc
        hostname = parsed.hostname or ""
        wildcard = hostname.startswith("*.") and hostname.count("*") == 1
        if "*" in value and not wildcard:
            raise ConfigError(f"{name} permits only a left-most hostname wildcard")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ConfigError(f"{name} redirect URIs must not contain credentials, queries, or fragments")
        if not hostname or not parsed.path.startswith("/") or "\\" in parsed.path or ".." in parsed.path.split("/"):
            raise ConfigError(f"{name} contains an unsafe redirect URI")
        loopback = hostname in {"localhost", "127.0.0.1", "::1"} and not wildcard
        if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
            raise ConfigError(f"{name} redirect URIs must use HTTPS except on loopback")
    return values


@dataclass(frozen=True, slots=True)
class Settings:
    snipeit_url: str
    snipeit_token: str
    oauth_client_id: str
    oauth_client_secret: str
    oauth_base_url: str
    oauth_redirect_path: str
    oauth_allowed_redirect_uris: tuple[str, ...]
    oauth_jwt_signing_key: str
    mcp_transport: str
    mcp_host: str
    mcp_port: int
    mcp_token: str
    allowed_tools: tuple[str, ...]
    ca_bundle: str
    verify_tls: bool
    timeout: int
    upload_timeout: int
    download_timeout: int
    long_timeout: int
    max_upload_bytes: int
    max_download_bytes: int
    max_json_bytes: int
    log_level: str

    @property
    def oauth_enabled(self) -> bool:
        return bool(self.oauth_client_id or self.oauth_client_secret)

    @property
    def http_enabled(self) -> bool:
        return self.mcp_transport in {"http", "streamable-http"}

    def validate(self, *, require_credentials: bool = True) -> None:
        if require_credentials and not self.snipeit_url:
            raise ConfigError("SNIPEIT_URL is required")
        if self.oauth_enabled:
            missing = [
                name
                for name, value in (
                    ("SNIPEIT_OAUTH_CLIENT_ID", self.oauth_client_id),
                    ("SNIPEIT_OAUTH_CLIENT_SECRET", self.oauth_client_secret),
                    ("SNIPEIT_MCP_BASE_URL", self.oauth_base_url),
                    ("SNIPEIT_OAUTH_JWT_SIGNING_KEY", self.oauth_jwt_signing_key),
                )
                if not value
            ]
            if missing:
                raise ConfigError("OAuth mode is missing: " + ", ".join(missing))
            if not self.http_enabled:
                raise ConfigError("OAuth mode requires Streamable HTTP")
            if not self.oauth_allowed_redirect_uris:
                raise ConfigError("OAuth mode requires SNIPEIT_OAUTH_ALLOWED_REDIRECT_URIS")
            if len(self.oauth_jwt_signing_key) < 32:
                raise ConfigError("SNIPEIT_OAUTH_JWT_SIGNING_KEY must be at least 32 characters")
        elif require_credentials and not self.snipeit_token:
            raise ConfigError("SNIPEIT_TOKEN is required in API-token mode")
        if self.http_enabled and not self.oauth_enabled and require_credentials:
            if len(self.mcp_token) < 32:
                raise ConfigError("SNIPEIT_MCP_TOKEN must be at least 32 characters in HTTP API-token mode")
            if self.mcp_token == self.snipeit_token:
                raise ConfigError("SNIPEIT_MCP_TOKEN must differ from SNIPEIT_TOKEN")
        if not self.verify_tls and os.getenv("SNIPEIT_ALLOW_INSECURE_TLS", "").lower() != "true":
            raise ConfigError("Disabling TLS verification also requires SNIPEIT_ALLOW_INSECURE_TLS=true")
        if self.ca_bundle:
            path = Path(self.ca_bundle).expanduser()
            if not path.is_file():
                raise ConfigError("SNIPEIT_CA_BUNDLE must name a readable CA bundle file")


def load_settings(*, require_credentials: bool = False) -> Settings:
    raw_url = os.getenv("SNIPEIT_URL", "").strip()
    base_url = os.getenv("SNIPEIT_MCP_BASE_URL", "").strip()
    transport = os.getenv("MCP_TRANSPORT", "streamable-http").strip().lower()
    if transport not in {"stdio", "http", "streamable-http"}:
        raise ConfigError("MCP_TRANSPORT must be stdio, http, or streamable-http")
    host = os.getenv("MCP_HOST", "127.0.0.1").strip()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not host or len(host) > 253 or any(c.isspace() or ord(c) < 32 for c in host):
            raise ConfigError("MCP_HOST is invalid")
    redirect_path = os.getenv("SNIPEIT_MCP_REDIRECT_PATH", "/auth/callback").strip()
    if not redirect_path.startswith("/") or ".." in redirect_path or "\\" in redirect_path:
        raise ConfigError("SNIPEIT_MCP_REDIRECT_PATH is unsafe")
    settings = Settings(
        snipeit_url=_service_url("SNIPEIT_URL", raw_url) if raw_url else "",
        snipeit_token=os.getenv("SNIPEIT_TOKEN", "").strip(),
        oauth_client_id=os.getenv("SNIPEIT_OAUTH_CLIENT_ID", "").strip(),
        oauth_client_secret=os.getenv("SNIPEIT_OAUTH_CLIENT_SECRET", "").strip(),
        oauth_base_url=_service_url("SNIPEIT_MCP_BASE_URL", base_url, allow_path=True) if base_url else "",
        oauth_redirect_path=redirect_path,
        oauth_allowed_redirect_uris=_redirect_uris("SNIPEIT_OAUTH_ALLOWED_REDIRECT_URIS"),
        oauth_jwt_signing_key=os.getenv("SNIPEIT_OAUTH_JWT_SIGNING_KEY", "").strip(),
        mcp_transport=transport,
        mcp_host=host,
        mcp_port=_integer("MCP_PORT", 8000, 1, 65535),
        mcp_token=os.getenv("SNIPEIT_MCP_TOKEN", "").strip(),
        allowed_tools=_csv("SNIPEIT_ALLOWED_TOOLS"),
        ca_bundle=os.getenv("SNIPEIT_CA_BUNDLE", "").strip(),
        verify_tls=_boolean("SNIPEIT_VERIFY_TLS", True),
        timeout=_integer("SNIPEIT_TIMEOUT", 20, 1, 300),
        upload_timeout=_integer("SNIPEIT_UPLOAD_TIMEOUT", 120, 1, 1800),
        download_timeout=_integer("SNIPEIT_DOWNLOAD_TIMEOUT", 120, 1, 1800),
        long_timeout=_integer("SNIPEIT_LONG_OPERATION_TIMEOUT", 300, 1, 3600),
        max_upload_bytes=_integer("SNIPEIT_MAX_UPLOAD_BYTES", 50 * 1024 * 1024, 1024, 1024 * 1024 * 1024),
        max_download_bytes=_integer("SNIPEIT_MAX_DOWNLOAD_BYTES", 100 * 1024 * 1024, 1024, 2 * 1024 * 1024 * 1024),
        max_json_bytes=_integer("SNIPEIT_MAX_JSON_RESPONSE_BYTES", 10 * 1024 * 1024, 1024, 100 * 1024 * 1024),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
    )
    settings.validate(require_credentials=require_credentials)
    return settings
