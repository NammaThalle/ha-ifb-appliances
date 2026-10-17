"""Buttons for the IFB Washer Cloud integration."""

from __future__ import annotations

import logging
from typing import Dict, Optional

from homeassistant.components.button import ButtonEntity
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
    from .ifb_cloud.const import MachineState
    from .ifb_cloud.models import IfbCycleProgress, IfbDevice
except ImportError:
    from ifb_cloud.client import IfbCloudClient, IfbError
    from ifb_cloud.const import MachineState
    from ifb_cloud.models import IfbCycleProgress, IfbDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up IFB Washer buttons from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator: IfbWasherCoordinator = entry_data["coordinator"]
    client: IfbCloudClient = entry_data["client"]
    devices: Dict[str, IfbDevice] = entry_data["devices"]
    settings: Dict[str, Dict[str, int]] = entry_data["settings"]

    entities: list[ButtonEntity] = []
    for mac, device in devices.items():
        dev_settings = settings[mac]
        entities.extend(
            [
                IfbStartButton(coordinator, client, device, dev_settings),
                IfbPauseButton(coordinator, client, device),
                IfbCancelButton(coordinator, client, device),
                IfbChildLockButton(coordinator, client, device),
                IfbChildUnlockButton(coordinator, client, device),
                IfbRefreshButton(coordinator, client, device),
            ]
        )

    async_add_entities(entities)


class IfbBaseButton(CoordinatorEntity[IfbWasherCoordinator], ButtonEntity):
    """Base class for IFB Washer buttons."""

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
    ) -> None:
        """Initialize button entity."""
        super().__init__(coordinator)
        self.client = client
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


class IfbStartButton(IfbBaseButton):
    """Button to start/resume cycle with currently selected settings."""

    _attr_icon = "mdi:play"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
        settings: Dict[str, int],
    ) -> None:
        super().__init__(coordinator, client, device)
        self.settings = settings
        self._attr_name = f"{device.name} Start"
        self._attr_unique_id = f"{device.mac}_start"

    async def async_press(self) -> None:
        """Handle button press."""
        program = self.settings.get("program", 1)
        temp = self.settings.get("temp", 3)
        spin = self.settings.get("spin", 4)
        dry = self.settings.get("dry", 0)
        is_paused = bool(
            self.progress
            and (
                getattr(self.progress, "is_paused", False)
                or getattr(self.progress, "state", None) == MachineState.PAUSED
            )
        )

        _LOGGER.warning(
            "Sending Start command to %s (program=%s, temp_idx=%s, spin_idx=%s, dry=%s, is_paused=%s)",
            self.mac,
            program,
            temp,
            spin,
            dry,
            is_paused,
        )
        try:
            await self.client.start(
                self.mac,
                program=program,
                temp=temp,
                spin=spin,
                dry=dry,
                serial=self.device.serial_number,
                resume_only=is_paused,
            )
            await self.coordinator.async_request_refresh()
        except IfbError as err:
            raise HomeAssistantError(f"Failed to start IFB washer: {err}") from err


class IfbPauseButton(IfbBaseButton):
    """Button to pause running cycle."""

    _attr_icon = "mdi:pause"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
    ) -> None:
        super().__init__(coordinator, client, device)
        self._attr_name = f"{device.name} Pause"
        self._attr_unique_id = f"{device.mac}_pause"

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.warning("Sending Pause command to %s", self.mac)
        try:
            await self.client.pause(self.mac, serial=self.device.serial_number)
            await self.coordinator.async_request_refresh()
        except IfbError as err:
            raise HomeAssistantError(f"Failed to pause IFB washer: {err}") from err


class IfbCancelButton(IfbBaseButton):
    """Button to cancel cycle / power off."""

    _attr_icon = "mdi:stop"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
    ) -> None:
        super().__init__(coordinator, client, device)
        self._attr_name = f"{device.name} Stop"
        self._attr_unique_id = f"{device.mac}_cancel"

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.warning("Sending Cancel command to %s", self.mac)
        try:
            await self.client.cancel(self.mac, serial=self.device.serial_number)
            await self.coordinator.async_request_refresh()
        except IfbError as err:
            raise HomeAssistantError(f"Failed to stop/cancel IFB washer: {err}") from err


class IfbRefreshButton(IfbBaseButton):
    """Button to immediately poll cloud telemetry."""

    _attr_icon = "mdi:refresh"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
    ) -> None:
        super().__init__(coordinator, client, device)
        self._attr_name = f"{device.name} Refresh"
        self._attr_unique_id = f"{device.mac}_refresh"

    async def async_press(self) -> None:
        """Handle button press."""
        await self.coordinator.async_request_refresh()


class IfbChildLockButton(IfbBaseButton):
    """Button to engage child lock on running cycle."""

    _attr_icon = "mdi:lock"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
    ) -> None:
        super().__init__(coordinator, client, device)
        self._attr_name = f"{device.name} Child Lock"
        self._attr_unique_id = f"{device.mac}_child_lock"

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Sending Child Lock command to %s", self.mac)
        try:
            await self.client.child_lock(self.mac, serial=self.device.serial_number)
            await self.coordinator.async_request_refresh()
        except IfbError as err:
            raise HomeAssistantError(f"Failed to engage Child Lock on IFB washer: {err}") from err


class IfbChildUnlockButton(IfbBaseButton):
    """Button to disengage child lock on running cycle."""

    _attr_icon = "mdi:lock-open"

    def __init__(
        self,
        coordinator: IfbWasherCoordinator,
        client: IfbCloudClient,
        device: IfbDevice,
    ) -> None:
        super().__init__(coordinator, client, device)
        self._attr_name = f"{device.name} Child Unlock"
        self._attr_unique_id = f"{device.mac}_child_unlock"

    async def async_press(self) -> None:
        """Handle button press."""
        _LOGGER.info("Sending Child Unlock command to %s", self.mac)
        try:
            await self.client.child_unlock(self.mac, serial=self.device.serial_number)
            await self.coordinator.async_request_refresh()
        except IfbError as err:
            raise HomeAssistantError(f"Failed to disengage Child Lock on IFB washer: {err}") from err
