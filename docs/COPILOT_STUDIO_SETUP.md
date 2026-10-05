# Microsoft Copilot Studio setup

This guide reflects the current Streamable MCP onboarding experience audited on 2026-08-07. SSE is deprecated and is not used.

## Prerequisites

- Public HTTPS URL with a trusted certificate and no interactive reverse-proxy authentication in front of the MCP protocol.
- Reachable `https://mcp.example.com/mcp` endpoint.
- `/health` returns 200 and `/ready` returns 200.
- One configured authentication mode.
- Generative orchestration enabled for the agent.

## Add the server

1. Open the agent in Copilot Studio.
2. Open **Tools**.
3. Select **Add a tool** > **New tool** > **Model Context Protocol**.
4. Enter:
   - Server name: `Snipe-IT Inventory`
   - Server description: `Snipe-IT inventory and IT asset management. Use whenever current assets, tags, serials, models, users, assignments, accessories, components, consumables, licences, locations, audits, reports, imports, or administration data is required.`
   - Server URL: `https://mcp.example.com/mcp`
5. Select the Streamable transport when shown. Do not configure an SSE URL.
6. Configure authentication as below, create/sign in to the connection, and finish the wizard.
7. Confirm all expected tools appear. The default is 29; an allowlist intentionally lowers that count.

## API key / shared service account

Use this for controlled internal agents, autonomous/background scenarios, and maker-provided credential deployments where all callers are intentionally authorized as the same Snipe-IT service account.

1. Select API key/bearer authentication in the MCP wizard.
2. Enter `SNIPEIT_MCP_TOKEN`, not `SNIPEIT_TOKEN`.
3. Select maker-provided credentials only when organisation policy and the service-account permission model permit it.
4. Restrict tools with `SNIPEIT_ALLOWED_TOOLS` and keep the Snipe-IT service account least-privileged.

## Per-user OAuth

Use this when Snipe-IT permissions must follow each employee.

1. Configure all OAuth environment settings and start the MCP server.
2. In Snipe-IT **Admin > OAuth clients**, register the MCP proxy callback: `https://mcp.example.com/auth/callback`.
3. Begin OAuth configuration in the Copilot MCP wizard. Copilot supplies its callback URL.
4. Add the exact supplied callback to `SNIPEIT_OAUTH_ALLOWED_REDIRECT_URIS`, restart the service, and continue.
5. Use end-user credentials so each person signs in to Snipe-IT. Their Snipe-IT roles/permissions remain authoritative.

FastMCP publishes OAuth discovery and a DCR-compatible proxy. If tenant policy requires manual OAuth fields, use:

- Authorization URL: `https://mcp.example.com/authorize`
- Token URL: `https://mcp.example.com/token`
- Refresh URL: `https://mcp.example.com/token`
- Client details: those issued/accepted by the MCP OAuth onboarding flow

Exact Copilot callback hostnames can vary by environment/region; copy the value the wizard displays and allowlist it rather than using a broad wildcard.

## Maker-provided versus end-user credentials

- Maker-provided: one shared connection; appropriate for a deliberately scoped service account and background/autonomous use.
- End-user: each user authenticates; preferred for enterprise least privilege and user-level Snipe-IT authorization.

Power Platform administrators can restrict maker-provided credentials for the environment. If end-user credentials are enforced, autonomous/background invocations that cannot display sign-in may fail by design.

## Confirmation settings

Copilot Studio's **Ask the end user before running** setting is independent of MCP annotations. Recommended configuration:

- Read-only tools: No.
- Ordinary create/update/checkout/checkin/audit/request tools: No when the prompt explicitly requests the operation and organisational policy permits it.
- `imports`, `ldap_operations`, and `users_write`: use agent instructions to require explicit intent for process/sync/reset actions; platform confirmation can be enabled if policy requires it.
- `delete_resource`: keep platform confirmation enabled when available and always enforce the conversational exact-target confirmation in the agent instructions.

MCP annotations are advisory descriptions; they do not guarantee a Microsoft confirmation dialog.

## Verify discovery

1. Confirm generative orchestration is enabled.
2. Refresh the MCP connection/tool list.
3. Expect 29 tools with the full set.
4. Test prompts:
   - `Find asset LAP-104 and show tag, serial, model name, and model number.`
   - `What equipment does user@example.com have?`
   - `List accessories with low remaining quantity.`
5. Confirm `user_inventory` exposes rich asset identity in both the declared output schema and results.

## Selectively disable tools

Set an exact allowlist and restart:

```env
SNIPEIT_ALLOWED_TOOLS=assets_search,users_search,user_inventory,inventory_search,catalog_search,reports,system_read
```

Invalid names fail closed at startup. Refresh the Copilot connection after changing the list.

## MCP Inspector

```bash
npx @modelcontextprotocol/inspector https://mcp.example.com/mcp
```

Supply the inbound bearer/OAuth connection, run `tools/list`, inspect all schemas/annotations, then invoke representative read calls and safe mocked/test writes.

## Troubleshooting

- Tool missing: run `uv run python scripts/validate_copilot_schemas.py`; fix any `$ref`, multi-type, or missing output report; check the allowlist; refresh the connection.
- Schema truncated: every `type` must be a single JSON type. Do not add `Optional`/nullable public signatures without rerunning the linter.
- 401 at `/mcp`: the MCP API key/OAuth connection is wrong or absent.
- `authentication_failed` result: upstream Snipe-IT token/session is wrong or expired.
- 403/`permission_denied`: grant the Snipe-IT user the needed permission or choose a less privileged action; the MCP will not bypass it.
- TLS error: use a publicly trusted certificate; for private Snipe-IT CAs configure `SNIPEIT_CA_BUNDLE` on the MCP host.
- HTML response: verify `SNIPEIT_URL`, proxy routing, and Snipe-IT API availability.
- Only some tools visible: inspect `SNIPEIT_ALLOWED_TOOLS` and Power Platform data policies.
- OAuth loop: verify the public base URL, both callback allowlists, proxy forwarded headers, persistent `FASTMCP_HOME`, and stable signing key.

Sources: [Microsoft MCP onboarding](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent), [MCP troubleshooting](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-troubleshooting), and [maker credential governance](https://learn.microsoft.com/en-us/microsoft-copilot-studio/configure-no-maker-authentication).

