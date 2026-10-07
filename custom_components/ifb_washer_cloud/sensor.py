"""Sensors for the IFB Washer Cloud integration."""

from __future__ import annotations

from typing import Any, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime, PERCENTAGE
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
    """Set up IFB Washer sensors from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: IfbWasherCoordinator = entry_data["coordinator"]
    devices: Dict[str, IfbDevice] = entry_data["devices"]

    entities: list[SensorEntity] = []
    for mac, device in devices.items():
        entities.extend(
            [
                IfbStateSensor(coordinator, device),
                IfbProgramSensor(coordinator, device),
                IfbTimeRemainingSensor(coordinator, device),
                IfbProgressPercentSensor(coordinator, device),
                IfbMotorSpeedSensor(coordinator, device),
                IfbWaterTempSensor(coordinator, device),
                IfbSelectedSpinSensor(coordinator, device),
                IfbSelectedDryModeSensor(coordinator, device),
            ]
        )

    async_add_entities(entities)


class IfbBaseSensor(CoordinatorEntity[IfbWasherCoordinator], SensorEntity):
    """Base class for IFB Washer sensors."""

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        """Initialize the sensor."""
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


class IfbStateSensor(IfbBaseSensor):
    """Current cycle phase / machine state sensor."""

    _attr_icon = "mdi:washing-machine"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Machine State"
        self._attr_unique_id = f"{device.mac}_machine_state"

    @property
    def native_value(self) -> str:
        """Return state representation."""
        if not self.progress:
            return "standby"
        return self.progress.state.value


class IfbProgramSensor(IfbBaseSensor):
    """Active wash/dry program sensor."""

    _attr_icon = "mdi:tumble-dryer"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Active Program"
        self._attr_unique_id = f"{device.mac}_active_program"

    @property
    def native_value(self) -> str:
        """Return selected program name."""
        if not self.progress:
            return "Standby"
        return self.progress.program_name

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return extra attributes for frontend cards."""
        if not self.progress:
            return {}
        return {
            "program_code": self.progress.program_code,
            "door_locked": self.progress.door_locked,
            "child_lock": self.progress.child_lock_active,
            "prewash": self.progress.prewash_active,
            "steam": self.progress.steam_active,
        }


class IfbTimeRemainingSensor(IfbBaseSensor):
    """Remaining cycle countdown timer in minutes."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:timer-outline"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Time Remaining"
        self._attr_unique_id = f"{device.mac}_time_remaining"

    @property
    def native_value(self) -> int:
        if not self.progress:
            return 0
        return self.progress.time_remaining_minutes


class IfbProgressPercentSensor(IfbBaseSensor):
    """Cycle progress percentage sensor."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:progress-clock"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Progress"
        self._attr_unique_id = f"{device.mac}_progress"

    @property
    def native_value(self) -> int:
        if not self.progress:
            return 0
        return self.progress.progress_percentage


class IfbMotorSpeedSensor(IfbBaseSensor):
    """Real-time drum rotation speed in RPM."""

    _attr_native_unit_of_measurement = "RPM"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:rotate-right"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Motor Speed"
        self._attr_unique_id = f"{device.mac}_motor_speed"

    @property
    def native_value(self) -> int:
        if not self.progress:
            return 0
        return self.progress.motor_speed_rpm


class IfbWaterTempSensor(IfbBaseSensor):
    """Drum water temperature sensor in Celsius."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Water Temperature"
        self._attr_unique_id = f"{device.mac}_water_temperature"

    @property
    def native_value(self) -> int:
        if not self.progress:
            return 0
        return self.progress.water_temperature_c


class IfbSelectedSpinSensor(IfbBaseSensor):
    """Configured spin speed sensor."""

    _attr_icon = "mdi:rotate-3d-variant"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Selected Spin Speed"
        self._attr_unique_id = f"{device.mac}_selected_spin"

    @property
    def native_value(self) -> str:
        if not self.progress:
            return "No Spin"
        return self.progress.selected_spin_speed


class IfbSelectedDryModeSensor(IfbBaseSensor):
    """Configured drying mode sensor."""

    _attr_icon = "mdi:weather-sunny"

    def __init__(self, coordinator: IfbWasherCoordinator, device: IfbDevice) -> None:
        super().__init__(coordinator, device)
        self._attr_name = f"{device.name} Selected Dry Mode"
        self._attr_unique_id = f"{device.mac}_selected_dry_mode"

    @property
    def native_value(self) -> str:
        if not self.progress:
            return "No Dry"
        return self.progress.selected_dry_mode
