"""Unit tests for binary packet framing and checksum algorithms."""

import unittest
from ifb_cloud.frame import IfbFrameBuilder, calculate_checksum


class TestIfbFrameBuilder(unittest.TestCase):
    """Test suite for binary command frame building."""

    def test_checksum_algorithm(self):
        """Verify 8-bit checksum calculation matches protocol specs."""
        test_payload = bytes([99, 10, 1, 0, 1, 1, 0, 0, 0, 0])
        c1, c2 = calculate_checksum(test_payload)
        self.assertEqual(c1, 112)
        self.assertEqual(c2, 224)

    def test_start_frame_structure(self):
        """Verify Start cycle binary frame fields and header bytes."""
        frame = IfbFrameBuilder.start()
        self.assertEqual(len(frame), 12)
        self.assertEqual(frame[0], 99)  # 0x63 header
        self.assertEqual(frame[1], 10)  # length
        self.assertEqual(frame[2], 1)   # opcode
        self.assertEqual(frame[5], 1)   # start command
        c1, c2 = calculate_checksum(bytes(frame[:10]))
        self.assertEqual(frame[10], c1)
        self.assertEqual(frame[11], c2)

    def test_cycle_frame_structure(self):
        """Verify 21-byte program/cycle setup frame."""
        frame = IfbFrameBuilder.build_cycle_frame(program=6, temp=40, spin=1000)
        self.assertEqual(len(frame), 21)
        self.assertEqual(frame[0], 99)  # 0x63 header
        self.assertEqual(frame[1], 19)  # payload length
        self.assertEqual(frame[2], 3)   # cycle config opcode
        self.assertEqual(frame[5], 6)   # program code (Express 15)
        self.assertEqual(frame[7], 3)   # spin hi (1000 RPM >> 8)
        self.assertEqual(frame[8], 232) # spin lo (1000 RPM & 0xFF)
        self.assertEqual(frame[9], 40)  # temp 40C
        c1, c2 = calculate_checksum(bytes(frame[:19]))
        self.assertEqual(frame[19], c1)
        self.assertEqual(frame[20], c2)

    def test_pause_frame_structure(self):
        """Verify Pause cycle command frame."""
        frame = IfbFrameBuilder.pause()
        self.assertEqual(len(frame), 12)
        self.assertEqual(frame[0], 99)
        self.assertEqual(frame[5], 3)  # Pause opcode
        c1, c2 = calculate_checksum(bytes(frame[:10]))
        self.assertEqual(frame[10], c1)
        self.assertEqual(frame[11], c2)

    def test_cancel_frame_structure(self):
        """Verify Cancel/Off cycle command frame."""
        frame = IfbFrameBuilder.cancel()
        self.assertEqual(len(frame), 12)
        self.assertEqual(frame[0], 99)
        self.assertEqual(frame[5], 4)  # Cancel opcode
        c1, c2 = calculate_checksum(bytes(frame[:10]))
        self.assertEqual(frame[10], c1)
        self.assertEqual(frame[11], c2)

    def test_read_state_frame_structure(self):
        """Verify Read State command frame."""
        frame = IfbFrameBuilder.read_state()
        self.assertEqual(len(frame), 12)
        self.assertEqual(frame[0], 99)
        self.assertEqual(frame[5], 7)  # Read state opcode
        c1, c2 = calculate_checksum(bytes(frame[:10]))
        self.assertEqual(frame[10], c1)
        self.assertEqual(frame[11], c2)

    def test_child_lock_frame_structure(self):
        """Verify Child Lock and Unlock binary command frames."""
        lock_frame = IfbFrameBuilder.child_lock()
        self.assertEqual(len(lock_frame), 12)
        self.assertEqual(lock_frame[4], 11)
        self.assertEqual(lock_frame[5], 1)
        c1, c2 = calculate_checksum(bytes(lock_frame[:10]))
        self.assertEqual(lock_frame[10], c1)
        self.assertEqual(lock_frame[11], c2)

        unlock_frame = IfbFrameBuilder.child_unlock()
        self.assertEqual(len(unlock_frame), 12)
        self.assertEqual(unlock_frame[4], 11)
        self.assertEqual(unlock_frame[5], 0)
        c1, c2 = calculate_checksum(bytes(unlock_frame[:10]))
        self.assertEqual(unlock_frame[10], c1)
        self.assertEqual(unlock_frame[11], c2)

    def test_decode_56_byte_telemetry_frame(self):
        """Verify decoding of a real 56-byte ESP32 response frame."""
        from ifb_cloud.frame import decode_frame
        # Captured live telemetry frame from physical washer
        raw = bytes([
            99, 56, 1, 0, 1, 1, 1, 0, 6, 0, 2, 0, 0, 0, 0, 0,
            0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 0, 1, 0,
            0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
            0, 0, 0, 0, 0, 0, 69, 242
        ])
        decoded = decode_frame(raw)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.program_code, 1)  # Mixed Soiled
        self.assertEqual(decoded.set_spin_rpm, 1400)     # index 6 -> 1400
        self.assertEqual(decoded.set_temperature_c, 30)      # index 2 -> 30C
        self.assertEqual(decoded.dry_mode, 7)       # Time Dry 120 Min
        self.assertEqual(decoded.remaining_seconds, 7200) # 2h 0m -> 7200s
        self.assertFalse(decoded.child_lock)
        self.assertTrue(decoded.door_locked)


    def test_dial_programs_catalog_and_profiles(self):
        """Verify the 14 dial programs and capability profiles match physical hardware."""
        from ifb_cloud.const import WASHER_DRYER_PROGRAMS, PROGRAM_PROFILES
        self.assertEqual(len(WASHER_DRYER_PROGRAMS), 14)
        expected_dial = [
            (14, "Express 15'"),
            (13, "Mix/Daily"),
            (17, "Cotton"),
            (8, "Synthetic"),
            (9, "Anti-Allergen"),
            (10, "Baby Wear"),
            (11, "Bulky"),
            (1, "Wash+Dry 2Hr"),
            (2, "Wash+Dry 4Hr"),
            (5, "Spin & Dry"),
            (4, "Refresh"),
            (16, "PowerSteam®"),
            (6, "CradleWash®"),
            (7, "Wool"),
        ]
        for code, name in expected_dial:
            self.assertIn(code, WASHER_DRYER_PROGRAMS)
            self.assertEqual(WASHER_DRYER_PROGRAMS[code], name)
            self.assertIn(code, PROGRAM_PROFILES)
            profile = PROGRAM_PROFILES[code]
            self.assertIn("temps", profile)
            self.assertIn("spins", profile)
            self.assertIn("dry", profile)


if __name__ == "__main__":
    unittest.main()

