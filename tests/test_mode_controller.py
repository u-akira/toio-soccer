import unittest

from test_support import load_target

mode_module = load_target("mode_controller")
DEMO = mode_module.DEMO
MANUAL = mode_module.MANUAL
ModeController = mode_module.ModeController


class ModeControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = ModeController()

    def update(self, now, logo=False, posture=1, a=False, b=False,
               tilt=(5, 6), collision=False):
        return self.controller.update(
            now, logo, posture, a, b, tilt[0], tilt[1], collision)

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

    def test_collision_overrides_manual_inputs_for_half_second_then_resumes(self):
        self.assertEqual(self.update(1, collision=True, logo=True, a=True,
                                     tilt=(30000, 30000)),
                         (-16, -16, MANUAL, "collision"))
        self.assertEqual(self.update(1.25, logo=False, b=True,
                                     tilt=(-30000, 0)),
                         (-16, -16, MANUAL, None))
        self.assertEqual(self.update(1.5, b=True), (16, -16, MANUAL, "button_turn"))

    def test_collision_pause_preserves_demo_and_posture_stop_still_wins(self):
        self.update(0, logo=True)
        self.update(0.01, logo=False)
        self.assertEqual(self.update(1, collision=True),
                         (-16, -16, DEMO, "collision"))
        self.assertEqual(self.update(1.1, posture=2),
                         (0, 0, DEMO, None))
        self.assertEqual(self.update(1.51), (12, -12, DEMO, None))

    def test_collision_lamp_blinks_red_only_during_backoff(self):
        self.update(2, collision=True)
        self.assertTrue(self.controller.backoff_lamp_on(2.1))
        self.assertFalse(self.controller.backoff_lamp_on(2.25))
        self.assertFalse(self.controller.backoff_lamp_on(2.5))


if __name__ == "__main__":
    unittest.main()
