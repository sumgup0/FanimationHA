"""Light entity for Fanimation BLE integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ColorMode,
    LightEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DOWNLIGHT_MAX
from .coordinator import FanimationCoordinator
from .entity import FanimationEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light entity."""
    coordinator: FanimationCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([FanimationLight(coordinator, entry.entry_id)])


class FanimationLight(FanimationEntity, LightEntity):
    """Fanimation downlight entity."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_translation_key = "downlight"

    def __init__(
        self,
        coordinator: FanimationCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the light entity."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{coordinator.device.mac}_light"

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.downlight > 0

    @property
    def brightness(self) -> int | None:
        """Return brightness (HA 0-255 scale)."""
        if self.coordinator.data is None:
            return None
        # Scale fan 0-100 → HA 0-255
        return round(self.coordinator.data.downlight * 255 / DOWNLIGHT_MAX)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "rf_remote_sync": "State is verified before every command — RF remote changes are always respected",
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light."""
        if ATTR_BRIGHTNESS in kwargs:
            # Scale HA 0-255 → fan 0-100
            fan_brightness = round(kwargs[ATTR_BRIGHTNESS] * DOWNLIGHT_MAX / 255)
            fan_brightness = max(1, min(fan_brightness, DOWNLIGHT_MAX))
        else:
            # No brightness specified — use full brightness
            fan_brightness = DOWNLIGHT_MAX

        await self.coordinator.device.async_set_state(downlight=fan_brightness)
        await self.coordinator.async_start_fast_poll()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        await self.coordinator.device.async_set_state(downlight=0)
        await self.coordinator.async_start_fast_poll()
