"""Shared test fixtures for Fanimation BLE integration.

The device protocol tests are pure-logic unit tests that should run on ANY
platform (including Windows).  The heavy Home Assistant + Bluetooth import
chain only resolves on Linux, so we pre-seed ``sys.modules`` with lightweight
stubs **before** importing any integration code.  This lets ``_build_packet``,
``_parse_response``, and ``FanimationState`` load without pulling in the full
HA bluetooth stack.

Config-flow tests require the full ``pytest-homeassistant-custom-component``
harness (Linux CI only) and are skipped automatically on Windows.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub heavy HA / BLE modules that are Linux-only or pull massive dep trees.
# This MUST run before any import of custom_components.fanimation.
# ---------------------------------------------------------------------------

_STUB_MODULES = [
    "homeassistant.components.bluetooth",
    "homeassistant.components.usb",
    "bleak_retry_connector",
]

for _mod in _STUB_MODULES:
    sys.modules.setdefault(_mod, MagicMock())

# homeassistant.const has pure constants — ensure a real copy is used if
# it already loaded, but it usually resolves fine.
# homeassistant.core / homeassistant.config_entries are also lightweight.

# ---------------------------------------------------------------------------
# Now safe to import our integration modules
# ---------------------------------------------------------------------------

import pytest  # noqa: E402

from custom_components.fanimation.const import (  # noqa: E402
    CMD_STATUS_RESPONSE,
    START_BYTE,
)
from custom_components.fanimation.device import FanimationState  # noqa: E402

TEST_MAC = "50:8C:B1:4A:16:A0"
TEST_NAME = "Test Fan"


def build_response(
    speed: int = 0,
    direction: int = 0,
    uplight: int = 0,
    downlight: int = 0,
    timer_minutes: int = 0,
    fan_type: int = 0,
) -> bytearray:
    """Build a valid 10-byte status response with correct checksum."""
    timer_hi = (timer_minutes >> 8) & 0xFF
    timer_lo = timer_minutes & 0xFF
    data = bytearray(
        [
            START_BYTE,
            CMD_STATUS_RESPONSE,
            speed,
            direction,
            uplight,
            downlight,
            timer_hi,
            timer_lo,
            fan_type,
            0,
        ]
    )
    data[9] = sum(data[:9]) & 0xFF
    return data


@pytest.fixture
def mock_state() -> FanimationState:
    """Return a default FanimationState for testing."""
    return FanimationState(
        speed=1,
        direction=0,
        uplight=0,
        downlight=50,
        timer_minutes=120,
        fan_type=0,
    )
