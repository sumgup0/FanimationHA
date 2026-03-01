"""Fan entity for Fanimation BLE integration."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    ordered_list_item_to_percentage,
    percentage_to_ordered_list_item,
)

from . import FanimationConfigEntry
from .const import (
    DIRECTION_CHANGE_WAIT,
    DIR_FORWARD,
    DIR_REVERSE,
    LOGGER,
    SPEED_COUNT,
    SPEED_HIGH,
    SPEED_LOW,
    SPEED_MED,
    SPEED_OFF,
)
from .coordinator import FanimationCoordinator
from .entity import FanimationEntity

ORDERED_NAMED_FAN_SPEEDS = [SPEED_LOW, SPEED_MED, SPEED_HIGH]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FanimationConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the fan entity."""
    coordinator = entry.runtime_data
    async_add_entities([FanimationFan(coordinator, entry.entry_id)])


class FanimationFan(FanimationEntity, FanEntity):
    """Fanimation ceiling fan entity."""

    _attr_speed_count = SPEED_COUNT
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.DIRECTION
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )
    _attr_translation_key = "fan"

    def __init__(
        self,
        coordinator: FanimationCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the fan entity."""
        super().__init__(coordinator, entry_id)
        self._attr_unique_id = f"{coordinator.device.mac}_fan"
        self._last_speed = SPEED_LOW  # default for turn_on without speed
        self._direction_change_task: asyncio.Task | None = None
        self._direction_change_ends_at: datetime | None = None
        self._direction_change_target: str | None = None
        self._original_speed: int = 0

        # Register cleanup so unload cancels any pending direction change
        coordinator.register_shutdown_callback(self._cancel_direction_change)

    @property
    def is_on(self) -> bool | None:
        """Return True if the fan is on."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.speed > SPEED_OFF

    @property
    def percentage(self) -> int | None:
        """Return the current speed percentage."""
        if self.coordinator.data is None:
            return None
        speed = self.coordinator.data.speed
        if speed == SPEED_OFF:
            return 0
        return ordered_list_item_to_percentage(ORDERED_NAMED_FAN_SPEEDS, speed)

    @property
    def current_direction(self) -> str | None:
        """Return the current direction."""
        if self.coordinator.data is None:
            return None
        if self._direction_change_target is not None:
            # Show target direction during pending change
            return self._direction_change_target
        return "forward" if self.coordinator.data.direction == DIR_FORWARD else "reverse"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs: dict[str, Any] = {
            "direction_hint": "Summer=Forward (wind chill), Winter=Reverse (circulate warm air)",
            "rf_remote_sync": "State is verified before every command — RF remote changes are always respected",
            "direction_change_in_progress": self._direction_change_target is not None,
        }
        if self._direction_change_target is not None:
            attrs["direction_change_ends_at"] = (
                self._direction_change_ends_at.isoformat()
                if self._direction_change_ends_at
                else None
            )
            attrs["direction_change_target"] = self._direction_change_target
        return attrs

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn on the fan."""
        if percentage is not None:
            await self.async_set_percentage(percentage)
        else:
            await self._async_set_speed(self._last_speed)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the fan."""
        self._cancel_direction_change()
        await self._async_set_speed(SPEED_OFF)

    async def async_set_percentage(self, percentage: int) -> None:
        """Set fan speed by percentage."""
        self._cancel_direction_change()
        if percentage == 0:
            await self._async_set_speed(SPEED_OFF)
        else:
            speed = percentage_to_ordered_list_item(ORDERED_NAMED_FAN_SPEEDS, percentage)
            await self._async_set_speed(speed)

    async def async_set_direction(self, direction: str) -> None:
        """Set fan direction (with 60s motor stop wait if fan is on)."""
        new_dir = DIR_FORWARD if direction == "forward" else DIR_REVERSE

        # Cancel any pending direction change
        self._cancel_direction_change()

        if self.coordinator.data and self.coordinator.data.speed > SPEED_OFF:
            # Fan is on — need to stop and wait
            self._original_speed = self.coordinator.data.speed
            self._direction_change_target = direction
            self._direction_change_ends_at = datetime.now(timezone.utc).replace(
                microsecond=0
            ) + timedelta(seconds=DIRECTION_CHANGE_WAIT)

            # Stop the fan first
            await self.coordinator.device.async_set_state(speed=SPEED_OFF)
            await self.coordinator.async_start_fast_poll()
            self.async_write_ha_state()  # Publish "in_progress" state once

            # Start the wait task — single sleep, NOT a per-second loop
            self._direction_change_task = asyncio.create_task(
                self._direction_change_sequence(new_dir, self._original_speed)
            )
        else:
            # Fan is off — change direction immediately
            await self.coordinator.device.async_set_state(direction=new_dir)
            await self.coordinator.async_start_fast_poll()

    async def _direction_change_sequence(self, new_dir: int, restore_speed: int) -> None:
        """Wait for motor to stop, then apply direction change.

        Uses a single sleep instead of per-second countdown to avoid
        spamming the HA state machine / recorder with 60 state changes.
        """
        try:
            await asyncio.sleep(DIRECTION_CHANGE_WAIT)

            # Apply direction + restore speed
            await self.coordinator.device.async_set_state(
                speed=restore_speed, direction=new_dir
            )
            LOGGER.info(
                "Direction change complete for %s: %s at speed %d",
                self.coordinator.device.name,
                "forward" if new_dir == DIR_FORWARD else "reverse",
                restore_speed,
            )
        except asyncio.CancelledError:
            LOGGER.debug("Direction change cancelled for %s", self.coordinator.device.name)
            return
        finally:
            self._direction_change_target = None
            self._direction_change_ends_at = None
            self._direction_change_task = None
            self.async_write_ha_state()  # Publish "done" state once
            await self.coordinator.async_start_fast_poll()

    def _cancel_direction_change(self) -> None:
        """Cancel any pending direction change."""
        if self._direction_change_task and not self._direction_change_task.done():
            self._direction_change_task.cancel()
            self._direction_change_target = None
            self._direction_change_ends_at = None
            self._direction_change_task = None

    async def _async_set_speed(self, speed: int) -> None:
        """Set fan speed and trigger fast poll."""
        if speed > SPEED_OFF:
            self._last_speed = speed
        await self.coordinator.device.async_set_state(speed=speed)
        await self.coordinator.async_start_fast_poll()
