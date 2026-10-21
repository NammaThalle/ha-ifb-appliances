"""DataUpdateCoordinator for IFB Washer Cloud integration."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Dict, Optional

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DEFAULT_SCAN_INTERVAL_IDLE,
    DEFAULT_SCAN_INTERVAL_RUNNING,
    DOMAIN,
)

# Support both bundled and top-level imports
try:
    from .ifb_cloud.client import IfbCloudClient, IfbError
    from .ifb_cloud.const import MachineState
    from .ifb_cloud.models import IfbCycleProgress, IfbDevice
except ImportError:
    from ifb_cloud.client import IfbCloudClient, IfbError
    from ifb_cloud.const import MachineState
    from ifb_cloud.models import IfbCycleProgress, IfbDevice

_LOGGER = logging.getLogger(__name__)


class IfbWasherCoordinator(DataUpdateCoordinator[Dict[str, IfbCycleProgress]]):
    """Coordinator to manage polling of IFB cloud telemetry."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: IfbCloudClient,
        devices: Dict[str, IfbDevice],
        settings: Optional[Dict[str, Dict[str, int]]] = None,
        scan_interval_idle: int = DEFAULT_SCAN_INTERVAL_IDLE,
        scan_interval_running: int = DEFAULT_SCAN_INTERVAL_RUNNING,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval_idle),
        )
        self.client = client
        self.devices = devices
        self.settings = settings if settings is not None else {}
        self.scan_interval_idle = scan_interval_idle
        self.scan_interval_running = scan_interval_running
        self._is_any_running = False

    async def _async_update_data(self) -> Dict[str, IfbCycleProgress]:
        """Fetch latest telemetry progress for all registered devices."""
        progress_data: Dict[str, IfbCycleProgress] = {}
        any_running = False

        for mac, device in self.devices.items():
            try:
                progress = await self.client.get_device_progress(mac, serial=device.serial_number)
            except Exception as err:
                _LOGGER.debug("Could not fetch progress for device %s: %s", mac, err)
                progress = IfbCycleProgress(mac=mac, is_running=False, state=MachineState.STANDBY)
            progress_data[mac] = progress

            # Automatically update live dropdown settings if machine reported non-zero program
            if progress and progress.program_code and mac in self.settings:
                self.settings[mac]["program"] = progress.program_code
                if progress.temp_idx is not None:
                    self.settings[mac]["temp"] = progress.temp_idx
                if progress.spin_idx is not None:
                    self.settings[mac]["spin"] = progress.spin_idx
                if progress.dry_mode_code is not None:
                    self.settings[mac]["dry"] = progress.dry_mode_code

            if progress.is_running:
                any_running = True

        # Dynamically adapt polling frequency:
        # Poll every 5s while actively washing/drying, relax to 15s when idle.
        if any_running != self._is_any_running:
            self._is_any_running = any_running
            new_interval = self.scan_interval_running if any_running else self.scan_interval_idle
            self.update_interval = timedelta(seconds=new_interval)
            _LOGGER.debug(
                "IFB Washer state changed (any_running=%s). Adjusted update interval to %ss",
                any_running,
                new_interval,
            )

        return progress_data
