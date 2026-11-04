import sys
import types
import unittest
from unittest.mock import patch

from lib.sound_effects import SoundEffects


class FakePWM:
    def __init__(self, pin, frequency, duty_cycle, variable_frequency):
        self.pin = pin
        self.frequency = frequency
        self.duty_cycle = duty_cycle
        self.variable_frequency = variable_frequency
        self.deinitialized = False

    def deinit(self):
        self.deinitialized = True


class SoundEffectsTests(unittest.TestCase):
    def setUp(self):
        self.pwm = None

        def create_pwm(*args, **kwargs):
            self.pwm = FakePWM(*args, **kwargs)
            return self.pwm

        self.pwmio = types.SimpleNamespace(PWMOut=create_pwm)
        self.board = types.SimpleNamespace(SPEAKER="speaker")

    def test_turn_chirp_changes_frequency_without_audio_file(self):
        with patch.dict(sys.modules, {"pwmio": self.pwmio}):
            sound = SoundEffects(self.board)
        self.assertTrue(self.pwm.variable_frequency)
        self.assertEqual(self.pwm.duty_cycle, 0)
        sound.play_turn(10.0)
        self.assertEqual((self.pwm.frequency, self.pwm.duty_cycle), (1700, 32768))
        sound.poll(10.07)
        self.assertEqual(self.pwm.frequency, 2300)
        sound.poll(10.13)
        self.assertEqual(self.pwm.frequency, 2900)
        sound.poll(10.20)
        self.assertEqual(self.pwm.frequency, 2100)
        sound.poll(10.28)
        self.assertEqual(self.pwm.duty_cycle, 0)
        sound.deinit()
        self.assertTrue(self.pwm.deinitialized)


if __name__ == "__main__":
    unittest.main()
