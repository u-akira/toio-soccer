import unittest

from lib.tilt_display import TiltDisplay, tilt_to_led


class FakePin:
    def __init__(self, name):
        self.name = name
        self.value = None
        self.deinitialized = False

    def switch_to_output(self, value):
        self.value = value

    def deinit(self):
        self.deinitialized = True


class FakeDigitalIO:
    @staticmethod
    def DigitalInOut(pin):
        return pin


class TiltDisplayTests(unittest.TestCase):
    def test_center_and_tilt_direction_and_strength_map_to_led_position(self):
        self.assertEqual(tilt_to_led(0, 0), (2, 2))
        self.assertEqual(tilt_to_led(1401, 0), (2, 3))
        self.assertEqual(tilt_to_led(-1401, 0), (2, 1))
        self.assertEqual(tilt_to_led(0, 2241), (1, 2))
        self.assertEqual(tilt_to_led(0, -2241), (3, 2))
        self.assertEqual(tilt_to_led(30000, 30000), (0, 4))

    def test_poll_shows_point_and_deinit_releases_matrix_pins(self):
        class Board:
            pass

        for index in range(1, 6):
            setattr(Board, "ROW" + str(index), FakePin("ROW" + str(index)))
            setattr(Board, "COL" + str(index), FakePin("COL" + str(index)))

        display = TiltDisplay(Board, FakeDigitalIO)
        display.poll(-2000, 0)
        self.assertTrue(Board.ROW3.value)
        self.assertFalse(Board.COL2.value)
        display.deinit()
        self.assertTrue(all(pin.deinitialized for pin in display.rows + display.columns))


if __name__ == "__main__":
    unittest.main()
