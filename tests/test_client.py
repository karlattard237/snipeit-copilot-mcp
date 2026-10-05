from __future__ import annotations

import httpx
import pytest
import respx

from snipeit_copilot_mcp.client import SnipeITClient, _validate_endpoint
from snipeit_copilot_mcp.errors import SnipeITError


@pytest.mark.asyncio
async def test_json_headers_and_auth(settings) -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://snipe.example/api/v1/hardware").mock(return_value=httpx.Response(200, json={"rows": [], "total": 0}))
        async with SnipeITClient(settings, "secret-token") as client:
            await client.request_json("GET", "hardware")
    request = route.calls[0].request
    assert request.headers["authorization"] == "Bearer secret-token"
    assert request.headers["accept"] == "application/json"
    assert request.headers["user-agent"] == "snipeit-copilot-mcp/1.0"


@pytest.mark.asyncio
async def test_json_content_type(settings) -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://snipe.example/api/v1/hardware").mock(return_value=httpx.Response(200, json={"status": "success"}))
        async with SnipeITClient(settings, "token") as client:
            await client.request_json("POST", "hardware", json_body={"name": "Laptop"})
    assert route.calls[0].request.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_multipart_does_not_force_json_content_type(settings) -> None:
    with respx.mock(assert_all_called=True) as router:
        route = router.post("https://snipe.example/api/v1/hardware/1/files").mock(return_value=httpx.Response(200, json={"status": "success"}))
        async with SnipeITClient(settings, "token") as client:
            await client.request_json("POST", "hardware/1/files", files={"file": ("a.txt", b"data", "text/plain")})
    content_type = route.calls[0].request.headers["content-type"]
    assert content_type.startswith("multipart/form-data; boundary=")


@pytest.mark.asyncio
async def test_http_200_error_payload_is_failure(settings) -> None:
    with respx.mock as router:
        router.post("https://snipe.example/api/v1/hardware").mock(return_value=httpx.Response(200, json={"status": "error", "messages": {"model_id": ["Invalid model"]}}))
        async with SnipeITClient(settings, "token") as client:
            with pytest.raises(SnipeITError) as raised:
                await client.request_json("POST", "hardware", json_body={})
    assert raised.value.code == "validation_failed"
    assert raised.value.validation_errors == [{"field": "model_id", "message": "Invalid model"}]


@pytest.mark.parametrize(
    ("status", "code"),
    [(401, "authentication_failed"), (403, "permission_denied"), (404, "not_found"), (409, "conflict"), (422, "validation_failed"), (429, "rate_limited"), (500, "upstream_error")],
)
@pytest.mark.asyncio
async def test_http_error_mapping(settings, status: int, code: str) -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware/1").mock(return_value=httpx.Response(status, json={"message": "failure"}))
        async with SnipeITClient(settings, "token") as client:
            with pytest.raises(SnipeITError) as raised:
                await client.request_json("GET", "hardware/1")
    assert raised.value.code == code


@pytest.mark.asyncio
async def test_malformed_json(settings) -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/version").mock(return_value=httpx.Response(200, text="{oops", headers={"content-type": "application/json"}))
        async with SnipeITClient(settings, "token") as client:
            with pytest.raises(SnipeITError) as raised:
                await client.request_json("GET", "version")
    assert raised.value.code == "invalid_response"


@pytest.mark.asyncio
async def test_html_response(settings) -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/version").mock(return_value=httpx.Response(200, text="<html>login</html>", headers={"content-type": "text/html"}))
        async with SnipeITClient(settings, "token") as client:
            with pytest.raises(SnipeITError) as raised:
                await client.request_json("GET", "version")
    assert "HTML" in raised.value.message


@pytest.mark.asyncio
async def test_timeout_maps_cleanly(settings) -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/version").mock(side_effect=httpx.ReadTimeout("secret URL detail"))
        async with SnipeITClient(settings, "token") as client:
            with pytest.raises(SnipeITError) as raised:
                await client.request_json("GET", "version")
    assert raised.value.code == "timeout"
    assert "secret" not in raised.value.message


@pytest.mark.asyncio
async def test_connection_failure_maps_cleanly(settings) -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/version").mock(side_effect=httpx.ConnectError("token=secret"))
        async with SnipeITClient(settings, "token") as client:
            with pytest.raises(SnipeITError) as raised:
                await client.request_json("GET", "version")
    assert raised.value.code == "connectivity_failure"


@pytest.mark.asyncio
async def test_safe_get_retries_once(settings) -> None:
    with respx.mock as router:
        route = router.get("https://snipe.example/api/v1/version").mock(side_effect=[httpx.ConnectError("down"), httpx.Response(200, json={"version": "8.6.2"})])
        async with SnipeITClient(settings, "token") as client:
            payload = await client.request_json("GET", "version")
    assert payload["version"] == "8.6.2"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_mutation_is_not_retried(settings) -> None:
    with respx.mock as router:
        route = router.post("https://snipe.example/api/v1/hardware").mock(side_effect=httpx.ConnectError("down"))
        async with SnipeITClient(settings, "token") as client:
            with pytest.raises(SnipeITError):
                await client.request_json("POST", "hardware", json_body={})
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_limit_offset_pagination(settings) -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware", params__contains={"limit": 2, "offset": 2}).mock(return_value=httpx.Response(200, json={"rows": [{"id": 3}], "total": 5}))
        async with SnipeITClient(settings, "token") as client:
            rows, meta = await client.list_page("hardware", limit=2, offset=2)
    assert rows == [{"id": 3}]
    assert meta == {"count": 1, "total": 5, "limit": 2, "offset": 2, "has_more": True}


@pytest.mark.asyncio
async def test_page_pagination(settings) -> None:
    with respx.mock as router:
        router.get("https://snipe.example/api/v1/hardware", params__contains={"page": 2, "per_page": 10}).mock(return_value=httpx.Response(200, json={"rows": [{"id": 11}], "total": 25, "current_page": 2, "last_page": 3}))
        async with SnipeITClient(settings, "token") as client:
            _, meta = await client.list_page("hardware", page=2, per_page=10)
    assert meta["current_page"] == 2
    assert meta["total_pages"] == 3
    assert meta["has_more"] is True


@pytest.mark.parametrize("path", ["https://evil.example/x", "/hardware", "hardware/../users", "hardware/%2fusers", "hardware?x=1", "unknown/1"])
def test_endpoint_allowlist_rejects_arbitrary_paths(path: str) -> None:
    with pytest.raises(SnipeITError):
        _validate_endpoint(path)

