from __future__ import annotations

import base64
import json

import httpx
import pytest
import respx

from snipeit_copilot_mcp.tools.admin import ldap_operations, system_read
from snipeit_copilot_mcp.tools.assets import asset_lifecycle, assets_search, assets_write
from snipeit_copilot_mcp.tools.catalog import catalog_search
from snipeit_copilot_mcp.tools.custom_fields import custom_fields_write
from snipeit_copilot_mcp.tools.deletion import delete_resource
from snipeit_copilot_mcp.tools.files import files_read, files_upload
from snipeit_copilot_mcp.tools.imports import imports
from snipeit_copilot_mcp.tools.inventory import inventory_lifecycle, inventory_search
from snipeit_copilot_mcp.tools.licenses import licenses_write
from snipeit_copilot_mcp.tools.organization import organization_search
from snipeit_copilot_mcp.tools.reports import reports
from snipeit_copilot_mcp.tools.users import user_inventory, users_search, users_write


RICH_ASSET = {
    "id": 10,
    "name": "John laptop",
    "asset_tag": "LAP-104",
    "serial": "ABC123",
    "model": {"id": 5, "name": "Dell Latitude 7440", "model_number": "7440", "manufacturer": {"id": 2, "name": "Dell"}},
    "status_label": {"id": 1, "name": "Ready"},
    "location": {"id": 4, "name": "HQ"},
}


@pytest.mark.asyncio
async def test_assets_exact_tag_runtime_contract() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware/bytag/LAP-104").mock(return_value=httpx.Response(200, json=RICH_ASSET))
        result = await assets_search("by_tag", asset_tag="LAP-104")
    item = result["items"][0]
    assert result["success"] is True
    assert item["asset_tag"] == "LAP-104"
    assert item["serial"] == "ABC123"
    assert item["model_name"] == "Dell Latitude 7440"
    assert item["model_number"] == "7440"


@pytest.mark.asyncio
async def test_assets_by_serial() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware/byserial/ABC123").mock(return_value=httpx.Response(200, json={"rows": [RICH_ASSET], "total": 1}))
        result = await assets_search("by_serial", serial="ABC123")
    assert result["items"][0]["asset_tag"] == "LAP-104"


@pytest.mark.asyncio
async def test_requestable_assets_use_account_catalog() -> None:
    with respx.mock as router:
        route = router.get("https://snipe.example/api/v1/account/requestable/hardware").mock(
            return_value=httpx.Response(200, json={"rows": [RICH_ASSET], "total": 1})
        )
        result = await assets_search("requestable")
    assert route.call_count == 1
    assert result["items"][0]["asset_tag"] == "LAP-104"


@pytest.mark.asyncio
async def test_asset_custom_field_name_resolves_to_db_column() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/fields").mock(return_value=httpx.Response(200, json={"rows": [{"id": 1, "name": "CPU", "db_column": "_snipeit_cpu_4"}], "total": 1}))
        hardware = router.get("https://snipe.example/api/v1/hardware").mock(return_value=httpx.Response(200, json={"rows": [], "total": 0}))
        result = await assets_search("search", custom_field_name="CPU", custom_field_value="i7")
    assert result["success"] is True
    assert json.loads(hardware.calls[0].request.url.params["filter"]) == {"_snipeit_cpu_4": "i7"}


@pytest.mark.asyncio
async def test_asset_write_has_no_delete_action() -> None:
    result = await assets_write("delete", asset_id=1)
    assert result["success"] is False
    assert result["error_code"] == "validation_failed"


@pytest.mark.asyncio
async def test_asset_create_and_update() -> None:
    with respx.mock as router:
        router.post("https://snipe.example/api/v1/hardware").mock(return_value=httpx.Response(200, json={"payload": RICH_ASSET, "status": "success"}))
        router.patch("https://snipe.example/api/v1/hardware/10").mock(return_value=httpx.Response(200, json={"payload": RICH_ASSET, "status": "success"}))
        created = await assets_write("create", asset_tag="LAP-104", model_id=5, status_id=1)
        updated = await assets_write("update", asset_id=10, notes="Checked")
    assert created["success"] and updated["success"]


@pytest.mark.asyncio
async def test_asset_checkout_resolves_tag_and_user_email() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware/bytag/LAP-104").mock(return_value=httpx.Response(200, json=RICH_ASSET))
        router.get("https://snipe.example/api/v1/users").mock(return_value=httpx.Response(200, json={"rows": [{"id": 7, "email": "john@example.com"}], "total": 1}))
        checkout = router.post("https://snipe.example/api/v1/hardware/10/checkout").mock(return_value=httpx.Response(200, json={"status": "success", "payload": RICH_ASSET}))
        result = await asset_lifecycle("checkout", asset_tag="LAP-104", user_email="john@example.com")
    assert result["success"] is True
    assert json.loads(checkout.calls[0].request.content)["assigned_to"] == 7


@pytest.mark.asyncio
async def test_user_inventory_critical_regression() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/users/7").mock(return_value=httpx.Response(200, json={"id": 7, "first_name": "John", "email": "john@example.com"}))
        router.get("https://snipe.example/api/v1/users/7/assets").mock(return_value=httpx.Response(200, json={"rows": [RICH_ASSET]}))
        router.get("https://snipe.example/api/v1/users/7/accessories").mock(return_value=httpx.Response(200, json={"rows": [{"id": 2, "name": "Dock"}]}))
        router.get("https://snipe.example/api/v1/users/7/licenses").mock(return_value=httpx.Response(200, json={"rows": [{"id": 3, "name": "Office", "product_key": "KEY"}]}))
        router.get("https://snipe.example/api/v1/users/7/consumables").mock(return_value=httpx.Response(200, json={"rows": [{"id": 4, "name": "Toner"}]}))
        router.get("https://snipe.example/api/v1/users/7/eulas").mock(return_value=httpx.Response(200, json={"rows": [{"id": 5, "name": "Accept policy"}]}))
        result = await user_inventory(user_id=7)
    item = result["assets"][0]
    assert result["success"] is True
    assert item["asset_tag"] == "LAP-104"
    assert item["serial"] == "ABC123"
    assert item["model_name"] == "Dell Latitude 7440"
    assert item["model_number"] == "7440"
    assert result["accessories_count"] == 1
    assert result["licences_count"] == 1
    assert result["consumables_count"] == 1
    assert result["eulas_count"] == 1


@pytest.mark.asyncio
async def test_users_exact_email() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/users").mock(return_value=httpx.Response(200, json={"rows": [{"id": 7, "email": "john@example.com"}, {"id": 8, "email": "other@example.com"}], "total": 2}))
        result = await users_search("by_email", email="john@example.com")
    assert result["count"] == 1
    assert result["items"][0]["id"] == 7


@pytest.mark.asyncio
async def test_two_factor_requires_explicit_action() -> None:
    with respx.mock as router:
        update = router.patch("https://snipe.example/api/v1/users/7").mock(return_value=httpx.Response(200, json={"status": "success", "payload": {"id": 7, "jobtitle": "Engineer"}}))
        result = await users_write("update", user_id=7, jobtitle="Engineer")
    assert result["success"] is True
    assert update.call_count == 1  # it did not silently call the 2FA endpoint


@pytest.mark.asyncio
async def test_inventory_assignment_relationship() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/components/2/assets").mock(return_value=httpx.Response(200, json={"rows": [RICH_ASSET], "total": 1}))
        result = await inventory_search("component", "assignments", item_id=2)
    assert result["success"] is True
    assert result["items"][0]["asset_tag"] == "LAP-104"


@pytest.mark.asyncio
async def test_inventory_component_checkout_restricts_target() -> None:
    result = await inventory_lifecycle("component", "checkout", 2, assigned_to_id=7, checkout_to_type="user")
    assert result["success"] is False
    assert "assets" in result["message"]


@pytest.mark.asyncio
async def test_license_write_translates_product_key_to_serial() -> None:
    with respx.mock as router:
        route = router.post("https://snipe.example/api/v1/licenses").mock(return_value=httpx.Response(200, json={"status": "success", "payload": {"id": 2, "name": "App", "product_key": "SECRET"}}))
        result = await licenses_write("create", name="App", product_key="SECRET", seats=3, category_id=1)
    sent = json.loads(route.calls[0].request.content)
    assert sent["serial"] == "SECRET"
    assert "product_key" not in sent
    assert result["item"]["product_key"] == "SECRET"


@pytest.mark.asyncio
async def test_file_upload_is_multipart() -> None:
    with respx.mock as router:
        route = router.post("https://snipe.example/api/v1/hardware/10/files").mock(return_value=httpx.Response(200, json={"status": "success", "payload": {"id": 4, "filename": "note.txt"}}))
        result = await files_upload("hardware", 10, "note.txt", base64.b64encode(b"hello").decode(), "text/plain")
    assert result["success"] is True
    assert route.calls[0].request.headers["content-type"].startswith("multipart/form-data")


@pytest.mark.asyncio
async def test_file_download_large_content_is_not_embedded() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware/10/files/4").mock(return_value=httpx.Response(200, content=b"12345", headers={"content-type": "application/octet-stream"}))
        result = await files_read("download", "hardware", 10, file_id=4, max_inline_bytes=4)
    assert result["items"][0]["content_truncated"] is True
    assert "content_base64" not in result["items"][0]


@pytest.mark.asyncio
async def test_import_upload_does_not_process() -> None:
    with respx.mock as router:
        upload = router.post("https://snipe.example/api/v1/imports").mock(return_value=httpx.Response(200, json={"status": "success", "payload": {"id": 9, "name": "assets.csv"}}))
        result = await imports("upload", filename="assets.csv", content_base64=base64.b64encode(b"asset_tag\nLAP-1").decode())
    assert result["success"] is True
    assert upload.call_count == 1
    assert "not processed" in result["message"]


@pytest.mark.asyncio
async def test_ldap_test_does_not_sync() -> None:
    with respx.mock as router:
        test_route = router.get("https://snipe.example/api/v1/settings/ldaptest").mock(return_value=httpx.Response(200, json={"status": "success"}))
        result = await ldap_operations("test")
    assert result["success"] is True
    assert test_route.call_count == 1


@pytest.mark.asyncio
async def test_delete_resource_record_and_file() -> None:
    with respx.mock as router:
        record = router.delete("https://snipe.example/api/v1/hardware/10").mock(return_value=httpx.Response(200, json={"status": "success"}))
        attachment = router.delete("https://snipe.example/api/v1/licenses/2/files/3/delete").mock(return_value=httpx.Response(200, json={"status": "success"}))
        first = await delete_resource("asset", resource_id=10)
        second = await delete_resource("licence_file", parent_id=2, file_id=3)
    assert first["success"] and second["success"]
    assert record.call_count == attachment.call_count == 1


@pytest.mark.asyncio
async def test_delete_rejects_unknown_resource() -> None:
    result = await delete_resource("arbitrary_endpoint", resource_id=1)
    assert result["success"] is False


@pytest.mark.asyncio
async def test_representative_read_domains() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/companies").mock(return_value=httpx.Response(200, json={"rows": [{"id": 1, "name": "Contoso"}], "total": 1}))
        router.get("https://snipe.example/api/v1/models").mock(return_value=httpx.Response(200, json={"rows": [{"id": 2, "name": "Latitude"}], "total": 1}))
        router.get("https://snipe.example/api/v1/reports/activity").mock(return_value=httpx.Response(200, json={"rows": [{"id": 3, "action_type": "checkout"}], "total": 1}))
        router.get("https://snipe.example/api/v1/version").mock(return_value=httpx.Response(200, json={"version": "8.6.2", "full_version": "v8.6.2"}))
        org = await organization_search("company")
        cat = await catalog_search("model")
        rep = await reports("activity")
        sys = await system_read("version")
    assert org["success"] and cat["success"] and rep["success"] and sys["success"]


@pytest.mark.asyncio
async def test_catalog_relationships_preserve_domain_fields() -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware").mock(
            return_value=httpx.Response(200, json={"rows": [RICH_ASSET], "total": 1})
        )
        router.get("https://snipe.example/api/v1/users").mock(
            return_value=httpx.Response(200, json={"rows": [{"id": 7, "email": "john@example.com", "username": "john"}], "total": 1})
        )
        assets = await catalog_search("location", "assets_at_location", item_id=4)
        people = await catalog_search("location", "users_at_location", item_id=4)
    assert assets["items"][0]["asset_tag"] == "LAP-104"
    assert people["items"][0]["email"] == "john@example.com"


@pytest.mark.asyncio
async def test_custom_field_association_uses_current_route() -> None:
    with respx.mock as router:
        route = router.post("https://snipe.example/api/v1/fields/1/associate").mock(return_value=httpx.Response(200, json={"status": "success"}))
        result = await custom_fields_write("associate", field_id=1, fieldset_id=2, required=True)
    assert result["success"] is True
    assert json.loads(route.calls[0].request.content)["fieldset_id"] == 2
