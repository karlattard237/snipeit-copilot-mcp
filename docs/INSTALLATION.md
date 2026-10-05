# Installation guide

This guide takes a new checkout through a working Snipe-IT connection and a Microsoft Copilot Studio MCP connection. Run commands from the project directory containing `pyproject.toml`.

## 1. Prerequisites

- A reachable Snipe-IT instance with its API enabled and a user or service account granted only the permissions the agent needs.
- Python 3.11 or newer and [uv](https://docs.astral.sh/uv/getting-started/installation/) for a source installation, or Docker for a container installation.
- A public HTTPS hostname with a trusted certificate for Copilot Studio. The MCP process can listen on `127.0.0.1:8000` behind a reverse proxy.
- For the Linux service path: a systemd host, Git, root access, and a trusted `uv` executable at `/usr/local/bin/uv` (or a custom `UV_BIN` path).

Decide which authentication mode to use before editing configuration:

| Mode | Snipe-IT identity | Configure in Copilot Studio |
|---|---|---|
| Shared API token | Every caller uses one deliberately scoped Snipe-IT account | The separate `SNIPEIT_MCP_TOKEN` as the MCP bearer/API key |
| Per-user OAuth | Each caller signs in to Snipe-IT and uses their own permissions | OAuth 2.0 connection to the MCP server |

The upstream Snipe-IT token and the inbound MCP token are different credentials. Never enter `SNIPEIT_TOKEN` into Copilot Studio.

## 2. Get the project and configure credentials

Clone your published repository, then enter the project directory:

```bash
git clone YOUR_REPOSITORY_URL
cd snipeit-copilot-mcp
cp .env.example .env
```

If you are using a local copy before publishing, enter its `snipeit-copilot-mcp` directory and start with `cp .env.example .env`. The `.env` file is ignored by Git; keep it private.

### Shared API-token mode

Create a Snipe-IT personal access token for a dedicated account with the required permissions. In `.env`, set:

```env
SNIPEIT_URL=https://snipeit.example.com
SNIPEIT_TOKEN=your-real-snipeit-personal-access-token
SNIPEIT_MCP_TOKEN=your-separate-random-secret-of-at-least-32-characters
MCP_TRANSPORT=streamable-http
MCP_HOST=127.0.0.1
MCP_PORT=8000
```

Replace every example value with your own. `SNIPEIT_URL` is the origin of the Snipe-IT site, without `/api/v1` or a trailing path. Generate an independent MCP secret, for example with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`, and store it only in the private environment file and the Copilot connection. The application rejects an MCP secret shorter than 32 characters or identical to the upstream token.

### Per-user OAuth mode

In Snipe-IT, create a Laravel Passport OAuth client. Set its redirect URI to `https://YOUR_MCP_HOST/auth/callback`. In `.env`, comment out or remove the active `SNIPEIT_TOKEN` and `SNIPEIT_MCP_TOKEN` lines, then configure:

```env
SNIPEIT_URL=https://snipeit.example.com
SNIPEIT_OAUTH_CLIENT_ID=your-passport-client-id
SNIPEIT_OAUTH_CLIENT_SECRET=your-passport-client-secret
SNIPEIT_MCP_BASE_URL=https://YOUR_MCP_HOST
SNIPEIT_OAUTH_ALLOWED_REDIRECT_URIS=https://YOUR_COPILOT_CALLBACK
SNIPEIT_OAUTH_JWT_SIGNING_KEY=your-long-random-signing-key
MCP_TRANSPORT=streamable-http
```

The signing key must be at least 32 characters. Use the exact callback URL supplied during Copilot Studio onboarding in `SNIPEIT_OAUTH_ALLOWED_REDIRECT_URIS`; update it and restart the MCP service if the wizard shows a different callback. Preserve `FASTMCP_HOME` on restricted persistent storage so OAuth state survives restarts. See [Copilot Studio setup](COPILOT_STUDIO_SETUP.md) for the full OAuth flow.

### Optional settings

- Set `SNIPEIT_ALLOWED_TOOLS` to a comma-separated list of exact tool names when an agent should see fewer than the default 29 tools. An unknown name stops startup.
- Set `SNIPEIT_CA_BUNDLE` to a readable CA bundle when Snipe-IT uses a private certificate authority. TLS verification is enabled by default.
- Leave the upload, download, response, and timeout limits from `.env.example` in place until a real workload requires different values.

## 3. Run locally with Python and uv

From the project directory on macOS or Linux:

```bash
uv sync --frozen
set -a
. ./.env
set +a
mkdir -p .tmp/fastmcp
FASTMCP_HOME="$PWD/.tmp/fastmcp" uv run --frozen python -m snipeit_copilot_mcp
```

The server stays in the foreground. In another terminal, check its local routes:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

`/health` shows that the process is responding. `/ready` checks that its required configuration is present; it does not prove that Snipe-IT is reachable or that the token has every permission. To test tool discovery in shared-token mode with the full tool set, run `SNIPEIT_SMOKE_MCP_URL=http://127.0.0.1:8000/mcp uv run --frozen python scripts/smoke_http.py` from a terminal where `SNIPEIT_MCP_TOKEN` is loaded. This smoke script expects all 29 tools, so it is not suitable when you have set a smaller allowlist.

For local stdio development, set `MCP_TRANSPORT=stdio` before starting the module. Copilot Studio requires the hosted Streamable HTTP endpoint.

## 4. Run with Docker

After creating `.env` as above, build and start the container:

```bash
docker build -t snipeit-copilot-mcp:1.0.0 .
docker run --rm --name snipeit-copilot-mcp \
  --env-file .env \
  -p 127.0.0.1:8000:8000 \
  -v snipeit-mcp-state:/var/lib/snipeit-copilot-mcp \
  snipeit-copilot-mcp:1.0.0
```

The container already binds its internal listener to `0.0.0.0`; the `-p 127.0.0.1:8000:8000` option keeps the published host port on loopback. The named volume persists FastMCP state, which is especially important for OAuth. In another terminal, run the two `curl` checks above. Put an HTTPS reverse proxy in front before connecting Copilot Studio.

## 5. Install as a Linux systemd service

The included installer uses fixed production paths. Install a trusted `uv` executable at `/usr/local/bin/uv`, or pass its absolute path with `UV_BIN`. Then:

```bash
sudo git clone YOUR_REPOSITORY_URL /opt/snipeit-copilot-mcp
cd /opt/snipeit-copilot-mcp
sudo bash scripts/setup.sh
```

The installer creates the `snipeit-copilot-mcp` service user, a restricted state directory, a locked Python environment, and `/etc/snipeit-copilot-mcp.env`. On the first run, it enables the service but leaves it stopped while active example values remain. Edit the private environment file:

```bash
sudoedit /etc/snipeit-copilot-mcp.env
sudo systemctl start snipeit-copilot-mcp.service
sudo systemctl status snipeit-copilot-mcp.service
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

Apply the shared-token or OAuth settings from step 2. Remove active `replace-with-...` values, while leaving unrelated commented examples alone. The unit runs as a non-login account, binds to loopback, and reads credentials from the mode-0640 environment file. To inspect startup errors, use `sudo journalctl -u snipeit-copilot-mcp.service -n 100 --no-pager`.

If `uv` is in a different location, run the installer as `sudo env UV_BIN=/absolute/path/to/uv bash scripts/setup.sh`. To update a Git checkout later, use `sudo bash /opt/snipeit-copilot-mcp/scripts/update.sh` with the same `UV_BIN` setting if needed.

## 6. Add HTTPS and connect Copilot Studio

Use [deploy/nginx.conf](../deploy/nginx.conf) as a reverse-proxy starting point. Replace `mcp.example.com` and the certificate paths with your real public hostname and trusted certificate, then test and reload nginx. Route HTTPS traffic to the local `127.0.0.1:8000` listener and preserve the forwarded host and scheme headers. Confirm `https://YOUR_MCP_HOST/health` and `https://YOUR_MCP_HOST/ready` respond before configuring Copilot Studio.

In Copilot Studio, open the agent's **Tools** page and add a **Model Context Protocol** tool. Set the server URL to `https://YOUR_MCP_HOST/mcp` and choose the Streamable transport. For shared-token mode, configure the connection to send `SNIPEIT_MCP_TOKEN` as the MCP bearer credential. For OAuth mode, use the OAuth connection and register the callback shown by the wizard. Enable generative orchestration and refresh the tool list; the default installation exposes 29 tools, while an allowlist exposes fewer. The detailed wizard steps and example agent prompts are in [Copilot Studio setup](COPILOT_STUDIO_SETUP.md).

## 7. Validate the installation

Run the local contract checks from a development checkout:

```bash
uv sync --frozen --extra test
uv run --frozen python -m pytest -q
uv run --frozen python scripts/validate_copilot_schemas.py
```

Then perform a read-only request through the Copilot connection, such as searching for a known asset tag. If tool discovery works but a request returns `permission_denied`, adjust the Snipe-IT account's permissions for that operation. If Copilot cannot reach the server, verify the public HTTPS URL, reverse-proxy routing, and authentication mode before changing application settings.
