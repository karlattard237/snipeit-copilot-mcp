"""Configuration and reference catalog tools."""

from __future__ import annotations

from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_asset, normalize_user
from ..schemas import ASSET_SINGLE_OUTPUT, CATALOG_LIST_OUTPUT
from .common import action, compact, guarded, result_item, success_item, success_list

_ENDPOINTS = {
    "category": "categories", "manufacturer": "manufacturers", "model": "models",
    "status_label": "statuslabels", "location": "locations", "supplier": "suppliers",
    "depreciation": "depreciations", "kit": "kits", "maintenance_type": "maintenance-types",
}
READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}


def _type(value: str) -> tuple[str, str]:
    normalized = value.strip().lower().replace("-", "_")
    aliases = {"status": "status_label", "statuses": "status_label", "models": "model", "locations": "location", "predefined_kit": "kit"}
    normalized = aliases.get(normalized, normalized.rstrip("s"))
    if normalized not in _ENDPOINTS:
        raise invalid("catalog_type must be category, manufacturer, model, status_label, location, supplier, depreciation, kit, or maintenance_type")
    return normalized, _ENDPOINTS[normalized]


async def catalog_search(catalog_type: str, action_name: str = "list", item_id: int = 0, query: str = "", category_type: str = "", limit: int = 50, offset: int = 0, sort: str = "id", order: str = "asc") -> dict[str, object]:
    """Read Snipe-IT categories, manufacturers, models, status labels, locations, suppliers, depreciations, predefined kits, and maintenance types. Relationship actions assets_by_model, assets_by_status, assets_at_location, and users_at_location return rich records without hiding model information. This tool is read-only."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "search", "get", "assets_by_model", "assets_by_status", "assets_at_location", "users_at_location"}, "catalog_search")
        kind, endpoint = _type(catalog_type)
        async with client_for_request() as client:
            if selected == "get":
                if item_id <= 0:
                    raise invalid("item_id is required for action=get")
                payload = await client.request_json("GET", f"{endpoint}/{item_id}")
                return success_list([normalize_asset(result_item(payload))], {"count": 1, "total": 1, "has_more": False})
            if selected.startswith("assets_"):
                expected = {"assets_by_model": "model", "assets_by_status": "status_label", "assets_at_location": "location"}[selected]
                if kind != expected or item_id <= 0:
                    raise invalid(f"{selected} requires catalog_type={expected} and a positive item_id")
                filter_name = {"model": "model_id", "status_label": "status_id", "location": "location_id"}[kind]
                rows, meta = await client.list_page("hardware", limit=limit, offset=offset, extra={filter_name: item_id})
                return success_list([normalize_asset(row) for row in rows], meta)
            if selected == "users_at_location":
                if kind != "location" or item_id <= 0:
                    raise invalid("users_at_location requires catalog_type=location and a positive item_id")
                rows, meta = await client.list_page("users", limit=limit, offset=offset, extra={"location_id": item_id})
                return success_list([normalize_user(row) for row in rows], meta)
            extra = {"category_type": category_type} if category_type else None
            rows, meta = await client.list_page(endpoint, limit=limit, offset=offset, search=query if selected == "search" or query else "", sort=sort, order=order, extra=extra)
            return success_list([normalize_asset(row) for row in rows], meta)

    return await guarded(run)


async def catalog_write(
    catalog_type: str,
    action_name: str,
    item_id: int = 0,
    name: str = "",
    model_number: str = "",
    category_id: int = 0,
    manufacturer_id: int = 0,
    depreciation_id: int = 0,
    fieldset_id: int = 0,
    parent_id: int = 0,
    manager_id: int = 0,
    months: int = 0,
    category_type: str = "",
    status_type: str = "",
    deployable: bool = False,
    pending: bool = False,
    archived: bool = False,
    address: str = "",
    city: str = "",
    state: str = "",
    country: str = "",
    zip_code: str = "",
    email: str = "",
    phone: str = "",
    url: str = "",
    notes: str = "",
) -> dict[str, object]:
    """Create or update supported Snipe-IT catalog records with explicit model, status, hierarchy, contact, depreciation, and type fields. Use for normal requested configuration writes. This tool has no delete action; all catalog deletion goes through delete_resource."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"create", "update"}, "catalog_write")
        kind, endpoint = _type(catalog_type)
        if selected == "create" and not name:
            raise invalid("name is required to create a catalog record")
        if selected == "update" and item_id <= 0:
            raise invalid("item_id is required to update a catalog record")
        data = compact({"name": name, "model_number": model_number, "category_id": category_id, "manufacturer_id": manufacturer_id, "depreciation_id": depreciation_id, "fieldset_id": fieldset_id, "parent_id": parent_id, "manager_id": manager_id, "months": months, "category_type": category_type, "status_type": status_type, "address": address, "city": city, "state": state, "country": country, "zip": zip_code, "email": email, "phone": phone, "url": url, "notes": notes})
        if kind == "status_label":
            if sum((deployable, pending, archived)) > 1:
                raise invalid("Only one of deployable, pending, or archived may be true")
            data.update({"deployable": deployable, "pending": pending, "archived": archived})
        async with client_for_request() as client:
            payload = await client.request_json("POST" if selected == "create" else "PATCH", endpoint if selected == "create" else f"{endpoint}/{item_id}", json_body=data)
            return success_item(normalize_asset(result_item(payload)), f"{kind.replace('_', ' ').title()} {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="catalog_search", description=catalog_search.__doc__, annotations=READ, output_schema=CATALOG_LIST_OUTPUT)(catalog_search)
    mcp.tool(name="catalog_write", description=catalog_write.__doc__, annotations=WRITE, output_schema=ASSET_SINGLE_OUTPUT)(catalog_write)
