"""Comprehensive unit tests for IfbCloudClient async operations."""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from ifb_cloud.client import IfbApiError, IfbAuthError, IfbCloudClient
from ifb_cloud.const import MachineState
from ifb_cloud.models import IfbCycleProgress, IfbDevice


class TestIfbCloudClient(unittest.IsolatedAsyncioTestCase):
    """Test suite for IfbCloudClient async operations."""

    async def asyncSetUp(self):
        """Set up test client with mocked session."""
        self.mock_session = MagicMock()
        self.mock_session.closed = False
        self.client = IfbCloudClient(
            token="mock_test_token_12345",
            user_id="9876543210",
            session=self.mock_session,
        )

    async def asyncTearDown(self):
        """Clean up client session."""
        await self.client.close()

    async def test_auth_guard(self):
        """Verify client rejects API calls when unauthenticated."""
        unauth_session = MagicMock()
        unauth_session.closed = False
        unauth_client = IfbCloudClient(session=unauth_session)
        with self.assertRaises(IfbAuthError):
            await unauth_client.get_all_devices()
        await unauth_client.close()

    async def test_request_otp_success(self):
        """Verify request_otp sends correct GraphQL mutation and parses status."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "sendLoginOtp": {
                    "status": True,
                    "message": "OTP sent successfully"
                }
            }
        })
        self.mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

        res = await self.client.request_otp("9876543210")
        self.assertTrue(res.get("status"))

    async def test_verify_otp_success(self):
        """Verify verify_otp extracts Bearer token upon successful verification."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "verifyOtpAndLogin": {
                    "status": True,
                    "token": "new_mock_token_abc",
                    "isCustomerExist": True
                }
            }
        })
        self.mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

        res = await self.client.verify_otp("9876543210", "1234")
        self.assertEqual(self.client.token, "new_mock_token_abc")
        self.assertEqual(res.get("token"), "new_mock_token_abc")

    async def test_get_all_devices_graphql_catalog(self):
        """Verify get_all_devices correctly parses WiFi products from GraphQL."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "getRegisterAppliances": {
                    "products": [
                        {
                            "serial_no": "IFB00112233",
                            "custom_name": "My Washer",
                            "product": {"name": "Executive Plus", "sku": "IFB-WASH-01"},
                            "wifi_enabled": True,
                            "category": "Washer Dryer",
                            "mac": "aa:bb:cc:dd:ee:ff"
                        }
                    ]
                }
            }
        })
        self.mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

        devices = await self.client.get_all_devices()
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].mac, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(devices[0].name, "My Washer")

    async def test_get_all_devices_fallback_mac(self):
        """Verify get_all_devices links user-configured fallback_mac when cloud returns empty."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "getRegisterAppliances": {
                    "products": []
                }
            }
        })
        self.mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
        self.client._post_api = AsyncMock(return_value={"devices": []})

        devices = await self.client.get_all_devices(fallback_mac="aa:bb:cc:dd:ee:ff", fallback_name="Laundry Washer")
        self.assertEqual(len(devices), 1)
        self.assertEqual(devices[0].mac, "aa:bb:cc:dd:ee:ff")
        self.assertEqual(devices[0].name, "Laundry Washer")

    async def test_get_all_devices_empty_without_fallback(self):
        """Verify get_all_devices returns empty list when cloud is empty and no fallback provided."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "getRegisterAppliances": {
                    "products": []
                }
            }
        })
        self.mock_session.post = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))
        self.client._post_api = AsyncMock(return_value={"devices": []})

        devices = await self.client.get_all_devices(fallback_mac=None)
        self.assertEqual(len(devices), 0)

    async def test_get_device_progress_valid_telemetry(self):
        """Verify get_device_progress parses live telemetry response."""
        self.client._post_api = AsyncMock(return_value={
            "data": {
                "running": True,
                "state": "spinning",
                "program": 7,
                "timeRemaining": 12,
                "totalTime": 15,
                "rpm": 1200,
                "temp": 0,
                "doorLocked": True,
                "childLock": False,
                "dryMode": 0
            }
        })

        prog = await self.client.get_device_progress("aa:bb:cc:dd:ee:ff")
        self.assertTrue(prog.is_running)
        self.assertEqual(prog.state, MachineState.SPINNING)
        self.assertEqual(prog.motor_speed_rpm, 1200)

    async def test_get_device_progress_404_resilient_fallback(self):
        """Verify get_device_progress catches 404/non-JSON and returns Standby instead of crashing."""
        self.client._post_api = AsyncMock(side_effect=IfbApiError("Endpoint getUserDeviceProgress failed (404)"))

        prog = await self.client.get_device_progress("aa:bb:cc:dd:ee:ff")
        self.assertFalse(prog.is_running)
        self.assertEqual(prog.state, MachineState.STANDBY)
        self.assertEqual(prog.mac, "aa:bb:cc:dd:ee:ff")

    async def test_get_device_progress_invalid_mac(self):
        """Verify get_device_progress guards against invalid MAC syntax."""
        prog = await self.client.get_device_progress("not-a-mac")
        self.assertFalse(prog.is_running)
        self.assertEqual(prog.state, MachineState.STANDBY)

    async def test_send_command_invalid_mac(self):
        """Verify send_command rejects invalid MAC format with exception."""
        with self.assertRaises(IfbApiError):
            await self.client.send_command("invalid-mac", b"\x01\x02")


if __name__ == "__main__":
    unittest.main()
