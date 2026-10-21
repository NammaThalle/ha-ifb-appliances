"""Unit tests for IFB Washer Cloud diagnostics platform."""

import unittest
from unittest.mock import MagicMock
from datetime import timedelta

import tests
from custom_components.ifb_washer_cloud.const import DOMAIN
from custom_components.ifb_washer_cloud.diagnostics import async_get_config_entry_diagnostics
from ifb_cloud.const import MachineState
from ifb_cloud.models import IfbCycleProgress, IfbDevice


class TestIfbDiagnostics(unittest.IsolatedAsyncioTestCase):
    """Test suite for diagnostics data export and redaction."""

    async def test_diagnostics_export_and_redaction(self):
        """Verify diagnostics dump redacts credentials and includes coordinator telemetry."""
        hass = MagicMock()
        entry = MagicMock()
        entry.entry_id = "test_entry_123"
        entry.title = "IFB Cloud (Senator)"
        entry.unique_id = "ifb_cloud_test_user"
        entry.data = {
            "token": "secret_bearer_token",
            "password": "secret_password",
            "phone": "9876543210",
            "user_id": "usr_9988",
            "mqtt_client_id": "client_abc_123",
        }
        entry.options = {
            "mqtt_backoff": 120,
            "scan_interval_running": 5,
            "scan_interval_idle": 15,
        }

        client = MagicMock()
        client.token = "secret_bearer_token"
        client._mqtt_listener_active = True
        client._phone_app_active_until = 0.0
        client._phone_app_backoff = 120.0

        device = IfbDevice(
            mac="aa:bb:cc:dd:ee:ff",
            name="Senator Smart Washer",
            model_name="Senator Smart",
            category="Washer Dryer",
            hardware_type="esp",
            firmware_version="v2.1",
            is_online=True,
            serial_number="IFB12345678",
        )
        devices = {"aa:bb:cc:dd:ee:ff": device}

        progress = IfbCycleProgress(
            mac="aa:bb:cc:dd:ee:ff",
            is_running=True,
            state=MachineState.MAIN_WASH,
            program_code=14,
            program_name="Express 15'",
            time_remaining_minutes=12,
            total_time_minutes=15,
            progress_percentage=20,
            motor_speed_rpm=800,
            water_temperature_c=40,
            selected_spin_speed="800 RPM",
            selected_temperature="40°C",
            selected_dry_mode="No Dry",
            door_locked=True,
            water_level_frequency=2550,
            tub_clean_reminder=False,
            error_code=None,
            error_description="None",
            raw_data={"state_code": 2},
        )

        coordinator = MagicMock()
        coordinator.data = {"aa:bb:cc:dd:ee:ff": progress}
        coordinator.last_update_success = True
        coordinator.update_interval = timedelta(seconds=5)

        hass.data = {
            DOMAIN: {
                "test_entry_123": {
                    "coordinator": coordinator,
                    "devices": devices,
                    "client": client,
                }
            }
        }

        diag = await async_get_config_entry_diagnostics(hass, entry)

        self.assertIn("entry", diag)
        self.assertIn("client", diag)
        self.assertIn("coordinator", diag)
        self.assertIn("devices", diag)
        self.assertIn("telemetry", diag)

        # Verify sensitive fields are redacted
        self.assertEqual(diag["entry"]["data"]["token"], "**REDACTED**")
        self.assertEqual(diag["entry"]["data"]["password"], "**REDACTED**")
        self.assertEqual(diag["entry"]["data"]["phone"], "**REDACTED**")
        self.assertEqual(diag["entry"]["data"]["user_id"], "**REDACTED**")
        self.assertEqual(diag["entry"]["data"]["mqtt_client_id"], "**REDACTED**")

        # Verify client and coordinator state
        self.assertTrue(diag["client"]["is_connected"])
        self.assertTrue(diag["client"]["mqtt_listener_active"])
        self.assertEqual(diag["client"]["phone_app_backoff"], 120.0)
        self.assertEqual(diag["coordinator"]["update_interval_seconds"], 5.0)

        # Verify device telemetry details
        device_telemetry = list(diag["telemetry"].values())[0]
        self.assertTrue(device_telemetry["is_running"])
        self.assertEqual(device_telemetry["program_name"], "Express 15'")
        self.assertEqual(device_telemetry["water_level_frequency"], 2550)
        self.assertFalse(device_telemetry["tub_clean_reminder"])


if __name__ == "__main__":
    unittest.main()
