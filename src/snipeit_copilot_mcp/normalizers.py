"""Defensive normalization from inconsistent Snipe-IT response shapes."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _value(value: object) -> object:
    if isinstance(value, dict):
        for key in ("datetime", "date", "formatted", "value", "name"):
            candidate = value.get(key)
            if candidate is not None and not isinstance(candidate, (dict, list)):
                return candidate
        return None
    return value


def _put(target: dict[str, object], key: str, value: object, expected: type | tuple[type, ...] | None = None) -> None:
    value = _value(value)
    if value is None or value == "":
        return
    if expected is bool:
        if isinstance(value, bool):
            target[key] = value
        elif isinstance(value, (int, str)) and str(value).lower() in {"0", "1", "true", "false", "yes", "no"}:
            target[key] = str(value).lower() in {"1", "true", "yes"}
        return
    if expected is int:
        if isinstance(value, bool):
            return
        try:
            target[key] = int(value)
        except (TypeError, ValueError):
            return
        return
    if expected is float:
        if isinstance(value, bool):
            return
        raw = str(value).replace(",", "").replace("$", "").replace("€", "").strip()
        try:
            target[key] = float(raw)
        except (TypeError, ValueError):
            return
        return
    if expected is str or expected is None:
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            target[key] = str(value) if expected is str else value


def _relation(target: dict[str, object], source: dict[str, Any], source_key: str, prefix: str) -> None:
    relation = _dict(source.get(source_key))
    _put(target, f"{prefix}_id", relation.get("id"), int)
    _put(target, f"{prefix}_name", relation.get("name") or relation.get("display_name"), str)


def _extra(source: dict[str, Any], consumed: set[str]) -> list[dict[str, str]]:
    extra: list[dict[str, str]] = []
    for key in sorted(source):
        if key in consumed or key == "custom_fields" or source[key] is None:
            continue
        value = source[key]
        if isinstance(value, (dict, list)):
            try:
                rendered = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
            except (TypeError, ValueError, RecursionError):
                continue
        else:
            rendered = str(value)
        if len(rendered) > 4096:
            rendered = rendered[:4093] + "..."
        extra.append({"name": str(key), "value": rendered})
    return extra[:100]


def _custom_fields(value: object) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    if isinstance(value, dict):
        iterable = value.items()
    elif isinstance(value, list):
        iterable = ((str(item.get("name", "")), item) for item in value if isinstance(item, dict))
    else:
        return output
    for name, raw in iterable:
        data = _dict(raw)
        field_value = data.get("value") if data else raw
        if isinstance(field_value, dict):
            field_value = field_value.get("value") or field_value.get("formatted") or ""
        item = {
            "name": str(data.get("name") or name),
            "db_column": str(data.get("db_column") or data.get("field") or name),
            "value": "" if field_value is None else str(field_value),
        }
        field_format = data.get("field_format") or data.get("format")
        if field_format:
            item["field_format"] = str(field_format)
        output.append(item)
    return output


def normalize_asset(raw: object) -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {}
    scalar = {
        "id": int,
        "name": str,
        "asset_tag": str,
        "serial": str,
        "order_number": str,
        "purchase_date": str,
        "purchase_cost": float,
        "warranty_months": int,
        "warranty_expires": str,
        "notes": str,
        "last_checkout": str,
        "expected_checkin": str,
        "next_audit_date": str,
        "last_audit_date": str,
        "requestable": bool,
        "archived": bool,
        "created_at": str,
        "updated_at": str,
    }
    for key, kind in scalar.items():
        _put(result, key, source.get(key), kind)
    for key, prefix in (
        ("model", "model"), ("manufacturer", "manufacturer"), ("category", "category"),
        ("status_label", "status"), ("company", "company"), ("supplier", "supplier"),
    ):
        _relation(result, source, key, prefix)
    model = _dict(source.get("model"))
    _put(result, "model_number", model.get("model_number") or source.get("model_number"), str)
    if "manufacturer_name" not in result:
        _relation(result, model, "manufacturer", "manufacturer")
    assigned = _dict(source.get("assigned_to"))
    _put(result, "assigned_to_id", assigned.get("id"), int)
    _put(result, "assigned_to_name", assigned.get("name") or assigned.get("display_name"), str)
    _put(result, "assigned_to_type", assigned.get("type") or source.get("assigned_type"), str)
    _put(result, "assigned_to_email", assigned.get("email"), str)
    location = _dict(source.get("location")) or _dict(assigned.get("location"))
    _put(result, "location_id", location.get("id"), int)
    _put(result, "location_name", location.get("name"), str)
    default_location = _dict(source.get("rtd_location")) or _dict(source.get("default_location"))
    _put(result, "default_location_id", default_location.get("id"), int)
    _put(result, "default_location_name", default_location.get("name"), str)
    custom = _custom_fields(source.get("custom_fields"))
    if custom:
        result["custom_fields"] = custom
    consumed = set(scalar) | {"model", "manufacturer", "category", "status_label", "company", "supplier", "assigned_to", "assigned_type", "location", "rtd_location", "default_location", "model_number", "custom_fields"}
    extra = _extra(source, consumed)
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_user(raw: object) -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {}
    scalar = {
        "id": int, "first_name": str, "last_name": str, "username": str, "email": str,
        "employee_num": str, "jobtitle": str, "phone": str, "remote": bool, "vip": bool,
        "activated": bool, "deleted": bool, "assets_count": int, "accessories_count": int,
        "licences_count": int, "consumables_count": int, "created_at": str, "updated_at": str,
    }
    for key, kind in scalar.items():
        _put(result, key, source.get(key), kind)
    _put(result, "name", source.get("name") or source.get("display_name") or " ".join(filter(None, [source.get("first_name"), source.get("last_name")])), str)
    for relation in ("department", "location", "company", "manager"):
        _relation(result, source, relation, relation)
    consumed = set(scalar) | {"name", "display_name", "department", "location", "company", "manager"}
    extra = _extra(source, consumed)
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_license(raw: object) -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {}
    scalar = {
        "id": int, "name": str, "product_key": str, "seats": int, "free_seats": int,
        "order_number": str, "purchase_date": str, "purchase_cost": float,
        "expiration_date": str, "termination_date": str, "maintained": bool,
        "reassignable": bool, "notes": str, "created_at": str, "updated_at": str,
    }
    for key, kind in scalar.items():
        _put(result, key, source.get(key), kind)
    for relation in ("category", "manufacturer", "supplier", "company"):
        _relation(result, source, relation, relation)
    consumed = set(scalar) | {"category", "manufacturer", "supplier", "company", "serial"}
    extra = _extra(source, consumed)
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_inventory(raw: object, inventory_type: str) -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {"inventory_type": inventory_type}
    scalar = {
        "id": int, "name": str, "asset_tag": str, "model_number": str, "serial": str, "qty": int,
        "remaining_qty": int, "min_amt": int, "order_number": str, "purchase_date": str,
        "purchase_cost": float, "notes": str, "created_at": str, "updated_at": str,
    }
    for key, kind in scalar.items():
        _put(result, key, source.get(key), kind)
    for relation in ("category", "manufacturer", "location", "company", "supplier"):
        _relation(result, source, relation, relation)
    assigned = _dict(source.get("assigned_to")) or _dict(source.get("assigned_user")) or _dict(source.get("assigned_asset")) or _dict(source.get("assigned_location"))
    _put(result, "assigned_to_id", assigned.get("id"), int)
    _put(result, "assigned_to_name", assigned.get("name"), str)
    _put(result, "assigned_to_type", assigned.get("type"), str)
    consumed = set(scalar) | {"category", "manufacturer", "location", "company", "supplier", "assigned_to", "assigned_user", "assigned_asset", "assigned_location"}
    extra = _extra(source, consumed)
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_generic(raw: object, resource_type: str = "") -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {}
    if resource_type:
        result["resource_type"] = resource_type
    for key, kind in {
        "id": int, "name": str, "type": str, "email": str, "phone": str, "address": str,
        "city": str, "state": str, "country": str, "zip": str, "notes": str,
        "created_at": str, "updated_at": str,
    }.items():
        _put(result, key, source.get(key), kind)
    extra = _extra(source, set(result) | {"id", "name", "type", "email", "phone", "address", "city", "state", "country", "zip", "notes", "created_at", "updated_at"})
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_file(raw: object, parent_type: str, parent_id: int) -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {"parent_type": parent_type, "parent_id": parent_id}
    _put(result, "file_id", source.get("id") or source.get("file_id"), int)
    _put(result, "filename", source.get("filename") or source.get("name") or source.get("file"), str)
    _put(result, "size", source.get("size") or source.get("filesize"), int)
    _put(result, "mime_type", source.get("mime_type") or source.get("mimetype"), str)
    _put(result, "notes", source.get("notes") or source.get("note"), str)
    _put(result, "created_at", source.get("created_at"), str)
    extra = _extra(source, {"id", "file_id", "filename", "name", "file", "size", "filesize", "mime_type", "mimetype", "notes", "note", "created_at"})
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_activity(raw: object) -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {}
    for key, kind in {"id": int, "action_type": str, "item_type": str, "item_id": int, "item_name": str, "user_id": int, "user_name": str, "target_id": int, "target_name": str, "note": str, "created_at": str}.items():
        _put(result, key, source.get(key), kind)
    for source_key, prefix in (("item", "item"), ("user", "user"), ("target", "target")):
        relation = _dict(source.get(source_key))
        _put(result, f"{prefix}_id", relation.get("id"), int)
        _put(result, f"{prefix}_name", relation.get("name"), str)
        if source_key == "item":
            _put(result, "item_type", relation.get("type"), str)
    extra = _extra(source, set(result) | {"item", "user", "target"})
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_custom_field(raw: object, resource_type: str = "field") -> dict[str, object]:
    source = _dict(raw)
    result: dict[str, object] = {"resource_type": resource_type}
    mapping = {
        "id": int, "name": str, "db_column": str, "element": str,
        "field_values": str, "field_encrypted": bool, "show_in_email": bool,
        "help_text": str, "created_at": str, "updated_at": str,
    }
    for key, kind in mapping.items():
        _put(result, key, source.get(key), kind)
    _put(result, "field_format", source.get("field_format") or source.get("format"), str)
    fieldset = _dict(source.get("fieldset"))
    _put(result, "fieldset_id", fieldset.get("id") or source.get("fieldset_id"), int)
    _put(result, "fieldset_name", fieldset.get("name"), str)
    extra = _extra(source, set(mapping) | {"field_format", "format", "fieldset", "fieldset_id"})
    if extra:
        result["extra_fields"] = extra
    return result


def normalize_report(raw: object) -> dict[str, object]:
    """Combine explicit asset and activity fields for mixed report endpoints."""
    result = normalize_asset(raw)
    activity = normalize_activity(raw)
    asset_extra = result.pop("extra_fields", [])
    activity_extra = activity.pop("extra_fields", [])
    result.update(activity)
    merged: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for entry in [*asset_extra, *activity_extra]:
        key = (entry["name"], entry["value"])
        if key not in seen:
            merged.append(entry)
            seen.add(key)
    if merged:
        result["extra_fields"] = merged[:100]
    return result


Normalizer = Callable[[object], dict[str, object]]
