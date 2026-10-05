"""Unit tests for binary packet framing and checksum algorithms."""

import unittest
from ifb_cloud.frame import IfbFrameBuilder, calculate_checksum


class TestIfbFrameBuilder(unittest.TestCase):
    """Test suite for binary command frame building."""

    def test_checksum_algorithm(self):
        """Verify signed 8-bit checksum calculation matches protocol specs."""
        test_payload = bytes([0xAA, 0x55, 0x01, 0x02, 0x03, 0x04])
        c1, c2 = calculate_checksum(test_payload)
        self.assertIsInstance(c1, int)
        self.assertIsInstance(c2, int)
        self.assertTrue(0 <= c1 <= 255)
        self.assertTrue(0 <= c2 <= 255)

    def test_start_frame_structure(self):
        """Verify Start cycle binary frame fields and header bytes."""
        frame = IfbFrameBuilder.start(program=0x01, temp=0x03, spin=0x04, dry=0x00)
        self.assertEqual(len(frame), 16)
        # Header magic bytes
        self.assertEqual(frame[0], 0xAA)
        self.assertEqual(frame[1], 0x55)
        # Frame length and command
        self.assertEqual(frame[2], 0x0E)
        self.assertEqual(frame[3], 0x01)  # 0x01 = Start
        self.assertEqual(frame[4], 0x01)  # Program
        self.assertEqual(frame[5], 0x03)  # Temp
        self.assertEqual(frame[6], 0x04)  # Spin
        self.assertEqual(frame[7], 0x00)  # Dry
        # Checksum bytes at trailer
        c1, c2 = calculate_checksum(bytes(frame[2:14]))
        self.assertEqual(frame[14], c1)
        self.assertEqual(frame[15], c2)

    def test_pause_frame_structure(self):
        """Verify Pause cycle command frame."""
        frame = IfbFrameBuilder.pause()
        self.assertEqual(len(frame), 16)
        self.assertEqual(frame[0], 0xAA)
        self.assertEqual(frame[1], 0x55)
        self.assertEqual(frame[3], 0x02)  # 0x02 = Pause
        c1, c2 = calculate_checksum(bytes(frame[2:14]))
        self.assertEqual(frame[14], c1)
        self.assertEqual(frame[15], c2)

    def test_cancel_frame_structure(self):
        """Verify Cancel/Off cycle command frame."""
        frame = IfbFrameBuilder.cancel()
        self.assertEqual(len(frame), 16)
        self.assertEqual(frame[0], 0xAA)
        self.assertEqual(frame[1], 0x55)
        self.assertEqual(frame[3], 0x03)  # 0x03 = Cancel / Power Off
        c1, c2 = calculate_checksum(bytes(frame[2:14]))
        self.assertEqual(frame[14], c1)
        self.assertEqual(frame[15], c2)


if __name__ == "__main__":
    unittest.main()
