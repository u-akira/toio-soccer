"""Convert accelerometer readings into toio motor speeds."""

DEADZONE_X = 1400
DEADZONE_Y = 2240
BASE_SPEED = 16
MAX_SPEED = 112
STEERING_GAIN = 0.5


def tilt_to_speeds(x, y):
    forward = 0
    if abs(y) > DEADZONE_Y:
        forward = BASE_SPEED + (abs(y) - DEADZONE_Y) // 100
        if y < 0:
            forward = -forward

    turn = 0
    if abs(x) > DEADZONE_X:
        turn = BASE_SPEED + int((abs(x) - DEADZONE_X) * STEERING_GAIN // 100)
        if x < 0:
            turn = -turn

    left = max(-MAX_SPEED, min(MAX_SPEED, forward + turn))
    right = max(-MAX_SPEED, min(MAX_SPEED, forward - turn))
    return left, right


def posture_aware_speeds(posture, x, y):
    if posture != 0x01:
        return 0, 0
    return tilt_to_speeds(x, y)


def motor_packet(left, right):
    left = int(max(-MAX_SPEED, min(MAX_SPEED, left)))
    right = int(max(-MAX_SPEED, min(MAX_SPEED, right)))
    return bytes((0x01, 0x01, 0x01 if left >= 0 else 0x02, abs(left),
                  0x02, 0x01 if right >= 0 else 0x02, abs(right)))
