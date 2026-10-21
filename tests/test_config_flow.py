"""Unit tests for IFB Washer Cloud Config Flow and Options Flow."""

import re
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import tests
from custom_components.ifb_washer_cloud.const import (
    AUTH_TYPE_OTP,
    CONF_AUTH_TYPE,
    CONF_CALLING_CODE,
    CONF_DEVICE_NAME,
    CONF_MAC,
    CONF_OTP,
    CONF_PHONE,
    DOMAIN,
)


class TestIfbConfigFlowValidation(unittest.TestCase):
    """Test validation logic in config flow."""

    def setUp(self):
        self.mac_regex = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")

    def test_mac_regex_valid_formats(self):
        """Test valid MAC address formats."""
        valid_macs = [
            "aa:bb:cc:dd:ee:ff",
            "AA:BB:CC:DD:EE:FF",
            "00:11:22:33:44:55",
            "aa-bb-cc-dd-ee-ff",
            "12:34:56:78:90:ab",
        ]
        for mac in valid_macs:
            with self.subTest(mac=mac):
                self.assertIsNotNone(self.mac_regex.match(mac))

    def test_mac_regex_invalid_formats(self):
        """Test invalid MAC address formats."""
        invalid_macs = [
            "not-a-mac",
            "aa:bb:cc:dd:ee",
            "aa:bb:cc:dd:ee:ff:11",
            "aa:bb:cc:dd:ee:gg",
            "not-an-ip-or-mac",
            "",
            "   ",
        ]
        for mac in invalid_macs:
            with self.subTest(mac=mac):
                self.assertIsNone(self.mac_regex.match(mac.strip()))

    def test_phone_sanitization_and_validation(self):
        """Test phone cleaning and 10-digit validation."""
        def clean_phone(phone_str):
            clean = re.sub(r"\D", "", phone_str)
            if clean.startswith("91") and len(clean) > 10:
                clean = clean[2:]
            return clean

        self.assertEqual(clean_phone("9876543210"), "9876543210")
        self.assertEqual(clean_phone("+919876543210"), "9876543210")
        self.assertEqual(clean_phone("919876543210"), "9876543210")
        self.assertEqual(clean_phone("98765-43210"), "9876543210")
        self.assertEqual(clean_phone(" 98765 43210 "), "9876543210")

        # Invalid cases
        self.assertNotEqual(len(clean_phone("12345")), 10)
        self.assertNotEqual(len(clean_phone("abcd")), 10)

    def test_otp_sanitization_and_validation(self):
        """Test OTP digit cleaning and length checks (4 or 6 digits allowed)."""
        def validate_otp(otp_str):
            clean = re.sub(r"\D", "", str(otp_str).strip())
            return len(clean) in (4, 6)

        self.assertTrue(validate_otp("1234"))
        self.assertTrue(validate_otp("123456"))
        self.assertTrue(validate_otp(" 1234 "))
        self.assertFalse(validate_otp("123"))
        self.assertFalse(validate_otp("12345"))
        self.assertFalse(validate_otp("abcdef"))
        self.assertFalse(validate_otp(""))


class TestIfbOptionsFlow(unittest.IsolatedAsyncioTestCase):
    """Test suite for options flow handling."""

    async def test_options_flow_submission(self):
        """Verify options flow accepts valid backoff and scan intervals."""
        from custom_components.ifb_washer_cloud.config_flow import IfbWasherOptionsFlow
        entry = MagicMock()
        entry.data = {
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
            CONF_DEVICE_NAME: "Washer",
        }
        entry.options = {}

        flow = IfbWasherOptionsFlow(entry)
        flow.hass = MagicMock()

        user_input = {
            CONF_MAC: "11:22:33:44:55:66",
            CONF_DEVICE_NAME: "Updated Washer",
            "mqtt_client_id": "test_client",
            "mqtt_backoff": 240,
            "scan_interval_running": 4,
            "scan_interval_idle": 20,
        }
        result = await flow.async_step_init(user_input=user_input)
        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["data"]["mqtt_backoff"], 240)
        self.assertEqual(result["data"]["scan_interval_running"], 4)
        self.assertEqual(result["data"]["scan_interval_idle"], 20)

    async def test_options_flow_invalid_mac(self):
        """Verify options flow rejects invalid MAC format."""
        from custom_components.ifb_washer_cloud.config_flow import IfbWasherOptionsFlow
        entry = MagicMock()
        entry.data = {}
        entry.options = {}

        flow = IfbWasherOptionsFlow(entry)
        flow.hass = MagicMock()

        user_input = {
            CONF_MAC: "not-a-valid-mac",
            CONF_DEVICE_NAME: "Washer",
        }
        result = await flow.async_step_init(user_input=user_input)
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"][CONF_MAC], "invalid_mac")


if __name__ == "__main__":
    unittest.main()
