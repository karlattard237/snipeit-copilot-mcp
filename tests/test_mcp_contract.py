from __future__ import annotations

import inspect
from pathlib import Path

import pytest
from fastmcp import Client

from snipeit_copilot_mcp.schemas import ASSET_SCHEMA, USER_INVENTORY_OUTPUT
from snipeit_copilot_mcp.server import TOOL_NAMES, apply_allowlist, build_server, mcp


def walk(value: object):
    if isinstance(value, dict):
        yield from value.items()
        for nested in value.values():
            yield from walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from walk(nested)


@pytest.mark.asyncio
async def test_tool_registry_and_count() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert len(tools) == 29
    assert {tool.name for tool in tools} == set(TOOL_NAMES)


@pytest.mark.asyncio
async def test_all_schemas_are_copilot_safe() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    banned = {"$ref", "$defs", "definitions", "anyOf", "oneOf", "allOf"}
    for tool in tools:
        assert tool.outputSchema["type"] == "object"
        assert tool.description and len(tool.description) >= 80
        for schema in (tool.inputSchema, tool.outputSchema):
            for key, value in walk(schema):
                assert key not in banned, f"{tool.name}: {key}"
                if key == "type":
                    assert not isinstance(value, list), tool.name


@pytest.mark.asyncio
async def test_annotations_are_truthful() -> None:
    async with Client(mcp) as client:
        tools = {tool.name: tool for tool in await client.list_tools()}
    assert tools["assets_search"].annotations.readOnlyHint is True
    assert tools["user_inventory"].annotations.readOnlyHint is True
    assert tools["assets_write"].annotations.readOnlyHint is False
    assert tools["delete_resource"].annotations.destructiveHint is True
    assert tools["delete_resource"].annotations.readOnlyHint is False


def test_asset_schema_advertises_identity() -> None:
    properties = ASSET_SCHEMA["properties"]
    assert {"asset_tag", "serial", "model_name", "model_number"} <= properties.keys()


def test_user_inventory_schema_advertises_rich_assets() -> None:
    properties = USER_INVENTORY_OUTPUT["properties"]["assets"]["items"]["properties"]
    assert {"asset_tag", "serial", "model_name", "model_number"} <= properties.keys()


def test_delete_isolation_static() -> None:
    root = Path(__file__).parents[1] / "src" / "snipeit_copilot_mcp" / "tools"
    offenders = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if 'request_json("DELETE"' in text and path.name != "deletion.py":
            offenders.append(path.name)
        if path.name != "deletion.py":
            assert '"delete"},' not in text
            assert '"delete",' not in text
    assert offenders == []
    deletion_text = (root / "deletion.py").read_text(encoding="utf-8")
    assert 'request_json("DELETE"' in deletion_text


@pytest.mark.asyncio
async def test_only_delete_tool_mentions_destructive_removal() -> None:
    async with Client(mcp) as client:
        tools = await client.list_tools()
    assert "delete_resource" in {tool.name for tool in tools}
    for tool in tools:
        if tool.name != "delete_resource":
            assert "delete" not in tool.inputSchema.get("properties", {}).get("action_name", {}).get("enum", [])


def test_allowlist_rejects_unknown() -> None:
    server = build_server()
    with pytest.raises(Exception):
        apply_allowlist(server, ("not_a_tool",))


@pytest.mark.asyncio
async def test_allowlist_hides_non_selected() -> None:
    server = build_server()
    apply_allowlist(server, ("assets_search", "user_inventory"))
    async with Client(server) as client:
        names = {tool.name for tool in await client.list_tools()}
    assert names == {"assets_search", "user_inventory"}

