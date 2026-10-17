"""Data models for IFB Cloud API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .frame import DecodedFrame

from .const import MachineState, PROGRAM_NAMES, DRY_MODES, SPIN_SPEEDS, TEMPERATURES

# Numeric state code → MachineState (must match frame.STATE_MAP)
_STATE_CODE_MAP: Dict[int, MachineState] = {
    0: MachineState.STANDBY,     # idle
    1: MachineState.STANDBY,     # standby
    2: MachineState.MAIN_WASH,   # start
    3: MachineState.PREWASH,
    4: MachineState.MAIN_WASH,
    5: MachineState.RINSING,
    6: MachineState.RINSING,
    7: MachineState.RINSING,
    8: MachineState.RINSING,
    9: MachineState.RINSING,
    10: MachineState.RINSING,
    11: MachineState.SPINNING,   # final spin
    12: MachineState.ANTI_CREASE,
    13: MachineState.COMPLETE,   # end
    14: MachineState.PAUSED,
    15: MachineState.SOAK,
    16: MachineState.RINSING,    # rinse hold
    17: MachineState.MAIN_WASH,  # heating
    18: MachineState.SPINNING,   # drain
    19: MachineState.SPINNING,   # intermediate spin
    20: MachineState.DELAY_START,
    22: MachineState.DRYING,     # cooling / drying phase
}


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
    temp_idx: int = 0
    spin_idx: int = 0
    dry_mode_code: int = 0
    error_code: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_paused(self) -> bool:
        """Return True if appliance state is paused."""
        return self.state == MachineState.PAUSED

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

    @classmethod
    def from_decoded_frame(cls, mac: str, frame: "DecodedFrame") -> "IfbCycleProgress":
        """Build IfbCycleProgress from a DecodedFrame (binary telemetry).

        Time fields come from the frame as *seconds* (balanceTimeHigh*60+balanceTimeLow).
        We expose them as integer minutes for the HA sensor (rounding up so the display
        shows "1 min" rather than "0 min" when 30 seconds remain).
        """
        state = _STATE_CODE_MAP.get(frame.state_code, MachineState.UNKNOWN)
        prog_name = PROGRAM_NAMES.get(frame.program_code, f"Program {frame.program_code}")

        # Convert seconds → minutes (ceiling so "1 min" shows when <60 s remain)
        remaining_min = (frame.remaining_seconds + 59) // 60 if frame.remaining_seconds > 0 else 0
        total_min = (frame.total_seconds + 59) // 60 if frame.total_seconds > 0 else 0

        # Resolve spin speed and index
        spin_rpm = frame.set_spin_rpm
        spin_speeds_table = [0, 400, 600, 800, 1000, 1200, 1400]
        if spin_rpm in spin_speeds_table:
            spin_idx = spin_speeds_table.index(spin_rpm)
        else:
            spin_idx = 4
        spin_label = "No Spin" if spin_rpm == 0 else f"{spin_rpm} RPM"

        # Resolve temperature and index
        temp_c = frame.set_temperature_c
        temp_table = [0, 20, 30, 40, 60, 95]
        if temp_c in temp_table:
            temp_idx = temp_table.index(temp_c)
        else:
            temp_idx = 3
        temp_label = "Cold" if temp_c == 0 else f"{temp_c}°C"

        # Resolve dry mode
        dry_code = getattr(frame, "dry_mode", 0)
        dry_label = DRY_MODES.get(dry_code, "No Dry")

        # Error: alarm bytes non-zero
        error_code: Optional[str] = None
        if frame.alarm1 or frame.alarm2:
            error_code = f"E{frame.alarm1:02X}{frame.alarm2:02X}"

        return cls(
            mac=mac,
            is_running=frame.is_running,
            state=state,
            program_code=frame.program_code,
            program_name=prog_name,
            time_remaining_minutes=remaining_min,
            total_time_minutes=total_min,
            progress_percentage=frame.progress_pct,
            motor_speed_rpm=frame.live_rpm,
            water_temperature_c=frame.water_temperature_c,
            selected_spin_speed=spin_label,
            selected_temperature=temp_label,
            selected_dry_mode=dry_label,
            temp_idx=temp_idx,
            spin_idx=spin_idx,
            dry_mode_code=dry_code,
            door_locked=frame.door_locked,
            child_lock_active=frame.child_lock,
            prewash_active=frame.prewash_active,
            soak_active=frame.soak_active,
            steam_active=frame.steam_active,
            extra_rinse_count=frame.extra_rinse_count,
            error_code=error_code,
            raw_data={
                "state_code": frame.state_code,
                "option1": frame.option1,
                "option_enable": frame.option_enable,
                "user_control": frame.user_control,
                "previous_state": frame.previous_state,
                "alarm1": frame.alarm1,
                "alarm2": frame.alarm2,
                "remaining_seconds": frame.remaining_seconds,
                "total_seconds": frame.total_seconds,
                "dry_mode": dry_code,
            },
        )
