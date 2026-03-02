"""DataUpdateCoordinator for Fanimation BLE fans."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    LOGGER,
    MAX_CONNECTION_FAILURES,
    POLL_FAST,
    POLL_FAST_CYCLES,
    POLL_SLOW,
)
from .device import FanimationDevice, FanimationState


class FanimationCoordinator(DataUpdateCoordinator[FanimationState]):
    """Coordinator that polls the fan via BLE and manages fast/slow poll cycles."""

    def __init__(self, hass: HomeAssistant, device: FanimationDevice, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_{device.mac}",
            update_interval=timedelta(seconds=POLL_SLOW),
            config_entry=entry,
        )
        self.device = device
        self._fast_poll_remaining = 0
        self._connection_failures = 0

    async def _async_update_data(self) -> FanimationState:
        """Poll the fan for current state."""
        should_disconnect = False
        try:
            state = await self.device.async_get_status()
        except Exception as err:
            self._connection_failures += 1
            # Always disconnect on failure to force clean reconnect
            await self.device.disconnect()

            if self._connection_failures >= MAX_CONNECTION_FAILURES:
                raise UpdateFailed(
                    f"Failed to connect to {self.device.name} after {self._connection_failures} attempts: {err}"
                ) from err

            LOGGER.warning(
                "Connection to %s failed (%d/%d): %s",
                self.device.name,
                self._connection_failures,
                MAX_CONNECTION_FAILURES,
                err,
            )
            raise UpdateFailed(str(err)) from err

        if state is None:
            self._connection_failures += 1
            raise UpdateFailed(f"No response from {self.device.name}")

        # Success — reset failure counter
        self._connection_failures = 0

        # Manage fast/slow polling transition
        if self._fast_poll_remaining > 0:
            self._fast_poll_remaining -= 1
            if self._fast_poll_remaining == 0:
                # Revert to slow polling and disconnect
                self.update_interval = timedelta(seconds=POLL_SLOW)
                should_disconnect = True
                LOGGER.debug("Reverting to slow poll for %s", self.device.name)
        else:
            # Slow poll — disconnect to free BLE slot
            should_disconnect = True

        if should_disconnect:
            try:
                await self.device.disconnect()
            except Exception:
                LOGGER.debug("Error disconnecting from %s (non-fatal)", self.device.name)

        return state

    async def async_start_fast_poll(self) -> None:
        """Switch to fast polling after a command.

        Changes the interval AND triggers an immediate refresh.
        Just changing update_interval doesn't cancel the pending timer,
        so without the immediate refresh the first fast poll would wait
        until the old slow timer expires.
        """
        self._fast_poll_remaining = POLL_FAST_CYCLES
        self.update_interval = timedelta(seconds=POLL_FAST)
        LOGGER.debug(
            "Fast polling for %s (%d cycles)",
            self.device.name,
            POLL_FAST_CYCLES,
        )
        # Kick off the first fast poll immediately
        await self.async_request_refresh()
