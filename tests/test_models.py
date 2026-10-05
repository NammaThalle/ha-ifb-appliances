"""Unit tests for IFB Cloud data models."""

import unittest
from ifb_cloud.const import MachineState
from ifb_cloud.models import IfbCycleProgress, IfbDevice


class TestIfbModels(unittest.TestCase):
    """Test suite for data models."""

    def test_device_from_api_dict_esp(self):
        """Verify ESP module detection from API dictionary."""
        data = {
            "mac": "AA:BB:CC:DD:EE:FF",
            "name": "Front Load Washer",
            "model": "Senator Plus",
            "serialNumber": "IFB99887766",
            "isOnline": True,
            "category": "Washing Machine",
        }
        dev = IfbDevice.from_api_dict(data)
        self.assertEqual(dev.mac, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(dev.name, "Front Load Washer")
        self.assertEqual(dev.model_name, "Senator Plus")
        self.assertEqual(dev.serial_number, "IFB99887766")
        self.assertTrue(dev.is_online)
        self.assertEqual(dev.hardware_type, "esp")

    def test_device_from_api_dict_gainspan(self):
        """Verify GainSpan module detection based on OUI prefix 20:f8:5e."""
        data = {
            "mac": "20:F8:5E:11:22:33",
            "name": "Legacy Washer",
            "model": "Elena",
            "isOnline": False,
        }
        dev = IfbDevice.from_api_dict(data)
        self.assertEqual(dev.mac, "20:f8:5e:11:22:33")
        self.assertEqual(dev.hardware_type, "gainspan")
        self.assertFalse(dev.is_online)

    def test_cycle_progress_parsing(self):
        """Verify complete parsing of telemetry dictionary."""
        data = {
            "running": True,
            "state": "washing",
            "program": 1,
            "timeRemaining": 35,
            "totalTime": 60,
            "rpm": 1000,
            "temp": 40,
            "doorLocked": True,
            "childLock": False,
            "dryMode": 0,
        }
        prog = IfbCycleProgress.from_api_dict("aa:bb:cc:dd:ee:ff", data)
        self.assertEqual(prog.mac, "aa:bb:cc:dd:ee:ff")
        self.assertTrue(prog.is_running)
        self.assertEqual(prog.state, MachineState.MAIN_WASH)
        self.assertEqual(prog.program_name, "Mix / Daily")
        self.assertEqual(prog.time_remaining_minutes, 35)
        self.assertEqual(prog.total_time_minutes, 60)
        self.assertEqual(prog.progress_percentage, 41)
        self.assertEqual(prog.motor_speed_rpm, 1000)
        self.assertEqual(prog.water_temperature_c, 40)
        self.assertTrue(prog.door_locked)

    def test_cycle_progress_defaults(self):
        """Verify default values when telemetry payload is empty or standby."""
        prog = IfbCycleProgress(mac="aa:bb:cc:dd:ee:ff")
        self.assertFalse(prog.is_running)
        self.assertEqual(prog.state, MachineState.STANDBY)
        self.assertEqual(prog.program_name, "Standby")
        self.assertEqual(prog.time_remaining_minutes, 0)
        self.assertEqual(prog.progress_percentage, 0)


if __name__ == "__main__":
    unittest.main()
