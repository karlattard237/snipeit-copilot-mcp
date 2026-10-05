"""FastMCP construction, 29-tool registration, filtering, and health routes."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .auth import build_auth
from .config import ConfigError, Settings, load_settings
from .tools import admin, assets, catalog, custom_fields, deletion, files, imports, inventory, licenses, organization, reports, users

SERVER_DESCRIPTION = (
    "Snipe-IT inventory and IT asset management server. Provides structured access to assets, "
    "asset tags, serial numbers, models, users, assignments, accessories, components, consumables, "
    "software licences, locations, departments, companies, custom fields, audits, reports, imports "
    "and administration. Supports searching, creating, updating, checking items in/out and controlled "
    "deletion. Use this server whenever current Snipe-IT inventory or asset-management data is required."
)

TOOL_NAMES = frozenset(
    {
        "assets_search", "assets_write", "asset_lifecycle", "files_read", "files_upload",
        "asset_labels", "asset_maintenance", "asset_licenses", "asset_requests",
        "inventory_search", "inventory_write", "inventory_lifecycle", "users_search",
        "users_write", "user_inventory", "organization_search", "organization_write",
        "catalog_search", "catalog_write", "custom_fields_search", "custom_fields_write",
        "licenses_search", "licenses_write", "license_seats", "reports", "imports",
        "system_read", "ldap_operations", "delete_resource",
    }
)


def apply_allowlist(mcp: FastMCP, configured: tuple[str, ...]) -> None:
    if not configured:
        return
    allowed = set(configured)
    unknown = allowed - TOOL_NAMES
    if unknown:
        raise ConfigError("SNIPEIT_ALLOWED_TOOLS contains unknown names: " + ", ".join(sorted(unknown)))
    mcp.enable(names=allowed, components={"tool"}, only=True)


def build_server(settings: Settings | None = None) -> FastMCP:
    selected = settings or load_settings(require_credentials=False)
    auth = build_auth(selected) if selected.snipeit_url else None
    mcp = FastMCP(
        name="Snipe-IT Copilot MCP",
        instructions=SERVER_DESCRIPTION,
        auth=auth,
        dereference_schemas=True,
    )
    for module in (assets, files, inventory, users, organization, catalog, custom_fields, licenses, reports, imports, admin, deletion):
        module.register(mcp)
    apply_allowlist(mcp, selected.allowed_tools)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "snipeit-copilot-mcp"})

    @mcp.custom_route("/ready", methods=["GET"])
    async def ready(_: Request) -> JSONResponse:
        try:
            selected.validate(require_credentials=True)
        except ConfigError:
            return JSONResponse({"status": "not_ready", "reason": "configuration"}, status_code=503)
        return JSONResponse({"status": "ready", "authentication_mode": "oauth" if selected.oauth_enabled else "api_token"})

    return mcp


mcp = build_server()

