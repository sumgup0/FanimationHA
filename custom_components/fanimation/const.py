"""Constants for the Fanimation BLE integration."""
from __future__ import annotations

import logging

from homeassistant.const import Platform

DOMAIN = "fanimation"
LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.FAN, Platform.LIGHT, Platform.NUMBER]

# Config entry keys
CONF_MAC = "mac"
CONF_NAME = "name"

# BLE Protocol — Fan Controller Service (0xE000)
CHAR_WRITE = "0000e001-0000-1000-8000-00805f9b34fb"
CHAR_NOTIFY = "0000e002-0000-1000-8000-00805f9b34fb"

# DANGER ZONE — TI OAD (Over-the-Air Download) firmware update service.
# Writing to these characteristics can BRICK the fan. They exist on the
# device but must NEVER be used by this integration. Listed here as an
# explicit exclusion so no one accidentally adds them.
# OAD_SERVICE  = "539c6813-0ad0-2137-4f79-bf1a11984790"  # DO NOT USE
# OAD_IDENTIFY = "539c6813-0ad1-2137-4f79-bf1a11984790"  # DO NOT USE
# OAD_BLOCK    = "539c6813-0ad2-2137-4f79-bf1a11984790"  # DO NOT USE

START_BYTE = 0x53
CMD_GET_STATUS = 0x30
CMD_SET_STATE = 0x31
CMD_STATUS_RESPONSE = 0x32

# Fan speed mapping (AC motor: 3 speeds only)
SPEED_OFF = 0
SPEED_LOW = 1
SPEED_MED = 2
SPEED_HIGH = 3
SPEED_COUNT = 3

# Downlight
DOWNLIGHT_MIN = 0
DOWNLIGHT_MAX = 100

# Timer
TIMER_MIN = 0
TIMER_MAX = 360  # 6 hours in minutes

# Polling intervals (seconds)
POLL_SLOW = 300
POLL_FAST = 1
POLL_FAST_CYCLES = 3

# Connection
MAX_CONNECTION_FAILURES = 3
