"""Sleep timer entity for Fanimation BLE integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FanimationConfigEntry
from .const import TIMER_MAX, TIMER_MIN
from .entity import FanimationEntity

if TYPE_CHECKING:
    from .coordinator import FanimationCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FanimationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the timer entity."""
    coordinator = entry.runtime_data
    async_add_entities([FanimationTimer(coordinator, entry.entry_id)])


class FanimationTimer(FanimationEntity, NumberEntity):
    """Fanimation sleep timer entity."""

    _attr_icon = "mdi:timer-outline"
    _attr_mode = NumberMode.SLIDER
    _attr_native_min_value = TIMER_MIN
    _attr_native_max_value = TIMER_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_translation_key = "sleep_timer"

    def __init__(
        self,
        coordinator: FanimationCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the timer entity."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{coordinator.device.mac}_timer"

    @property
    def native_value(self) -> float | None:
        """Return current timer value in minutes."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.timer_minutes

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        return {
            "timer_note": "Timer turns off BOTH fan and light when it expires. Set to 0 to cancel.",
            "rf_remote_sync": "State is verified before every command — RF remote changes are always respected",
        }

    async def async_set_native_value(self, value: float) -> None:
        """Set the sleep timer."""
        await self.coordinator.device.async_set_state(timer_minutes=int(value))
        await self.coordinator.async_start_fast_poll()
