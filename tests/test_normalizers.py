from __future__ import annotations

from snipeit_copilot_mcp.normalizers import normalize_asset, normalize_custom_field, normalize_inventory, normalize_license, normalize_user


def test_asset_exposes_full_identity() -> None:
    item = normalize_asset(
        {
            "id": 10,
            "name": "John laptop",
            "asset_tag": "LAP-104",
            "serial": "ABC123",
            "model": {"id": 5, "name": "Dell Latitude 7440", "model_number": "7440", "manufacturer": {"id": 2, "name": "Dell"}},
            "status_label": {"id": 1, "name": "Ready", "status_type": "deployable"},
            "assigned_to": {"id": 8, "name": "John", "email": "john@example.com", "type": "user", "location": {"id": 4, "name": "HQ"}},
            "custom_fields": {"CPU": {"db_column": "_snipeit_cpu_4", "value": "i7", "field_format": "ANY"}},
        }
    )
    assert item["asset_tag"] == "LAP-104"
    assert item["serial"] == "ABC123"
    assert item["model_name"] == "Dell Latitude 7440"
    assert item["model_number"] == "7440"
    assert item["manufacturer_name"] == "Dell"
    assert item["assigned_to_email"] == "john@example.com"
    assert item["location_name"] == "HQ"
    assert item["custom_fields"][0]["db_column"] == "_snipeit_cpu_4"


def test_asset_tolerates_missing_nested_values() -> None:
    assert normalize_asset({"id": 1, "model": None, "assigned_to": None}) == {"id": 1}


def test_unknown_values_are_preserved_as_entries() -> None:
    item = normalize_asset({"id": 1, "future_field": {"enabled": True}})
    assert {"name": "future_field", "value": '{"enabled":true}'} in item["extra_fields"]


def test_user_normalization() -> None:
    user = normalize_user({"id": 7, "first_name": "Ada", "last_name": "Lovelace", "department": {"id": 2, "name": "IT"}, "vip": 1})
    assert user["name"] == "Ada Lovelace"
    assert user["department_name"] == "IT"
    assert user["vip"] is True


def test_inventory_normalization() -> None:
    item = normalize_inventory({"id": 3, "qty": "10", "remaining_qty": "4", "manufacturer": {"id": 1, "name": "HP"}}, "component")
    assert item["inventory_type"] == "component"
    assert item["qty"] == 10
    assert item["manufacturer_name"] == "HP"


def test_license_read_product_key() -> None:
    item = normalize_license({"id": 2, "product_key": "KEY", "seats": 5, "free_seats": 2})
    assert item["product_key"] == "KEY"
    assert item["free_seats"] == 2


def test_custom_field_definition() -> None:
    item = normalize_custom_field({"id": 1, "name": "CPU", "db_column": "_snipeit_cpu_4", "format": "ANY"})
    assert item["db_column"] == "_snipeit_cpu_4"
    assert item["field_format"] == "ANY"

