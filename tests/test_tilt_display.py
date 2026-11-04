import unittest

from test_support import load_target

tilt_display = load_target("tilt_display")
TiltDisplay = tilt_display.TiltDisplay
tilt_to_led = tilt_display.tilt_to_led


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

    def test_show_tilt_sets_pixel_and_deinit_releases_matrix_pins(self):
        class Board:
            pass

        for index in range(1, 6):
            setattr(Board, "ROW" + str(index), FakePin("ROW" + str(index)))
            setattr(Board, "COL" + str(index), FakePin("COL" + str(index)))

        display = TiltDisplay(Board, FakeDigitalIO)
        display.show_tilt(-2000, 0)
        self.assertEqual(display._pixels[2], (0, 1, 0, 0, 0))
        display.refresh()
        display.refresh()
        display.refresh()
        self.assertTrue(Board.ROW3.value)
        self.assertFalse(Board.COL2.value)
        display.deinit()
        self.assertTrue(all(pin.deinitialized for pin in display.rows + display.columns))

    def test_demo_frame_displays_letter_d(self):
        class Board:
            pass

        for index in range(1, 6):
            setattr(Board, "ROW" + str(index), FakePin("ROW" + str(index)))
            setattr(Board, "COL" + str(index), FakePin("COL" + str(index)))
        display = TiltDisplay(Board, FakeDigitalIO)
        display.show_demo()
        self.assertEqual(display._pixels, (
            (1, 1, 1, 1, 0),
            (1, 0, 0, 0, 1),
            (1, 0, 0, 0, 1),
            (1, 0, 0, 0, 1),
            (1, 1, 1, 1, 0),
        ))


if __name__ == "__main__":
    unittest.main()
