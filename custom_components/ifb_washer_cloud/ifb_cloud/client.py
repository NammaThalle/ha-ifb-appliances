"""Async client for IFB Cloud API."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any, Dict, List, Optional

import aiohttp

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")

from .const import (
    API_V4_BASE_URL,
    DEFAULT_HEADERS,
    ENDPOINT_AUTH_GENERATE_TOKEN,
    ENDPOINT_AUTH_LOGIN,
    ENDPOINT_AUTH_VERIFY_OTP,
    ENDPOINT_CONNECT,
    ENDPOINT_DISCONNECT,
    ENDPOINT_GET_ALL_DEVICES,
    ENDPOINT_GET_DEVICE_META,
    ENDPOINT_GET_DEVICE_PROGRESS,
    ENDPOINT_GET_DEVICE_STATUS,
    ENDPOINT_GET_MODEL_SPECIFICATIONS,
    ENDPOINT_GET_MQTT_CLIENT,
    ENDPOINT_SEND_COMMAND,
    GRAPHQL_AUTH_URL,
    MAGENTO_BASE_URL,
    MachineState,
)
from .frame import IfbFrameBuilder
from .models import IfbCycleProgress, IfbDevice

_LOGGER = logging.getLogger(__name__)


class IfbError(Exception):
    """Base exception for IFB Cloud."""


class IfbAuthError(IfbError):
    """Authentication failure."""


class IfbConnectionError(IfbError):
    """Connection or network timeout."""


class IfbApiError(IfbError):
    """API responded with error payload."""


class IfbCloudClient:
    """Client for communicating with IFB Cloud backend."""

    def __init__(
        self,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        base_url: str = API_V4_BASE_URL,
    ) -> None:
        """Initialize the IFB Cloud client."""
        self._token: Optional[str] = token
        self._user_id: Optional[str] = user_id
        self._session: Optional[aiohttp.ClientSession] = session
        self._own_session: bool = session is None
        self._base_url: str = base_url.rstrip("/")

    @property
    def token(self) -> Optional[str]:
        """Return the active Bearer token."""
        return self._token

    @property
    def user_id(self) -> Optional[str]:
        """Return the active user identifier."""
        return self._user_id

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
            self._own_session = True
        return self._session

    async def close(self) -> None:
        """Close session if internally created."""
        if self._own_session and self._session and not self._session.closed:
            await self._session.close()

    def set_auth(self, token: str, user_id: Optional[str] = None) -> None:
        """Set authentication credentials directly."""
        self._token = token
        if user_id:
            self._user_id = user_id

    async def request_otp(
        self,
        phone: str,
        calling_code: str = "+91",
    ) -> Dict[str, Any]:
        """Request an OTP sent via SMS to the user's mobile number."""
        session = await self._get_session()
        clean_phone = re.sub(r"\D", "", phone)
        if clean_phone.startswith("91") and len(clean_phone) > 10:
            clean_phone = clean_phone[2:]

        query = """
        mutation SendLoginOtp($mobileNumber: String!) {
          sendLoginOtp(mobileNumber: $mobileNumber) {
            status
            message
          }
        }
        """
        payload = {
            "query": query,
            "variables": {
                "mobileNumber": clean_phone,
            },
        }
        headers = {
            "Content-Type": "application/json",
            "Store": "default",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU OS 18_0 like Mac OS X)",
        }
        try:
            async with session.post(
                GRAPHQL_AUTH_URL,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                if resp.status != 200:
                    raise IfbAuthError(f"OTP request failed with HTTP {resp.status}")

                errors = data.get("errors")
                if errors:
                    err_msg = errors[0].get("message") if isinstance(errors, list) and errors else "Unknown error"
                    raise IfbAuthError(f"OTP request failed: {err_msg}")

                result = data.get("data", {}).get("sendLoginOtp") or {}
                if not result.get("status"):
                    raise IfbAuthError(result.get("message") or "Failed to send OTP")
                return result
        except asyncio.TimeoutError as err:
            raise IfbConnectionError("Timeout while contacting OTP service") from err
        except aiohttp.ClientError as err:
            raise IfbConnectionError(f"Network error during OTP request: {err}") from err

    async def verify_otp(
        self,
        phone: str,
        otp: str,
        calling_code: str = "+91",
    ) -> Dict[str, Any]:
        """Verify the received OTP and extract Bearer token and user ID."""
        session = await self._get_session()
        clean_phone = re.sub(r"\D", "", phone)
        if clean_phone.startswith("91") and len(clean_phone) > 10:
            clean_phone = clean_phone[2:]

        otp_str = str(otp).strip()
        headers = {
            "Content-Type": "application/json",
            "Store": "default",
            "User-Agent": "Mozilla/5.0 (iPhone; CPU OS 18_0 like Mac OS X)",
        }

        # Try verifyOtpAndLogin (clean Adobe Commerce 4-digit OTP login)
        login_query = """
        mutation VerifyOtpAndLogin($input: verifyOtpInput!) {
          verifyOtpAndLogin(input: $input) {
            status
            message
            token
            isCustomerExist
          }
        }
        """
        login_payload = {
            "query": login_query,
            "variables": {
                "input": {
                    "mobileNumber": clean_phone,
                    "otp": otp_str,
                }
            },
        }

        token = None
        try:
            async with session.post(
                GRAPHQL_AUTH_URL,
                json=login_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                result = data.get("data", {}).get("verifyOtpAndLogin") or {}
                token = result.get("token")

                # If verifyOtpAndLogin didn't return a token and OTP is 6 digits, fallback to verifyAppOtp
                if not token and len(otp_str) == 6:
                    app_query = """
                    mutation VerifyAppOtp($input: AppVerifyOtpInput!) {
                      verifyAppOtp(input: $input) {
                        status
                        message
                        token
                      }
                    }
                    """
                    app_payload = {
                        "query": app_query,
                        "variables": {
                            "input": {
                                "callingCode": calling_code,
                                "userName": clean_phone,
                                "otp": otp_str,
                            }
                        },
                    }
                    async with session.post(
                        GRAPHQL_AUTH_URL,
                        json=app_payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as app_resp:
                        app_data = await app_resp.json()
                        app_result = app_data.get("data", {}).get("verifyAppOtp") or {}
                        token = app_result.get("token")
                        if not token:
                            err_list = app_data.get("errors") or data.get("errors") or []
                            msg = err_list[0].get("message") if err_list else (result.get("message") or "Invalid or expired OTP")
                            raise IfbAuthError(msg)
                elif not token:
                    err_list = data.get("errors") or []
                    msg = err_list[0].get("message") if err_list else (result.get("message") or "Invalid or expired OTP")
                    raise IfbAuthError(msg)

            self._token = str(token)
            self._user_id = clean_phone
            return {
                "token": self._token,
                "userId": self._user_id,
            }
        except asyncio.TimeoutError as err:
            raise IfbConnectionError("Timeout while contacting OTP verification service") from err
        except aiohttp.ClientError as err:
            raise IfbConnectionError(f"Network error during OTP verification: {err}") from err

    async def login_with_password(
        self,
        phone_or_email: str,
        password: str,
        calling_code: str = "+91",
    ) -> Dict[str, Any]:
        """Authenticate using mobile number or email and password."""
        session = await self._get_session()
        is_email = "@" in phone_or_email

        if is_email:
            payload = {
                "method": "mail",
                "username": phone_or_email,
                "password": password,
                "quote_id": "",
            }
        else:
            clean_phone = re.sub(r"\D", "", phone_or_email)
            if clean_phone.startswith("91") and len(clean_phone) > 10:
                clean_phone = clean_phone[2:]
            payload = {
                "method": "phonepass",
                "callingCode": calling_code,
                "phonenumber": clean_phone,
                "password": password,
            }

        url = f"{MAGENTO_BASE_URL}/{ENDPOINT_AUTH_LOGIN}"
        try:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                if resp.status != 200 or not data.get("status", True):
                    msg = data.get("message") or f"Login failed with HTTP {resp.status}"
                    raise IfbAuthError(msg)

                # Extract token and user identifier
                token = data.get("token") or data.get("authToken") or data.get("data", {}).get("token")
                user_id = data.get("userId") or data.get("customerId") or data.get("data", {}).get("userId")
                
                if not token:
                    raise IfbAuthError("Login succeeded but no token received in payload")

                self._token = str(token)
                self._user_id = str(user_id) if user_id else None
                return data

        except asyncio.TimeoutError as err:
            raise IfbConnectionError("Timeout while contacting authentication service") from err
        except aiohttp.ClientError as err:
            raise IfbConnectionError(f"Network error during login: {err}") from err

    async def _post_api(self, endpoint: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send authenticated POST request to API v4."""
        if not self._token:
            raise IfbAuthError("Missing Bearer authorization token. Please login first.")

        session = await self._get_session()
        url = f"{self._base_url}/{endpoint}"
        headers = {
            **DEFAULT_HEADERS,
            "Authorization": f"Bearer {self._token}",
        }

        body = payload or {}
        if self._user_id and "userId" not in body:
            body["userId"] = self._user_id

        try:
            async with session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 401 or resp.status == 403:
                    raise IfbAuthError(f"Authorization expired or invalid ({resp.status})")

                text = await resp.text()
                try:
                    data = await resp.json()
                except Exception:
                    clean_text = text[:60].replace("\n", " ").strip()
                    raise IfbApiError(f"Invalid non-JSON response from {endpoint}: {clean_text}")

                if resp.status != 200:
                    raise IfbApiError(f"Endpoint {endpoint} failed with HTTP {resp.status}")

                return data

        except asyncio.TimeoutError as err:
            raise IfbConnectionError(f"Timeout while calling {endpoint}") from err
        except aiohttp.ClientError as err:
            raise IfbConnectionError(f"Network error connecting to {endpoint}: {err}") from err

    async def get_all_devices(
        self,
        fallback_mac: Optional[str] = None,
        fallback_name: Optional[str] = None,
    ) -> List[IfbDevice]:
        """Fetch all registered appliances for the account."""
        if not self._token:
            raise IfbAuthError("Client is not authenticated. Please login or set token first.")

        session = await self._get_session()
        device_list: List[IfbDevice] = []

        # 1. Query GraphQL getRegisterAppliances if token is available
        if self._token:
            headers = {
                "Content-Type": "application/json",
                "Store": "default",
                "Authorization": f"Bearer {self._token}",
                "User-Agent": "Mozilla/5.0 (iPhone; CPU OS 18_0 like Mac OS X)",
            }
            query = """
            query GetRegisterAppliances {
              getRegisterAppliances {
                message
                mobileValidation
                products {
                  serial_no
                  custom_name
                  product {
                    name
                    sku
                  }
                  sku
                  category
                  type
                  wifi_enabled
                  status
                }
              }
            }
            """
            try:
                async with session.post(
                    GRAPHQL_AUTH_URL,
                    json={"query": query},
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        products = (
                            data.get("data", {})
                            .get("getRegisterAppliances", {})
                            .get("products")
                            or []
                        )
                        for p in products:
                            if isinstance(p, dict):
                                s_no = p.get("serial_no") or p.get("sku")
                                p_prod = p.get("product") if isinstance(p.get("product"), dict) else {}
                                p_name = p_prod.get("name") or "IFB Washer Dryer"
                                name = p.get("custom_name") or p_name
                                model = p_name or p.get("sku") or "IFB Appliance"
                                is_wifi = bool(p.get("wifi_enabled"))
                                cat_str = str(p.get("category") or "").lower()

                                if is_wifi or "washer" in name.lower() or "washer" in model.lower() or "laundry" in cat_str:
                                    dev_mac = str(p.get("mac") or p.get("wifi_mac") or p.get("macAddress") or fallback_mac or s_no or "").strip().lower()
                                    if dev_mac:
                                        device_list.append(
                                            IfbDevice(
                                                mac=dev_mac,
                                                name=name,
                                                model_name=model,
                                                device_id=str(s_no) if s_no else dev_mac,
                                                serial_number=str(s_no) if s_no else None,
                                                category=p.get("category") or "Washer Dryer",
                                                is_online=True,
                                                hardware_type="esp",
                                                raw_data=p,
                                            )
                                        )
            except Exception as err:
                _LOGGER.debug("GraphQL getRegisterAppliances error: %s", err)

        # 2. Check legacy API endpoint if still empty
        if not device_list:
            try:
                resp = await self._post_api(ENDPOINT_GET_ALL_DEVICES)
                raw_devices = resp.get("devices") or resp.get("data") or resp.get("deviceList") or []
                if isinstance(raw_devices, list):
                    for d in raw_devices:
                        if isinstance(d, dict):
                            device_list.append(IfbDevice.from_api_dict(d))
            except Exception as err:
                _LOGGER.debug("Legacy getAllDevices error: %s", err)

        # 3. If cloud does not list IoT appliances but user configured a MAC address, link it
        if not device_list and fallback_mac:
            clean_mac = fallback_mac.strip().lower()
            device_list.append(
                IfbDevice(
                    mac=clean_mac,
                    name=fallback_name or "IFB Washer Dryer",
                    model_name="IFB Appliance",
                    device_id=clean_mac,
                    serial_number=clean_mac,
                    category="Washer Dryer",
                    is_online=True,
                    hardware_type="esp",
                    raw_data={},
                )
            )

        return device_list

    async def get_device_progress(self, mac: str) -> IfbCycleProgress:
        """Fetch current telemetry and cycle progress for appliance."""
        clean_mac = mac.strip().lower()
        if not MAC_REGEX.match(clean_mac):
            _LOGGER.debug("Invalid MAC address syntax: %s", mac)
            return IfbCycleProgress(mac=clean_mac, is_running=False, state=MachineState.STANDBY)
        try:
            resp = await self._post_api(ENDPOINT_GET_DEVICE_PROGRESS, {"mac": clean_mac})
            progress_data = resp.get("data") or resp.get("progress") or resp
            return IfbCycleProgress.from_api_dict(clean_mac, progress_data)
        except Exception as err:
            _LOGGER.debug("Could not fetch device progress from cloud for %s: %s", clean_mac, err)
            return IfbCycleProgress(mac=clean_mac, is_running=False, state=MachineState.STANDBY)

    async def get_device_status(self, mac: str) -> Dict[str, Any]:
        """Check live connectivity status of appliance."""
        clean_mac = mac.strip().lower()
        if not MAC_REGEX.match(clean_mac):
            return {"status": "offline", "isOnline": False}
        try:
            return await self._post_api(ENDPOINT_GET_DEVICE_STATUS, {"mac": clean_mac})
        except Exception as err:
            _LOGGER.debug("Could not fetch device status for %s: %s", clean_mac, err)
            return {"status": "online", "isOnline": True}

    async def get_model_specifications(self, model_name: str) -> Dict[str, Any]:
        """Fetch programs and hardware limits catalog for model."""
        return await self._post_api(ENDPOINT_GET_MODEL_SPECIFICATIONS, {"model": model_name})

    async def send_command(self, mac: str, command_bytes: bytes) -> Dict[str, Any]:
        """Transmit binary control frame to appliance via cloud MQTT bridge."""
        clean_mac = mac.strip().lower()
        if not MAC_REGEX.match(clean_mac):
            raise IfbApiError(f"Invalid MAC address format: {mac}")
        payload = {
            "mac": clean_mac,
            "message": list(command_bytes),
        }
        return await self._post_api(ENDPOINT_SEND_COMMAND, payload)

    async def start(self, mac: str, program: int = 1, temp: int = 2, spin: int = 4, dry: int = 0) -> Dict[str, Any]:
        """Send Start cycle command."""
        frame = IfbFrameBuilder.start(program=program, temp=temp, spin=spin, dry=dry)
        return await self.send_command(mac, frame)

    async def pause(self, mac: str) -> Dict[str, Any]:
        """Send Pause cycle command."""
        frame = IfbFrameBuilder.pause()
        return await self.send_command(mac, frame)

    async def cancel(self, mac: str) -> Dict[str, Any]:
        """Send Cancel / Off command."""
        frame = IfbFrameBuilder.cancel()
        return await self.send_command(mac, frame)
