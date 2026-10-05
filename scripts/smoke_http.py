#!/usr/bin/env python3
"""Exercise a running authenticated Streamable HTTP MCP endpoint."""

from __future__ import annotations

import asyncio
import os
import sys

from fastmcp import Client

from snipeit_copilot_mcp.server import TOOL_NAMES


def annotation_value(annotation: object, camel: str, snake: str) -> object:
    return getattr(annotation, camel, getattr(annotation, snake, None))


async def smoke() -> int:
    base_url = os.getenv("SNIPEIT_SMOKE_MCP_URL", "http://127.0.0.1:8765/mcp")
    token = os.getenv("SNIPEIT_MCP_TOKEN", "")
    if not token:
        print("SNIPEIT_MCP_TOKEN is required", file=sys.stderr)
        return 2

    unauthenticated_rejected = False
    try:
        async def anonymous_request() -> None:
            async with Client(base_url, timeout=5) as client:
                await client.list_tools()

        await asyncio.wait_for(anonymous_request(), timeout=10)
    except Exception:  # the exact HTTP/MCP exception is transport-version specific
        unauthenticated_rejected = True
    if not unauthenticated_rejected:
        print("Unauthenticated MCP request unexpectedly succeeded", file=sys.stderr)
        return 1

    async def authenticated_request() -> list[object]:
        async with Client(base_url, auth=token, timeout=10) as client:
            return list(await client.list_tools())

    tools = await asyncio.wait_for(authenticated_request(), timeout=20)
    names = {tool.name for tool in tools}
    if names != set(TOOL_NAMES):
        print(f"Unexpected tool inventory: {sorted(names ^ set(TOOL_NAMES))}", file=sys.stderr)
        return 1

    print(f"Authenticated Streamable HTTP smoke test PASSED ({len(tools)} tools)")
    print("tool\tread_only\tdestructive\tidempotent")
    for tool in sorted(tools, key=lambda item: item.name):
        annotations = tool.annotations
        print(
            f"{tool.name}\t"
            f"{annotation_value(annotations, 'readOnlyHint', 'read_only_hint')}\t"
            f"{annotation_value(annotations, 'destructiveHint', 'destructive_hint')}\t"
            f"{annotation_value(annotations, 'idempotentHint', 'idempotent_hint')}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(smoke()))
