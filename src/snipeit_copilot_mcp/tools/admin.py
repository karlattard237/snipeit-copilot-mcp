"""Read-only system administration and explicit LDAP operations."""

from __future__ import annotations

import base64
from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_file, normalize_generic
from ..schemas import GENERIC_SINGLE_OUTPUT, SYSTEM_OUTPUT
from ..security import path_segment
from .common import action, guarded, result_item, success_item

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
LDAP = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True}


async def system_read(action_name: str = "version", backup_filename: str = "", max_inline_bytes: int = 1048576, limit: int = 50, offset: int = 0) -> dict[str, object]:
    """Read Snipe-IT version/system information, list backups, or download one bounded backup. Version data supports capability diagnosis. Backup content is base64 only when it fits max_inline_bytes. This tool cannot change settings or delete backups."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"version", "backups", "backup_download"}, "system_read")
        async with client_for_request() as client:
            if selected == "version":
                payload = await client.request_json("GET", "version")
                result: dict[str, object] = {"success": True}
                for key in ("version", "build_version", "hash_version", "full_version"):
                    if payload.get(key) is not None:
                        result[key] = str(payload[key])
                return result
            if selected == "backups":
                rows, meta = await client.list_page("settings/backups", limit=limit, offset=offset)
                return {"success": True, "items": [normalize_generic(row, "backup") for row in rows], "count": meta["count"]}
            if not backup_filename:
                raise invalid("backup_filename is required for action=backup_download")
            if not 0 <= max_inline_bytes <= 10 * 1024 * 1024:
                raise invalid("max_inline_bytes must be between 0 and 10485760")
            content, mime, _ = await client.request_bytes("GET", f"settings/backups/download/{path_segment(backup_filename, 'backup_filename')}")
            item = normalize_file({"filename": backup_filename, "size": len(content), "mime_type": mime}, "backup", 0)
            if len(content) <= max_inline_bytes:
                item["content_base64"] = base64.b64encode(content).decode("ascii")
                item["content_truncated"] = False
            else:
                item["content_truncated"] = True
            return {"success": True, "message": "Backup downloaded" if not item["content_truncated"] else "Backup metadata returned; content exceeds max_inline_bytes", "item": item}

    return await guarded(run)


async def ldap_operations(action_name: str) -> dict[str, object]:
    """Test the configured Snipe-IT LDAP connection or explicitly synchronize LDAP users. action_name=test only checks connectivity; action_name=sync can materially change users and must be used only when synchronization was explicitly requested. This tool never infers sync from a test request."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"test", "sync"}, "ldap_operations")
        async with client_for_request() as client:
            payload = await client.request_json("GET" if selected == "test" else "POST", "settings/ldaptest" if selected == "test" else "users/ldapsync", json_body=None if selected == "test" else {}, timeout_kind="long" if selected == "sync" else "default")
            return success_item(normalize_generic(result_item(payload), "ldap"), f"LDAP {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="system_read", description=system_read.__doc__, annotations=READ, output_schema=SYSTEM_OUTPUT)(system_read)
    mcp.tool(name="ldap_operations", description=ldap_operations.__doc__, annotations=LDAP, output_schema=GENERIC_SINGLE_OUTPUT, timeout=900)(ldap_operations)

