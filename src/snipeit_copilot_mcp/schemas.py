"""Inline JSON Schemas deliberately limited to Copilot Studio-safe constructs."""

from __future__ import annotations

from copy import deepcopy


def _string(description: str = "") -> dict[str, object]:
    value: dict[str, object] = {"type": "string"}
    if description:
        value["description"] = description
    return value


def _integer(description: str = "") -> dict[str, object]:
    value: dict[str, object] = {"type": "integer"}
    if description:
        value["description"] = description
    return value


def _number(description: str = "") -> dict[str, object]:
    value: dict[str, object] = {"type": "number"}
    if description:
        value["description"] = description
    return value


def _boolean(description: str = "") -> dict[str, object]:
    value: dict[str, object] = {"type": "boolean"}
    if description:
        value["description"] = description
    return value


EXTRA_FIELD_SCHEMA = {
    "type": "object",
    "properties": {"name": _string(), "value": _string()},
    "required": ["name", "value"],
    "additionalProperties": False,
}

CUSTOM_FIELD_SCHEMA = {
    "type": "object",
    "properties": {
        "name": _string("Human-readable custom-field name"),
        "db_column": _string("Snipe-IT database column identifier"),
        "value": _string("Display-safe string value"),
        "field_format": _string("Configured validation format"),
    },
    "required": ["name", "db_column", "value"],
    "additionalProperties": False,
}


def object_schema(properties: dict[str, object], required: list[str] | None = None) -> dict[str, object]:
    schema: dict[str, object] = {
        "type": "object",
        "properties": deepcopy(properties),
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


ASSET_SCHEMA = object_schema(
    {
        "id": _integer(),
        "name": _string(),
        "asset_tag": _string(),
        "serial": _string(),
        "model_id": _integer(),
        "model_name": _string(),
        "model_number": _string(),
        "manufacturer_id": _integer(),
        "manufacturer_name": _string(),
        "category_id": _integer(),
        "category_name": _string(),
        "status_id": _integer(),
        "status_name": _string(),
        "status_type": _string(),
        "assigned_to_id": _integer(),
        "assigned_to_name": _string(),
        "assigned_to_type": _string(),
        "assigned_to_email": _string(),
        "location_id": _integer(),
        "location_name": _string(),
        "default_location_id": _integer(),
        "default_location_name": _string(),
        "company_id": _integer(),
        "company_name": _string(),
        "order_number": _string(),
        "purchase_date": _string(),
        "purchase_cost": _number(),
        "supplier_id": _integer(),
        "supplier_name": _string(),
        "warranty_months": _integer(),
        "warranty_expires": _string(),
        "notes": _string(),
        "last_checkout": _string(),
        "expected_checkin": _string(),
        "next_audit_date": _string(),
        "last_audit_date": _string(),
        "requestable": _boolean(),
        "archived": _boolean(),
        "created_at": _string(),
        "updated_at": _string(),
        "custom_fields": {"type": "array", "items": deepcopy(CUSTOM_FIELD_SCHEMA)},
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

USER_SCHEMA = object_schema(
    {
        "id": _integer(),
        "first_name": _string(),
        "last_name": _string(),
        "name": _string(),
        "username": _string(),
        "email": _string(),
        "employee_num": _string(),
        "jobtitle": _string(),
        "phone": _string(),
        "department_id": _integer(),
        "department_name": _string(),
        "location_id": _integer(),
        "location_name": _string(),
        "company_id": _integer(),
        "company_name": _string(),
        "manager_id": _integer(),
        "manager_name": _string(),
        "remote": _boolean(),
        "vip": _boolean(),
        "activated": _boolean(),
        "deleted": _boolean(),
        "assets_count": _integer(),
        "accessories_count": _integer(),
        "licences_count": _integer(),
        "consumables_count": _integer(),
        "created_at": _string(),
        "updated_at": _string(),
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

# Catalog reads can return either reference records, rich assets, or users from
# relationship actions. Keep every useful field visible in one inline schema.
CATALOG_SCHEMA = object_schema(
    {
        **deepcopy(ASSET_SCHEMA["properties"]),
        **deepcopy(USER_SCHEMA["properties"]),
    }
)

LICENSE_SCHEMA = object_schema(
    {
        "id": _integer(),
        "name": _string(),
        "product_key": _string(),
        "seats": _integer(),
        "free_seats": _integer(),
        "category_id": _integer(),
        "category_name": _string(),
        "manufacturer_id": _integer(),
        "manufacturer_name": _string(),
        "supplier_id": _integer(),
        "supplier_name": _string(),
        "company_id": _integer(),
        "company_name": _string(),
        "order_number": _string(),
        "purchase_date": _string(),
        "purchase_cost": _number(),
        "expiration_date": _string(),
        "termination_date": _string(),
        "maintained": _boolean(),
        "reassignable": _boolean(),
        "notes": _string(),
        "created_at": _string(),
        "updated_at": _string(),
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

INVENTORY_SCHEMA = object_schema(
    {
        "id": _integer(),
        "inventory_type": _string(),
        "name": _string(),
        "asset_tag": _string(),
        "model_number": _string(),
        "serial": _string(),
        "qty": _integer(),
        "remaining_qty": _integer(),
        "min_amt": _integer(),
        "category_id": _integer(),
        "category_name": _string(),
        "manufacturer_id": _integer(),
        "manufacturer_name": _string(),
        "location_id": _integer(),
        "location_name": _string(),
        "company_id": _integer(),
        "company_name": _string(),
        "supplier_id": _integer(),
        "supplier_name": _string(),
        "assigned_to_id": _integer(),
        "assigned_to_name": _string(),
        "assigned_to_type": _string(),
        "order_number": _string(),
        "purchase_date": _string(),
        "purchase_cost": _number(),
        "notes": _string(),
        "created_at": _string(),
        "updated_at": _string(),
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

GENERIC_ITEM_SCHEMA = object_schema(
    {
        "id": _integer(),
        "resource_type": _string(),
        "name": _string(),
        "type": _string(),
        "email": _string(),
        "phone": _string(),
        "address": _string(),
        "city": _string(),
        "state": _string(),
        "country": _string(),
        "zip": _string(),
        "notes": _string(),
        "created_at": _string(),
        "updated_at": _string(),
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

FILE_SCHEMA = object_schema(
    {
        "file_id": _integer(),
        "filename": _string(),
        "size": _integer(),
        "mime_type": _string(),
        "notes": _string(),
        "created_at": _string(),
        "parent_type": _string(),
        "parent_id": _integer(),
        "content_base64": _string("Present only for an explicitly requested bounded download"),
        "content_truncated": _boolean(),
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

ACTIVITY_SCHEMA = object_schema(
    {
        "id": _integer(),
        "action_type": _string(),
        "item_type": _string(),
        "item_id": _integer(),
        "item_name": _string(),
        "user_id": _integer(),
        "user_name": _string(),
        "target_id": _integer(),
        "target_name": _string(),
        "note": _string(),
        "created_at": _string(),
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

CUSTOM_FIELD_DEFINITION_SCHEMA = object_schema(
    {
        "id": _integer(),
        "resource_type": _string(),
        "name": _string(),
        "db_column": _string(),
        "element": _string(),
        "field_format": _string(),
        "field_values": _string(),
        "field_encrypted": _boolean(),
        "show_in_email": _boolean(),
        "help_text": _string(),
        "fieldset_id": _integer(),
        "fieldset_name": _string(),
        "created_at": _string(),
        "updated_at": _string(),
        "extra_fields": {"type": "array", "items": deepcopy(EXTRA_FIELD_SCHEMA)},
    }
)

REPORT_SCHEMA = object_schema(
    {
        **deepcopy(ASSET_SCHEMA["properties"]),
        **deepcopy(ACTIVITY_SCHEMA["properties"]),
    }
)

VALIDATION_ENTRY_SCHEMA = object_schema({"field": _string(), "message": _string()}, ["field", "message"])


def _base_properties() -> dict[str, object]:
    return {
        "success": _boolean(),
        "message": _string(),
        "error_code": _string(),
        "validation_errors": {"type": "array", "items": deepcopy(VALIDATION_ENTRY_SCHEMA)},
    }


def single_schema(item: dict[str, object]) -> dict[str, object]:
    props = _base_properties()
    props["item"] = deepcopy(item)
    return object_schema(props, ["success"])


def list_schema(item: dict[str, object]) -> dict[str, object]:
    props = _base_properties()
    props.update(
        {
            "items": {"type": "array", "items": deepcopy(item)},
            "count": _integer(),
            "total": _integer(),
            "limit": _integer(),
            "offset": _integer(),
            "page": _integer(),
            "per_page": _integer(),
            "current_page": _integer(),
            "total_pages": _integer(),
            "has_more": _boolean(),
        }
    )
    return object_schema(props, ["success"])


ASSET_SINGLE_OUTPUT = single_schema(ASSET_SCHEMA)
ASSET_LIST_OUTPUT = list_schema(ASSET_SCHEMA)
CATALOG_LIST_OUTPUT = list_schema(CATALOG_SCHEMA)
USER_SINGLE_OUTPUT = single_schema(USER_SCHEMA)
USER_LIST_OUTPUT = list_schema(USER_SCHEMA)
LICENSE_SINGLE_OUTPUT = single_schema(LICENSE_SCHEMA)
LICENSE_LIST_OUTPUT = list_schema(LICENSE_SCHEMA)
INVENTORY_SINGLE_OUTPUT = single_schema(INVENTORY_SCHEMA)
INVENTORY_LIST_OUTPUT = list_schema(INVENTORY_SCHEMA)
GENERIC_SINGLE_OUTPUT = single_schema(GENERIC_ITEM_SCHEMA)
GENERIC_LIST_OUTPUT = list_schema(GENERIC_ITEM_SCHEMA)
FILE_SINGLE_OUTPUT = single_schema(FILE_SCHEMA)
FILE_LIST_OUTPUT = list_schema(FILE_SCHEMA)
ACTIVITY_LIST_OUTPUT = list_schema(ACTIVITY_SCHEMA)
CUSTOM_FIELD_SINGLE_OUTPUT = single_schema(CUSTOM_FIELD_DEFINITION_SCHEMA)
CUSTOM_FIELD_LIST_OUTPUT = list_schema(CUSTOM_FIELD_DEFINITION_SCHEMA)
REPORT_LIST_OUTPUT = list_schema(REPORT_SCHEMA)

USER_INVENTORY_OUTPUT = object_schema(
    {
        **_base_properties(),
        "user": deepcopy(USER_SCHEMA),
        "assets": {"type": "array", "items": deepcopy(ASSET_SCHEMA)},
        "accessories": {"type": "array", "items": deepcopy(INVENTORY_SCHEMA)},
        "licences": {"type": "array", "items": deepcopy(LICENSE_SCHEMA)},
        "consumables": {"type": "array", "items": deepcopy(INVENTORY_SCHEMA)},
        "eulas": {"type": "array", "items": deepcopy(GENERIC_ITEM_SCHEMA)},
        "assets_count": _integer(),
        "accessories_count": _integer(),
        "licences_count": _integer(),
        "consumables_count": _integer(),
        "eulas_count": _integer(),
    },
    ["success"],
)

SYSTEM_OUTPUT = object_schema(
    {
        **_base_properties(),
        "version": _string(),
        "build_version": _string(),
        "hash_version": _string(),
        "full_version": _string(),
        "items": {"type": "array", "items": deepcopy(GENERIC_ITEM_SCHEMA)},
        "count": _integer(),
        "item": deepcopy(FILE_SCHEMA),
    },
    ["success"],
)
