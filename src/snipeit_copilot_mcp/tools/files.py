"""Unified non-destructive attachment reading and upload tools."""

from __future__ import annotations

import base64
from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_file
from ..schemas import FILE_LIST_OUTPUT, FILE_SINGLE_OUTPUT
from ..security import decode_base64, safe_filename
from .common import action, guarded, result_item, success_item, success_list

FILE_TYPES = {
    "accessories", "audits", "assets", "components", "consumables", "hardware",
    "licenses", "locations", "maintenances", "models", "suppliers", "users",
    "companies", "departments",
}
READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}


def _parent(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in FILE_TYPES:
        raise invalid("parent_type is not supported by Snipe-IT attachment routes")
    return normalized


async def files_read(action_name: str, parent_type: str, parent_id: int, file_id: int = 0, max_inline_bytes: int = 1048576, limit: int = 50, offset: int = 0) -> dict[str, object]:
    """List attachment metadata or download one bounded attachment for a supported Snipe-IT parent. Download returns base64 only when the file fits max_inline_bytes; otherwise it reports metadata and content_truncated=true. This tool cannot upload or delete files."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "download"}, "files_read")
        parent = _parent(parent_type)
        if parent_id <= 0:
            raise invalid("parent_id must be positive")
        async with client_for_request() as client:
            if selected == "list":
                rows, meta = await client.list_page(f"{parent}/{parent_id}/files", limit=limit, offset=offset)
                return success_list([normalize_file(row, parent, parent_id) for row in rows], meta)
            if file_id <= 0:
                raise invalid("file_id is required for action=download")
            if not 0 <= max_inline_bytes <= 10 * 1024 * 1024:
                raise invalid("max_inline_bytes must be between 0 and 10485760")
            content, mime, disposition = await client.request_bytes("GET", f"{parent}/{parent_id}/files/{file_id}")
            filename = f"file-{file_id}"
            marker = "filename="
            if marker in disposition.lower():
                candidate = disposition[disposition.lower().find(marker) + len(marker):].strip().strip('"')
                try:
                    filename = safe_filename(candidate)
                except Exception:
                    pass
            item = normalize_file({"id": file_id, "filename": filename, "size": len(content), "mime_type": mime}, parent, parent_id)
            if len(content) <= max_inline_bytes:
                item["content_base64"] = base64.b64encode(content).decode("ascii")
                item["content_truncated"] = False
            else:
                item["content_truncated"] = True
            return success_list([item], {"count": 1, "total": 1, "has_more": False}, "Attachment downloaded" if not item["content_truncated"] else "Attachment metadata returned; content exceeds max_inline_bytes")

    return await guarded(run)


async def files_upload(parent_type: str, parent_id: int, filename: str, content_base64: str, mime_type: str = "application/octet-stream", notes: str = "") -> dict[str, object]:
    """Upload one explicitly supplied base64 attachment to a supported Snipe-IT parent. The filename is sanitized, upload size is bounded, and multipart encoding is used. This tool cannot read or delete attachments."""

    async def run() -> dict[str, object]:
        parent = _parent(parent_type)
        if parent_id <= 0:
            raise invalid("parent_id must be positive")
        name = safe_filename(filename)
        async with client_for_request() as client:
            content = decode_base64(content_base64, client.settings.max_upload_bytes)
            payload = await client.request_json(
                "POST", f"{parent}/{parent_id}/files",
                files={"file": (name, content, mime_type or "application/octet-stream")},
                form={"notes": notes} if notes else None,
                timeout_kind="upload",
            )
            item = normalize_file(result_item(payload), parent, parent_id)
            item.setdefault("filename", name)
            item.setdefault("size", len(content))
            item.setdefault("mime_type", mime_type or "application/octet-stream")
            return success_item(item, "Attachment upload succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="files_read", description=files_read.__doc__, annotations=READ, output_schema=FILE_LIST_OUTPUT)(files_read)
    mcp.tool(name="files_upload", description=files_upload.__doc__, annotations=WRITE, output_schema=FILE_SINGLE_OUTPUT)(files_upload)

