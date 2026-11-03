"""micro:bit V2: play one short guinea-pig-like chirp on startup."""

import time
import board
import pwmio

speaker = pwmio.PWMOut(
    board.SPEAKER, duty_cycle=0, frequency=1200, variable_frequency=True
)
try:
    for pitch in (1200, 1600, 2100, 1800, 1300):
        speaker.frequency = pitch
        speaker.duty_cycle = 32768
        time.sleep(0.1)
finally:
    speaker.duty_cycle = 0
    speaker.deinit()
