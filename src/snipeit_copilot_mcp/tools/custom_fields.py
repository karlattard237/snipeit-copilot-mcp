"""Custom fields and fieldsets with stable Copilot representations."""

from __future__ import annotations

import json
from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_custom_field
from ..schemas import CUSTOM_FIELD_LIST_OUTPUT, CUSTOM_FIELD_SINGLE_OUTPUT
from .common import action, compact, guarded, result_item, success_item, success_list

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}


async def custom_fields_search(resource_type: str = "field", action_name: str = "list", item_id: int = 0, fieldset_id: int = 0, query: str = "", limit: int = 50, offset: int = 0) -> dict[str, object]:
    """Read/search custom fields, fieldsets, db_column identifiers, validation metadata, and fieldset membership. Use resource_type=field or fieldset. Dynamic values are represented through stable named properties and extra_fields arrays. This tool is read-only."""

    async def run() -> dict[str, object]:
        kind = resource_type.strip().lower().rstrip("s")
        if kind not in {"field", "fieldset"}:
            raise invalid("resource_type must be field or fieldset")
        selected = action(action_name, {"list", "search", "get", "membership"}, "custom_fields_search")
        endpoint = "fields" if kind == "field" else "fieldsets"
        async with client_for_request() as client:
            if selected == "get":
                if item_id <= 0:
                    raise invalid("item_id is required for action=get")
                payload = await client.request_json("GET", f"{endpoint}/{item_id}")
                return success_list([normalize_custom_field(result_item(payload), kind)], {"count": 1, "total": 1, "has_more": False})
            if selected == "membership":
                target = fieldset_id or item_id
                if target <= 0:
                    raise invalid("fieldset_id is required for action=membership")
                payload = await client.request_json("POST", f"fieldsets/{target}/fields", json_body={})
                rows = payload.get("rows", payload.get("fields", []))
                if isinstance(rows, dict):
                    rows = list(rows.values())
                items = [normalize_custom_field(row, "field") for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
                return success_list(items, {"count": len(items), "total": len(items), "has_more": False})
            rows, meta = await client.list_page(endpoint, limit=limit, offset=offset, search=query if selected == "search" or query else "")
            return success_list([normalize_custom_field(row, kind) for row in rows], meta)

    return await guarded(run)


async def custom_fields_write(
    action_name: str,
    field_id: int = 0,
    fieldset_id: int = 0,
    name: str = "",
    element: str = "text",
    field_format: str = "ANY",
    field_values: str = "",
    field_encrypted: bool = False,
    show_in_email: bool = False,
    help_text: str = "",
    required: bool = False,
    order: int = 0,
    field_order_json: str = "",
) -> dict[str, object]:
    """Create/update fields and fieldsets, associate or disassociate a field, or reorder fields. Use explicit actions create_field, update_field, create_fieldset, update_fieldset, associate, disassociate, or reorder. This tool cannot delete fields or fieldsets."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"create_field", "update_field", "create_fieldset", "update_fieldset", "associate", "disassociate", "reorder"}, "custom_fields_write")
        async with client_for_request() as client:
            if selected in {"create_field", "update_field"}:
                if selected == "create_field" and not name:
                    raise invalid("name is required to create a field")
                if selected == "update_field" and field_id <= 0:
                    raise invalid("field_id is required to update a field")
                if element not in {"text", "textarea", "listbox", "checkbox", "radio"}:
                    raise invalid("element is not a supported custom-field element")
                data = compact({"name": name, "element": element, "format": field_format, "field_values": field_values, "help_text": help_text})
                data.update({"field_encrypted": field_encrypted, "show_in_email": show_in_email})
                payload = await client.request_json("POST" if selected == "create_field" else "PATCH", "fields" if selected == "create_field" else f"fields/{field_id}", json_body=data)
                item = normalize_custom_field(result_item(payload), "field")
            elif selected in {"create_fieldset", "update_fieldset"}:
                if selected == "create_fieldset" and not name:
                    raise invalid("name is required to create a fieldset")
                if selected == "update_fieldset" and fieldset_id <= 0:
                    raise invalid("fieldset_id is required to update a fieldset")
                payload = await client.request_json("POST" if selected == "create_fieldset" else "PATCH", "fieldsets" if selected == "create_fieldset" else f"fieldsets/{fieldset_id}", json_body={"name": name})
                item = normalize_custom_field(result_item(payload), "fieldset")
            elif selected in {"associate", "disassociate"}:
                if field_id <= 0 or fieldset_id <= 0:
                    raise invalid("field_id and fieldset_id are required")
                data: dict[str, object] = {"fieldset_id": fieldset_id}
                if selected == "associate":
                    data.update({"required": required, "order": order})
                payload = await client.request_json("POST", f"fields/{field_id}/{selected}", json_body=data)
                item = normalize_custom_field(result_item(payload), "field")
                item.setdefault("id", field_id)
                item.setdefault("fieldset_id", fieldset_id)
            else:
                if fieldset_id <= 0:
                    raise invalid("fieldset_id is required for reorder")
                try:
                    ordering = json.loads(field_order_json)
                except json.JSONDecodeError as exc:
                    raise invalid("field_order_json must be a JSON array of field IDs") from exc
                if not isinstance(ordering, list) or not ordering or len(ordering) > 500 or len(set(ordering)) != len(ordering) or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in ordering):
                    raise invalid("field_order_json must contain 1-500 unique positive integer IDs")
                payload = await client.request_json("POST", f"fields/fieldsets/{fieldset_id}/order", json_body={"item": ordering})
                item = normalize_custom_field(result_item(payload), "fieldset")
                item.setdefault("id", fieldset_id)
            return success_item(item, f"Custom-field action {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="custom_fields_search", description=custom_fields_search.__doc__, annotations=READ, output_schema=CUSTOM_FIELD_LIST_OUTPUT)(custom_fields_search)
    mcp.tool(name="custom_fields_write", description=custom_fields_write.__doc__, annotations=WRITE, output_schema=CUSTOM_FIELD_SINGLE_OUTPUT)(custom_fields_write)

