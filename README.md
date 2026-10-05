# Snipe-IT Copilot MCP

A production-oriented Model Context Protocol server for Snipe-IT, designed specifically for Microsoft Copilot Studio generative orchestration.

This is a greenfield implementation. It talks directly to Snipe-IT with asynchronous `httpx`, exposes exactly 29 semantic tools, uses Streamable HTTP at `/mcp`, and declares inline Copilot-safe input/output schemas. It does not depend on a third-party Snipe-IT Python wrapper.

## Why this server exists

Generic CRUD tools and loosely typed `dict` outputs make it difficult for an orchestrator to know which fields actually exist. This server makes important inventory data visible in the MCP contract itself. In particular, asset responses explicitly advertise `asset_tag`, `serial`, `model_name`, `model_number`, manufacturer, status, assignment, and location. `user_inventory` reuses the same asset normalizer and schema.

The public contract avoids `$ref`, `$defs`, `definitions`, multi-type `type` arrays, and ambiguous schema unions that Copilot Studio currently does not support reliably.

## Highlights

- 29 tools, grouped by domain and safety class.
- Only `delete_resource` can issue HTTP `DELETE`.
- Direct asynchronous Snipe-IT REST calls with bounded requests/responses.
- Shared service-account token and per-user Snipe-IT Passport OAuth modes.
- HTTP 200 plus Snipe-IT application-error detection.
- Exact tag, serial, email, username, and employee-number resolution.
- Global search, per-field filters, advanced filter JSON, and custom-field name resolution.
- Rich, defensive normalizers that preserve unknown values as `extra_fields` name/value arrays.
- Limit/offset and page/per-page pagination normalized into predictable envelopes.
- Structured JSON logs with credential redaction.
- Health (`/health`) and readiness (`/ready`) endpoints.
- Docker, systemd, nginx, idempotent setup/update scripts, schema linting, and tests.

## Architecture

```text
Copilot Studio -- Streamable HTTP /mcp --> FastMCP 3
                                             |
                 explicit schemas + 29 semantic tools
                                             |
                 resolvers -> normalizers -> async httpx client
                                             |
                                  Snipe-IT /api/v1
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/SECURITY.md](docs/SECURITY.md), [docs/FEATURE_PARITY.md](docs/FEATURE_PARITY.md), and [docs/SNIPEIT_API_COVERAGE.md](docs/SNIPEIT_API_COVERAGE.md).

## Requirements

- Python 3.11 or newer
- `uv`
- A reasonably current Snipe-IT release with API access
- HTTPS with a publicly trusted or explicitly configured enterprise CA for production

The API audit was refreshed against Snipe-IT v8.6.2/current source on 2026-08-07. Optional endpoints remain registered and fail cleanly when an older connected server does not support them.

## Quick start

For a complete installation walkthrough covering credentials, local development, Docker, Linux/systemd, HTTPS, and the Copilot Studio connection, see [docs/INSTALLATION.md](docs/INSTALLATION.md).

```bash
cp .env.example .env
# Edit .env first; do not commit it.
uv sync --frozen
set -a; . ./.env; set +a
mkdir -p .tmp/fastmcp
FASTMCP_HOME="$PWD/.tmp/fastmcp" uv run --frozen python -m snipeit_copilot_mcp
```

The production MCP URL is:

```text
https://your-mcp-host.example/mcp
```

For local stdio development only:

```bash
MCP_TRANSPORT=stdio uv run python -m snipeit_copilot_mcp
```

## Authentication

### Shared API-token mode

Configure `SNIPEIT_URL`, `SNIPEIT_TOKEN`, and—in HTTP mode—a separate `SNIPEIT_MCP_TOKEN` of at least 32 characters. Copilot sends the latter as the MCP server bearer/API key. Snipe-IT sees only the service account represented by `SNIPEIT_TOKEN`; its permissions remain authoritative.

Never reuse the privileged upstream token as the inbound MCP credential.

### Per-user OAuth mode

Create a Laravel Passport OAuth client in Snipe-IT with redirect URI:

```text
https://your-mcp-host.example/auth/callback
```

Configure all `SNIPEIT_OAUTH_*` values, the public `SNIPEIT_MCP_BASE_URL`, an explicit Copilot callback allowlist, and a durable `SNIPEIT_OAUTH_JWT_SIGNING_KEY`. FastMCP exposes OAuth discovery/DCR-compatible proxy endpoints and forwards interactive login to Snipe-IT. Each tool call uses the authenticated user's upstream token, so their Snipe-IT permissions are preserved.

Keep `FASTMCP_HOME` on persistent, mode-restricted storage. For a horizontally scaled deployment, use a supported shared encrypted storage backend instead of local state.

Detailed configuration is in [docs/COPILOT_STUDIO_SETUP.md](docs/COPILOT_STUDIO_SETUP.md).

## Tool overview

| Tool | Purpose | Safety |
|---|---|---|
| `assets_search` | Asset list/get/search/exact tag/exact serial/requestable catalog | Read-only |
| `assets_write` | Asset create/update | Write, non-delete |
| `asset_lifecycle` | Checkout/checkin/audit/restore | Write, non-delete |
| `files_read` | Attachment list/bounded download | Read-only |
| `files_upload` | Bounded multipart upload | Write, non-delete |
| `asset_labels` | Generate label PDF | Read/generate |
| `asset_maintenance` | Maintenance records, notes, types, completion | Mixed, non-delete |
| `asset_licenses` | Licences associated with an asset | Read-only |
| `asset_requests` | Request/cancel requestable asset | Write, non-delete |
| `inventory_search` | Accessories/components/consumables | Read-only |
| `inventory_write` | Inventory create/update | Write, non-delete |
| `inventory_lifecycle` | Inventory assignment/checkin | Write, non-delete |
| `users_search` | User lookup/current user | Read-only |
| `users_write` | Create/update/restore/explicit 2FA reset | High-impact write |
| `user_inventory` | All inventory assigned to one user | Read-only |
| `organization_search` | Companies/departments/groups | Read-only |
| `organization_write` | Organisation create/update | Write, non-delete |
| `catalog_search` | Reference/configuration and relationships | Read-only |
| `catalog_write` | Reference/configuration create/update | Write, non-delete |
| `custom_fields_search` | Fields/fieldsets/membership | Read-only |
| `custom_fields_write` | Field/fieldset writes and ordering | Write, non-delete |
| `licenses_search` | Licence search/get | Read-only |
| `licenses_write` | Licence create/update | Write, non-delete |
| `license_seats` | Seat list/checkout/checkin/update | Mixed, non-delete |
| `reports` | Activity/status/audit/depreciation reports | Read-only |
| `imports` | Explicit staged CSV workflow | High-impact write |
| `system_read` | Version/backups | Read-only |
| `ldap_operations` | Connection test or explicit sync | High-impact write |
| `delete_resource` | Confirmed deletion only | Destructive |

## Tool filtering

Unset `SNIPEIT_ALLOWED_TOOLS` to expose all tools. Set an exact comma-separated allowlist to expose a least-privilege subset:

```env
SNIPEIT_ALLOWED_TOOLS=assets_search,users_search,user_inventory,inventory_search,catalog_search
```

Unknown, blank, or incorrectly cased names fail startup.

## Testing and validation

```bash
uv sync --extra test
uv run pytest --cov=snipeit_copilot_mcp --cov-report=term-missing
uv run python scripts/validate_copilot_schemas.py
```

Integration tests require `SNIPEIT_INTEGRATION_TESTS=true` and separate test-instance credentials. Destructive integration tests additionally require `SNIPEIT_INTEGRATION_ALLOW_DESTRUCTIVE=true`; they never run by default.

Use MCP Inspector against the production transport:

```bash
npx @modelcontextprotocol/inspector http://127.0.0.1:8000/mcp
```

## Docker

```bash
docker build -t snipeit-copilot-mcp:1.0.0 .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 \
  -e MCP_HOST=0.0.0.0 \
  -v snipeit-mcp-state:/var/lib/snipeit-copilot-mcp \
  snipeit-copilot-mcp:1.0.0
```

Terminate TLS at a trusted reverse proxy. Do not publish plaintext port 8000 directly to the internet.

## systemd deployment

```bash
sudo git clone YOUR_REPOSITORY_URL /opt/snipeit-copilot-mcp
cd /opt/snipeit-copilot-mcp
sudo ./scripts/setup.sh
sudoedit /etc/snipeit-copilot-mcp.env
sudo systemctl enable --now snipeit-copilot-mcp.service
curl http://127.0.0.1:8000/health
```

Update:

```bash
sudo /opt/snipeit-copilot-mcp/scripts/update.sh
```

The installer creates a non-login, non-root service user; root-owned source and virtual environment; a persistent state directory; a mode-0640 environment file; a hardened unit; and automatic boot startup. TLS guidance and the nginx example are in `deploy/`.

## Snipe-IT permissions

Tokens inherit the Snipe-IT user's permissions. Grant only the domains and actions the deployed allowlist needs. The MCP never retries alternative endpoints to bypass a 403 and returns `permission_denied` clearly.

## Troubleshooting

- `401` from the MCP boundary: verify Copilot's MCP API key/OAuth connection, not the upstream token.
- `authentication_failed`: verify `SNIPEIT_TOKEN` or complete the per-user Passport login.
- `permission_denied`: adjust the Snipe-IT user's permissions; the MCP will not bypass them.
- HTML instead of JSON: verify the Snipe-IT URL and reverse proxy and ensure API requests retain `Accept: application/json`.
- Missing tools: check the exact `SNIPEIT_ALLOWED_TOOLS` allowlist and run the schema linter.
- TLS failure: install the correct CA and set `SNIPEIT_CA_BUNDLE`; do not disable verification in production.
- Optional endpoint unavailable: inspect `system_read(action_name="version")` and the API coverage matrix.

## Upgrade strategy

The client ignores unknown response fields, normalizers tolerate missing nested objects, and useful unknown values are retained as bounded `extra_fields`. Public schemas remain stable. Before upgrading FastMCP or Snipe-IT, run the full suite, schema linter, MCP Inspector `tools/list`, and representative mocked/safe integration calls.

## Acknowledgements

This project was inspired by [jameshgordy/snipeit-mcp](https://github.com/jameshgordy/snipeit-mcp). The [feature parity guide](docs/FEATURE_PARITY.md) maps its capabilities to this Copilot Studio implementation.

OpenAI Codex assisted with the design, implementation, security review, testing, and documentation of this project.

## License

MIT. See [LICENSE](LICENSE).
