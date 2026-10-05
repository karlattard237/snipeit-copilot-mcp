"""Companies, departments, and groups."""

from __future__ import annotations

from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_generic
from ..schemas import GENERIC_LIST_OUTPUT, GENERIC_SINGLE_OUTPUT
from .common import action, compact, guarded, payload_json, result_item, success_item, success_list

_ENDPOINTS = {"company": "companies", "department": "departments", "group": "groups"}
READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}


def _resource(value: str) -> tuple[str, str]:
    selected = value.strip().lower().rstrip("s")
    if selected not in _ENDPOINTS:
        raise invalid("organization_type must be company, department, or group")
    return selected, _ENDPOINTS[selected]


async def organization_search(organization_type: str, action_name: str = "list", item_id: int = 0, query: str = "", company_id: int = 0, location_id: int = 0, manager_id: int = 0, limit: int = 50, offset: int = 0) -> dict[str, object]:
    """List, search, or retrieve Snipe-IT companies, departments, and permission groups. Use organization_type=company, department, or group. Returns stable identity/contact fields and safe extra field entries. This tool is read-only and cannot modify memberships or delete records."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "search", "get"}, "organization_search")
        kind, endpoint = _resource(organization_type)
        async with client_for_request() as client:
            if selected == "get":
                if item_id <= 0:
                    raise invalid("item_id is required for action=get")
                payload = await client.request_json("GET", f"{endpoint}/{item_id}")
                return success_list([normalize_generic(result_item(payload), kind)], {"count": 1, "total": 1, "has_more": False})
            rows, meta = await client.list_page(endpoint, limit=limit, offset=offset, search=query if selected == "search" or query else "", extra=compact({"company_id": company_id, "location_id": location_id, "manager_id": manager_id}))
            return success_list([normalize_generic(row, kind) for row in rows], meta)

    return await guarded(run)


async def organization_write(organization_type: str, action_name: str, item_id: int = 0, name: str = "", company_id: int = 0, location_id: int = 0, manager_id: int = 0, notes: str = "", permissions_json: str = "") -> dict[str, object]:
    """Create or update a Snipe-IT company, department, or group. Common relationship fields are explicit; group permissions can be supplied as a JSON object. Use only for requested writes. This tool cannot delete organisation records."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"create", "update"}, "organization_write")
        kind, endpoint = _resource(organization_type)
        if selected == "create" and not name:
            raise invalid("name is required to create an organisation record")
        if selected == "update" and item_id <= 0:
            raise invalid("item_id is required to update an organisation record")
        data = compact({"name": name, "company_id": company_id, "location_id": location_id, "manager_id": manager_id, "notes": notes})
        if permissions_json:
            if kind != "group":
                raise invalid("permissions_json is only valid for groups")
            data["permissions"] = payload_json(permissions_json, "permissions_json")
        async with client_for_request() as client:
            payload = await client.request_json("POST" if selected == "create" else "PATCH", endpoint if selected == "create" else f"{endpoint}/{item_id}", json_body=data)
            return success_item(normalize_generic(result_item(payload), kind), f"{kind.title()} {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="organization_search", description=organization_search.__doc__, annotations=READ, output_schema=GENERIC_LIST_OUTPUT)(organization_search)
    mcp.tool(name="organization_write", description=organization_write.__doc__, annotations=WRITE, output_schema=GENERIC_SINGLE_OUTPUT)(organization_write)

