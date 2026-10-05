# Architecture

## Design goals

The server is an AI-facing semantic contract, not a generic HTTP relay. Tool boundaries separate read, ordinary write, lifecycle, high-impact, and destructive behavior. The default set is fixed at 29 tools so Copilot Studio receives enough semantic precision without hundreds of endpoint-shaped actions.

## Request path

1. FastMCP accepts Streamable HTTP at `/mcp` and authenticates the caller.
2. A tool validates its action and resource allowlists.
3. Human identifiers are resolved only when an exact, unambiguous result exists.
4. A request-scoped `httpx.AsyncClient` sends a fixed, code-owned `/api/v1` route.
5. HTTP and Snipe-IT JSON status semantics are evaluated independently.
6. A domain normalizer flattens common nested values and preserves bounded unknown data as name/value `extra_fields`.
7. The result is emitted in the tool's explicit, inline output schema.

## Modules

- `config.py`: environment validation and secure defaults.
- `auth.py`: separate inbound shared bearer or per-user Passport OAuth proxy.
- `client.py`: async HTTP, headers, TLS, bounds, timeouts, safe read retry, pagination, and errors.
- `normalizers.py`: rich, reusable asset/user/licence/inventory/file/activity serializers.
- `schemas.py`: inline, reference-free public JSON Schemas.
- `tools/`: domain modules; only `deletion.py` calls HTTP `DELETE`.
- `server.py`: server description, tool registration, allowlist, health, and readiness.

## Authentication isolation

API-token mode creates request-scoped clients using the configured service-account token. OAuth mode retrieves the upstream token from the current FastMCP authentication context. Clients and normalized data are not cached globally, preventing one user's authorization-sensitive data from leaking to another.

FastMCP manages OAuth refresh serialization and proxy token lifecycle. Token validation has a small, bounded positive cache and an async lock; it contains only opaque tokens and minimal user identity and is never logged.

## Compatibility

The version endpoint is exposed through `system_read`. Optional endpoints remain in a stable tool list; older installations return a structured backend/not-found result instead of causing tool-list churn. Normalizers tolerate missing nested objects and ignore unknown types. Pagination accepts both limit/offset and page/per-page and reports whether more data remains.

## Output size

Lists are paginated, normal JSON responses are bounded, uploads/downloads have separate limits, and base64 file content is returned only when it fits the caller's explicit `max_inline_bytes`. Large content is reported through metadata with `content_truncated=true`.

