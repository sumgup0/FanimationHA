"""Fanimation BLE Ceiling Fan integration for Home Assistant."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOGGER, PLATFORMS
from .coordinator import FanimationCoordinator
from .device import FanimationDevice


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fanimation BLE from a config entry."""
    mac = entry.data[CONF_MAC]
    name = entry.data[CONF_NAME]

    LOGGER.info("Setting up Fanimation fan: %s (%s)", name, mac)

    # Create device and coordinator
    device = FanimationDevice(hass, mac, name)
    coordinator = FanimationCoordinator(hass, device)

    # First refresh — if it fails, raise ConfigEntryNotReady so HA
    # retries with exponential backoff instead of leaving entities
    # permanently unavailable.
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platform setup
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Forward setup to entity platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry.

    Must clean up all resources: cancel pending tasks, disconnect BLE.
    """
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: FanimationCoordinator = hass.data[DOMAIN].pop(entry.entry_id)

        # Cancel any pending direction-change tasks on the fan entity.
        # The fan entity stores the task reference, but the coordinator
        # also needs a shutdown hook so __init__.py can trigger cleanup
        # without reaching into entity internals.
        coordinator.async_shutdown()

        await coordinator.device.disconnect()
        LOGGER.info("Unloaded Fanimation fan: %s", entry.title)

    return unload_ok
