"""Generate short non-blocking electronic turn chirps with PWM."""

CHIRP_STEPS = ((0.00, 1700), (0.06, 2300), (0.12, 2900), (0.19, 2100))
CHIRP_DURATION = 0.27


class SoundEffects:
    def __init__(self, board):
        self.output = None
        self.started_at = None
        self.step = -1
        try:
            import pwmio
            self.output = pwmio.PWMOut(board.SPEAKER, frequency=1700,
                                       duty_cycle=0, variable_frequency=True)
        except Exception as error:
            print("SE disabled:", error)

    def play_turn(self, now):
        if self.output is None:
            return
        self.started_at = now
        self.step = -1
        self.poll(now)

    def poll(self, now):
        if self.output is None or self.started_at is None:
            return
        elapsed = now - self.started_at
        if elapsed >= CHIRP_DURATION:
            self.output.duty_cycle = 0
            self.started_at = None
            self.step = -1
            return
        active_step = 0
        for index, (start, frequency) in enumerate(CHIRP_STEPS):
            if elapsed >= start:
                active_step = index
        if active_step != self.step:
            self.output.frequency = CHIRP_STEPS[active_step][1]
            self.output.duty_cycle = 32768
            self.step = active_step

    def deinit(self):
        if self.output is not None:
            self.output.duty_cycle = 0
            self.output.deinit()
            self.output = None
        self.started_at = None
