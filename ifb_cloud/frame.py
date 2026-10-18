"""Binary frame encoding and decoding for IFB washing machines.

Binary protocol reverse-engineered from com.sqt_smartapp.Models.MachineState
(decompiled from My IFB Android APK).

setMachineState(byte[] bArr) layout (ESP32 response frame, 0-indexed):
  [0]  = 0x63 (99) frame start marker
  [1]  = sequence / header byte
  [2]  = length (hex-encoded nibble, read as 0xNN)
  [3]  = ack
  [4]  = applianceType
  [5]  = userControl        (4=off/cancelled, 0=normal)
  [6]  = programCode
  [7]  = detergentOrder     (bit7=tub-clean reminder)
  [8]  = setSpeedHigh
  [9]  = setSpeedLow        → setRPM = (high<<8)|low
  [10] = setTemperature     (°C)
  [11] = option1            (bitmask: bit1=extra-rinse, bit2=prewash, bit4=steam)
  [12] = delayStartHigh
  [13] = delayStartLow
  [14] = soak               (1=active)
  [15] = childLock          (1=locked, used for childlock_end detection)
  [16] = type
  [17] = balanceTimeHigh    → remaining = high*60 + low  (seconds)
  [18] = balanceTimeLow
  [19] = motorSpeedHigh
  [20] = motorSpeedLow      → liveRPM = (high<<8)|low
  [21] = waterTemperature   (°C live reading)
  [22] = waterLevelFreqHigh
  [23] = waterLevelFreqLow
  [24] = waterLevel
  [25] = unbalance
  [26] = alarm1
  [27] = alarm2
  [28] = childLock2         (secondary child-lock byte)
  [29] = optionEnable       (bitmask of enabled options)
  [30] = state              (cycle phase — see STATE_MAP below)
  [31] = loadFlag
  [32] = programTimeHigh
  [33] = programTimeLow     → totalTime = high*60 + low  (seconds)
  [34] = previousState
  [35] = door               (non-zero = locked)

State codes (from TextUtility.getMachineState):
  0  = idle
  1  = standby
  2  = start
  3  = prewash
  4  = main wash
  5  = extra rinse 1
  6  = extra rinse 2
  7  = extra rinse 3
  8  = first rinse
  9  = second rinse
  10 = final rinse
  11 = final spin
  12 = anti-crease
  13 = end (complete)
  14 = paused
  15 = soak
  16 = rinse hold
  17 = heating
  18 = drain
  19 = intermediate spin
  20 = delay start
  22 = cooling (washer-dryer drying phase)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple


# State code → MachineState enum value (from TextUtility.getMachineState & AppConstants)
STATE_MAP = {
    0: "idle",
    1: "standby",
    2: "start",
    3: "prewash",
    4: "washing",
    5: "rinsing",   # extra rinse 1
    6: "rinsing",   # extra rinse 2
    7: "rinsing",   # extra rinse 3
    8: "rinsing",   # first rinse
    9: "rinsing",   # second rinse
    10: "rinsing",  # final rinse
    11: "spinning", # final spin
    12: "anti_crease",
    13: "complete",
    14: "paused",
    15: "soak",
    16: "rinsing",  # rinse hold
    17: "washing",  # heating (still in wash phase)
    18: "spinning", # drain (pump-out, no drum)
    19: "spinning", # intermediate spin
    20: "delay_start",
    22: "drying",   # cooling / drying phase (washer-dryer)
    35: "rinsing",  # hot rinse
    36: "steam",    # steam
    39: "rinsing",  # rinse hold child lock
    40: "drying",   # drying (washer-dryer main dry phase)
    42: "soak",     # warm soak / warm wash
    50: "complete", # child lock end
    100: "complete", # program completed
}

RUNNING_STATES = {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 17, 18, 19, 22, 35, 36, 39, 40, 42}


def calculate_checksum(payload: bytes) -> Tuple[int, int]:
    """Calculate IFB two-byte accumulation checksum.

    Byte len-2: sum of payload bytes & 0xFF
    Byte len-1: (sum of payload bytes * 2) & 0xFF
    """
    s1 = sum(payload) & 0xFF
    s2 = (s1 * 2) & 0xFF
    return s1, s2


@dataclass
class DecodedFrame:
    """Parsed telemetry from a 36+ byte IFB binary response frame."""
    state_code: int
    state_name: str
    is_running: bool
    is_paused: bool
    program_code: int
    set_spin_rpm: int
    set_temperature_c: int
    live_rpm: int
    water_temperature_c: int
    remaining_seconds: int
    total_seconds: int
    progress_pct: int
    door_locked: bool
    child_lock: bool
    soak_active: bool
    prewash_active: bool
    steam_active: bool
    extra_rinse_count: int
    alarm1: int
    alarm2: int
    option1: int
    option_enable: int
    user_control: int
    previous_state: int
    dry_mode: int
    raw: bytes


def decode_frame(data: bytes) -> Optional[DecodedFrame]:
    """Decode a raw IFB binary telemetry frame.

    Returns None if the frame is too short or does not start with 0x63.
    The frame must be at least 36 bytes long.
    """
    if not data or len(data) < 36:
        return None
    if data[0] != 0x63:
        return None

    state_code = data[30] & 0xFF
    state_name = STATE_MAP.get(state_code, "unknown")
    is_paused = state_code == 14

    program_code = data[6] & 0xFF

    # Spin speed: data[8] is setSpeedHigh, data[9] is setSpeedLow (extra rinse)
    # Checks index into spin_table (0..6) first, then hundreds of RPM (8 -> 800, 10 -> 1000)
    spin_hi = data[8] & 0xFF
    spin_lo = data[9] & 0xFF
    spin_table = [0, 400, 600, 800, 1000, 1200, 1400]
    if spin_hi < len(spin_table) and spin_lo == 0:
        set_spin_rpm = spin_table[spin_hi]
    elif spin_hi * 100 in spin_table:
        set_spin_rpm = spin_hi * 100
    elif (spin_hi << 8 | spin_lo) in spin_table:
        set_spin_rpm = (spin_hi << 8) | spin_lo
    else:
        set_spin_rpm = 1000

    # Temperature: data[10] is setTemperature in °C or index into table
    temp_raw = data[10] & 0xFF
    temp_table = [0, 20, 30, 40, 60, 95]
    if temp_raw in temp_table:
        set_temp = temp_raw
    elif temp_raw < len(temp_table):
        set_temp = temp_table[temp_raw]
    else:
        set_temp = temp_raw

    # balanceTime = remaining time; balanceTimeHigh is hours, balanceTimeLow is minutes
    bal_hi = data[17] & 0xFF
    bal_lo = data[18] & 0xFF
    remaining_minutes = bal_hi * 60 + bal_lo
    remaining_seconds = remaining_minutes * 60

    motor_hi = data[19] & 0xFF
    motor_lo = data[20] & 0xFF
    live_rpm = (motor_hi << 8) | motor_lo

    water_temp = data[21] & 0xFF

    # programTime = total cycle duration; programTimeHigh is hours, programTimeLow is minutes
    prog_hi = data[32] & 0xFF
    prog_lo = data[33] & 0xFF
    total_minutes = prog_hi * 60 + prog_lo
    total_seconds = total_minutes * 60

    progress_pct = 0
    if total_seconds > 0 and remaining_seconds <= total_seconds:
        progress_pct = int((1.0 - remaining_seconds / total_seconds) * 100)

    door_locked = (data[35] & 0xFF) != 0
    child_lock = (data[15] & 0xFF) == 1
    soak_active = (data[14] & 0xFF) != 0

    is_running = (state_code in RUNNING_STATES) or (
        remaining_seconds > 0 and state_code not in {0, 1, 13, 14, 50, 100} and door_locked
    )

    option1 = data[11] & 0xFF
    prewash_active = bool(option1 & 0x04)   # bit 2
    steam_active = bool(option1 & 0x10)     # bit 4
    extra_rinse_count = option1 & 0x03      # bits 0-1

    alarm1 = data[26] & 0xFF
    alarm2 = data[27] & 0xFF
    option_enable = data[29] & 0xFF
    user_control = data[5] & 0xFF
    previous_state = data[34] & 0xFF
    dry_mode = data[28] & 0xFF if len(data) > 28 else 0

    return DecodedFrame(
        state_code=state_code,
        state_name=state_name,
        is_running=is_running,
        is_paused=is_paused,
        program_code=program_code,
        set_spin_rpm=set_spin_rpm,
        set_temperature_c=set_temp,
        live_rpm=live_rpm,
        water_temperature_c=water_temp,
        remaining_seconds=remaining_seconds,
        total_seconds=total_seconds,
        progress_pct=progress_pct,
        door_locked=door_locked,
        child_lock=child_lock,
        soak_active=soak_active,
        prewash_active=prewash_active,
        steam_active=steam_active,
        extra_rinse_count=extra_rinse_count,
        alarm1=alarm1,
        alarm2=alarm2,
        option1=option1,
        option_enable=option_enable,
        user_control=user_control,
        previous_state=previous_state,
        dry_mode=dry_mode,
        raw=bytes(data),
    )


class IfbFrameBuilder:
    """Builds binary command frames for IFB washing machines."""

    # Fixed command frames directly matching com.sqt_smartapp.ifb_remote.Constant.Command
    CMD_START = bytes([99, 10, 1, 0, 1, 1, 0, 0, 0, 0, 112, 224])
    CMD_PAUSE = bytes([99, 10, 1, 0, 1, 3, 0, 0, 0, 0, 114, 228])
    CMD_CANCEL = bytes([99, 10, 1, 0, 1, 4, 0, 0, 0, 0, 115, 230])
    CMD_TURN_ON = bytes([99, 10, 1, 0, 1, 17, 0, 0, 0, 0, 128, 0])
    CMD_TURN_OFF = bytes([99, 10, 1, 0, 1, 18, 0, 0, 0, 0, 129, 2])
    CMD_READ_STATE = bytes([99, 10, 1, 0, 1, 7, 0, 0, 0, 0, 118, 236])
    CMD_CHILD_LOCK = bytes([99, 10, 2, 1, 11, 1, 0, 0, 0, 0, 124, 248])
    CMD_CHILD_UNLOCK = bytes([99, 10, 2, 1, 11, 0, 0, 0, 0, 0, 123, 246])

    @classmethod
    def build_cycle_frame(
        cls, program: int = 1, temp: int = 40, spin: int = 1000
    ) -> bytes:
        """Build the 21-byte program/cycle configuration frame.

        Matches official IFB Android app cottonWash command structure:
        [99, 19, 3, 0, 1, program, 0, spin_hi, spin_lo, temp, 0, 0, 0, 10, 1, 0, 0, 0, 0, cs1, cs2]
        """
        spin_hi = (spin >> 8) & 0xFF
        spin_lo = spin & 0xFF
        raw = [99, 19, 3, 0, 1, program, 0, spin_hi, spin_lo, temp, 0, 0, 0, 10, 1, 0, 0, 0, 0]
        cs1, cs2 = calculate_checksum(bytes(raw))
        raw.extend([cs1, cs2])
        return bytes(raw)

    @classmethod
    def start(cls, *args, **kwargs) -> bytes:
        """Create Start / Play machine command frame (12 bytes)."""
        return cls.CMD_START

    @classmethod
    def pause(cls) -> bytes:
        """Create Pause cycle command frame."""
        return cls.CMD_PAUSE

    @classmethod
    def cancel(cls) -> bytes:
        """Create Cancel cycle command frame."""
        return cls.CMD_CANCEL

    @classmethod
    def read_state(cls) -> bytes:
        """Create Read machine state command frame."""
        return cls.CMD_READ_STATE

    @classmethod
    def turn_on(cls) -> bytes:
        """Create Turn On command frame."""
        return cls.CMD_TURN_ON

    @classmethod
    def turn_off(cls) -> bytes:
        """Create Turn Off command frame."""
        return cls.CMD_TURN_OFF

    @classmethod
    def child_lock(cls) -> bytes:
        """Create Child Lock command frame."""
        return cls.CMD_CHILD_LOCK

    @classmethod
    def child_unlock(cls) -> bytes:
        """Create Child Unlock command frame."""
        return cls.CMD_CHILD_UNLOCK
