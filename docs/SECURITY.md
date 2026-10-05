# Security

## Trust boundaries

There are two separate credentials in shared-token HTTP mode:

- `SNIPEIT_MCP_TOKEN` authenticates Copilot to this MCP server.
- `SNIPEIT_TOKEN` authenticates the service account to Snipe-IT.

They must differ. In OAuth mode, FastMCP proxies the Passport authorization flow and each user's Snipe-IT access token remains subject to that user's permissions.

## Controls

- TLS verification is on by default; enterprise CAs use `SNIPEIT_CA_BUNDLE`.
- Disabling TLS requires both `SNIPEIT_VERIFY_TLS=false` and `SNIPEIT_ALLOW_INSECURE_TLS=true`.
- Redirects are refused, preventing same-client origin changes.
- The LLM cannot provide a URL or arbitrary API path.
- Root endpoint families, resource types, actions, and deletion targets are server allowlists.
- Encoded separators, traversal, control characters, unsafe filenames, oversized queries, JSON, uploads, and downloads are rejected.
- Multipart requests omit JSON `Content-Type` and use bounded in-memory bytes.
- Only safe GET requests receive one conservative transient retry. Mutations are never automatically retried.
- Snipe-IT HTTP 200 error envelopes are treated as failures.
- 401, 403, 404, conflict, 422, 429, timeout, TLS, connectivity, malformed JSON, and HTML responses have distinct error codes.
- Logs are JSON and redact configured secrets, bearer values, authorization headers, passwords, OAuth codes, access tokens, and refresh tokens.
- Tool results never contain raw exception text.
- `delete_resource` is the sole code path that sends HTTP `DELETE`.
- Imports upload/configure/process are separate; LDAP test and sync are separate actions.

## Deployment

Run as the non-login `snipeit-copilot-mcp` service user. Keep source, lockfile, and `.venv` root-owned and read-only to the service. Store secrets in `/etc/snipeit-copilot-mcp.env` with mode `0640`. Keep `FASTMCP_HOME` under `/var/lib/snipeit-copilot-mcp` with mode `0700`. Terminate public traffic with HTTPS and a trusted certificate.

For OAuth production, use a long random `SNIPEIT_OAUTH_JWT_SIGNING_KEY`, protect persistent state, explicitly allow Copilot callback URLs, and use shared encrypted storage when horizontally scaling.

## Least privilege

Set `SNIPEIT_ALLOWED_TOOLS` to the minimum required tool set and grant the Snipe-IT service account or users only the corresponding backend permissions. A read-only helpdesk deployment normally needs `assets_search`, `users_search`, `user_inventory`, `inventory_search`, `organization_search`, `catalog_search`, `licenses_search`, `reports`, and `system_read`.

## Incident response

If a credential may have leaked, revoke it in Snipe-IT, rotate the separate MCP bearer and OAuth client/signing keys as applicable, restart the service, invalidate persistent OAuth sessions, and inspect reverse-proxy plus structured application logs. Debug logging is still redacted but should not be left enabled unnecessarily.

