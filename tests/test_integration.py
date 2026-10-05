from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_integration_mode_is_explicit() -> None:
    if os.getenv("SNIPEIT_INTEGRATION_TESTS", "").lower() != "true":
        pytest.skip("Set SNIPEIT_INTEGRATION_TESTS=true for a separate test instance")
    assert os.getenv("SNIPEIT_INTEGRATION_URL")
    assert os.getenv("SNIPEIT_INTEGRATION_TOKEN")


@pytest.mark.destructive
def test_destructive_integration_requires_second_opt_in() -> None:
    if os.getenv("SNIPEIT_INTEGRATION_ALLOW_DESTRUCTIVE", "").lower() != "true":
        pytest.skip("Destructive integration tests require explicit second opt-in")
    assert os.getenv("SNIPEIT_INTEGRATION_TESTS", "").lower() == "true"

