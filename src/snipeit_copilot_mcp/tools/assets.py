"""Asset discovery, writes, lifecycle, maintenance, relationships, and requests."""

from __future__ import annotations

import base64
import json
import re
from typing import Any

from ..client import client_for_request
from ..errors import invalid
from ..normalizers import normalize_asset, normalize_file, normalize_generic, normalize_license
from ..schemas import ASSET_LIST_OUTPUT, ASSET_SINGLE_OUTPUT, FILE_SINGLE_OUTPUT, GENERIC_LIST_OUTPUT, GENERIC_SINGLE_OUTPUT, LICENSE_LIST_OUTPUT
from ..security import path_segment
from .common import action, compact, guarded, payload_json, result_item, success_item, success_list

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": False, "openWorldHint": True}
UPDATE = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}


async def _asset_id(client: Any, asset_id: int, asset_tag: str, serial: str) -> int:
    if asset_id > 0:
        return asset_id
    if asset_tag:
        payload = await client.request_json("GET", f"hardware/bytag/{path_segment(asset_tag, 'asset_tag')}")
    elif serial:
        payload = await client.request_json("GET", f"hardware/byserial/{path_segment(serial, 'serial')}")
    else:
        raise invalid("Provide asset_id, asset_tag, or serial")
    rows = payload.get("rows") if isinstance(payload, dict) else None
    candidates = rows if isinstance(rows, list) else [result_item(payload)]
    identifiers = [item.get("id") for item in candidates if isinstance(item, dict) and isinstance(item.get("id"), int)]
    if len(identifiers) != 1:
        if not identifiers:
            raise invalid("No asset matched the supplied identifier")
        raise invalid("The supplied identifier matched multiple assets; use asset_id")
    return identifiers[0]


async def _user_id(client: Any, user_id: int, email: str) -> int:
    if user_id > 0:
        return user_id
    if not email:
        raise invalid("Provide assigned_to_id or user_email for a user checkout")
    rows, _ = await client.list_page("users", limit=20, search=email, extra={"email": email})
    exact = [row for row in rows if str(row.get("email", "")).casefold() == email.casefold()]
    if len(exact) != 1 or not isinstance(exact[0].get("id"), int):
        raise invalid("The user email was not an unambiguous exact match")
    return int(exact[0]["id"])


async def assets_search(
    action_name: str,
    asset_id: int = 0,
    asset_tag: str = "",
    serial: str = "",
    query: str = "",
    model_id: int = 0,
    status_id: int = 0,
    category_id: int = 0,
    manufacturer_id: int = 0,
    location_id: int = 0,
    company_id: int = 0,
    assigned_to_id: int = 0,
    custom_field_name: str = "",
    custom_field_value: str = "",
    custom_field_operator: str = "contains",
    advanced_filter_json: str = "",
    filter_operator: str = "and",
    limit: int = 50,
    offset: int = 0,
    page: int = 0,
    per_page: int = 0,
    sort: str = "id",
    order: str = "asc",
) -> dict[str, object]:
    """Search and retrieve Snipe-IT hardware by ID, exact asset tag, exact serial, text, structured fields, custom fields, or the authenticated user's requestable catalog. Use for every read-only asset question. Returns explicit asset_tag, serial, model_name, model_number, manufacturer, status, assignment, location, dates, cost, and stable custom_fields. Do not use for writes, lifecycle actions, or deletion."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "get", "search", "by_tag", "by_serial", "requestable"}, "assets_search")
        async with client_for_request() as client:
            if selected == "get":
                if asset_id <= 0:
                    raise invalid("asset_id is required for action=get")
                payload = await client.request_json("GET", f"hardware/{asset_id}")
                return success_list([normalize_asset(result_item(payload))], {"count": 1, "total": 1, "has_more": False})
            if selected == "by_tag":
                if not asset_tag:
                    raise invalid("asset_tag is required for action=by_tag")
                payload = await client.request_json("GET", f"hardware/bytag/{path_segment(asset_tag, 'asset_tag')}")
                rows = payload.get("rows") if isinstance(payload.get("rows"), list) else [result_item(payload)]
                items = [normalize_asset(row) for row in rows if isinstance(row, dict)]
                return success_list(items, {"count": len(items), "total": len(items), "has_more": False})
            if selected == "by_serial":
                if not serial:
                    raise invalid("serial is required for action=by_serial")
                payload = await client.request_json("GET", f"hardware/byserial/{path_segment(serial, 'serial')}")
                rows = payload.get("rows") if isinstance(payload.get("rows"), list) else [result_item(payload)]
                items = [normalize_asset(row) for row in rows if isinstance(row, dict)]
                return success_list(items, {"count": len(items), "total": len(items), "has_more": False})

            if selected == "requestable":
                rows, meta = await client.list_page(
                    "account/requestable/hardware",
                    limit=limit,
                    offset=offset,
                    page=page,
                    per_page=per_page,
                    search=query,
                    sort=sort,
                    order=order,
                )
                return success_list([normalize_asset(row) for row in rows], meta)

            extra: dict[str, object] = compact(
                {
                    "model_id": model_id, "status_id": status_id, "category_id": category_id,
                    "manufacturer_id": manufacturer_id, "location_id": location_id,
                    "company_id": company_id, "assigned_to": assigned_to_id,
                }
            )
            filters = payload_json(advanced_filter_json, "advanced_filter_json")
            if custom_field_name:
                db_column = custom_field_name
                if not custom_field_name.startswith("_snipeit_"):
                    field_rows, _ = await client.list_page("fields", limit=100, search=custom_field_name)
                    matches = [row for row in field_rows if str(row.get("name", "")).casefold() == custom_field_name.casefold()]
                    if len(matches) != 1 or not matches[0].get("db_column"):
                        raise invalid("custom_field_name did not resolve to one Snipe-IT field; use its db_column")
                    db_column = str(matches[0]["db_column"])
                operator_prefix = {"contains": "", "is": "is:", "not": "!", "starts_with": "starts:"}.get(custom_field_operator)
                if operator_prefix is None:
                    raise invalid("custom_field_operator must be contains, is, not, or starts_with")
                filters[db_column] = operator_prefix + custom_field_value
            if filters:
                extra["filter"] = json.dumps(filters, ensure_ascii=False, separators=(",", ":"))
                if filter_operator.lower() not in {"and", "or"}:
                    raise invalid("filter_operator must be and or or")
                extra["filter_operator"] = filter_operator.lower()
            rows, meta = await client.list_page(
                "hardware", limit=limit, offset=offset, page=page, per_page=per_page,
                search=query if selected == "search" or query else "", sort=sort, order=order, extra=extra,
            )
            return success_list([normalize_asset(row) for row in rows], meta)

    return await guarded(run)


async def assets_write(
    action_name: str,
    asset_id: int = 0,
    asset_tag: str = "",
    serial: str = "",
    name: str = "",
    model_id: int = 0,
    status_id: int = 0,
    location_id: int = 0,
    company_id: int = 0,
    supplier_id: int = 0,
    purchase_date: str = "",
    purchase_cost: float = 0.0,
    order_number: str = "",
    warranty_months: int = 0,
    notes: str = "",
    requestable: bool = False,
    archived: bool = False,
    custom_fields_json: str = "",
) -> dict[str, object]:
    """Create or update a Snipe-IT hardware asset using explicit common fields and optional custom fields. Use only for an explicit create or update request. This tool cannot delete, checkout, checkin, audit, or restore assets. Returns the normalized asset when the backend includes it."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"create", "update"}, "assets_write")
        data = compact(
            {
                "asset_tag": asset_tag, "serial": serial, "name": name, "model_id": model_id,
                "status_id": status_id, "location_id": location_id, "company_id": company_id,
                "supplier_id": supplier_id, "purchase_date": purchase_date, "purchase_cost": purchase_cost,
                "order_number": order_number, "warranty_months": warranty_months, "notes": notes,
            }
        )
        if requestable:
            data["requestable"] = True
        if archived:
            data["archived"] = True
        custom = payload_json(custom_fields_json, "custom_fields_json")
        for key, value in custom.items():
            if not re.fullmatch(r"_snipeit_[A-Za-z0-9_]+", key):
                raise invalid("custom_fields_json keys must be Snipe-IT db_column names")
            data[key] = value
        if selected == "create" and (model_id <= 0 or status_id <= 0):
            raise invalid("model_id and status_id are required to create an asset")
        if selected == "update" and asset_id <= 0:
            raise invalid("asset_id is required to update an asset")
        async with client_for_request() as client:
            payload = await client.request_json("POST" if selected == "create" else "PATCH", "hardware" if selected == "create" else f"hardware/{asset_id}", json_body=data)
            item = normalize_asset(result_item(payload))
            return success_item(item, f"Asset {selected} succeeded")

    return await guarded(run)


async def asset_lifecycle(
    action_name: str,
    asset_id: int = 0,
    asset_tag: str = "",
    serial: str = "",
    checkout_to_type: str = "user",
    assigned_to_id: int = 0,
    user_email: str = "",
    expected_checkin: str = "",
    note: str = "",
    location_id: int = 0,
    next_audit_date: str = "",
) -> dict[str, object]:
    """Checkout, checkin, audit, or restore one Snipe-IT asset after deterministically resolving its ID. Human identifiers and exact user email are accepted when unambiguous. Use only when the user explicitly requests the lifecycle action. This tool never deletes an asset."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"checkout", "checkin", "audit", "restore"}, "asset_lifecycle")
        async with client_for_request() as client:
            resolved = await _asset_id(client, asset_id, asset_tag, serial)
            data: dict[str, object] = {}
            if selected == "checkout":
                target_type = checkout_to_type.strip().lower()
                if target_type not in {"user", "asset", "location"}:
                    raise invalid("checkout_to_type must be user, asset, or location")
                target = await _user_id(client, assigned_to_id, user_email) if target_type == "user" else assigned_to_id
                if target <= 0:
                    raise invalid("assigned_to_id is required for this checkout target")
                data = {"checkout_to_type": target_type, "assigned_to": target}
                data[f"assigned_{target_type}"] = target
                data.update(compact({"expected_checkin": expected_checkin, "note": note}))
                endpoint = f"hardware/{resolved}/checkout"
            elif selected == "checkin":
                data = compact({"note": note, "location_id": location_id})
                endpoint = f"hardware/{resolved}/checkin"
            elif selected == "audit":
                data = compact({"note": note, "location_id": location_id, "next_audit_date": next_audit_date})
                endpoint = f"hardware/{resolved}/audit"
            else:
                endpoint = f"hardware/{resolved}/restore"
            payload = await client.request_json("POST", endpoint, json_body=data)
            item = normalize_asset(result_item(payload))
            if not item:
                item = {"id": resolved}
            return success_item(item, f"Asset {selected} succeeded")

    return await guarded(run)


async def asset_labels(asset_ids_json: str, label_name: str = "") -> dict[str, object]:
    """Generate a bounded printable Snipe-IT asset-label PDF for explicitly supplied asset IDs. Returns file metadata and base64 content suitable for a client to save. Do not use for ordinary asset lookup or for unbounded label generation."""

    async def run() -> dict[str, object]:
        try:
            ids = json.loads(asset_ids_json)
        except json.JSONDecodeError as exc:
            raise invalid("asset_ids_json must be a JSON array of integer IDs") from exc
        if not isinstance(ids, list) or not ids or len(ids) > 500 or any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in ids):
            raise invalid("asset_ids_json must contain 1-500 positive integer IDs")
        data: dict[str, object] = {"ids": ids}
        if label_name:
            data["label_name"] = label_name
        async with client_for_request() as client:
            content, mime, _ = await client.request_bytes("POST", "hardware/labels", json_body=data)
        item = normalize_file({"id": 0, "filename": "asset-labels.pdf", "size": len(content), "mime_type": mime}, "asset", 0)
        item["content_base64"] = base64.b64encode(content).decode("ascii")
        item["content_truncated"] = False
        return success_item(item, "Asset labels generated")

    return await guarded(run)


async def asset_maintenance(
    action_name: str,
    maintenance_id: int = 0,
    asset_id: int = 0,
    maintenance_type_id: int = 0,
    title: str = "",
    supplier_id: int = 0,
    start_date: str = "",
    completion_date: str = "",
    cost: float = 0.0,
    notes: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, object]:
    """List, retrieve, create, update, complete, or add/list notes for Snipe-IT asset maintenance, and list maintenance types. Use for maintenance records only. The tool cannot delete maintenance records or types; deletion is isolated in delete_resource."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "get", "create", "update", "complete", "list_notes", "add_note", "list_types"}, "asset_maintenance")
        async with client_for_request() as client:
            if selected in {"list", "list_types"}:
                endpoint = "maintenance-types" if selected == "list_types" else "maintenances"
                rows, meta = await client.list_page(endpoint, limit=limit, offset=offset)
                return success_list([normalize_generic(row, endpoint) for row in rows], meta)
            if maintenance_id <= 0 and selected not in {"create"}:
                raise invalid("maintenance_id is required")
            if selected == "get":
                payload = await client.request_json("GET", f"maintenances/{maintenance_id}")
            elif selected == "list_notes":
                payload = await client.request_json("GET", f"maintenances/{maintenance_id}/notes")
                rows = payload.get("rows", [])
                items = [normalize_generic(row, "maintenance_note") for row in rows if isinstance(row, dict)]
                return success_list(items, {"count": len(items), "total": len(items), "has_more": False})
            elif selected == "add_note":
                if not notes:
                    raise invalid("notes is required for add_note")
                payload = await client.request_json("POST", f"maintenances/{maintenance_id}/notes", json_body={"note": notes})
            elif selected == "complete":
                payload = await client.request_json("POST", f"maintenances/{maintenance_id}/complete", json_body=compact({"completion_date": completion_date, "notes": notes}))
            else:
                data = compact({"asset_id": asset_id, "asset_maintenance_type": maintenance_type_id, "title": title, "supplier_id": supplier_id, "start_date": start_date, "completion_date": completion_date, "cost": cost, "notes": notes})
                if selected == "create" and (asset_id <= 0 or maintenance_type_id <= 0 or not title):
                    raise invalid("asset_id, maintenance_type_id, and title are required to create maintenance")
                if selected == "update" and maintenance_id <= 0:
                    raise invalid("maintenance_id is required to update maintenance")
                payload = await client.request_json("POST" if selected == "create" else "PATCH", "maintenances" if selected == "create" else f"maintenances/{maintenance_id}", json_body=data)
            item = normalize_generic(result_item(payload), "maintenance")
            return success_list([item], {"count": 1, "total": 1, "has_more": False}, f"Maintenance {selected} succeeded")

    return await guarded(run)


async def asset_licenses(asset_id: int = 0, asset_tag: str = "", serial: str = "", limit: int = 50, offset: int = 0) -> dict[str, object]:
    """Read software licences associated with one asset, resolving an exact asset tag or serial when needed. Returns product keys only when Snipe-IT and the caller's permissions expose them. This tool is read-only."""

    async def run() -> dict[str, object]:
        async with client_for_request() as client:
            resolved = await _asset_id(client, asset_id, asset_tag, serial)
            rows, meta = await client.list_page(f"hardware/{resolved}/licenses", limit=limit, offset=offset)
            return success_list([normalize_license(row) for row in rows], meta)

    return await guarded(run)


async def asset_requests(action_name: str, asset_id: int = 0, asset_tag: str = "", serial: str = "", expected_checkout: str = "", note: str = "") -> dict[str, object]:
    """Submit or cancel the authenticated user's request for a requestable asset. Use only when the user explicitly asks to request or cancel a request. This does not approve requests, checkout assets, or delete data."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"request", "cancel"}, "asset_requests")
        async with client_for_request() as client:
            resolved = await _asset_id(client, asset_id, asset_tag, serial)
            endpoint = f"account/request/{resolved}" + ("/cancel" if selected == "cancel" else "")
            payload = await client.request_json("POST", endpoint, json_body=compact({"expected_checkout": expected_checkout, "note": note}))
            return success_item(normalize_generic(result_item(payload), "asset_request"), f"Asset request {selected} succeeded")

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="assets_search", description=assets_search.__doc__, annotations=READ, output_schema=ASSET_LIST_OUTPUT)(assets_search)
    mcp.tool(name="assets_write", description=assets_write.__doc__, annotations=UPDATE, output_schema=ASSET_SINGLE_OUTPUT)(assets_write)
    mcp.tool(name="asset_lifecycle", description=asset_lifecycle.__doc__, annotations=WRITE, output_schema=ASSET_SINGLE_OUTPUT)(asset_lifecycle)
    mcp.tool(name="asset_labels", description=asset_labels.__doc__, annotations=READ, output_schema=FILE_SINGLE_OUTPUT)(asset_labels)
    mcp.tool(name="asset_maintenance", description=asset_maintenance.__doc__, annotations=WRITE, output_schema=GENERIC_LIST_OUTPUT)(asset_maintenance)
    mcp.tool(name="asset_licenses", description=asset_licenses.__doc__, annotations=READ, output_schema=LICENSE_LIST_OUTPUT)(asset_licenses)
    mcp.tool(name="asset_requests", description=asset_requests.__doc__, annotations=WRITE, output_schema=GENERIC_SINGLE_OUTPUT)(asset_requests)
