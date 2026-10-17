"""Select entities for the IFB Washer Cloud integration."""

from __future__ import annotations

import logging
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
    from .ifb_cloud.client import IfbCloudClient
    from .ifb_cloud.const import (
        DRY_MODES,
        PROGRAM_NAMES,
        PROGRAM_PROFILES,
        SPIN_SPEEDS,
        TEMPERATURES,
        WASHER_DRYER_PROGRAMS,
    )
    from .ifb_cloud.models import IfbCycleProgress, IfbDevice
except ImportError:
    from ifb_cloud.client import IfbCloudClient
    from ifb_cloud.const import (
        DRY_MODES,
        PROGRAM_NAMES,
        PROGRAM_PROFILES,
        SPIN_SPEEDS,
        TEMPERATURES,
        WASHER_DRYER_PROGRAMS,
    )
    from ifb_cloud.models import IfbCycleProgress, IfbDevice

_LOGGER = logging.getLogger(__name__)

PROG_NAME_TO_CODE = {v: k for k, v in WASHER_DRYER_PROGRAMS.items()}
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
    client: IfbCloudClient = entry_data["client"]
    devices: Dict[str, IfbDevice] = entry_data["devices"]
    settings: Dict[str, Dict[str, int]] = entry_data["settings"]

    entities: list[SelectEntity] = []
    for mac, device in devices.items():
        dev_settings = settings[mac]
        entities.extend(
            [
                IfbProgramSelect(coordinator, client, device, dev_settings),
                IfbSpinSpeedSelect(coordinator, client, device, dev_settings),
                IfbTemperatureSelect(coordinator, client, device, dev_settings),
                IfbDryModeSelect(coordinator, client, device, dev_settings),
            ]
        )

    async_add_entities(entities)


class IfbBaseSelect(CoordinatorEntity[IfbWasherCoordinator], SelectEntity):
    """Base class for IFB Washer select entities."""

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        """Initialize select entity."""
        super().__init__(coordinator)
        self.client = client
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
        client: IfbCloudClient,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, client, device, settings)
        self._attr_name = f"{device.name} Program"
        self._attr_unique_id = f"{device.mac}_program_select"
        self._attr_options = list(WASHER_DRYER_PROGRAMS.values())

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.program_name and self.progress.program_name in self.options:
            if self.progress.program_code:
                self.settings["program"] = self.progress.program_code
            return self.progress.program_name
        code = self.settings.get("program", 14)
        return WASHER_DRYER_PROGRAMS.get(code, self.options[0])

    async def async_select_option(self, option: str) -> None:
        """Change selected program."""
        if option in PROG_NAME_TO_CODE:
            code = PROG_NAME_TO_CODE[option]
            self.settings["program"] = code
            if self.progress:
                self.progress.program_code = code
                self.progress.program_name = option

            # Dynamically clamp temp/spin settings to profile limits
            profile = PROGRAM_PROFILES.get(code)
            if profile:
                allowed_temps = profile.get("temps", TEMPERATURES)
                cur_temp_idx = self.settings.get("temp", 3)
                cur_temp_str = TEMPERATURES[cur_temp_idx] if cur_temp_idx < len(TEMPERATURES) else "40°C"
                if cur_temp_str not in allowed_temps:
                    new_temp_str = allowed_temps[0]
                    new_idx = TEMP_NAME_TO_CODE.get(new_temp_str, 0)
                    self.settings["temp"] = new_idx
                    if self.progress:
                        self.progress.temp_idx = new_idx
                        self.progress.selected_temperature = new_temp_str

                allowed_spins = profile.get("spins", SPIN_SPEEDS)
                cur_spin_idx = self.settings.get("spin", 4)
                cur_spin_str = SPIN_SPEEDS[cur_spin_idx] if cur_spin_idx < len(SPIN_SPEEDS) else "1000 RPM"
                if cur_spin_str not in allowed_spins:
                    new_spin_str = allowed_spins[-1]
                    new_idx = SPIN_NAME_TO_CODE.get(new_spin_str, 0)
                    self.settings["spin"] = new_idx
                    if self.progress:
                        self.progress.spin_idx = new_idx
                        self.progress.selected_spin_speed = new_spin_str

                if not profile.get("dry", True):
                    self.settings["dry"] = 0
                    if self.progress:
                        self.progress.dry_mode_code = 0
                        self.progress.selected_dry_mode = "No Dry"

            self.async_write_ha_state()
            self.coordinator.async_update_listeners()

            if not (self.progress and self.progress.is_running):
                try:
                    await self.client.configure_cycle(
                        self.mac,
                        program=code,
                        temp=self.settings.get("temp", 3),
                        spin=self.settings.get("spin", 4),
                        serial=self.device.serial_number,
                    )
                except Exception as err:
                    _LOGGER.debug("Could not sync program selection to washer %s: %s", self.mac, err)


class IfbSpinSpeedSelect(IfbBaseSelect):
    """Selector for spin speed."""

    _attr_icon = "mdi:rotate-3d-variant"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, client, device, settings)
        self._attr_name = f"{device.name} Spin Speed"
        self._attr_unique_id = f"{device.mac}_spin_select"

    @property
    def options(self) -> List[str]:
        prog_code = self.settings.get("program", 1)
        if self.progress and self.progress.program_code:
            prog_code = self.progress.program_code
        profile = PROGRAM_PROFILES.get(prog_code)
        if profile and "spins" in profile:
            return profile["spins"]
        return list(SPIN_SPEEDS)

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.selected_spin_speed in self.options:
            if self.progress.spin_idx is not None:
                self.settings["spin"] = self.progress.spin_idx
            return self.progress.selected_spin_speed
        idx = self.settings.get("spin", 4)
        if 0 <= idx < len(SPIN_SPEEDS) and SPIN_SPEEDS[idx] in self.options:
            return SPIN_SPEEDS[idx]
        return self.options[0] if self.options else None

    async def async_select_option(self, option: str) -> None:
        """Change selected spin speed."""
        if option in SPIN_NAME_TO_CODE:
            spin_code = SPIN_NAME_TO_CODE[option]
            self.settings["spin"] = spin_code
            if self.progress:
                self.progress.spin_idx = spin_code
                self.progress.selected_spin_speed = option
            self.async_write_ha_state()

            if not (self.progress and self.progress.is_running):
                try:
                    await self.client.configure_cycle(
                        self.mac,
                        program=self.settings.get("program", 1),
                        temp=self.settings.get("temp", 3),
                        spin=spin_code,
                        serial=self.device.serial_number,
                    )
                except Exception as err:
                    _LOGGER.debug("Could not sync spin speed to washer %s: %s", self.mac, err)


class IfbTemperatureSelect(IfbBaseSelect):
    """Selector for wash temperature."""

    _attr_icon = "mdi:thermometer"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, client, device, settings)
        self._attr_name = f"{device.name} Temperature"
        self._attr_unique_id = f"{device.mac}_temp_select"

    @property
    def options(self) -> List[str]:
        prog_code = self.settings.get("program", 1)
        if self.progress and self.progress.program_code:
            prog_code = self.progress.program_code
        profile = PROGRAM_PROFILES.get(prog_code)
        if profile and "temps" in profile:
            return profile["temps"]
        return list(TEMPERATURES)

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.selected_temperature in self.options:
            if self.progress.temp_idx is not None:
                self.settings["temp"] = self.progress.temp_idx
            return self.progress.selected_temperature
        idx = self.settings.get("temp", 3)
        if 0 <= idx < len(TEMPERATURES) and TEMPERATURES[idx] in self.options:
            return TEMPERATURES[idx]
        return self.options[0] if self.options else None

    async def async_select_option(self, option: str) -> None:
        """Change selected temperature."""
        if option in TEMP_NAME_TO_CODE:
            temp_code = TEMP_NAME_TO_CODE[option]
            self.settings["temp"] = temp_code
            if self.progress:
                self.progress.temp_idx = temp_code
                self.progress.selected_temperature = option
            self.async_write_ha_state()

            if not (self.progress and self.progress.is_running):
                try:
                    await self.client.configure_cycle(
                        self.mac,
                        program=self.settings.get("program", 1),
                        temp=temp_code,
                        spin=self.settings.get("spin", 4),
                        serial=self.device.serial_number,
                    )
                except Exception as err:
                    _LOGGER.debug("Could not sync temperature to washer %s: %s", self.mac, err)


class IfbDryModeSelect(IfbBaseSelect):
    """Selector for drying mode."""

    _attr_icon = "mdi:weather-sunny"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, client, device, settings)
        self._attr_name = f"{device.name} Dry Mode"
        self._attr_unique_id = f"{device.mac}_dry_select"

    @property
    def options(self) -> List[str]:
        prog_code = self.settings.get("program", 14)
        if self.progress and self.progress.program_code:
            prog_code = self.progress.program_code
        profile = PROGRAM_PROFILES.get(prog_code)
        if profile and not profile.get("dry", True):
            return ["No Dry"]
        return list(DRY_MODES.values())

    @property
    def current_option(self) -> Optional[str]:
        if self.progress and self.progress.selected_dry_mode in self.options:
            if self.progress.dry_mode_code is not None:
                self.settings["dry"] = self.progress.dry_mode_code
            return self.progress.selected_dry_mode
        code = self.settings.get("dry", 0)
        mode = DRY_MODES.get(code, self.options[0])
        return mode if mode in self.options else self.options[0]

    async def async_select_option(self, option: str) -> None:
        """Change selected drying mode."""
        if option in DRY_MODE_TO_CODE:
            dry_code = DRY_MODE_TO_CODE[option]
            self.settings["dry"] = dry_code
            if self.progress:
                self.progress.dry_mode_code = dry_code
                self.progress.selected_dry_mode = option
            self.async_write_ha_state()
