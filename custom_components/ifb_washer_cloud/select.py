"""Select entities for the IFB Washer Cloud integration."""

from __future__ import annotations

from typing import Dict, List, Optional

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IfbWasherCoordinator

try:
    from .ifb_cloud.const import DRY_MODES, PROGRAM_NAMES, SPIN_SPEEDS, TEMPERATURES
    from .ifb_cloud.models import IfbCycleProgress, IfbDevice
except ImportError:
    from ifb_cloud.const import DRY_MODES, PROGRAM_NAMES, SPIN_SPEEDS, TEMPERATURES
    from ifb_cloud.models import IfbCycleProgress, IfbDevice

PROG_NAME_TO_CODE = {v: k for k, v in PROGRAM_NAMES.items()}
DRY_MODE_TO_CODE = {v: k for k, v in DRY_MODES.items()}
SPIN_NAME_TO_CODE = {v: i for i, v in enumerate(SPIN_SPEEDS)}
TEMP_NAME_TO_CODE = {v: i for i, v in enumerate(TEMPERATURES)}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IFB Washer select entities from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: IfbWasherCoordinator = entry_data["coordinator"]
    devices: Dict[str, IfbDevice] = entry_data["devices"]
    settings: Dict[str, Dict[str, int]] = entry_data["settings"]

    entities: list[SelectEntity] = []
    for mac, device in devices.items():
        dev_settings = settings[mac]
        entities.extend(
            [
                IfbProgramSelect(coordinator, device, dev_settings),
                IfbSpinSpeedSelect(coordinator, device, dev_settings),
                IfbTemperatureSelect(coordinator, device, dev_settings),
                IfbDryModeSelect(coordinator, device, dev_settings),
            ]
        )

    async_add_entities(entities)


class IfbBaseSelect(CoordinatorEntity[IfbWasherCoordinator], SelectEntity):
    """Base class for IFB Washer select entities."""

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        """Initialize select entity."""
        super().__init__(coordinator)
        self.device = device
        self.mac = device.mac
        self.settings = settings

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


class IfbProgramSelect(IfbBaseSelect):
    """Selector for wash/dry cycle program."""

    _attr_icon = "mdi:washing-machine"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, device, settings)
        self._attr_name = f"{device.name} Program"
        self._attr_unique_id = f"{device.mac}_program_select"
        self._attr_options = list(PROGRAM_NAMES.values())

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.is_running and self.progress.program_name in self.options:
            return self.progress.program_name
        code = self.settings.get("program", 1)
        return PROGRAM_NAMES.get(code, self.options[0])

    async def async_select_option(self, option: str) -> None:
        """Change selected program."""
        if option in PROG_NAME_TO_CODE:
            self.settings["program"] = PROG_NAME_TO_CODE[option]
            self.async_write_ha_state()


class IfbSpinSpeedSelect(IfbBaseSelect):
    """Selector for spin speed."""

    _attr_icon = "mdi:rotate-3d-variant"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, device, settings)
        self._attr_name = f"{device.name} Spin Speed"
        self._attr_unique_id = f"{device.mac}_spin_select"
        self._attr_options = list(SPIN_SPEEDS)

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.is_running and self.progress.selected_spin_speed in self.options:
            return self.progress.selected_spin_speed
        idx = self.settings.get("spin", 4)
        if 0 <= idx < len(SPIN_SPEEDS):
            return SPIN_SPEEDS[idx]
        return self.options[4]

    async def async_select_option(self, option: str) -> None:
        """Change selected spin speed."""
        if option in SPIN_NAME_TO_CODE:
            self.settings["spin"] = SPIN_NAME_TO_CODE[option]
            self.async_write_ha_state()


class IfbTemperatureSelect(IfbBaseSelect):
    """Selector for wash temperature."""

    _attr_icon = "mdi:thermometer"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, device, settings)
        self._attr_name = f"{device.name} Temperature"
        self._attr_unique_id = f"{device.mac}_temp_select"
        self._attr_options = list(TEMPERATURES)

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.is_running and self.progress.selected_temperature in self.options:
            return self.progress.selected_temperature
        idx = self.settings.get("temp", 3)
        if 0 <= idx < len(TEMPERATURES):
            return TEMPERATURES[idx]
        return self.options[3]

    async def async_select_option(self, option: str) -> None:
        """Change selected temperature."""
        if option in TEMP_NAME_TO_CODE:
            self.settings["temp"] = TEMP_NAME_TO_CODE[option]
            self.async_write_ha_state()


class IfbDryModeSelect(IfbBaseSelect):
    """Selector for drying mode."""

    _attr_icon = "mdi:weather-sunny"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, device, settings)
        self._attr_name = f"{device.name} Dry Mode"
        self._attr_unique_id = f"{device.mac}_dry_select"
        self._attr_options = list(DRY_MODES.values())

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.is_running and self.progress.selected_dry_mode in self.options:
            return self.progress.selected_dry_mode
        code = self.settings.get("dry", 0)
        return DRY_MODES.get(code, self.options[0])

    async def async_select_option(self, option: str) -> None:
        """Change selected drying mode."""
        if option in DRY_MODE_TO_CODE:
            self.settings["dry"] = DRY_MODE_TO_CODE[option]
            self.async_write_ha_state()
