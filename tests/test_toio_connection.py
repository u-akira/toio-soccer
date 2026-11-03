import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


fake_bleio = types.SimpleNamespace(UUID=lambda value: value)
with patch.dict(sys.modules, {"_bleio": fake_bleio}):
    toio_connection = importlib.import_module("lib.toio_connection")


class IdentificationBlinkTests(unittest.TestCase):
    def test_blinks_yellow_for_three_seconds_and_releases_packet_buffer(self):
        packets = types.SimpleNamespace(write=Mock(), deinit=Mock())
        clock = [0.0]

        def sleep(duration):
            clock[0] += duration

        with patch.dict(toio_connection.__dict__, {
            "_bleio": types.SimpleNamespace(
                PacketBuffer=Mock(return_value=packets)),
            "time": types.SimpleNamespace(sleep=sleep),
        }):
            toio_connection._blink_identification("lamp")

        yellow = bytes((3, 1, 1, 1, 255, 255, 0))
        off = bytes((3, 1, 1, 1, 0, 0, 0))
        self.assertEqual([call.args[0] for call in packets.write.call_args_list],
                         [yellow, off] * 6)
        self.assertEqual(clock[0], 3.0)
        packets.deinit.assert_called_once()

    def test_missing_lamp_skips_blink(self):
        with patch.dict(toio_connection.__dict__, {
            "_bleio": Mock(),
        }):
            self.assertIsNone(toio_connection._blink_identification(None))


if __name__ == "__main__":
    unittest.main()
