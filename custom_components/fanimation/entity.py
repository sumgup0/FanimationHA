"""Base entity for Fanimation BLE integration."""
from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FanimationCoordinator


class FanimationEntity(CoordinatorEntity[FanimationCoordinator]):
    """Base class for all Fanimation entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: FanimationCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device.mac)},
            connections={(CONNECTION_BLUETOOTH, coordinator.device.mac)},
            name=coordinator.device.name,
            manufacturer="Fanimation",
            model="BTCR9 FanSync Bluetooth",
        )
