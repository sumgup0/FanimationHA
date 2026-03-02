"""Fanimation BLE Ceiling Fan integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import LOGGER, PLATFORMS
from .coordinator import FanimationCoordinator
from .device import FanimationDevice

type FanimationConfigEntry = ConfigEntry[FanimationCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: FanimationConfigEntry) -> bool:
    """Set up Fanimation BLE from a config entry."""
    mac = entry.data[CONF_MAC]
    name = entry.data[CONF_NAME]

    LOGGER.info("Setting up Fanimation fan: %s (%s)", name, mac)

    # Create device and coordinator
    device = FanimationDevice(hass, mac, name)
    coordinator = FanimationCoordinator(hass, device, entry)

    # First refresh — if it fails, raise ConfigEntryNotReady so HA
    # retries with exponential backoff instead of leaving entities
    # permanently unavailable.
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator on the config entry for platform access
    entry.runtime_data = coordinator

    # Forward setup to entity platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: FanimationConfigEntry) -> bool:
    """Unload a config entry.

    Must clean up all resources: cancel pending tasks, disconnect BLE.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = entry.runtime_data
        await coordinator.device.disconnect()
        LOGGER.info("Unloaded Fanimation fan: %s", entry.title)

    return unload_ok
