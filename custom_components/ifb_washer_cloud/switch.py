"""Switch entities for the IFB Washer Cloud integration."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IfbWasherCoordinator

try:
    from .ifb_cloud.client import IfbCloudClient, IfbError
    from .ifb_cloud.models import IfbCycleProgress, IfbDevice
except ImportError:
    from ifb_cloud.client import IfbCloudClient, IfbError
    from ifb_cloud.models import IfbCycleProgress, IfbDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IFB Washer switch entities from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: IfbWasherCoordinator = entry_data["coordinator"]
    client: IfbCloudClient = entry_data["client"]
    devices: Dict[str, IfbDevice] = entry_data["devices"]

    entities: list[SwitchEntity] = []
    for mac, device in devices.items():
        entities.append(IfbChildLockSwitch(coordinator, client, device))

    async_add_entities(entities)


class IfbChildLockSwitch(CoordinatorEntity[IfbWasherCoordinator], SwitchEntity):
    """Switch to view and toggle Child Lock on IFB washing machines."""

    _attr_icon = "mdi:lock"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
    ) -> None:
        """Initialize child lock switch."""
        super().__init__(coordinator)
        self.client = client
        self.device = device
        self.mac = device.mac
        self._attr_name = f"{device.name} Child Lock"
        self._attr_unique_id = f"{device.mac}_child_lock_switch"

    @property
    def progress(self) -> Optional[IfbCycleProgress]:
        """Return the latest cycle progress for this appliance."""
        return self.coordinator.data.get(self.mac)

    @property
    def is_on(self) -> bool:
        """Return True if Child Lock is active."""
        if self.progress:
            return bool(self.progress.child_lock_active)
        return False

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for Home Assistant registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.mac)},
            name=self.device.name,
            manufacturer="IFB",
            model=self.device.model_name,
            serial_number=self.device.serial_number,
            sw_version=self.device.firmware_version or "Cloud v4",
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on child lock."""
        if not (self.progress and self.progress.is_running):
            raise HomeAssistantError("Child Lock can only be engaged while a wash cycle is running.")
        _LOGGER.warning("Sending Child Lock ON command to %s", self.mac)
        try:
            await self.client.child_lock(self.mac, serial=self.device.serial_number)
            await self.coordinator.async_request_refresh()
        except IfbError as err:
            raise HomeAssistantError(f"Failed to engage Child Lock on IFB washer: {err}") from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off child lock."""
        if not (self.progress and self.progress.is_running):
            raise HomeAssistantError("Child Lock can only be disengaged while a wash cycle is running.")
        _LOGGER.warning("Sending Child Lock OFF command to %s", self.mac)
        try:
            await self.client.child_unlock(self.mac, serial=self.device.serial_number)
            await self.coordinator.async_request_refresh()
        except IfbError as err:
            raise HomeAssistantError(f"Failed to disengage Child Lock on IFB washer: {err}") from err
