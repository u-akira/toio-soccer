import unittest

from lib.accel_i2c import create_i2c


class FakeBusio:
    def __init__(self):
        self.calls = []
        self.bus = object()

    def I2C(self, scl, sda):
        self.calls.append((scl, sda))
        return self.bus


class AccelI2CTests(unittest.TestCase):
    def test_uses_board_i2c_when_available(self):
        expected = object()

        class Board:
            SCL = object()
            SDA = object()

            @staticmethod
            def I2C():
                return expected

        busio = FakeBusio()
        self.assertIs(create_i2c(Board, busio), expected)
        self.assertEqual(busio.calls, [])

    def test_falls_back_to_busio_when_board_i2c_is_missing(self):
        class Board:
            SCL = object()
            SDA = object()

        busio = FakeBusio()
        self.assertIs(create_i2c(Board, busio), busio.bus)
        self.assertEqual(busio.calls, [(Board.SCL, Board.SDA)])


if __name__ == "__main__":
    unittest.main()
