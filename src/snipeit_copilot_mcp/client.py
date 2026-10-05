"""Asynchronous, bounded, direct Snipe-IT REST client."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import ssl
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import unquote, urlencode

import httpx

from .config import Settings, load_settings
from .errors import SnipeITError

logger = logging.getLogger(__name__)

_ALLOWED_ROOTS = {
    "account", "accessories", "categories", "companies", "departments", "components",
    "consumables", "depreciations", "fields", "fieldsets", "groups", "hardware",
    "maintenances", "maintenance-types", "imports", "labels", "licenses", "locations",
    "manufacturers", "models", "notes", "settings", "statuslabels", "suppliers", "users",
    "kits", "reports", "version",
}
_PATH = re.compile(r"^[A-Za-z0-9._~%{}-]+(?:/[A-Za-z0-9._~%{}-]+)*$")
_QUERY_KEY = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_SAFE_METHODS = {"GET"}
_RETRYABLE_STATUS = {502, 503, 504}


def _validate_endpoint(path: str) -> str:
    if not path or len(path) > 2048 or path.startswith("/") or not _PATH.fullmatch(path):
        raise SnipeITError("invalid_request", "The requested Snipe-IT endpoint is not allowed")
    decoded = path
    slash_count = path.count("/")
    for _ in range(4):
        updated = unquote(decoded)
        if updated == decoded:
            break
        if updated.count("/") != slash_count or "\\" in updated or "?" in updated or "#" in updated:
            raise SnipeITError("invalid_request", "The requested Snipe-IT endpoint is unsafe")
        decoded = updated
    segments = decoded.split("/")
    if segments[0] not in _ALLOWED_ROOTS or any(segment in {"", ".", ".."} for segment in segments):
        raise SnipeITError("invalid_request", "The requested Snipe-IT endpoint is not allowed")
    return path


def _validate_params(params: dict[str, object] | None) -> dict[str, object]:
    if not params:
        return {}
    cleaned = {key: value for key, value in params.items() if value is not None and value != ""}
    if len(cleaned) > 60:
        raise SnipeITError("invalid_request", "Too many query parameters")
    for key, value in cleaned.items():
        if not _QUERY_KEY.fullmatch(key) or not isinstance(value, (str, int, float, bool)):
            raise SnipeITError("invalid_request", "A query parameter is invalid")
        if isinstance(value, str) and len(value) > 16_384:
            raise SnipeITError("invalid_request", "A query parameter is too long")
    if len(urlencode(cleaned).encode()) > 64 * 1024:
        raise SnipeITError("invalid_request", "Query parameters exceed the size limit")
    limit = cleaned.get("limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500):
        raise SnipeITError("invalid_request", "limit must be between 1 and 500")
    offset = cleaned.get("offset")
    if offset is not None and (isinstance(offset, bool) or not isinstance(offset, int) or not 0 <= offset <= 1_000_000):
        raise SnipeITError("invalid_request", "offset must be between 0 and 1000000")
    return cleaned


def _validation_entries(value: object) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    if isinstance(value, dict):
        for field, messages in value.items():
            values = messages if isinstance(messages, list) else [messages]
            for message in values:
                output.append({"field": str(field), "message": str(message)})
    elif isinstance(value, list):
        output.extend({"field": "request", "message": str(message)} for message in value)
    return output[:100]


def _message(payload: object, fallback: str) -> str:
    if not isinstance(payload, dict):
        return fallback
    value = payload.get("messages", payload.get("message", fallback))
    if isinstance(value, str) and value.strip():
        return value.strip()[:2000]
    if isinstance(value, dict):
        entries = _validation_entries(value)
        if entries:
            return "; ".join(f"{entry['field']}: {entry['message']}" for entry in entries)[:2000]
    return fallback


class SnipeITClient:
    """One request-scope async client, safe for concurrent operations."""

    def __init__(self, settings: Settings, token: str):
        if not token or len(token) > 8192 or any(c.isspace() or ord(c) < 32 for c in token):
            raise SnipeITError("authentication_failed", "A valid Snipe-IT bearer token is required")
        self.settings = settings
        self._token = token
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "SnipeITClient":
        verify: bool | ssl.SSLContext = self.settings.verify_tls
        if self.settings.ca_bundle:
            verify = ssl.create_default_context(cafile=self.settings.ca_bundle)
        self._http = httpx.AsyncClient(
            base_url=f"{self.settings.snipeit_url}/api/v1/",
            headers={
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/json",
                "User-Agent": "snipeit-copilot-mcp/1.0",
            },
            verify=verify,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
            timeout=httpx.Timeout(self.settings.timeout),
        )
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._http is not None:
            await self._http.aclose()
        self._http = None
        self._token = ""

    def _timeout(self, kind: str) -> httpx.Timeout:
        seconds = {
            "default": self.settings.timeout,
            "upload": self.settings.upload_timeout,
            "download": self.settings.download_timeout,
            "long": self.settings.long_timeout,
        }.get(kind, self.settings.timeout)
        return httpx.Timeout(seconds)

    async def _response(self, method: str, path: str, *, timeout_kind: str = "default", **kwargs: Any) -> tuple[httpx.Response, bytes]:
        if self._http is None:
            raise RuntimeError("SnipeITClient must be used as an async context manager")
        method = method.upper()
        if method not in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
            raise SnipeITError("invalid_request", "Unsupported HTTP method")
        path = _validate_endpoint(path)
        kwargs["params"] = _validate_params(kwargs.get("params"))
        kwargs["timeout"] = self._timeout(timeout_kind)
        attempts = 2 if method in _SAFE_METHODS else 1
        correlation_id = str(uuid.uuid4())
        started = time.perf_counter()
        for attempt in range(attempts):
            try:
                request = self._http.build_request(method, path, **kwargs)
                response = await self._http.send(request, stream=True)
                if response.status_code in _RETRYABLE_STATUS and attempt + 1 < attempts:
                    await response.aclose()
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                maximum = self.settings.max_json_bytes if timeout_kind != "download" else self.settings.max_download_bytes
                length = response.headers.get("Content-Length")
                if length and length.isdigit() and int(length) > maximum:
                    await response.aclose()
                    raise SnipeITError("response_too_large", "Snipe-IT response exceeds the configured size limit")
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > maximum:
                        await response.aclose()
                        raise SnipeITError("response_too_large", "Snipe-IT response exceeds the configured size limit")
                await response.aclose()
                logger.info(
                    "Snipe-IT request completed",
                    extra={
                        "correlation_id": correlation_id,
                        "endpoint_family": path.split("/", 1)[0],
                        "operation": method,
                        "status": response.status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                    },
                )
                return response, bytes(body)
            except httpx.TimeoutException as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                raise SnipeITError("timeout", "The Snipe-IT request timed out") from exc
            except httpx.ConnectError as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(0.05 * (attempt + 1))
                    continue
                raise SnipeITError("connectivity_failure", "Could not connect to Snipe-IT") from exc
            except httpx.TransportError as exc:
                name = type(exc).__name__.lower()
                code = "tls_failure" if "ssl" in name or "tls" in name else "connectivity_failure"
                message = "TLS validation failed while connecting to Snipe-IT" if code == "tls_failure" else "The Snipe-IT connection failed"
                raise SnipeITError(code, message) from exc
        raise SnipeITError("connectivity_failure", "The Snipe-IT request failed")

    @staticmethod
    def _http_error(response: httpx.Response, payload: object) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if status == 401:
            raise SnipeITError("authentication_failed", "Snipe-IT rejected the bearer token", http_status=status)
        if status == 403:
            raise SnipeITError("permission_denied", "The authenticated Snipe-IT user does not have permission for this operation", http_status=status)
        if status == 404:
            raise SnipeITError("not_found", "The requested Snipe-IT resource was not found", http_status=status)
        if status in {409, 423}:
            raise SnipeITError("conflict", _message(payload, "Snipe-IT reported a resource conflict"), http_status=status)
        if status == 422:
            messages = payload.get("messages") if isinstance(payload, dict) else None
            raise SnipeITError("validation_failed", _message(payload, "Snipe-IT rejected the request data"), _validation_entries(messages), status)
        if status == 429:
            raise SnipeITError("rate_limited", "Snipe-IT rate limited the request", http_status=status)
        if 300 <= status < 400:
            raise SnipeITError("unexpected_redirect", "Snipe-IT returned a redirect, which was refused", http_status=status)
        raise SnipeITError("upstream_error", f"Snipe-IT returned HTTP {status}", http_status=status)

    async def request_json(self, method: str, path: str, *, params: dict[str, object] | None = None, json_body: object = None, files: dict[str, object] | None = None, form: dict[str, str] | None = None, timeout_kind: str = "default") -> dict[str, Any]:
        kwargs: dict[str, object] = {"params": params or {}}
        if files is not None:
            kwargs["files"] = files
            if form:
                kwargs["data"] = form
        elif json_body is not None:
            try:
                encoded = json.dumps(json_body, ensure_ascii=False, separators=(",", ":"))
            except (TypeError, ValueError, RecursionError) as exc:
                raise SnipeITError("invalid_request", "Request data is not JSON serializable") from exc
            if len(encoded.encode()) > self.settings.max_upload_bytes:
                raise SnipeITError("request_too_large", "Request data exceeds the configured size limit")
            kwargs["json"] = json_body
            kwargs["headers"] = {"Content-Type": "application/json"}
        response, body = await self._response(method, path, timeout_kind=timeout_kind, **kwargs)
        if not body:
            payload: object = {}
        else:
            try:
                payload = json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
                kind = response.headers.get("content-type", "").lower()
                message = "Snipe-IT returned HTML instead of JSON" if "html" in kind or body.lstrip().startswith(b"<") else "Snipe-IT returned malformed JSON"
                raise SnipeITError("invalid_response", message) from exc
        self._http_error(response, payload)
        if not isinstance(payload, dict):
            raise SnipeITError("invalid_response", "Snipe-IT returned an unexpected JSON shape")
        status = payload.get("status")
        if isinstance(status, str) and status.lower().strip() in {"error", "failed", "failure"}:
            messages = payload.get("messages", payload.get("message"))
            entries = _validation_entries(messages)
            code = "not_found" if "not found" in _message(payload, "").lower() or "does not exist" in _message(payload, "").lower() else "validation_failed"
            raise SnipeITError(code, _message(payload, "Snipe-IT reported that the operation failed"), entries, response.status_code)
        rows = payload.get("rows")
        if rows is not None and (not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows)):
            raise SnipeITError("invalid_response", "Snipe-IT returned invalid list data")
        return payload

    async def request_bytes(self, method: str, path: str, *, json_body: object = None, timeout_kind: str = "download") -> tuple[bytes, str, str]:
        kwargs: dict[str, object] = {"params": {}, "headers": {"Accept": "application/octet-stream"}}
        if json_body is not None:
            kwargs["json"] = json_body
        response, body = await self._response(method, path, timeout_kind=timeout_kind, **kwargs)
        self._http_error(response, {})
        content_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
        disposition = response.headers.get("content-disposition", "")
        return body, content_type, disposition

    async def list_page(self, path: str, *, limit: int = 50, offset: int = 0, page: int = 0, per_page: int = 0, search: str = "", sort: str = "id", order: str = "asc", extra: dict[str, object] | None = None) -> tuple[list[dict[str, Any]], dict[str, object]]:
        params: dict[str, object] = {"sort": sort or "id", "order": order or "asc"}
        if page > 0 or per_page > 0:
            actual_page = page or 1
            actual_per_page = per_page or limit
            if not 1 <= actual_per_page <= 500 or actual_page < 1:
                raise SnipeITError("invalid_request", "page and per_page are outside the permitted range")
            params.update({"page": actual_page, "per_page": actual_per_page})
        else:
            if not 1 <= limit <= 500 or not 0 <= offset <= 1_000_000:
                raise SnipeITError("invalid_request", "limit or offset is outside the permitted range")
            params.update({"limit": limit, "offset": offset})
        if search:
            params["search"] = search
        if extra:
            params.update(extra)
        payload = await self.request_json("GET", path, params=params)
        rows = payload.get("rows", payload.get("data", []))
        if isinstance(rows, dict):
            rows = rows.get("data", [])
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise SnipeITError("invalid_response", "Snipe-IT returned invalid list data")
        total = payload.get("total", len(rows))
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            total = len(rows)
        meta: dict[str, object] = {"count": len(rows), "total": total}
        if page > 0 or per_page > 0:
            actual_page = int(payload.get("current_page", page or 1))
            actual_per_page = per_page or limit
            total_pages = int(payload.get("last_page", (total + actual_per_page - 1) // actual_per_page if actual_per_page else 1))
            meta.update({"page": actual_page, "per_page": actual_per_page, "current_page": actual_page, "total_pages": total_pages, "has_more": actual_page < total_pages})
        else:
            meta.update({"limit": limit, "offset": offset, "has_more": offset + len(rows) < total})
        return rows, meta


def resolve_upstream_token(settings: Settings) -> str:
    if not settings.oauth_enabled:
        return settings.snipeit_token
    try:
        from fastmcp.server.dependencies import get_access_token

        access = get_access_token()
    except (ImportError, LookupError, RuntimeError) as exc:
        raise SnipeITError("authentication_failed", "An authenticated per-user OAuth request is required") from exc
    token = getattr(access, "token", None) if access is not None else None
    if not isinstance(token, str) or not token:
        raise SnipeITError("authentication_failed", "An authenticated per-user OAuth request is required")
    return token


ClientFactory = type[SnipeITClient]
_client_factory: ClientFactory = SnipeITClient


def set_client_factory(factory: ClientFactory) -> None:
    """Test seam for substituting a compatible request-scope client."""
    global _client_factory
    _client_factory = factory


@asynccontextmanager
async def client_for_request() -> AsyncIterator[SnipeITClient]:
    settings = load_settings(require_credentials=True)
    token = resolve_upstream_token(settings)
    async with _client_factory(settings, token) as client:
        yield client

