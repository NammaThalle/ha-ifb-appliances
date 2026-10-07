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
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL_IDLE),
        )
        self.client = client
        self.devices = devices
        self._is_any_running = False

    async def _async_update_data(self) -> Dict[str, IfbCycleProgress]:
        """Fetch latest telemetry progress for all registered devices."""
        progress_data: Dict[str, IfbCycleProgress] = {}
        any_running = False

        for mac, device in self.devices.items():
            try:
                progress = await self.client.get_device_progress(mac)
            except Exception as err:
                _LOGGER.debug("Could not fetch progress for device %s: %s", mac, err)
                progress = IfbCycleProgress(mac=mac, is_running=False, state=MachineState.STANDBY)
            progress_data[mac] = progress
            if progress.is_running:
                any_running = True

        # Dynamically adapt polling frequency:
        # Poll every 5s while actively washing/drying, relax to 15s when idle.
        if any_running != self._is_any_running:
            self._is_any_running = any_running
            new_interval = DEFAULT_SCAN_INTERVAL_RUNNING if any_running else DEFAULT_SCAN_INTERVAL_IDLE
            self.update_interval = timedelta(seconds=new_interval)
            _LOGGER.debug(
                "IFB Washer state changed (any_running=%s). Adjusted update interval to %ss",
                any_running,
                new_interval,
            )

        return progress_data
