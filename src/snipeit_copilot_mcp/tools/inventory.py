"""Accessory, component, and consumable tools."""

from __future__ import annotations

from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_inventory
from ..schemas import INVENTORY_LIST_OUTPUT, INVENTORY_SINGLE_OUTPUT
from .common import action, compact, guarded, result_item, success_item, success_list

_ENDPOINTS = {"accessory": "accessories", "component": "components", "consumable": "consumables"}
READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
UPDATE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}


def _type(value: str) -> tuple[str, str]:
    selected = value.strip().lower().rstrip("s")
    if selected not in _ENDPOINTS:
        raise invalid("inventory_type must be accessory, component, or consumable")
    return selected, _ENDPOINTS[selected]


async def inventory_search(
    inventory_type: str,
    action_name: str = "list",
    item_id: int = 0,
    query: str = "",
    category_id: int = 0,
    manufacturer_id: int = 0,
    location_id: int = 0,
    company_id: int = 0,
    supplier_id: int = 0,
    limit: int = 50,
    offset: int = 0,
    sort: str = "id",
    order: str = "asc",
) -> dict[str, object]:
    """Read accessories, components, or consumables with normalized quantity, model, serial, manufacturer, location, company, supplier, purchase, and audit-safe extra fields. Set inventory_type to accessory, component, or consumable. Do not use for writes, assignments, or deletion."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "search", "get", "assignments"}, "inventory_search")
        kind, endpoint = _type(inventory_type)
        async with client_for_request() as client:
            if selected == "get":
                if item_id <= 0:
                    raise invalid("item_id is required for action=get")
                payload = await client.request_json("GET", f"{endpoint}/{item_id}")
                return success_list([normalize_inventory(result_item(payload), kind)], {"count": 1, "total": 1, "has_more": False})
            if selected == "assignments":
                if item_id <= 0:
                    raise invalid("item_id is required for action=assignments")
                relationship = {"accessory": "checkedout", "component": "assets", "consumable": "users"}[kind]
                rows, meta = await client.list_page(f"{endpoint}/{item_id}/{relationship}", limit=limit, offset=offset)
                return success_list([normalize_inventory(row, kind) for row in rows], meta)
            extra = compact({"category_id": category_id, "manufacturer_id": manufacturer_id, "location_id": location_id, "company_id": company_id, "supplier_id": supplier_id})
            rows, meta = await client.list_page(endpoint, limit=limit, offset=offset, search=query if selected == "search" or query else "", sort=sort, order=order, extra=extra)
            return success_list([normalize_inventory(row, kind) for row in rows], meta)

    return await guarded(run)


async def inventory_write(
    inventory_type: str,
    action_name: str,
    item_id: int = 0,
    name: str = "",
    qty: int = 0,
    category_id: int = 0,
    manufacturer_id: int = 0,
    location_id: int = 0,
    company_id: int = 0,
    supplier_id: int = 0,
    model_number: str = "",
    serial: str = "",
    order_number: str = "",
    purchase_date: str = "",
    purchase_cost: float = 0.0,
    min_amt: int = 0,
    notes: str = "",
) -> dict[str, object]:
    """Create or update one accessory, component, or consumable using explicit fields. Use for ordinary inventory record writes after required IDs are known. This tool cannot assign, check in, check out, or delete inventory."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"create", "update"}, "inventory_write")
        kind, endpoint = _type(inventory_type)
        data = compact({"name": name, "qty": qty, "category_id": category_id, "manufacturer_id": manufacturer_id, "location_id": location_id, "company_id": company_id, "supplier_id": supplier_id, "model_number": model_number, "serial": serial, "order_number": order_number, "purchase_date": purchase_date, "purchase_cost": purchase_cost, "min_amt": min_amt, "notes": notes})
        if selected == "create" and (not name or qty <= 0 or category_id <= 0):
            raise invalid("name, positive qty, and category_id are required to create inventory")
        if selected == "update" and item_id <= 0:
            raise invalid("item_id is required to update inventory")
        async with client_for_request() as client:
            payload = await client.request_json("POST" if selected == "create" else "PATCH", endpoint if selected == "create" else f"{endpoint}/{item_id}", json_body=data)
            return success_item(normalize_inventory(result_item(payload), kind), f"{kind.title()} {selected} succeeded")

    return await guarded(run)


async def inventory_lifecycle(
    inventory_type: str,
    action_name: str,
    item_id: int,
    assigned_to_id: int = 0,
    checkout_to_type: str = "user",
    quantity: int = 1,
    note: str = "",
) -> dict[str, object]:
    """Checkout or check in accessories and components, or checkout consumables, using only assignment workflows officially exposed by Snipe-IT. Accessories accept user, asset, or location targets; components require an asset; consumables require a user. This tool never deletes records."""

    async def run() -> dict[str, object]:
        kind, endpoint = _type(inventory_type)
        allowed = {"checkout"} if kind == "consumable" else {"checkout", "checkin"}
        selected = action(action_name, allowed, "inventory_lifecycle")
        if item_id <= 0 or assigned_to_id <= 0 or quantity <= 0:
            raise invalid("item_id, assigned_to_id, and positive quantity are required")
        target_type = checkout_to_type.strip().lower()
        if kind == "accessory" and target_type not in {"user", "asset", "location"}:
            raise invalid("Accessory checkout_to_type must be user, asset, or location")
        if kind == "component" and target_type != "asset":
            raise invalid("Components can only be assigned to assets")
        if kind == "consumable" and target_type != "user":
            raise invalid("Consumables can only be checked out to users")
        target_field = {"user": "assigned_user", "asset": "assigned_asset", "location": "assigned_location"}[target_type]
        data: dict[str, object] = {target_field: assigned_to_id, "assigned_to": assigned_to_id, "note": note}
        if kind == "component":
            data["assigned_qty"] = quantity
        else:
            data["checkout_qty"] = quantity
        async with client_for_request() as client:
            payload = await client.request_json("POST", f"{endpoint}/{item_id}/{selected}", json_body=data)
            item = normalize_inventory(result_item(payload), kind)
            item.setdefault("id", item_id)
            return success_item(item, f"{kind.title()} {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="inventory_search", description=inventory_search.__doc__, annotations=READ, output_schema=INVENTORY_LIST_OUTPUT)(inventory_search)
    mcp.tool(name="inventory_write", description=inventory_write.__doc__, annotations=UPDATE, output_schema=INVENTORY_SINGLE_OUTPUT)(inventory_write)
    mcp.tool(name="inventory_lifecycle", description=inventory_lifecycle.__doc__, annotations=WRITE, output_schema=INVENTORY_SINGLE_OUTPUT)(inventory_lifecycle)
