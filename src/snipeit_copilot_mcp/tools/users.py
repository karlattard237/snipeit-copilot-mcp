"""User discovery, administration, and rich assigned inventory."""

from __future__ import annotations

import asyncio
from typing import Any

from ..client import client_for_request
from ..errors import SnipeITError, invalid
from ..normalizers import normalize_asset, normalize_generic, normalize_inventory, normalize_license, normalize_user
from ..schemas import USER_INVENTORY_OUTPUT, USER_LIST_OUTPUT, USER_SINGLE_OUTPUT
from .common import action, compact, guarded, result_item, success_item, success_list

READ = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}
WRITE_HIGH_IMPACT = {"readOnlyHint": False, "destructiveHint": True, "idempotentHint": False, "openWorldHint": True}


async def _resolve_user(client: Any, user_id: int, email: str, username: str, employee_num: str = "") -> int:
    if user_id > 0:
        return user_id
    supplied = [("email", email), ("username", username), ("employee_num", employee_num)]
    field, value = next(((field, value) for field, value in supplied if value), ("", ""))
    if not value:
        raise invalid("Provide user_id, email, username, or employee_num")
    rows, _ = await client.list_page("users", limit=50, search=value, extra={field: value})
    exact = [row for row in rows if str(row.get(field, "")).casefold() == value.casefold()]
    if len(exact) != 1 or not isinstance(exact[0].get("id"), int):
        raise invalid(f"{field} did not resolve to one exact user; use user_id")
    return int(exact[0]["id"])


async def users_search(
    action_name: str = "list",
    user_id: int = 0,
    query: str = "",
    email: str = "",
    username: str = "",
    employee_num: str = "",
    location_id: int = 0,
    department_id: int = 0,
    company_id: int = 0,
    deleted: bool = False,
    limit: int = 50,
    offset: int = 0,
    sort: str = "id",
    order: str = "asc",
) -> dict[str, object]:
    """List, search, retrieve, or identify the current authenticated Snipe-IT user. Supports exact email, username, employee number and organisation filters, including deleted-user queries. Returns explicit identity, department, location, company, manager, flags, and inventory counts. Do not use for writes or deletion."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"list", "search", "get", "me", "by_email", "by_username", "by_employee_num"}, "users_search")
        async with client_for_request() as client:
            if selected == "me":
                payload = await client.request_json("GET", "users/me")
                return success_list([normalize_user(result_item(payload))], {"count": 1, "total": 1, "has_more": False})
            if selected == "get":
                if user_id <= 0:
                    raise invalid("user_id is required for action=get")
                payload = await client.request_json("GET", f"users/{user_id}")
                return success_list([normalize_user(result_item(payload))], {"count": 1, "total": 1, "has_more": False})
            exact_field = {"by_email": ("email", email), "by_username": ("username", username), "by_employee_num": ("employee_num", employee_num)}.get(selected)
            search = query
            extra = compact({"location_id": location_id, "department_id": department_id, "company_id": company_id})
            if deleted:
                extra["deleted"] = True
            if exact_field:
                field, value = exact_field
                if not value:
                    raise invalid(f"{field} is required for action={selected}")
                search = value
                extra[field] = value
            elif email:
                search, extra["email"] = email, email
            elif username:
                search, extra["username"] = username, username
            elif employee_num:
                search, extra["employee_num"] = employee_num, employee_num
            rows, meta = await client.list_page("users", limit=limit, offset=offset, search=search if selected == "search" or search else "", sort=sort, order=order, extra=extra)
            if exact_field:
                field, value = exact_field
                rows = [row for row in rows if str(row.get(field, "")).casefold() == value.casefold()]
                meta = {"count": len(rows), "total": len(rows), "has_more": False}
            return success_list([normalize_user(row) for row in rows], meta)

    return await guarded(run)


async def users_write(
    action_name: str,
    user_id: int = 0,
    first_name: str = "",
    last_name: str = "",
    username: str = "",
    email: str = "",
    password: str = "",
    password_confirmation: str = "",
    employee_num: str = "",
    jobtitle: str = "",
    phone: str = "",
    department_id: int = 0,
    location_id: int = 0,
    company_id: int = 0,
    manager_id: int = 0,
    activated: bool = True,
    remote: bool = False,
    vip: bool = False,
    notes: str = "",
) -> dict[str, object]:
    """Create, update, restore, or explicitly reset two-factor authentication for a Snipe-IT user. Use create/update/restore for requested administration; use reset_2fa only when the user explicitly asks for that high-impact security action. This tool cannot delete users."""

    async def run() -> dict[str, object]:
        selected = action(action_name, {"create", "update", "restore", "reset_2fa"}, "users_write")
        if selected != "create" and user_id <= 0:
            raise invalid("user_id is required for update, restore, and reset_2fa")
        data = compact({"first_name": first_name, "last_name": last_name, "username": username, "email": email, "password": password, "password_confirmation": password_confirmation, "employee_num": employee_num, "jobtitle": jobtitle, "phone": phone, "department_id": department_id, "location_id": location_id, "company_id": company_id, "manager_id": manager_id, "notes": notes})
        if selected in {"create", "update"}:
            data.update({"activated": activated, "remote": remote, "vip": vip})
        if selected == "create" and (not first_name or not username or not password or password != password_confirmation):
            raise invalid("first_name, username, matching password and password_confirmation are required to create a user")
        async with client_for_request() as client:
            if selected == "create":
                payload = await client.request_json("POST", "users", json_body=data)
            elif selected == "update":
                payload = await client.request_json("PATCH", f"users/{user_id}", json_body=data)
            elif selected == "restore":
                payload = await client.request_json("POST", f"users/{user_id}/restore", json_body={})
            else:
                payload = await client.request_json("POST", f"users/{user_id}/two_factor_reset", json_body={})
            item = normalize_user(result_item(payload))
            item.setdefault("id", user_id)
            return success_item(item, f"User {selected} succeeded")

    return await guarded(run)


async def user_inventory(user_id: int = 0, email: str = "", username: str = "", include_eulas: bool = True) -> dict[str, object]:
    """Retrieve everything assigned to one unambiguously identified user in one call: rich assets, accessories, licences, consumables, and optional EULA/acceptance records. Assets use the same normalization as assets_search and explicitly include asset_tag, serial, model_name, model_number, manufacturer, status, and location. This tool is read-only."""

    async def run() -> dict[str, object]:
        async with client_for_request() as client:
            resolved = await _resolve_user(client, user_id, email, username)
            user_payload = await client.request_json("GET", f"users/{resolved}")

            async def fetch(suffix: str) -> list[dict[str, Any]]:
                try:
                    payload = await client.request_json("GET", f"users/{resolved}/{suffix}")
                except SnipeITError as exc:
                    if exc.code in {"not_found", "unsupported_feature"}:
                        return []
                    raise
                rows = payload.get("rows", [])
                return rows if isinstance(rows, list) else []

            suffixes = ["assets", "accessories", "licenses", "consumables"] + (["eulas"] if include_eulas else [])
            fetched = await asyncio.gather(*(fetch(suffix) for suffix in suffixes))
            grouped = dict(zip(suffixes, fetched, strict=True))
            assets = [normalize_asset(row) for row in grouped.get("assets", [])]
            accessories = [normalize_inventory(row, "accessory") for row in grouped.get("accessories", [])]
            licences = [normalize_license(row) for row in grouped.get("licenses", [])]
            consumables = [normalize_inventory(row, "consumable") for row in grouped.get("consumables", [])]
            eulas = [normalize_generic(row, "eula") for row in grouped.get("eulas", [])]
            return {
                "success": True,
                "user": normalize_user(result_item(user_payload)),
                "assets": assets,
                "accessories": accessories,
                "licences": licences,
                "consumables": consumables,
                "eulas": eulas,
                "assets_count": len(assets),
                "accessories_count": len(accessories),
                "licences_count": len(licences),
                "consumables_count": len(consumables),
                "eulas_count": len(eulas),
            }

    return await guarded(run)


def register(mcp: Any) -> None:
    mcp.tool(name="users_search", description=users_search.__doc__, annotations=READ, output_schema=USER_LIST_OUTPUT)(users_search)
    mcp.tool(name="users_write", description=users_write.__doc__, annotations=WRITE_HIGH_IMPACT, output_schema=USER_SINGLE_OUTPUT)(users_write)
    mcp.tool(name="user_inventory", description=user_inventory.__doc__, annotations=READ, output_schema=USER_INVENTORY_OUTPUT)(user_inventory)

