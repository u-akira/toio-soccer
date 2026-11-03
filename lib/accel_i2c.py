"""Create the micro:bit I2C bus used by its onboard accelerometer."""


def create_i2c(board, busio):
    try:
        return board.I2C()
    except AttributeError:
        return busio.I2C(board.SCL, board.SDA)
