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


class ToioPostureMonitorTests(unittest.TestCase):
    def test_updates_posture_from_motion_notifications_and_releases_buffer(self):
        class PacketBuffer:
            def __init__(self):
                self.queue = [b"\x01\x00\x00\x00\x02", b"\x01\x00\x00\x00\x01"]
                self.deinit_called = False
                self.writes = []

            def write(self, packet):
                self.writes.append(packet)

            def readinto(self, data):
                if not self.queue:
                    return 0
                packet = self.queue.pop(0)
                data[:len(packet)] = packet
                return len(packet)

            def deinit(self):
                self.deinit_called = True

        packet_buffer = PacketBuffer()
        with patch.dict(toio_connection.__dict__, {
            "_bleio": types.SimpleNamespace(
                PacketBuffer=lambda *args, **kwargs: packet_buffer),
        }):
            monitor = toio_connection.ToioPostureMonitor("posture", 1)
            self.assertEqual(packet_buffer.writes, [b"\x81"])
            self.assertTrue(monitor.poll())
            self.assertEqual(monitor.posture, 1)
            monitor.deinit()
        self.assertTrue(packet_buffer.deinit_called)


if __name__ == "__main__":
    unittest.main()
