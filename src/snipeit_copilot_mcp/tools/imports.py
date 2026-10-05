"""Explicit multi-stage CSV import workflow."""

from __future__ import annotations

from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_generic
from ..schemas import GENERIC_LIST_OUTPUT
from ..security import decode_base64, safe_filename
from .common import action, guarded, payload_json, result_item, success_list

HIGH_IMPACT = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True}
_IMPORT_TYPES = {"asset", "accessory", "consumable", "component", "license", "user", "location"}


async def imports(
    action_name: str,
    import_id: int = 0,
    filename: str = "",
    content_base64: str = "",
    import_type: str = "",
    field_map_json: str = "",
    run_backup: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    """Run the Snipe-IT CSV import workflow in explicit stages: list, get, upload, configure, validate, or process. Upload never processes a file; process runs only when action_name=process is explicitly requested. This tool cannot delete import files; use delete_resource after separate confirmation."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "get", "upload", "configure", "validate", "process"}, "imports")
        async with client_for_request() as client:
            if selected == "list":
                rows, meta = await client.list_page("imports", limit=limit, offset=offset)
                return success_list([normalize_generic(row, "import") for row in rows], meta)
            if selected == "upload":
                name = safe_filename(filename)
                if not name.lower().endswith(".csv"):
                    raise invalid("Import uploads must use a .csv filename")
                content = decode_base64(content_base64, client.settings.max_upload_bytes)
                payload = await client.request_json("POST", "imports", files={"file": (name, content, "text/csv")}, timeout_kind="upload")
                item = normalize_generic(result_item(payload), "import")
                item.setdefault("name", name)
                return success_list([item], {"count": 1, "total": 1, "has_more": False}, "CSV uploaded but not processed")
            if import_id <= 0:
                raise invalid("import_id is required for this action")
            if selected == "get":
                payload = await client.request_json("GET", f"imports/{import_id}")
            elif selected in {"configure", "validate"}:
                kind = import_type.strip().lower()
                if kind not in _IMPORT_TYPES:
                    raise invalid("import_type is not supported")
                mapping = payload_json(field_map_json, "field_map_json")
                if selected == "validate" and not mapping:
                    raise invalid("field_map_json must not be empty for validation")
                data = {"import_type": kind, "field_map": mapping, "run_backup": run_backup}
                if selected == "validate":
                    item = normalize_generic({"id": import_id, "name": "mapping valid", **data}, "import")
                    return success_list([item], {"count": 1, "total": 1, "has_more": False}, "Mapping passed MCP-side validation; configure it before processing")
                payload = await client.request_json("PATCH", f"imports/{import_id}", json_body=data)
            else:
                payload = await client.request_json("POST", f"imports/process/{import_id}", json_body={}, timeout_kind="long")
            item = normalize_generic(result_item(payload), "import")
            item.setdefault("id", import_id)
            return success_list([item], {"count": 1, "total": 1, "has_more": False}, f"Import {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="imports", description=imports.__doc__, annotations=HIGH_IMPACT, output_schema=GENERIC_LIST_OUTPUT, timeout=900)(imports)

