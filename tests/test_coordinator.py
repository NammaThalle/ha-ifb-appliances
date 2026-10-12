"""Unit tests for IfbWasherCoordinator adaptive polling and error isolation."""

import unittest
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

import tests
from custom_components.ifb_washer_cloud.const import (
    DEFAULT_SCAN_INTERVAL_IDLE,
    DEFAULT_SCAN_INTERVAL_RUNNING,
)
from custom_components.ifb_washer_cloud.coordinator import IfbWasherCoordinator
from ifb_cloud.const import MachineState
from ifb_cloud.models import IfbCycleProgress, IfbDevice


class TestIfbWasherCoordinator(unittest.IsolatedAsyncioTestCase):
    """Test suite for coordinator dynamic polling rate and resilient data fetching."""

    async def asyncSetUp(self):
        """Set up test coordinator and mocks."""
        self.hass = MagicMock()
        self.client = MagicMock()
        self.device = IfbDevice(
            mac="aa:bb:cc:dd:ee:ff",
            name="Test Washer",
            model_name="IFB Appliance",
            is_online=True,
            hardware_type="esp",
        )
        self.devices = {"aa:bb:cc:dd:ee:ff": self.device}
        self.coordinator = IfbWasherCoordinator(self.hass, self.client, self.devices)

    async def test_adaptive_polling_idle_state(self):
        """Verify coordinator keeps 15s scan interval when machine is standby / idle."""
        self.client.get_device_progress = AsyncMock(
            return_value=IfbCycleProgress(
                mac="aa:bb:cc:dd:ee:ff",
                is_running=False,
                state=MachineState.STANDBY,
            )
        )

        data = await self.coordinator._async_update_data()
        self.assertIn("aa:bb:cc:dd:ee:ff", data)
        self.assertFalse(data["aa:bb:cc:dd:ee:ff"].is_running)
        self.assertEqual(
            self.coordinator.update_interval,
            timedelta(seconds=DEFAULT_SCAN_INTERVAL_IDLE),
        )

    async def test_adaptive_polling_running_state(self):
        """Verify coordinator dynamically increases polling rate to 5s when cycle is active."""
        self.client.get_device_progress = AsyncMock(
            return_value=IfbCycleProgress(
                mac="aa:bb:cc:dd:ee:ff",
                is_running=True,
                state=MachineState.MAIN_WASH,
                time_remaining_minutes=42,
            )
        )

        data = await self.coordinator._async_update_data()
        self.assertIn("aa:bb:cc:dd:ee:ff", data)
        self.assertTrue(data["aa:bb:cc:dd:ee:ff"].is_running)
        self.assertEqual(
            self.coordinator.update_interval,
            timedelta(seconds=DEFAULT_SCAN_INTERVAL_RUNNING),
        )

    async def test_per_device_exception_resilience(self):
        """Verify cloud polling errors for a device do not crash coordinator."""
        # Simulate network or HTTP 404 error from client
        self.client.get_device_progress = AsyncMock(side_effect=Exception("Connection refused"))

        data = await self.coordinator._async_update_data()
        self.assertIn("aa:bb:cc:dd:ee:ff", data)
        # Should gracefully return a Standby object instead of raising UpdateFailed
        self.assertEqual(data["aa:bb:cc:dd:ee:ff"].state, MachineState.STANDBY)
        self.assertFalse(data["aa:bb:cc:dd:ee:ff"].is_running)


if __name__ == "__main__":
    unittest.main()
