"""Diagnostics support for IFB Washer Cloud."""

from __future__ import annotations

from typing import Any, Dict

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "password",
    "token",
    "cloud_token",
    "phone",
    "mobile",
    "email",
    "user_id",
    "serialNumber",
    "serial_number",
    "serial",
    "mac",
    "macAddress",
    "deviceMac",
    "mqtt_client_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> Dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data["coordinator"]
    devices = entry_data["devices"]
    client = entry_data["client"]

    devices_diag = {}
    for mac, device in devices.items():
        devices_diag[mac] = {
            "name": device.name,
            "model_name": device.model_name,
            "category": device.category,
            "hardware_type": device.hardware_type,
            "firmware_version": device.firmware_version,
            "is_online": device.is_online,
        }

    telemetry_diag = {}
    if coordinator.data:
        for mac, progress in coordinator.data.items():
            telemetry_diag[mac] = {
                "is_running": progress.is_running,
                "is_paused": progress.is_paused,
                "state": progress.state.value if hasattr(progress.state, "value") else str(progress.state),
                "program_code": progress.program_code,
                "program_name": progress.program_name,
                "time_remaining_minutes": progress.time_remaining_minutes,
                "total_time_minutes": progress.total_time_minutes,
                "progress_percentage": progress.progress_percentage,
                "motor_speed_rpm": progress.motor_speed_rpm,
                "water_temperature_c": progress.water_temperature_c,
                "selected_spin_speed": progress.selected_spin_speed,
                "selected_temperature": progress.selected_temperature,
                "selected_dry_mode": progress.selected_dry_mode,
                "door_locked": progress.door_locked,
                "child_lock_active": progress.child_lock_active,
                "prewash_active": progress.prewash_active,
                "soak_active": progress.soak_active,
                "steam_active": progress.steam_active,
                "water_level_frequency": getattr(progress, "water_level_frequency", 0),
                "tub_clean_reminder": getattr(progress, "tub_clean_reminder", False),
                "error_code": progress.error_code,
                "error_description": getattr(progress, "error_description", "None"),
                "raw_data": progress.raw_data,
            }

    diag = {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
            "unique_id": entry.unique_id,
        },
        "client": {
            "is_connected": bool(client.token),
            "mqtt_listener_active": getattr(client, "_mqtt_listener_active", False),
            "phone_app_active_until": getattr(client, "_phone_app_active_until", 0.0),
            "phone_app_backoff": getattr(client, "_phone_app_backoff", 180.0),
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
        },
        "devices": async_redact_data(devices_diag, TO_REDACT),
        "telemetry": async_redact_data(telemetry_diag, TO_REDACT),
    }

    return diag
