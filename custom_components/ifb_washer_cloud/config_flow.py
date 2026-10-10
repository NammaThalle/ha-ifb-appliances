"""Config flow for IFB Washer Cloud integration."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    AUTH_TYPE_CREDENTIALS,
    AUTH_TYPE_OTP,
    AUTH_TYPE_TOKEN,
    CONF_AUTH_TYPE,
    CONF_CALLING_CODE,
    CONF_DEVICE_NAME,
    CONF_MAC,
    CONF_OTP,
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_TOKEN,
    CONF_USER_ID,
    DEFAULT_CALLING_CODE,
    DOMAIN,
)

try:
    from .ifb_cloud.client import IfbAuthError, IfbCloudClient, IfbConnectionError
except ImportError:
    from ifb_cloud.client import IfbAuthError, IfbCloudClient, IfbConnectionError

_LOGGER = logging.getLogger(__name__)

MAC_REGEX = re.compile(r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$")


class IfbWasherCloudConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for IFB Washer Cloud."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._phone: str = ""
        self._calling_code: str = DEFAULT_CALLING_CODE
        self._client: Optional[IfbCloudClient] = None

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        """Get the options flow handler."""
        return IfbWasherOptionsFlow(config_entry)

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.ConfigFlowResult:
        """Handle initial step where user selects auth method or enters credentials."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            session = async_get_clientsession(self.hass)
            auth_type = user_input.get(CONF_AUTH_TYPE, AUTH_TYPE_OTP)

            try:
                if auth_type == AUTH_TYPE_OTP:
                    raw_phone = str(user_input.get(CONF_PHONE) or "").strip()
                    clean_phone = re.sub(r"\D", "", raw_phone)
                    if clean_phone.startswith("91") and len(clean_phone) > 10:
                        clean_phone = clean_phone[2:]

                    if not clean_phone:
                        errors[CONF_PHONE] = "phone_required"
                    elif len(clean_phone) != 10:
                        errors[CONF_PHONE] = "phone_format"
                    else:
                        calling_code = user_input.get(CONF_CALLING_CODE, DEFAULT_CALLING_CODE)
                        self._phone = clean_phone
                        self._calling_code = calling_code
                        self._client = IfbCloudClient(session=session)

                        await self._client.request_otp(phone=clean_phone, calling_code=calling_code)
                        return await self.async_step_otp()

                elif auth_type == AUTH_TYPE_TOKEN:
                    token = user_input.get(CONF_TOKEN, "").strip()
                    user_id = user_input.get(CONF_USER_ID)
                    if not token:
                        errors[CONF_TOKEN] = "invalid_auth"
                    else:
                        client = IfbCloudClient(token=token, user_id=user_id, session=session)
                        self._client = client
                        devices = await client.get_all_devices()
                        if not devices:
                            return await self.async_step_manual_mac()
                        else:
                            await self.async_set_unique_id(f"ifb_cloud_{user_id or devices[0].mac}")
                            self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title=f"IFB Cloud ({len(devices)} appliance{'s' if len(devices) > 1 else ''})",
                                data=user_input,
                            )

                else:
                    raw_phone = str(user_input.get(CONF_PHONE) or "").strip()
                    password = str(user_input.get(CONF_PASSWORD) or "")
                    calling_code = user_input.get(CONF_CALLING_CODE, DEFAULT_CALLING_CODE)

                    if not password:
                        errors[CONF_PASSWORD] = "invalid_auth"
                    else:
                        client = IfbCloudClient(session=session)
                        self._client = client
                        await client.login_with_password(
                            phone_or_email=raw_phone,
                            password=password,
                            calling_code=calling_code,
                        )
                        devices = await client.get_all_devices()
                        user_input[CONF_TOKEN] = client.token
                        user_input[CONF_USER_ID] = client.user_id

                        if not devices:
                            return await self.async_step_manual_mac()
                        else:
                            await self.async_set_unique_id(f"ifb_cloud_{client.user_id or raw_phone}")
                            self._abort_if_unique_id_configured()
                            return self.async_create_entry(
                                title=f"IFB Cloud ({raw_phone})",
                                data=user_input,
                            )

            except IfbAuthError as err:
                _LOGGER.warning("IFB auth error: %s", err)
                errors["base"] = "invalid_auth"
            except IfbConnectionError:
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("Unexpected error in IFB Cloud setup: %s", err)
                errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_AUTH_TYPE, default=AUTH_TYPE_OTP): vol.In(
                    {
                        AUTH_TYPE_OTP: "Mobile Number (SMS OTP Verification)",
                        AUTH_TYPE_CREDENTIALS: "Mobile Number / Email & Password",
                        AUTH_TYPE_TOKEN: "Direct Bearer Auth Token",
                    }
                ),
                vol.Required(CONF_PHONE): str,
                vol.Optional(CONF_CALLING_CODE, default=DEFAULT_CALLING_CODE): str,
                vol.Optional(CONF_PASSWORD): str,
                vol.Optional(CONF_TOKEN): str,
                vol.Optional(CONF_USER_ID): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_otp(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.ConfigFlowResult:
        """Handle OTP verification step."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            raw_otp = str(user_input.get(CONF_OTP) or "").strip()
            clean_otp = re.sub(r"\D", "", raw_otp)
            if len(clean_otp) not in (4, 6):
                errors["base"] = "invalid_otp"
            else:
                session = async_get_clientsession(self.hass)
                if self._client is None:
                    self._client = IfbCloudClient(session=session)

                try:
                    await self._client.verify_otp(
                        phone=self._phone,
                        otp=clean_otp,
                        calling_code=self._calling_code,
                    )
                    devices = await self._client.get_all_devices()
                    if not devices:
                        return await self.async_step_manual_mac()
                    else:
                        await self.async_set_unique_id(f"ifb_cloud_{self._client.user_id or self._phone}")
                        self._abort_if_unique_id_configured()

                        return self.async_create_entry(
                            title=f"IFB Cloud ({self._phone})",
                            data={
                                CONF_AUTH_TYPE: AUTH_TYPE_OTP,
                                CONF_PHONE: self._phone,
                                CONF_CALLING_CODE: self._calling_code,
                                CONF_TOKEN: self._client.token,
                                CONF_USER_ID: self._client.user_id,
                            },
                        )
                except IfbAuthError as err:
                    _LOGGER.warning("IFB OTP verification error: %s", err)
                    errors["base"] = "invalid_otp"
                except IfbConnectionError:
                    errors["base"] = "cannot_connect"
                except Exception as err:
                    _LOGGER.exception("Unexpected error verifying OTP: %s", err)
                    errors["base"] = "unknown"

        schema = vol.Schema(
            {
                vol.Required(CONF_OTP): str,
            }
        )

        return self.async_show_form(
            step_id="otp",
            data_schema=schema,
            errors=errors,
            description_placeholders={"phone": self._phone},
        )

    async def async_step_manual_mac(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> config_entries.ConfigFlowResult:
        """Prompt user for appliance MAC if not discovered via cloud catalog."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            mac_str = str(user_input.get(CONF_MAC) or "").strip()
            if not MAC_REGEX.match(mac_str):
                errors[CONF_MAC] = "invalid_mac"
            else:
                user_id = self._client.user_id if self._client else self._phone
                token = self._client.token if self._client else ""
                clean_mac = mac_str.lower()
                dev_name = str(user_input.get(CONF_DEVICE_NAME) or "IFB Washer Dryer").strip()

                await self.async_set_unique_id(f"ifb_cloud_{user_id or clean_mac}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=f"IFB Cloud ({dev_name})",
                    data={
                        CONF_AUTH_TYPE: AUTH_TYPE_OTP,
                        CONF_PHONE: self._phone,
                        CONF_CALLING_CODE: self._calling_code,
                        CONF_TOKEN: token,
                        CONF_USER_ID: user_id,
                        CONF_MAC: clean_mac,
                        CONF_DEVICE_NAME: dev_name,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_MAC): str,
                vol.Optional(CONF_DEVICE_NAME, default="IFB Washer Dryer"): str,
            }
        )

        return self.async_show_form(
            step_id="manual_mac",
            data_schema=schema,
            errors=errors,
        )


class IfbWasherOptionsFlow(config_entries.OptionsFlow):
    """Handle options for IFB Washer Cloud."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None) -> config_entries.ConfigFlowResult:
        """Manage integration options."""
        errors: Dict[str, str] = {}
        current_mac = self._config_entry.options.get(CONF_MAC) or self._config_entry.data.get(CONF_MAC, "")
        current_name = self._config_entry.options.get(CONF_DEVICE_NAME) or self._config_entry.data.get(
            CONF_DEVICE_NAME, "IFB Washer Dryer"
        )

        if user_input is not None:
            mac_str = str(user_input.get(CONF_MAC) or "").strip()
            if mac_str and not MAC_REGEX.match(mac_str):
                errors[CONF_MAC] = "invalid_mac"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(CONF_MAC, default=current_mac): str,
                vol.Optional(CONF_DEVICE_NAME, default=current_name): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
