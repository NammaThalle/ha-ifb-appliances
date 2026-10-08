"""Binary sensors for the IFB Washer Cloud integration."""

from __future__ import annotations

from typing import Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IfbWasherCoordinator

try:
    from .ifb_cloud.models import IfbCycleProgress, IfbDevice
except ImportError:
    from ifb_cloud.models import IfbCycleProgress, IfbDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IFB Washer binary sensors from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: IfbWasherCoordinator = entry_data["coordinator"]
    devices: Dict[str, IfbDevice] = entry_data["devices"]

    entities: list[BinarySensorEntity] = []
    for mac, device in devices.items():
        entities.extend(
            [
                IfbRunningBinarySensor(coordinator, device),
                IfbDoorLockBinarySensor(coordinator, device),
                IfbChildLockBinarySensor(coordinator, device),
                IfbProblemBinarySensor(coordinator, device),
                IfbSteamBinarySensor(coordinator, device),
                IfbPrewashBinarySensor(coordinator, device),
                IfbSoakBinarySensor(coordinator, device),
            ]
        )

    async_add_entities(entities)


class IfbBaseBinarySensor(CoordinatorEntity[IfbWasherCoordinator], BinarySensorEntity):
    """Base class for IFB Washer binary sensors."""

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.device = device
        self.mac = device.mac

    @property
    def progress(self) -> Optional[IfbCycleProgress]:
        """Return the latest cycle progress for this appliance."""
        return self.coordinator.data.get(self.mac)

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


class IfbRunningBinarySensor(IfbBaseBinarySensor):
    """Binary sensor indicating if the machine is actively running a cycle."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Running"
        self._attr_unique_id = f"{device.mac}_running"

    @property
    def is_on(self) -> bool:
        if not self.progress:
            return False
        return bool(self.progress.is_running)


class IfbDoorLockBinarySensor(IfbBaseBinarySensor):
    """Binary sensor indicating if the machine door is locked."""

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Door Locked"
        self._attr_unique_id = f"{device.mac}_door_locked"

    @property
    def icon(self) -> str:
        return "mdi:lock" if self.is_on else "mdi:lock-open-variant"

    @property
    def is_on(self) -> bool:
        if not self.progress:
            return False
        return bool(self.progress.door_locked)


class IfbChildLockBinarySensor(IfbBaseBinarySensor):
    """Binary sensor indicating if child lock is active."""

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Child Lock"
        self._attr_unique_id = f"{device.mac}_child_lock"

    @property
    def icon(self) -> str:
        return "mdi:account-lock" if self.is_on else "mdi:account-lock-open"

    @property
    def is_on(self) -> bool:
        if not self.progress:
            return False
        return bool(self.progress.child_lock_active)


class IfbProblemBinarySensor(IfbBaseBinarySensor):
    """Binary sensor indicating if the machine is reporting an error or fault."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Problem"
        self._attr_unique_id = f"{device.mac}_problem"

    @property
    def is_on(self) -> bool:
        if not self.progress:
            return False
        return bool(self.progress.error_code)

    @property
    def extra_state_attributes(self) -> Dict[str, str]:
        if not self.progress or not self.progress.error_code:
            return {}
        return {"error_code": str(self.progress.error_code)}


class IfbSteamBinarySensor(IfbBaseBinarySensor):
    """Binary sensor indicating steam stage/option active."""

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Steam Active"
        self._attr_unique_id = f"{device.mac}_steam_active"
        self._attr_icon = "mdi:radiator"

    @property
    def is_on(self) -> bool:
        if not self.progress:
            return False
        return bool(self.progress.steam_active)


class IfbPrewashBinarySensor(IfbBaseBinarySensor):
    """Binary sensor indicating prewash stage active."""

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Prewash Active"
        self._attr_unique_id = f"{device.mac}_prewash_active"
        self._attr_icon = "mdi:washing-machine-alert"

    @property
    def is_on(self) -> bool:
        if not self.progress:
            return False
        return bool(self.progress.prewash_active)


class IfbSoakBinarySensor(IfbBaseBinarySensor):
    """Binary sensor indicating soak stage active."""

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Soak Active"
        self._attr_unique_id = f"{device.mac}_soak_active"
        self._attr_icon = "mdi:water-opacity"

    @property
    def is_on(self) -> bool:
        if not self.progress:
            return False
        return bool(self.progress.soak_active)
