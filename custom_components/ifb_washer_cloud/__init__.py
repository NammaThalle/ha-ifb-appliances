"""The IFB Washer Cloud integration."""

from __future__ import annotations

import logging
from typing import Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CALLING_CODE,
    CONF_DEVICE_NAME,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PHONE,
    CONF_TOKEN,
    CONF_USER_ID,
    CONF_MQTT_CLIENT_ID,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import IfbWasherCoordinator

try:
    from .ifb_cloud.client import IfbCloudClient
    from .ifb_cloud.models import IfbDevice
except ImportError:
    from ifb_cloud.client import IfbCloudClient
    from ifb_cloud.models import IfbDevice

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up IFB Washer Cloud from a config entry."""
    session = async_get_clientsession(hass)
    token = entry.data.get(CONF_TOKEN)
    user_id = entry.data.get(CONF_USER_ID)
    cloud_token = entry.data.get("cloud_token")
    mqtt_client_id = entry.options.get(CONF_MQTT_CLIENT_ID) or entry.data.get(CONF_MQTT_CLIENT_ID)

    client = IfbCloudClient(
        token=token,
        cloud_token=cloud_token,
        mqtt_client_id=mqtt_client_id,
        user_id=user_id,
        session=session,
    )

    # If token expired or not stored, perform re-authentication
    if not token and entry.data.get(CONF_PHONE) and entry.data.get(CONF_PASSWORD):
        await client.login_with_password(
            phone_or_email=entry.data[CONF_PHONE],
            password=entry.data[CONF_PASSWORD],
            calling_code=entry.data.get(CONF_CALLING_CODE, "+91"),
        )

    # Ensure we have a server-assigned MQTT client ID (avoids MAC collision with washer).
    # This is the same call AppliancesFragment.checkAndGenerateMqttClientId() makes.
    if not mqtt_client_id and client.token:
        fetched = await client.fetch_mqtt_client_id()
        if fetched:
            _LOGGER.debug("Obtained MQTT client_id from server: %s", fetched)
            # Persist it so it survives HA restarts
            hass.config_entries.async_update_entry(
                entry,
                data={**entry.data, "mqtt_client_id": fetched},
            )

    # Discover all appliances (using cloud catalog or user-configured MAC)
    fallback_mac = entry.data.get(CONF_MAC) or entry.options.get(CONF_MAC)
    fallback_name = entry.data.get(CONF_DEVICE_NAME) or entry.options.get(CONF_DEVICE_NAME)
    fallback_serial = entry.data.get("serial")
    device_list = await client.get_all_devices(
        fallback_mac=fallback_mac,
        fallback_name=fallback_name,
        fallback_serial=fallback_serial,
    )
    devices: Dict[str, IfbDevice] = {d.mac: d for d in device_list}

    coordinator = IfbWasherCoordinator(hass, client, devices)
    await coordinator.async_config_entry_first_refresh()

    initial_settings: Dict[str, Dict[str, int]] = {}
    for mac in devices:
        prog = coordinator.data.get(mac) if coordinator.data else None
        p_code = prog.program_code if (prog and prog.program_code) else 1
        p_temp = prog.temp_idx if (prog and prog.temp_idx is not None) else 3
        p_spin = prog.spin_idx if (prog and prog.spin_idx is not None) else 4
        p_dry = prog.dry_mode_code if (prog and prog.dry_mode_code is not None) else 0
        initial_settings[mac] = {
            "program": p_code,
            "temp": p_temp,
            "spin": p_spin,
            "dry": p_dry,
        }

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "devices": devices,
        "settings": initial_settings,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
