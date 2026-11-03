import unittest
from lib.tilt_drive import tilt_to_speeds, motor_packet, posture_aware_speeds


class TiltDriveTests(unittest.TestCase):
    def test_level_is_stopped(self):
        self.assertEqual(tilt_to_speeds(0, 0), (0, 0))

    def test_deadzone_edges_are_stopped(self):
        self.assertEqual(tilt_to_speeds(1400, 2240), (0, 0))
        self.assertEqual(tilt_to_speeds(-1400, -2240), (0, 0))

    def test_forward_and_reverse(self):
        self.assertEqual(tilt_to_speeds(0, 2340), (17, 17))
        self.assertEqual(tilt_to_speeds(0, -2340), (-17, -17))

    def test_left_and_right_turn(self):
        self.assertEqual(tilt_to_speeds(1400, 0), (0, 0))
        self.assertEqual(tilt_to_speeds(1401, 0), (16, -16))
        self.assertEqual(tilt_to_speeds(-1401, 0), (-16, 16))

    def test_small_lateral_tilt_exceeds_toio_minimum_motor_speed(self):
        left, right = tilt_to_speeds(1500, 0)
        self.assertGreaterEqual(abs(left), 8)
        self.assertGreaterEqual(abs(right), 8)

    def test_motor_packet_uses_integer_signed_speed_fields(self):
        self.assertEqual(motor_packet(-16, 32),
                         bytes((1, 1, 2, 16, 2, 1, 32)))

    def test_speed_is_limited(self):
        self.assertEqual(tilt_to_speeds(0, 30000), (112, 112))

    def test_tilt_is_accepted_only_when_toio_is_upright(self):
        self.assertEqual(posture_aware_speeds(1, 0, 3000), (23, 23))
        for posture in (None, 2, 3, 4, 5, 6):
            self.assertEqual(posture_aware_speeds(posture, 0, 3000), (0, 0))


if __name__ == "__main__":
    unittest.main()

