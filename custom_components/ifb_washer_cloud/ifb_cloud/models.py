"""Data models for IFB Cloud API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .const import MachineState, PROGRAM_NAMES, DRY_MODES


@dataclass
class IfbDevice:
    """Represents a registered IFB appliance."""
    mac: str
    name: str
    model_name: str
    device_id: Optional[str] = None
    serial_number: Optional[str] = None
    category: Optional[str] = None
    is_online: bool = False
    hardware_type: str = "esp"  # 'esp' or 'gainspan'
    firmware_version: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_dict(cls, data: Dict[str, Any]) -> "IfbDevice":
        """Parse from API dictionary."""
        mac = str(data.get("mac") or data.get("macAddress") or data.get("deviceMac") or "").strip().lower()
        name = str(data.get("name") or data.get("deviceName") or data.get("alias") or "IFB Appliance")
        model = str(data.get("model") or data.get("modelName") or data.get("machineModel") or "IFB Appliance")
        serial = data.get("serialNumber") or data.get("srNo") or data.get("serial")
        is_online = bool(data.get("isOnline") or data.get("status") == "online" or data.get("online", False))
        
        # Hardware type: GainSpan Wi-Fi module IEEE OUI prefix is 20:f8:5e; modern IFB appliances use ESP32/ESP8266
        hw_type = "gainspan" if mac.startswith("20:f8:5e") or str(data.get("moduleType", "")).lower() == "gainspan" else "esp"
        
        return cls(
            mac=mac,
            name=name,
            model_name=model,
            device_id=data.get("deviceId") or data.get("id") or data.get("_id"),
            serial_number=str(serial) if serial else None,
            category=data.get("category") or data.get("deviceCategory") or "Washer Dryer",
            is_online=is_online,
            hardware_type=hw_type,
            firmware_version=data.get("firmwareVersion") or data.get("swVersion"),
            raw_data=data,
        )


@dataclass
class IfbCycleProgress:
    """Represents current live wash/dry cycle progress."""
    mac: str
    is_running: bool = False
    state: MachineState = MachineState.STANDBY
    program_code: int = 0
    program_name: str = "Standby"
    time_remaining_minutes: int = 0
    total_time_minutes: int = 0
    progress_percentage: int = 0
    motor_speed_rpm: int = 0
    water_temperature_c: int = 0
    selected_spin_speed: str = "No Spin"
    selected_temperature: str = "Cold"
    selected_dry_mode: str = "No Dry"
    door_locked: bool = False
    child_lock_active: bool = False
    prewash_active: bool = False
    soak_active: bool = False
    steam_active: bool = False
    extra_rinse_count: int = 0
    error_code: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_dict(cls, mac: str, data: Dict[str, Any]) -> "IfbCycleProgress":
        """Parse cycle progress from API dictionary or binary frame."""
        # Check running state
        is_running = bool(data.get("running") or data.get("isRunning") or data.get("runState", 0) == 1)
        
        # State mapping
        raw_state = str(data.get("state") or data.get("machineState") or "standby").lower()
        if "wash" in raw_state and "pre" not in raw_state:
            state = MachineState.MAIN_WASH
        elif "rinse" in raw_state:
            state = MachineState.RINSING
        elif "spin" in raw_state:
            state = MachineState.SPINNING
        elif "dry" in raw_state:
            state = MachineState.DRYING
        elif "steam" in raw_state:
            state = MachineState.STEAM
        elif "pause" in raw_state:
            state = MachineState.PAUSED
        elif "complete" in raw_state or "finish" in raw_state:
            state = MachineState.COMPLETE
        elif "error" in raw_state:
            state = MachineState.ERROR
        elif is_running:
            state = MachineState.MAIN_WASH
        else:
            state = MachineState.STANDBY

        prog_code = int(data.get("programCode") or data.get("program") or 0)
        prog_name = PROGRAM_NAMES.get(prog_code, str(data.get("programName") or "Custom"))

        dry_code = int(data.get("dryModeCode") or data.get("dryMode") or 0)
        dry_name = DRY_MODES.get(dry_code, "No Dry")

        remaining = int(data.get("remainingTime") or data.get("timeLeft") or data.get("timeRemaining") or 0)
        total = int(data.get("totalTime") or data.get("duration") or 0)
        progress_pct = int((1.0 - (remaining / total)) * 100) if total > 0 and remaining <= total else 0

        return cls(
            mac=mac,
            is_running=is_running,
            state=state,
            program_code=prog_code,
            program_name=prog_name,
            time_remaining_minutes=remaining,
            total_time_minutes=total,
            progress_percentage=progress_pct,
            motor_speed_rpm=int(data.get("rpm") or data.get("motorSpeed") or 0),
            water_temperature_c=int(data.get("temp") or data.get("waterTemp") or data.get("temperature") or 0),
            selected_spin_speed=str(data.get("selectedSpin") or data.get("spinSpeed") or "1000 RPM"),
            selected_temperature=str(data.get("selectedTemp") or data.get("tempSetting") or "40°C"),
            selected_dry_mode=dry_name,
            door_locked=bool(data.get("doorLocked") or data.get("door") or False),
            child_lock_active=bool(data.get("childLock") or False),
            prewash_active=bool(data.get("prewash") or False),
            soak_active=bool(data.get("soak") or False),
            steam_active=bool(data.get("steam") or False),
            extra_rinse_count=int(data.get("extraRinse") or 0),
            error_code=data.get("errorCode"),
            raw_data=data,
        )
