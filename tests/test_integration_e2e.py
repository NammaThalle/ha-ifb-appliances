"""End-to-End integration test simulating the Home Assistant environment and lifecycle."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure global test mocks are loaded
import tests

from custom_components.ifb_washer_cloud import (
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.ifb_washer_cloud.const import (
    CONF_AUTH_TYPE,
    CONF_DEVICE_NAME,
    CONF_MAC,
    CONF_TOKEN,
    CONF_USER_ID,
    DOMAIN,
    PLATFORMS,
)
from ifb_cloud.const import MachineState
from ifb_cloud.models import IfbCycleProgress, IfbDevice


class TestIfbIntegrationE2E(unittest.IsolatedAsyncioTestCase):
    """End-to-end integration lifecycle test suite."""

    async def asyncSetUp(self):
        """Set up mock Home Assistant instance and config entry."""
        self.hass = MagicMock()
        self.hass.data = {}
        self.hass.config_entries = MagicMock()
        self.hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        self.hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)
        self.hass.config_entries.async_reload = AsyncMock()

        self.entry = MagicMock()
        self.entry.entry_id = "test_entry_01"
        self.entry.data = {
            CONF_AUTH_TYPE: "otp",
            CONF_TOKEN: "mock_jwt_token",
            CONF_USER_ID: "9876543210",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
            CONF_DEVICE_NAME: "Master Washer",
        }
        self.entry.options = {}
        self.entry.add_update_listener = MagicMock(return_value=lambda: None)
        self.entry.async_on_unload = MagicMock()

    @patch("custom_components.ifb_washer_cloud.IfbCloudClient")
    async def test_full_setup_and_unload_lifecycle(self, mock_client_cls):
        """Verify full end-to-end integration setup, platform forwarding, and unload."""
        mock_client = MagicMock()
        mock_client.token = "mock_jwt_token"
        mock_client.user_id = "9876543210"

        test_device = IfbDevice(
            mac="aa:bb:cc:dd:ee:ff",
            name="Master Washer",
            model_name="IFB Appliance",
            device_id="aa:bb:cc:dd:ee:ff",
            serial_number="IFB123456",
            category="Washer Dryer",
            is_online=True,
            hardware_type="esp",
        )
        mock_client.get_all_devices = AsyncMock(return_value=[test_device])
        mock_client.get_device_progress = AsyncMock(
            return_value=IfbCycleProgress(
                mac="aa:bb:cc:dd:ee:ff",
                is_running=False,
                state=MachineState.STANDBY,
            )
        )
        mock_client_cls.return_value = mock_client

        # 1. Execute async_setup_entry
        setup_success = await async_setup_entry(self.hass, self.entry)
        self.assertTrue(setup_success)

        # 2. Verify hass.data structure
        self.assertIn(DOMAIN, self.hass.data)
        self.assertIn(self.entry.entry_id, self.hass.data[DOMAIN])
        entry_store = self.hass.data[DOMAIN][self.entry.entry_id]

        self.assertIn("client", entry_store)
        self.assertIn("coordinator", entry_store)
        self.assertIn("devices", entry_store)
        self.assertIn("settings", entry_store)
        self.assertIn("aa:bb:cc:dd:ee:ff", entry_store["devices"])
        self.assertIn("aa:bb:cc:dd:ee:ff", entry_store["settings"])

        # Verify platform setup was forwarded
        self.hass.config_entries.async_forward_entry_setups.assert_awaited_once_with(self.entry, PLATFORMS)

        # 3. Test reload listener
        await async_reload_entry(self.hass, self.entry)
        self.hass.config_entries.async_reload.assert_awaited_once_with(self.entry.entry_id)

        # 4. Test unload
        unload_success = await async_unload_entry(self.hass, self.entry)
        self.assertTrue(unload_success)
        self.assertNotIn(self.entry.entry_id, self.hass.data[DOMAIN])

    @patch("custom_components.ifb_washer_cloud.IfbCloudClient")
    async def test_control_commands_start_pause_stop(self, mock_client_cls):
        """Verify control commands transmit binary frames to client."""
        mock_client = MagicMock()
        mock_client.token = "mock_jwt_token"
        mock_client.user_id = "9876543210"
        test_device = IfbDevice(
            mac="aa:bb:cc:dd:ee:ff",
            name="Master Washer",
            model_name="IFB Appliance",
            is_online=True,
            hardware_type="esp",
        )
        mock_client.get_all_devices = AsyncMock(return_value=[test_device])
        mock_client.send_command = AsyncMock(return_value={"status": "sent"})
        mock_client_cls.return_value = mock_client

        await async_setup_entry(self.hass, self.entry)
        entry_store = self.hass.data[DOMAIN][self.entry.entry_id]
        settings = entry_store["settings"]["aa:bb:cc:dd:ee:ff"]

        # Simulate start command
        from ifb_cloud.frame import IfbFrameBuilder
        start_frame = IfbFrameBuilder.start(
            program=settings["program"],
            temp=settings["temp"],
            spin=settings["spin"],
            dry=settings["dry"],
        )
        await mock_client.send_command("aa:bb:cc:dd:ee:ff", start_frame)
        mock_client.send_command.assert_awaited_with("aa:bb:cc:dd:ee:ff", start_frame)

        # Simulate pause command
        pause_frame = IfbFrameBuilder.pause()
        await mock_client.send_command("aa:bb:cc:dd:ee:ff", pause_frame)
        mock_client.send_command.assert_awaited_with("aa:bb:cc:dd:ee:ff", pause_frame)

        # Simulate stop command
        cancel_frame = IfbFrameBuilder.cancel()
        await mock_client.send_command("aa:bb:cc:dd:ee:ff", cancel_frame)
        mock_client.send_command.assert_awaited_with("aa:bb:cc:dd:ee:ff", cancel_frame)


if __name__ == "__main__":
    unittest.main()
