"""Async client for IFB Cloud API."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from typing import Any, Dict, List, Optional, Union

import aiohttp

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")

from .const import (
    API_V5_BASE_URL,
    API_V4_BASE_URL,
    DEFAULT_BASE_URL,
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
    ENDPOINT_GET_RESPONSE,
    ENDPOINT_SEND_COMMAND,
    GRAPHQL_AUTH_URL,
    MAGENTO_BASE_URL,
    MachineState,
    MQTT_ESP_HOST,
    MQTT_ESP_PORT,
    MQTT_GAINSPAN_HOST,
    MQTT_GAINSPAN_PORT,
)
from .frame import IfbFrameBuilder, decode_frame
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
        cloud_token: Optional[str] = None,
        mqtt_client_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[aiohttp.ClientSession] = None,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        """Initialize the IFB Cloud client."""
        self._token: Optional[str] = token
        self._cloud_token: Optional[str] = cloud_token
        # mqtt_client_id is the server-assigned UUID from mapping/client endpoint.
        # It is NOT the MAC address — using the MAC as client_id causes a
        # "client ID collision" that kicks the physical washer offline.
        self._mqtt_client_id: Optional[str] = mqtt_client_id
        self._user_id: Optional[str] = user_id
        self._session: Optional[aiohttp.ClientSession] = session
        self._own_session: bool = session is None
        self._base_url: str = base_url.rstrip("/")
        self._device_serials: Dict[str, str] = {}

    @property
    def token(self) -> Optional[str]:
        """Return the active Bearer token."""
        return self._token

    @property
    def user_id(self) -> Optional[str]:
        """Return the active user identifier."""
        return self._user_id

    @property
    def mqtt_client_id(self) -> Optional[str]:
        """Return the server-assigned MQTT client ID."""
        return self._mqtt_client_id

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

        # Try verifyAppOtp first to get both token and cloudData (AWS token)
        app_query = f"""mutation {{
          verifyAppOtp(input: {{
            callingCode: "{calling_code}",
            userName: "{clean_phone}",
            otp: "{otp_str}"
          }}) {{
            status
            message
            token
            cloudData
          }}
        }}"""
        app_payload = {"query": app_query}

        token = None
        cloud_token = None
        try:
            async with session.post(
                GRAPHQL_AUTH_URL,
                json=app_payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as app_resp:
                app_data = await app_resp.json()
                app_result = app_data.get("data", {}).get("verifyAppOtp") or {}
                token = app_result.get("token")
                raw_cloud = app_result.get("cloudData")
                if raw_cloud:
                    try:
                        parsed_cloud = json.loads(raw_cloud) if isinstance(raw_cloud, str) else raw_cloud
                        cloud_token = (
                            parsed_cloud.get("data", {}).get("token", {}).get("token")
                            or parsed_cloud.get("token", {}).get("token")
                            or parsed_cloud.get("token")
                        )
                    except Exception as parse_err:
                        _LOGGER.debug("Could not parse cloudData JSON: %s", parse_err)

                # Fallback to verifyOtpAndLogin if verifyAppOtp didn't yield token
                if not token:
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
                    async with session.post(
                        GRAPHQL_AUTH_URL,
                        json=login_payload,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=15),
                    ) as resp:
                        data = await resp.json()
                        result = data.get("data", {}).get("verifyOtpAndLogin") or {}
                        token = result.get("token")
                        if not token:
                            err_list = app_data.get("errors") or data.get("errors") or []
                            msg = err_list[0].get("message") if err_list else "Invalid or expired OTP"
                            raise IfbAuthError(msg)

            self._token = str(token)
            if cloud_token:
                self._cloud_token = str(cloud_token)
            self._user_id = clean_phone
            return {
                "token": self._token,
                "cloudToken": self._cloud_token,
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

    async def fetch_mqtt_client_id(self) -> Optional[str]:
        """Fetch a server-assigned MQTT client ID from the mapping/client endpoint.

        The app (AppliancesFragment.checkAndGenerateMqttClientId) calls POST
        /api/v4/mapping/client with just the Bearer token — no body.  The server
        returns:
            { "status": true, "statusCode": 200, "message": "...",
              "data": { "clientID": "<uuid-string>" } }

        Using this UUID as the MQTT client_id avoids colliding with the
        washer's own connection (which uses the MAC as its client_id).
        """
        if not self._token:
            return None
        try:
            session = await self._get_session()
            url = f"{self._base_url}/{ENDPOINT_GET_MQTT_CLIENT}"
            headers = {
                **DEFAULT_HEADERS,
                "Authorization": f"Bearer {self._token}",
            }
            async with session.post(
                url,
                headers=headers,
                json={},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status not in (200, 201):
                    _LOGGER.debug("mapping/client returned HTTP %s", resp.status)
                    return None
                data = await resp.json()
                client_id = (
                    data.get("data", {}).get("clientID")
                    or data.get("data", {}).get("clientId")
                    or data.get("clientID")
                    or data.get("clientId")
                )
                if client_id:
                    self._mqtt_client_id = str(client_id)
                    _LOGGER.debug("Fetched server-assigned MQTT client_id: %s", self._mqtt_client_id)
                return self._mqtt_client_id
        except Exception as err:
            _LOGGER.debug("Could not fetch MQTT client ID: %s", err)
            return None

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
        if self._user_id and "userId" not in body and "api/v4" in self._base_url:
            body["userId"] = self._user_id

        try:
            async with session.post(url, json=body, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 401 or resp.status == 403:
                    raise IfbAuthError(f"Authorization expired or invalid ({resp.status})")

                text = await resp.text()
                try:
                    data = await resp.json()
                except Exception:
                    clean_text = text[:100].replace("\n", " ").strip()
                    if resp.status == 200:
                        return {"status": True, "message": clean_text, "data": clean_text}
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
        fallback_serial: Optional[str] = None,
    ) -> List[IfbDevice]:
        """Fetch all registered appliances for the account."""
        if not self._token:
            raise IfbAuthError("Client is not authenticated. Please login or set token first.")

        session = await self._get_session()
        device_list: List[IfbDevice] = []
        products: list[dict[str, Any]] = []

        # 1. Primary: Query v5 device/all endpoint (returns live IoT appliances with MAC and status)
        try:
            resp = await self._post_api(ENDPOINT_GET_ALL_DEVICES, {})
            raw_devices = resp.get("data") or resp.get("devices") or resp.get("deviceList") or []
            if isinstance(raw_devices, list):
                for d in raw_devices:
                    if isinstance(d, dict):
                        dev_mac = str(d.get("mac") or "").strip().lower()
                        app_type = str(d.get("applianceType") or "").upper()
                        conn = str(d.get("connectivity") or "")
                        if dev_mac and (conn == "WiFi" or "WASHER" in app_type or "DRYER" in app_type):
                            dev = IfbDevice.from_api_dict(d)
                            if dev.serial_number:
                                self._device_serials[dev.mac] = dev.serial_number
                            device_list.append(dev)
        except Exception as err:
            _LOGGER.debug("device/all API error: %s", err)

        # 2. Fallback: Query GraphQL getRegisterAppliances if device/all returned no IoT devices
        if not device_list:
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
                                        if s_no:
                                             self._device_serials[dev_mac] = str(s_no)
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

        # 3. Fallback: If cloud does not list IoT appliances but user configured a MAC address, link it
        if not device_list and fallback_mac:
            clean_mac = fallback_mac.strip().lower()
            first_serial = next(
                (str(p.get("serial_no")) for p in products if isinstance(p, dict) and p.get("serial_no")),
                fallback_serial,
            )
            if first_serial:
                self._device_serials[clean_mac] = first_serial
            device_list.append(
                IfbDevice(
                    mac=clean_mac,
                    name=fallback_name or "IFB Washer Dryer",
                    model_name="IFB Appliance",
                    device_id=clean_mac,
                    serial_number=first_serial or clean_mac,
                    category="Washer Dryer",
                    is_online=True,
                    hardware_type="esp",
                    raw_data={},
                )
            )

        return device_list

    async def get_device_progress(self, mac: str) -> IfbCycleProgress:
        """Fetch current telemetry for appliance."""
        clean_mac = mac.strip().lower()
        if not MAC_REGEX.match(clean_mac):
            _LOGGER.debug("Invalid MAC address syntax: %s", mac)
            return IfbCycleProgress(mac=clean_mac, is_running=False, state=MachineState.STANDBY)

        serial_no = self._device_serials.get(clean_mac)

        # 0. High-fidelity: Query physical appliance directly via MQTT CMD_READ_STATE
        if self._mqtt_client_id:
            try:
                live_progress = await self.read_machine_state(clean_mac, serial=serial_no, timeout=2.0)
                if live_progress is not None:
                    return live_progress
            except Exception as err:
                _LOGGER.debug("Direct MQTT state query failed for %s: %s", clean_mac, err)

        # 1. Primary: Query v5 device/smart/progress
        try:
            body = {"serial": serial_no} if serial_no else {}
            resp = await self._post_api(ENDPOINT_GET_DEVICE_PROGRESS, body)
            data_list = resp.get("data") or resp.get("progress") or []
            if isinstance(data_list, dict):
                data_list = [data_list]
            if isinstance(data_list, list) and data_list:
                item = next(
                    (d for d in data_list if isinstance(d, dict) and (d.get("serial") == serial_no or str(d.get("mac", "")).lower() == clean_mac)),
                    data_list[0] if isinstance(data_list[0], dict) else None,
                )
                if item and isinstance(item, dict):
                    # Enrich with device/all state if available
                    try:
                        all_resp = await self._post_api(ENDPOINT_GET_ALL_DEVICES, {})
                        for d in (all_resp.get("data") or []):
                            if isinstance(d, dict) and (str(d.get("mac", "")).lower() == clean_mac or d.get("serial") == serial_no):
                                item = {**d, **item}
                                break
                    except Exception:
                        pass
                    return IfbCycleProgress.from_api_dict(clean_mac, item)
        except Exception as err:
            _LOGGER.debug("device/smart/progress query error for %s: %s", clean_mac, err)

        # 2. Binary frame via getResponse if supported
        try:
            resp = await self._post_api(ENDPOINT_GET_RESPONSE, {"mac": clean_mac})
            raw_data = resp.get("data") or {}
            response_field = raw_data.get("response")
            if response_field:
                frame_bytes: Optional[bytes] = None
                if isinstance(response_field, (list, tuple)):
                    frame_bytes = bytes(int(b) & 0xFF for b in response_field)
                elif isinstance(response_field, str):
                    try:
                        frame_bytes = base64.b64decode(response_field)
                    except Exception:
                        pass
                elif isinstance(response_field, bytes):
                    frame_bytes = response_field

                if frame_bytes:
                    decoded = decode_frame(frame_bytes)
                    if decoded is not None:
                        return IfbCycleProgress.from_decoded_frame(clean_mac, decoded)
        except Exception as err:
            _LOGGER.debug("getResponse binary path failed for %s: %s", clean_mac, err)

        # 3. Fallback: device/all directly
        try:
            resp = await self._post_api(ENDPOINT_GET_ALL_DEVICES, {})
            for d in (resp.get("data") or []):
                if isinstance(d, dict) and (str(d.get("mac", "")).lower() == clean_mac or d.get("serial") == serial_no):
                    return IfbCycleProgress.from_api_dict(clean_mac, d)
        except Exception as err:
            _LOGGER.debug("device/all fallback failed for %s: %s", clean_mac, err)

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

    def _resolve_mqtt_credentials(self, clean_mac: str) -> tuple[str, str, str]:
        """Return (client_id, username, password) for MQTT connection.

        From decompiled app (MainActivity.makeMqttConnection):
          - client_id = server-assigned UUID from mapping/client (stored as mqtt_clientId
            in SharedPreferences).  NEVER the MAC — using MAC causes a client-ID collision
            that evicts the physical washer from the broker.
          - username  = device serial number (str2 = deviceDetail.getSerial())
          - password  = authToken (Bearer token)

        If no server-assigned client_id is available yet, we generate a safe
        fallback that still avoids collision by prefixing with "HA_" so the broker
        policy (which only grants the MAC's own client_id to the washer) does not
        kick our connection.
        """
        # Client ID: server-assigned UUID, or safe fallback
        if self._mqtt_client_id:
            client_id = self._mqtt_client_id
        else:
            # Fallback: use a stable but non-MAC identifier so we don't collide
            import hashlib
            h = hashlib.md5((self._user_id or clean_mac).encode()).hexdigest()[:12]
            client_id = f"HA_{h}"
            _LOGGER.warning(
                "No server-assigned MQTT client_id available for %s. "
                "Using fallback '%s'. Call fetch_mqtt_client_id() first for reliable operation.",
                clean_mac, client_id,
            )

        # Username: serial number (confirmed from Washscreenfragment.attemptReConnection)
        username = self._device_serials.get(clean_mac) or clean_mac

        # Password: Bearer token
        password = self._cloud_token or self._token or ""

        return client_id, username, password

    async def send_command(
        self,
        mac: str,
        command_bytes: Union[bytes, List[bytes]],
        serial: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Transmit binary control frame(s) to appliance via Cloud MQTT broker."""
        clean_mac = mac.strip().lower()
        if not MAC_REGEX.match(clean_mac):
            raise IfbApiError(f"Invalid MAC address format: {mac}")

        if serial:
            self._device_serials[clean_mac] = serial

        def _publish_mqtt() -> Dict[str, Any]:
            import ssl
            import time
            import paho.mqtt.client as mqtt

            client_id, username, password = self._resolve_mqtt_credentials(clean_mac)

            # GainSpan (older) -> mqtt2:8883; ESP32 (newer) -> mqttesp:8887
            mac_oui = clean_mac[:8].lower()
            if mac_oui == "20:f8:5e":
                endpoints = [(MQTT_GAINSPAN_HOST, MQTT_GAINSPAN_PORT)]
            else:
                endpoints = [(MQTT_ESP_HOST, MQTT_ESP_PORT), (MQTT_GAINSPAN_HOST, MQTT_GAINSPAN_PORT)]

            frames = command_bytes if isinstance(command_bytes, list) else [command_bytes]
            total_bytes = sum(len(f) for f in frames)

            last_err = None
            for host, port in endpoints:
                client = None
                try:
                    try:
                        client = mqtt.Client(
                            mqtt.CallbackAPIVersion.VERSION2,
                            client_id=client_id,
                        )
                    except Exception:
                        client = mqtt.Client(client_id=client_id)

                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    client.tls_set_context(ctx)
                    client.username_pw_set(username, password)

                    connected = [False]
                    published = [False]
                    conn_rc = [None]
                    topic = f"Command/{clean_mac}"
                    resp_topic = f"Response/{clean_mac}"

                    def on_connect(c, userdata, flags, rc, props=None):
                        conn_rc[0] = rc
                        if (hasattr(rc, "is_failure") and not rc.is_failure) or rc == 0:
                            connected[0] = True
                            try:
                                c.subscribe(resp_topic, qos=0)
                            except Exception as sub_err:
                                _LOGGER.debug("Could not subscribe to Response topic: %s", sub_err)
                            for f_idx, frame in enumerate(frames):
                                _LOGGER.info(
                                    "[IFB Cloud] Connected to %s:%s (client_id=%s, user=%s). "
                                    "Publishing frame %d/%d (%d bytes, qos=0) to %s: %s",
                                    host, port, client_id, username,
                                    f_idx + 1, len(frames), len(frame),
                                    topic, list(frame),
                                )
                                c.publish(topic, frame, qos=0, retain=False)
                                if f_idx < len(frames) - 1:
                                    time.sleep(0.3)
                            published[0] = True

                    client.on_connect = on_connect

                    _LOGGER.debug(
                        "Connecting to IFB MQTT %s:%s (client_id=%s, user=%s)",
                        host, port, client_id, username,
                    )
                    client.connect(host, port, keepalive=10)
                    client.loop_start()

                    wait_timeout = 3.0 + len(frames) * 0.5
                    start_t = time.time()
                    while time.time() - start_t < wait_timeout:
                        if published[0] or (conn_rc[0] is not None and conn_rc[0] != 0):
                            break
                        time.sleep(0.05)

                    time.sleep(0.2)
                    client.loop_stop()
                    client.disconnect()

                    if not connected[0] or not published[0]:
                        last_err = f"Failed to publish on {host}:{port}: conn_rc={conn_rc[0]}"
                        continue

                    return {
                        "status": "success",
                        "broker": f"{host}:{port}",
                        "topic": topic,
                        "bytes": total_bytes,
                        "frames": len(frames),
                    }
                except Exception as ex:
                    last_err = str(ex)
                    _LOGGER.warning("MQTT transmission error on %s:%s: %s", host, port, ex)
                finally:
                    if client is not None:
                        try:
                            client.loop_stop()
                            client.disconnect()
                        except Exception:
                            pass

            raise IfbConnectionError(
                f"Failed to publish command to {clean_mac} via any broker. Last error: {last_err}"
            )

        return await asyncio.to_thread(_publish_mqtt)

    async def read_machine_state(
        self,
        mac: str,
        serial: Optional[str] = None,
        timeout: float = 2.0,
    ) -> Optional[IfbCycleProgress]:
        """Request live machine state via MQTT CMD_READ_STATE and await binary telemetry response."""
        clean_mac = mac.strip().lower()
        if not MAC_REGEX.match(clean_mac):
            return None

        if serial:
            self._device_serials[clean_mac] = serial

        def _query_mqtt() -> Optional[IfbCycleProgress]:
            import ssl
            import time
            import paho.mqtt.client as mqtt

            client_id, username, password = self._resolve_mqtt_credentials(clean_mac)

            mac_oui = clean_mac[:8].lower()
            if mac_oui == "20:f8:5e":
                endpoints = [(MQTT_GAINSPAN_HOST, MQTT_GAINSPAN_PORT)]
            else:
                endpoints = [(MQTT_ESP_HOST, MQTT_ESP_PORT), (MQTT_GAINSPAN_HOST, MQTT_GAINSPAN_PORT)]

            cmd_frame = IfbFrameBuilder.read_state()
            topic = f"Command/{clean_mac}"
            resp_topic = f"Response/{clean_mac}"

            for host, port in endpoints:
                client = None
                try:
                    try:
                        client = mqtt.Client(
                            mqtt.CallbackAPIVersion.VERSION2,
                            client_id=client_id,
                        )
                    except Exception:
                        client = mqtt.Client(client_id=client_id)

                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    client.tls_set_context(ctx)
                    client.username_pw_set(username, password)

                    received_progress: list[Optional[IfbCycleProgress]] = [None]
                    connected = [False]

                    def on_connect(c, userdata, flags, rc, props=None):
                        if (hasattr(rc, "is_failure") and not rc.is_failure) or rc == 0:
                            connected[0] = True
                            c.subscribe(resp_topic, qos=0)
                            c.publish(topic, cmd_frame, qos=0, retain=False)

                    def on_message(c, userdata, msg):
                        try:
                            decoded = decode_frame(msg.payload)
                            if decoded is not None:
                                received_progress[0] = IfbCycleProgress.from_decoded_frame(clean_mac, decoded)
                        except Exception as parse_err:
                            _LOGGER.debug("Error parsing live MQTT telemetry: %s", parse_err)

                    client.on_connect = on_connect
                    client.on_message = on_message

                    client.connect(host, port, keepalive=10)
                    client.loop_start()

                    start_t = time.time()
                    while time.time() - start_t < timeout:
                        if received_progress[0] is not None:
                            break
                        time.sleep(0.05)

                    client.loop_stop()
                    client.disconnect()

                    if received_progress[0] is not None:
                        return received_progress[0]
                except Exception as ex:
                    _LOGGER.debug("read_machine_state failed on %s:%s: %s", host, port, ex)
                finally:
                    if client is not None:
                        try:
                            client.loop_stop()
                            client.disconnect()
                        except Exception:
                            pass

            return None

        return await asyncio.to_thread(_query_mqtt)

    async def start(
        self,
        mac: str,
        program: int = 1,
        temp: int = 40,
        spin: int = 1000,
        dry: int = 0,
        serial: Optional[str] = None,
        resume_only: bool = False,
    ) -> Dict[str, Any]:
        """Send Start / Resume cycle command.

        If resume_only is True (machine paused mid-cycle), sends only CMD_START (12 bytes).
        Otherwise, sends 21-byte cycle setup frame (program, temp, spin) followed by CMD_START.
        """
        start_frame = IfbFrameBuilder.start()
        if resume_only:
            return await self.send_command(mac, start_frame, serial=serial)

        # Map dropdown index to actual RPM / Temp if passed as dropdown index
        temp_table = [0, 20, 30, 40, 60, 95]
        real_temp = temp_table[temp] if 0 <= temp < len(temp_table) and temp < 10 else temp

        spin_table = [0, 400, 600, 800, 1000, 1200, 1400]
        real_spin = spin_table[spin] if 0 <= spin < len(spin_table) and spin < 10 else spin

        cycle_frame = IfbFrameBuilder.build_cycle_frame(
            program=program, temp=real_temp, spin=real_spin
        )
        return await self.send_command(mac, [cycle_frame, start_frame], serial=serial)

    async def configure_cycle(
        self,
        mac: str,
        program: int = 1,
        temp: int = 40,
        spin: int = 1000,
        serial: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send 21-byte program/cycle setup frame without starting."""
        temp_table = [0, 20, 30, 40, 60, 95]
        real_temp = temp_table[temp] if 0 <= temp < len(temp_table) and temp < 10 else temp

        spin_table = [0, 400, 600, 800, 1000, 1200, 1400]
        real_spin = spin_table[spin] if 0 <= spin < len(spin_table) and spin < 10 else spin

        cycle_frame = IfbFrameBuilder.build_cycle_frame(
            program=program, temp=real_temp, spin=real_spin
        )
        return await self.send_command(mac, cycle_frame, serial=serial)

    async def pause(self, mac: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Send Pause cycle command."""
        frame = IfbFrameBuilder.pause()
        return await self.send_command(mac, frame, serial=serial)

    async def cancel(self, mac: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Send Cancel / Off command."""
        frame = IfbFrameBuilder.cancel()
        return await self.send_command(mac, frame, serial=serial)

    async def turn_on(self, mac: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Send Power On command."""
        frame = IfbFrameBuilder.turn_on()
        return await self.send_command(mac, frame, serial=serial)

    async def turn_off(self, mac: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Send Power Off command."""
        frame = IfbFrameBuilder.turn_off()
        return await self.send_command(mac, frame, serial=serial)

    async def child_lock(self, mac: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Send Child Lock command."""
        frame = IfbFrameBuilder.child_lock()
        return await self.send_command(mac, frame, serial=serial)

    async def child_unlock(self, mac: str, serial: Optional[str] = None) -> Dict[str, Any]:
        """Send Child Unlock command."""
        frame = IfbFrameBuilder.child_unlock()
        return await self.send_command(mac, frame, serial=serial)
