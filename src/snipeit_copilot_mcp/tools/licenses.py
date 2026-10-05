"""Software licence and seat assignment tools."""

from __future__ import annotations

from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_generic, normalize_license
from ..schemas import GENERIC_LIST_OUTPUT, LICENSE_LIST_OUTPUT, LICENSE_SINGLE_OUTPUT
from .common import action, compact, guarded, result_item, success_item, success_list

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}


async def licenses_search(action_name: str = "list", license_id: int = 0, query: str = "", category_id: int = 0, manufacturer_id: int = 0, supplier_id: int = 0, company_id: int = 0, maintained: bool = False, limit: int = 50, offset: int = 0, sort: str = "id", order: str = "asc") -> dict[str, object]:
    """List, search, or retrieve software licences with explicit product_key, seat counts, category, manufacturer, supplier, company, purchase, expiry, maintenance, and reassignment fields. Product keys appear only when permissions allow. This tool is read-only."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "search", "get"}, "licenses_search")
        async with client_for_request() as client:
            if selected == "get":
                if license_id <= 0:
                    raise invalid("license_id is required for action=get")
                payload = await client.request_json("GET", f"licenses/{license_id}")
                return success_list([normalize_license(result_item(payload))], {"count": 1, "total": 1, "has_more": False})
            extra = compact({"category_id": category_id, "manufacturer_id": manufacturer_id, "supplier_id": supplier_id, "company_id": company_id})
            if maintained:
                extra["maintained"] = True
            rows, meta = await client.list_page("licenses", limit=limit, offset=offset, search=query if selected == "search" or query else "", sort=sort, order=order, extra=extra)
            return success_list([normalize_license(row) for row in rows], meta)

    return await guarded(run)


async def licenses_write(
    action_name: str,
    license_id: int = 0,
    name: str = "",
    product_key: str = "",
    seats: int = 0,
    category_id: int = 0,
    manufacturer_id: int = 0,
    supplier_id: int = 0,
    company_id: int = 0,
    purchase_date: str = "",
    purchase_cost: float = 0.0,
    expiration_date: str = "",
    termination_date: str = "",
    order_number: str = "",
    maintained: bool = False,
    reassignable: bool = True,
    notes: str = "",
) -> dict[str, object]:
    """Create or update a Snipe-IT software licence. The public product_key input is deliberately translated to Snipe-IT's write-side serial field while reads expose product_key. Use only for explicit writes. This tool cannot delete licences or assign seats."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"create", "update"}, "licenses_write")
        if selected == "create" and (not name or seats <= 0 or category_id <= 0):
            raise invalid("name, positive seats, and category_id are required to create a licence")
        if selected == "update" and license_id <= 0:
            raise invalid("license_id is required to update a licence")
        data = compact({"name": name, "serial": product_key, "seats": seats, "category_id": category_id, "manufacturer_id": manufacturer_id, "supplier_id": supplier_id, "company_id": company_id, "purchase_date": purchase_date, "purchase_cost": purchase_cost, "expiration_date": expiration_date, "termination_date": termination_date, "order_number": order_number, "notes": notes})
        data.update({"maintained": maintained, "reassignable": reassignable})
        async with client_for_request() as client:
            payload = await client.request_json("POST" if selected == "create" else "PATCH", "licenses" if selected == "create" else f"licenses/{license_id}", json_body=data)
            return success_item(normalize_license(result_item(payload)), f"Licence {selected} succeeded")

    return await guarded(run)


async def license_seats(action_name: str, license_id: int = 0, seat_id: int = 0, assigned_user_id: int = 0, assigned_asset_id: int = 0, note: str = "", limit: int = 50, offset: int = 0) -> dict[str, object]:
    """List, checkout, checkin, or update licence seats. Checkout accepts exactly one user or asset target; checkin removes an assignment but never deletes the licence or seat. Use mutation actions only for explicit assignment requests."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "checkout", "checkin", "update"}, "license_seats")
        async with client_for_request() as client:
            if selected == "list":
                if license_id <= 0:
                    raise invalid("license_id is required for action=list")
                rows, meta = await client.list_page(f"licenses/{license_id}/seats", limit=limit, offset=offset)
                return success_list([normalize_generic(row, "license_seat") for row in rows], meta)
            if seat_id <= 0:
                raise invalid("seat_id is required for seat mutations")
            if selected == "checkout":
                if license_id <= 0 or (assigned_user_id > 0) == (assigned_asset_id > 0):
                    raise invalid("license_id and exactly one of assigned_user_id or assigned_asset_id are required")
                data = compact({"assigned_to": assigned_user_id, "asset_id": assigned_asset_id, "note": note})
                endpoint = f"licenses/{license_id}/seats/{seat_id}/checkout"
                method = "POST"
            elif selected == "checkin":
                data = compact({"note": note})
                endpoint = f"licenses/seats/{seat_id}/checkin"
                method = "POST"
            else:
                data = compact({"assigned_to": assigned_user_id, "asset_id": assigned_asset_id, "note": note})
                endpoint = f"licenses/{license_id}/seats/{seat_id}"
                method = "PATCH"
            payload = await client.request_json(method, endpoint, json_body=data)
            item = normalize_generic(result_item(payload), "license_seat")
            item.setdefault("id", seat_id)
            return success_list([item], {"count": 1, "total": 1, "has_more": False}, f"Licence seat {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="licenses_search", description=licenses_search.__doc__, annotations=READ, output_schema=LICENSE_LIST_OUTPUT)(licenses_search)
    mcp.tool(name="licenses_write", description=licenses_write.__doc__, annotations=WRITE, output_schema=LICENSE_SINGLE_OUTPUT)(licenses_write)
    mcp.tool(name="license_seats", description=license_seats.__doc__, annotations=WRITE, output_schema=GENERIC_LIST_OUTPUT)(license_seats)

