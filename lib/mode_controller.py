"""Own operating-mode transitions and choose the active motor command."""

try:
    from .button_control import ButtonControl
except ImportError:
    from button_control import ButtonControl

MANUAL = "manual"
DEMO = "demo"

# Each entry is (seconds, left-wheel speed, right-wheel speed).
DEMO_SEQUENCE = (
    (1.5, 12, -12),
    (1.5, -12, 12),
)
BACKOFF_SPEED = 16
BACKOFF_DURATION = 0.5


class ModeController:
    def __init__(self):
        self.mode = MANUAL
        self._logo_down = False
        self._demo_started_at = 0.0
        self._backoff_until = None
        self._backoff_started_at = None
        self._buttons = ButtonControl()

    def backoff_lamp_on(self, now):
        if self._backoff_until is None or now >= self._backoff_until:
            return False
        return int((now - self._backoff_started_at) / 0.25) % 2 == 0

    def update(self, now, logo_pressed, posture, a, b, tilt_left, tilt_right,
               collision=False):
        logo_edge = logo_pressed and not self._logo_down
        self._logo_down = logo_pressed
        event = None

        if self._backoff_until is not None and now >= self._backoff_until:
            if self.mode == DEMO:
                self._demo_started_at += now - self._backoff_started_at
            self._backoff_until = None
            self._backoff_started_at = None
        if collision and self._backoff_until is None:
            self._backoff_until = now + BACKOFF_DURATION
            self._backoff_started_at = now
            event = "collision"
        if self._backoff_until is not None:
            if posture != 0x01:
                return 0, 0, self.mode, event
            return -BACKOFF_SPEED, -BACKOFF_SPEED, self.mode, event

        if logo_edge:
            if self.mode == MANUAL:
                self.mode = DEMO
                self._demo_started_at = now
                event = "demo_start"
            else:
                self.mode = MANUAL
                event = "demo_stop"
            self._buttons.reset()

        if self.mode == DEMO:
            left, right = self._demo_command(now)
            if posture != 0x01:
                left = right = 0
            return left, right, DEMO, event

        left, right, turn_started, _ = self._buttons.update(
            now, posture == 0x01 and a, posture == 0x01 and b,
            tilt_left, tilt_right)
        if posture != 0x01:
            left = right = 0
        if turn_started and event is None:
            event = "button_turn"
        return left, right, MANUAL, event

    def _demo_command(self, now):
        cycle_duration = 0.0
        for duration, _, _ in DEMO_SEQUENCE:
            cycle_duration += duration
        phase_time = (now - self._demo_started_at) % cycle_duration
        for duration, left, right in DEMO_SEQUENCE:
            if phase_time < duration:
                return left, right
            phase_time -= duration
        return 0, 0
