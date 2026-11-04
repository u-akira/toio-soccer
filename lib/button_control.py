"""Prioritize button commands over tilt control."""

TURN_SPEED = 16
FORWARD_SPEED = 112
FORWARD_DURATION = 0.2


class ButtonControl:
    def __init__(self):
        self._combo_down = False
        self._forward_until = None
        self._a_down = False
        self._b_down = False

    def update(self, now, a, b, tilt_left, tilt_right):
        combo = a and b
        if combo and not self._combo_down:
            self._forward_until = now + FORWARD_DURATION
        self._combo_down = combo

        if self._forward_until is not None:
            if now < self._forward_until:
                return FORWARD_SPEED, FORWARD_SPEED, False, False
            self._forward_until = None
            if combo:
                self._a_down = a
                self._b_down = b
                return 0, 0, False, False
        if combo:
            return 0, 0, False, False

        turn_started = (a and not self._a_down) or (b and not self._b_down)
        self._a_down = a
        self._b_down = b
        if a:
            return -TURN_SPEED, TURN_SPEED, turn_started, False
        if b:
            return TURN_SPEED, -TURN_SPEED, turn_started, False
        return tilt_left, tilt_right, False, True
