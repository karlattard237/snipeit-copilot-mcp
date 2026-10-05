"""The sole public deletion boundary."""

from __future__ import annotations

from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_generic
from ..schemas import GENERIC_SINGLE_OUTPUT
from .common import guarded, result_item, success_item

_RECORD_ENDPOINTS = {
    "asset": "hardware", "accessory": "accessories", "component": "components",
    "consumable": "consumables", "user": "users", "company": "companies",
    "department": "departments", "group": "groups", "category": "categories",
    "manufacturer": "manufacturers", "model": "models", "status_label": "statuslabels",
    "location": "locations", "supplier": "suppliers", "depreciation": "depreciations",
    "custom_field": "fields", "fieldset": "fieldsets", "licence": "licenses",
    "import": "imports", "maintenance": "maintenances", "maintenance_type": "maintenance-types",
    "kit": "kits",
}
_FILE_TYPES = {
    "asset_file": "hardware", "accessory_file": "accessories", "component_file": "components",
    "consumable_file": "consumables", "licence_file": "licenses", "location_file": "locations",
    "maintenance_file": "maintenances", "model_file": "models", "supplier_file": "suppliers",
    "user_file": "users", "company_file": "companies", "department_file": "departments",
}
DESTRUCTIVE = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True}


async def delete_resource(resource_type: str, resource_id: int = 0, parent_id: int = 0, file_id: int = 0) -> dict[str, object]:
    """Permanently or destructively remove confirmed Snipe-IT data. Use only for an explicit deletion request after the calling agent has retrieved and shown the exact target and received immediate user confirmation. For files, provide parent_id and file_id; for records, provide resource_id. This is the only MCP tool that can issue HTTP DELETE."""

    async def run() -> dict[str, object]:
        kind = resource_type.strip().lower().replace("-", "_")
        if kind in _RECORD_ENDPOINTS:
            if resource_id <= 0:
                raise invalid("resource_id is required for record deletion")
            endpoint = f"{_RECORD_ENDPOINTS[kind]}/{resource_id}"
            deleted_id = resource_id
        elif kind in _FILE_TYPES:
            if parent_id <= 0 or file_id <= 0:
                raise invalid("parent_id and file_id are required for file deletion")
            endpoint = f"{_FILE_TYPES[kind]}/{parent_id}/files/{file_id}/delete"
            deleted_id = file_id
        else:
            raise invalid("resource_type is not an allowlisted Snipe-IT deletion target")
        async with client_for_request() as client:
            payload = await client.request_json("DELETE", endpoint)
            item = normalize_generic(result_item(payload), kind)
            item.setdefault("id", deleted_id)
            item.setdefault("name", f"deleted {kind}")
            return success_item(item, f"Confirmed {kind} deletion succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="delete_resource", description=delete_resource.__doc__, annotations=DESTRUCTIVE, output_schema=GENERIC_SINGLE_OUTPUT)(delete_resource)

