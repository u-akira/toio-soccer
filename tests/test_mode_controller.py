import unittest

from lib.mode_controller import DEMO, MANUAL, ModeController


class ModeControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = ModeController()

    def update(self, now, logo=False, posture=1, a=False, b=False,
               tilt=(5, 6)):
        return self.controller.update(
            now, logo, posture, a, b, tilt[0], tilt[1])

    def test_logo_edges_toggle_mode_and_hold_cannot_repeat(self):
        self.assertEqual(self.update(0), (5, 6, MANUAL, None))
        self.assertEqual(self.update(1, logo=True), (12, -12, DEMO, "demo_start"))
        self.assertEqual(self.update(1.05, logo=True), (12, -12, DEMO, None))
        self.update(1.1, logo=False)
        self.assertEqual(self.update(1.2, logo=True), (5, 6, MANUAL, "demo_stop"))

    def test_demo_sequence_repeats_right_and_left_turns(self):
        self.update(10, logo=True)
        self.update(10.01, logo=False)
        self.assertEqual(self.update(11.49), (12, -12, DEMO, None))
        self.assertEqual(self.update(11.5), (-12, 12, DEMO, None))
        self.assertEqual(self.update(13.0), (12, -12, DEMO, None))

    def test_demo_ignores_buttons_and_tilt_and_posture_still_stops_motor(self):
        self.update(0, logo=True)
        self.update(0.01, logo=False)
        self.assertEqual(self.update(0.1, posture=1, a=True, b=True,
                                     tilt=(30000, -30000)),
                         (12, -12, DEMO, None))
        self.assertEqual(self.update(0.2, posture=2, a=True, tilt=(30000, 0)),
                         (0, 0, DEMO, None))

    def test_manual_button_control_resumes_after_demo(self):
        self.update(0, logo=True)
        self.update(0.01, logo=False)
        self.update(0.1, logo=True)
        self.assertEqual(self.update(0.11, logo=False, a=True),
                         (-16, 16, MANUAL, "button_turn"))


if __name__ == "__main__":
    unittest.main()
