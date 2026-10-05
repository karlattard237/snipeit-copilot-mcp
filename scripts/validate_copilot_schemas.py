#!/usr/bin/env python3
"""Fail on public MCP schemas known to be incompatible with Copilot Studio."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from fastmcp import Client

from snipeit_copilot_mcp.server import TOOL_NAMES, mcp

BANNED_KEYS = {"$ref", "$defs", "definitions", "anyOf", "oneOf", "allOf"}
REQUIRED_ASSET_FIELDS = {"asset_tag", "serial", "model_name", "model_number"}


def walk_schema(schema: object, path: str, errors: list[str]) -> None:
    if isinstance(schema, dict):
        for key, value in schema.items():
            current = f"{path}.{key}"
            if key in BANNED_KEYS:
                errors.append(f"{current}: banned schema construct")
            if key == "type" and isinstance(value, list):
                errors.append(f"{current}: type must contain exactly one JSON type, not an array")
            walk_schema(value, current, errors)
    elif isinstance(schema, list):
        for index, value in enumerate(schema):
            walk_schema(value, f"{path}[{index}]", errors)


def attribute(tool: Any, *names: str) -> Any:
    for name in names:
        value = getattr(tool, name, None)
        if value is not None:
            return value
    return None


def item_properties(schema: dict[str, Any], property_name: str) -> set[str]:
    properties = schema.get("properties", {})
    collection = properties.get(property_name, {})
    items = collection.get("items", {}) if isinstance(collection, dict) else {}
    return set(items.get("properties", {})) if isinstance(items, dict) else set()


async def validate() -> tuple[list[str], int]:
    errors: list[str] = []
    async with Client(mcp) as client:
        tools = await client.list_tools()
    if len(tools) > 30:
        errors.append(f"tool count is {len(tools)}; maximum is 30")
    names = {tool.name for tool in tools}
    if names != set(TOOL_NAMES):
        errors.append(f"registered tool names differ from the 29-tool contract: {sorted(names ^ set(TOOL_NAMES))}")
    by_name = {tool.name: tool for tool in tools}
    for tool in tools:
        description = attribute(tool, "description") or ""
        if len(description.strip()) < 80:
            errors.append(f"{tool.name}: description is missing or unhelpful")
        input_schema = attribute(tool, "inputSchema", "input_schema") or {}
        output_schema = attribute(tool, "outputSchema", "output_schema") or {}
        walk_schema(input_schema, f"{tool.name}.input", errors)
        walk_schema(output_schema, f"{tool.name}.output", errors)
        if output_schema.get("type") != "object":
            errors.append(f"{tool.name}: output schema root must be an object")
        if not output_schema.get("properties"):
            errors.append(f"{tool.name}: output schema has no useful properties")
        annotations = attribute(tool, "annotations")
        if annotations is None:
            errors.append(f"{tool.name}: annotations are missing")

    assets_schema = attribute(by_name["assets_search"], "outputSchema", "output_schema")
    missing = REQUIRED_ASSET_FIELDS - item_properties(assets_schema, "items")
    if missing:
        errors.append("assets_search: output items do not advertise " + ", ".join(sorted(missing)))
    inventory_schema = attribute(by_name["user_inventory"], "outputSchema", "output_schema")
    missing = REQUIRED_ASSET_FIELDS - item_properties(inventory_schema, "assets")
    if missing:
        errors.append("user_inventory: assets do not advertise " + ", ".join(sorted(missing)))
    return errors, len(tools)


def main() -> int:
    errors, count = asyncio.run(validate())
    if errors:
        print(f"Copilot schema validation FAILED ({len(errors)} findings, {count} tools)")
        for error in errors:
            print(f" - {error}")
        return 1
    print(f"Copilot schema validation PASSED ({count} tools)")
    print(" - $ref/$defs/definitions count: 0")
    print(" - anyOf/oneOf/allOf count: 0")
    print(" - multi-type type-array count: 0")
    print(" - assets_search identity fields: advertised")
    print(" - user_inventory asset identity fields: advertised")
    return 0


if __name__ == "__main__":
    sys.exit(main())

