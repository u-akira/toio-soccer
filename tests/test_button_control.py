import unittest

from lib.button_control import ButtonControl


class ButtonControlTests(unittest.TestCase):
    def setUp(self):
        self.control = ButtonControl()

    def update(self, now, a=False, b=False, tilt=(5, 6)):
        return self.control.update(now, a, b, *tilt)

    def test_a_and_b_turn_in_opposite_directions_and_sound_once(self):
        self.assertEqual(self.update(0, a=True), (-16, 16, True, False))
        self.assertEqual(self.update(0.1, a=True), (-16, 16, False, False))
        self.assertEqual(self.update(0.2, b=True), (16, -16, True, False))

    def test_both_buttons_drive_forward_for_point_two_seconds_without_feedback(self):
        self.assertEqual(self.update(10, a=True, b=True), (112, 112, False, False))
        self.assertEqual(self.update(10.19, a=True, b=True), (112, 112, False, False))
        self.assertEqual(self.update(10.2, a=True, b=True), (0, 0, False, False))
        self.assertEqual(self.update(10.25, a=True, b=True), (0, 0, False, False))
        self.assertEqual(self.update(10.3), (5, 6, False, True))

    def test_releasing_either_button_cancels_forward_on_next_update(self):
        self.update(0, a=True, b=True)
        self.assertEqual(self.update(0.1, a=True, b=True), (112, 112, False, False))
        self.assertEqual(self.update(0.2, a=True, b=True), (0, 0, False, False))
        self.assertEqual(self.update(0.25), (5, 6, False, True))

    def test_releasing_single_turn_button_returns_to_tilt_control(self):
        self.update(0, a=True)
        self.assertEqual(self.update(0.05, a=True), (-16, 16, False, False))
        self.assertEqual(self.update(0.1), (5, 6, False, True))


if __name__ == "__main__":
    unittest.main()
