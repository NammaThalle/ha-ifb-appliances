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


if __name__ == "__main__":
    unittest.main()
