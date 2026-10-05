"""Binary frame encoding and decoding for IFB washing machines."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple


def calculate_checksum(payload: bytes) -> Tuple[int, int]:
    """Calculate signed-byte two-byte accumulation checksum."""
    sum1 = 0
    sum2 = 0
    for b in payload:
        # Dalvik/Java signed byte cast: -128 to 127
        signed_b = b if b < 128 else b - 256
        sum1 = (sum1 + signed_b) & 0xFF
        sum2 = (sum2 + sum1) & 0xFF
    return sum1, sum2


class IfbFrameBuilder:
    """Builds binary command frames for IFB washer & dryer models."""

    @staticmethod
    def build_command_frame(
        command_code: int,
        program_code: int = 1,
        temperature_code: int = 2,
        spin_code: int = 4,
        dry_mode_code: int = 0,
        options_mask: int = 0,
    ) -> bytes:
        """Construct raw binary command frame.
        
        Args:
            command_code: 1=Start/Resume, 2=Pause, 3=Cancel/Off, 4=Update Settings
            program_code: rotary dial index (1-20)
            temperature_code: temperature setting (0=Cold, 1=20C, 2=30C, 3=40C, 4=60C, 5=95C)
            spin_code: spin speed setting (0=No Spin, 1=400, 2=600, 3=800, 4=1000, 5=1200, 6=1400)
            dry_mode_code: drying mode index (0=No Dry, 1=Cupboard, 2=Iron, 3=Extra, etc.)
            options_mask: bitmask for prewash, soak, steam, eco, anti-crease
        """
        # Base frame structure matching TextUtility.getSettingCommand_washer_dryer
        frame = bytearray(16)
        frame[0] = 0xAA          # Header
        frame[1] = 0x55          # Sync
        frame[2] = 0x0E          # Length
        frame[3] = command_code & 0xFF
        frame[4] = program_code & 0xFF
        frame[5] = temperature_code & 0xFF
        frame[6] = spin_code & 0xFF
        frame[7] = dry_mode_code & 0xFF
        frame[8] = options_mask & 0xFF
        frame[9] = 0x00          # Extra rinse
        frame[10] = 0x00         # Delay timer hours
        frame[11] = 0x00         # Reserved
        frame[12] = 0x00         # Reserved
        frame[13] = 0x00         # Reserved

        # Compute checksum over bytes [2:14]
        c1, c2 = calculate_checksum(bytes(frame[2:14]))
        frame[14] = c1
        frame[15] = c2

        return bytes(frame)

    @classmethod
    def start(cls, program: int = 1, temp: int = 2, spin: int = 4, dry: int = 0) -> bytes:
        """Create Start cycle command frame."""
        return cls.build_command_frame(command_code=0x01, program_code=program, temperature_code=temp, spin_code=spin, dry_mode_code=dry)

    @classmethod
    def pause(cls) -> bytes:
        """Create Pause cycle command frame."""
        return cls.build_command_frame(command_code=0x02)

    @classmethod
    def cancel(cls) -> bytes:
        """Create Cancel cycle command frame."""
        return cls.build_command_frame(command_code=0x03)
