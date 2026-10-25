"""PCで実行できる状態遷移・BLE送信・音源リソースの検証。"""
import contextlib
import io
from pathlib import Path
import runpy
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / 'code.py'
i2c = types.SimpleNamespace(try_lock=lambda: True, scan=lambda: [], unlock=lambda: None)
hardware = {
    '_bleio': types.SimpleNamespace(UUID=lambda value: value),
    'board': types.SimpleNamespace(I2C=lambda: i2c, BTN_A='A', BTN_B='B', LOGO='LOGO', SPEAKER='SPK'),
    'digitalio': types.SimpleNamespace(
        DigitalInOut=lambda pin: types.SimpleNamespace(value=True, switch_to_input=lambda **kw: None),
        Pull=types.SimpleNamespace(UP=1)),
    'busio': types.SimpleNamespace(),
    'touchio': types.SimpleNamespace(TouchIn=lambda pin, **kw: types.SimpleNamespace(value=False)),
}
with patch.dict('sys.modules', hardware), contextlib.redirect_stdout(io.StringIO()):
    program = runpy.run_path(str(SOURCE))


class LogoBootTests(unittest.TestCase):
    def boot(self, touch_in):
        modules = dict(hardware, touchio=types.SimpleNamespace(TouchIn=touch_in))
        with patch.dict('sys.modules', modules), contextlib.redirect_stdout(io.StringIO()):
            return runpy.run_path(str(SOURCE))

    def test_logo_uses_existing_external_pullup(self):
        logo = types.SimpleNamespace(value=False)

        def touch_in(pin, pull=None):
            if pull != hardware['digitalio'].Pull.UP:
                raise ValueError('No pulldown on pin; 1Mohm recommended')
            return logo

        self.assertIs(self.boot(touch_in)['btn_logo'], logo)

    def test_old_firmware_continues_without_logo(self):
        def touch_in(pin):
            raise ValueError('No pulldown on pin; 1Mohm recommended')

        self.assertIsNone(self.boot(touch_in)['btn_logo'])

    def test_failed_touch_calibration_continues_without_logo(self):
        touch_in = Mock(side_effect=ValueError('No pullup on pin; 1Mohm recommended'))
        self.assertIsNone(self.boot(touch_in)['btn_logo'])


class NotificationBuffer:
    def __init__(self, *packets):
        self.queue = list(packets)
        self.deinit = Mock()
        self.write = Mock()

    def readinto(self, buf):
        if not self.queue:
            return 0
        packet = self.queue.pop(0)
        buf[:len(packet)] = packet
        return len(packet)


class QuietCollisions:
    posture = 1
    def poll(self):
        return False

    def deinit(self):
        pass


class CollisionMonitorTests(unittest.TestCase):
    def setUp(self):
        self.buffer = NotificationBuffer()
        constructor = program['CollisionMonitor']
        with patch.dict(constructor.__init__.__globals__, {
            '_bleio': types.SimpleNamespace(PacketBuffer=lambda *a, **kw: self.buffer),
        }):
            self.monitor = constructor('sensor')

    def test_only_new_motion_collision_flag_triggers(self):
        for data, expected in [(b'\x01\x01\x00\x00\x01', False),
                               (b'\x01\x01\x01\x00\x01', True),
                               (b'\x01\x01\x01\x00\x02', False),
                               (b'\x01\x01\x00\x00\x01', False),
                               (b'\x01\x01\x01\x00\x01', True)]:
            self.buffer.queue.append(data)
            self.assertEqual(self.monitor.poll(), expected)
        self.assertFalse(self.monitor.poll())

    def test_other_sensor_types_and_short_packets_are_ignored(self):
        self.buffer.queue.extend([b'\x02\x01\x01\x00\x01', b'\x01\x01\x01'])
        self.assertFalse(self.monitor.poll())

    def test_burst_preserves_collision_and_falling_edge(self):
        self.buffer.queue.extend([b'\x01\x01\x01\x00\x01', b'\x01\x01\x00\x00\x01'])
        self.assertTrue(self.monitor.poll())
        self.buffer.queue.append(b'\x01\x01\x01\x00\x01')
        self.assertTrue(self.monitor.poll())
        self.monitor.deinit()
        self.buffer.deinit.assert_called_once()

    def test_posture_updates_from_motion_notifications(self):
        self.assertIsNone(self.monitor.posture)
        self.buffer.write.assert_called_once_with(b'\x81')
        self.buffer.queue.append(b'\x01\x00\x00\x00\x02')
        self.monitor.poll()
        self.assertEqual(self.monitor.posture, 2)
        self.buffer.queue.append(b'\x01\x01\x00\x00\x01')
        self.monitor.poll()
        self.assertEqual(self.monitor.posture, 1)


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.controller = program['Controller'](0.0)

    def update(self, now, a=False, b=False, x=0, y=0, logo=False, z=-16384, collision=False, posture=1):
        return self.controller.update(now, a, b, x, y, logo, z, collision, posture)

    def test_toio_upside_down_or_unknown_posture_stops_all_motion(self):
        for posture in (None, 2):
            self.setUp()
            self.assertEqual(self.update(1, a=True, b=True, logo=True, collision=True,
                                         posture=posture)[:3], (0, 0, (0, 0, 0)))
        self.update(2, posture=2)
        self.assertEqual(self.update(3, a=True, posture=2)[:2], (0, 0))

    def test_toio_upside_down_cancels_demo_and_backoff(self):
        for collision in (False, True):
            self.setUp()
            self.update(1, logo=True, collision=collision)
            self.assertEqual(self.update(1.05, posture=2)[:3], (0, 0, (0, 0, 0)))
            self.assertEqual(self.update(2), (0, 0, (0, 0, 0), None))
            self.assertEqual(self.controller.mode, 'MANUAL')

    def test_collision_light_blinks_and_normal_motion_is_dark(self):
        self.update(1, collision=True)
        self.assertEqual(self.update(1.1)[2], (255, 0, 0))
        self.assertEqual(self.update(1.3)[2], (0, 0, 0))
        self.assertEqual(self.update(1.6)[2], (255, 0, 0))
        self.update(2)
        for a, b, x, y in ((True, False, 0, 0), (False, True, 0, 0),
                            (True, True, 0, 0), (False, False, 5000, -5000)):
            self.assertEqual(self.update(3, a=a, b=b, x=x, y=y)[2], (0, 0, 0))

    def test_collision_forces_one_second_reverse_over_all_inputs(self):
        self.assertEqual(self.update(1, a=True, b=True, x=30000, y=30000,
                                     logo=True, collision=True), (-16, -16, (255, 0, 0), 'collision'))
        for now in (1.05, 1.5, 1.999):
            color = (255, 0, 0) if int((now - 1) / 0.25) % 2 == 0 else (0, 0, 0)
            self.assertEqual(self.update(now, a=True, b=True, logo=True, collision=True),
                             (-16, -16, color, None))
        self.assertEqual(self.update(2, a=True, b=True, collision=True),
                         (0, 0, (0, 0, 0), 'backoff_stop'))
        self.assertEqual(self.update(2.05, a=True, b=True)[:2], (112, 112))

    def test_collision_cancels_demo_without_resuming_it(self):
        self.update(1, logo=True)
        self.assertEqual(self.update(2, collision=True)[3], 'collision')
        self.update(3)
        self.assertEqual(self.update(4), (0, 0, (0, 0, 0), None))
        self.assertEqual(self.controller.mode, 'MANUAL')
        self.assertEqual(self.update(5, logo=True)[3], 'demo_start')

    def test_inverted_stop_overrides_collision_and_cancels_backoff(self):
        self.assertEqual(self.update(1, z=16384, collision=True), (0, 0, (0, 0, 0), None))
        self.update(2)
        self.update(3, collision=True)
        self.assertEqual(self.update(3.05, z=16384), (0, 0, (0, 0, 0), 'backoff_stop'))
        self.assertEqual(self.update(3.1), (0, 0, (0, 0, 0), None))

    def test_later_collision_starts_new_backoff(self):
        self.update(1, collision=True)
        self.update(2)
        self.assertEqual(self.update(3, collision=True)[3], 'collision')
        self.assertEqual(self.controller.backoff_until, 4)

    def test_inverted_stops_buttons_tilt_and_logo(self):
        self.assertEqual(self.update(1, a=True, b=True, x=32767, y=32767,
                                     logo=True, z=16384), (0, 0, (0, 0, 0), None))
        self.assertEqual(self.controller.mode, 'MANUAL')
        self.assertEqual(self.update(2, a=True, z=16384)[:2], (0, 0))

    def test_inverted_cancels_demo_and_requires_new_logo_touch(self):
        self.update(1, logo=True)
        self.assertEqual(self.update(1.05, z=16384), (0, 0, (0, 0, 0), 'demo_stop'))
        self.assertIsNone(self.update(1.1, z=16384)[3])
        self.assertEqual(self.update(2), (0, 0, (0, 0, 0), None))
        self.assertEqual(self.update(3, logo=True)[3], 'demo_start')

    def test_inverted_stop_latches_until_upright_threshold(self):
        self.assertEqual(self.update(1, a=True, z=8191)[:2], (-16, 16))
        self.assertEqual(self.update(2, a=True, z=8192)[:2], (0, 0))
        for index, z in enumerate((8191, 0, -8191)):
            self.assertEqual(self.update(3 + index, a=True, z=z)[:2], (0, 0))
        self.assertEqual(self.update(6, a=True, z=-8192)[:2], (-16, 16))

    def test_logo_held_while_inverted_does_not_start_on_upright(self):
        self.update(1, logo=True, z=16384)
        self.assertIsNone(self.update(2, logo=True)[3])
        self.update(3)
        self.assertEqual(self.update(4, logo=True)[3], 'demo_start')

    def test_logo_start_and_each_demo_step(self):
        self.assertEqual(self.update(9.999), (0, 0, (0, 0, 0), None))
        self.assertEqual(self.update(10, logo=True), (16, 16, (0, 0, 0), 'demo_start'))
        self.assertIsNone(self.update(10.05)[3])
        self.assertEqual(self.update(11.5), (32, 16, (0, 0, 0), 'curve'))
        self.assertEqual(self.update(13.5), (-16, 16, (0, 0, 0), 'turn'))
        self.assertEqual(self.update(14.5), (0, 0, (0, 0, 0), 'stop'))
        self.assertEqual(self.update(15.5), (0, 0, (0, 0, 0), 'demo_stop'))
        self.assertEqual(self.controller.mode, 'MANUAL')
        self.assertEqual(self.update(100), (0, 0, (0, 0, 0), None))

    def test_buttons_preempt_demo_in_same_tick(self):
        for a, b, expected in [(True, False, (-16, 16)),
                               (False, True, (16, -16)),
                               (True, True, (112, 112))]:
            self.setUp()
            self.update(10, logo=True)
            command = self.update(10.05, a=a, b=b, x=-32000, y=-32000)
            self.assertEqual(command[:2], expected)
            self.assertEqual(command[3], 'button_turn' if a != b else 'button_forward')
            self.assertEqual(self.controller.mode, 'MANUAL')

    def test_tilt_preempts_even_when_output_rounds_to_zero(self):
        self.update(10, logo=True)
        self.assertEqual(self.update(10.05, x=1401)[3], 'demo_stop')
        self.assertEqual(self.controller.mode, 'MANUAL')

    def test_button_sound_once_per_single_button_turn(self):
        self.assertEqual(self.update(1, a=True)[3], 'button_turn')
        self.assertIsNone(self.update(1.05, a=True)[3])
        self.assertEqual(self.update(2, b=True)[3], 'button_turn')
        self.assertIsNone(self.update(2.05, b=True)[3])
        self.update(3)
        self.assertEqual(self.update(4, b=True)[3], 'button_turn')

    def test_forward_sound_once_per_ab_press_and_tilt_is_silent(self):
        self.assertEqual(self.update(1, a=True, b=True)[3], 'button_forward')
        self.assertIsNone(self.update(1.05, a=True, b=True)[3])
        self.assertIsNone(self.update(2, x=5000, y=5000)[3])
        self.assertEqual(self.update(3, a=True, b=True)[3], 'button_forward')

    def test_switch_between_single_button_and_ab_changes_sound(self):
        self.assertEqual(self.update(1, a=True)[3], 'button_turn')
        self.assertEqual(self.update(2, a=True, b=True)[3], 'button_forward')
        self.assertEqual(self.update(3, b=True)[3], 'button_turn')

    def test_inverted_ab_press_is_silent_even_on_recovery(self):
        self.assertIsNone(self.update(1, a=True, b=True, z=16384)[3])
        self.assertIsNone(self.update(2, a=True, b=True)[3])

    def test_inverted_button_press_does_not_emit_sound_on_recovery(self):
        self.assertIsNone(self.update(1, a=True, z=16384)[3])
        self.assertIsNone(self.update(2, a=True)[3])

    def test_idle_never_starts_demo_and_deadzone_is_inclusive(self):
        for now in (0, 9.999, 10, 10.001, 100, 3600):
            self.assertEqual(self.update(now, x=1400, y=-2240), (0, 0, (0, 0, 0), None))
            self.assertEqual(self.controller.mode, 'MANUAL')

    def test_logo_starts_stops_once_per_touch_and_stays_stopped(self):
        self.assertEqual(self.update(1, logo=True)[3], 'demo_start')
        self.assertIsNone(self.update(1.5, logo=True)[3])
        self.update(1.6)
        self.assertEqual(self.update(2, logo=True), (0, 0, (0, 0, 0), 'demo_stop'))
        self.assertIsNone(self.update(3, logo=True)[3])
        self.assertIsNone(self.update(30)[3])
        self.assertEqual(self.update(31, logo=True)[3], 'demo_start')

    def test_logo_bounce_and_manual_input_priority(self):
        self.update(1, logo=True)
        self.update(1.05)
        self.assertIsNone(self.update(1.1, logo=True)[3])
        self.update(1.3)
        self.update(1.5, logo=True)
        self.update(2)
        self.assertEqual(self.update(3, a=True, logo=True)[:2], (-16, 16))
        self.assertEqual(self.controller.mode, 'MANUAL')

    def test_manual_input_does_not_enable_auto_demo_after_completion(self):
        self.update(10, logo=True)
        self.update(16)
        self.update(20, b=True)
        self.assertIsNone(self.update(29.99)[3])
        self.assertIsNone(self.update(30)[3])
        self.assertIsNone(self.update(3600)[3])
        self.assertEqual(self.update(3601, logo=True)[3], 'demo_start')

    def test_delayed_loop_uses_elapsed_time(self):
        self.update(10, logo=True)
        self.assertEqual(self.update(14)[3], 'turn')
        self.assertEqual(self.update(100)[3], 'demo_stop')

    def test_tilt_packets_are_integer_clamped_and_directional(self):
        for x in (-32768, -1401, 0, 1401, 32767):
            for y in (-32768, -2241, 0, 2241, 32767):
                left, right, color = program['manual_command'](False, False, x, y)
                packet = program['motor_packet'](left, right)
                self.assertEqual(len(packet), 7)
                self.assertLessEqual(packet[3], 112)
                self.assertLessEqual(packet[6], 112)
                self.assertEqual(packet[2], 1 if left >= 0 else 2)
                self.assertEqual(packet[5], 1 if right >= 0 else 2)
        self.assertEqual(program['manual_command'](False, False, 0, -3000)[2], (0, 0, 0))


class SoundTests(unittest.TestCase):
    def setUp(self):
        self.output = Mock(playing=True)
        self.wave = Mock()
        modules = {
            'audiopwmio': types.SimpleNamespace(PWMAudioOut=lambda pin: self.output),
            'audiocore': types.SimpleNamespace(WaveFile=lambda file: self.wave),
        }
        with patch.dict('sys.modules', modules):
            with contextlib.redirect_stdout(io.StringIO()):
                self.sounds = program['SoundEffects']()

    def test_play_does_not_wait_and_poll_releases_finished_file(self):
        file = Mock()
        with patch('builtins.open', return_value=file):
            self.sounds.play('turn')
        self.output.play.assert_called_once_with(self.wave)
        self.sounds.poll()
        file.close.assert_not_called()
        self.output.playing = False
        self.sounds.poll()
        self.wave.deinit.assert_called_once()
        file.close.assert_called_once()

    def test_missing_sound_interrupts_previous_and_can_be_retried(self):
        file = Mock()
        with patch('builtins.open', return_value=file):
            self.sounds.play('turn')
        with patch('builtins.open', side_effect=OSError('missing')) as opening:
            with contextlib.redirect_stdout(io.StringIO()):
                self.sounds.play('turn')
                self.sounds.play('turn')
            self.assertEqual(opening.call_count, 2)
        file.close.assert_called_once()
        self.assertIsNone(self.sounds.file)

    def test_absolute_sound_path_and_retry_after_file_is_added(self):
        with patch('builtins.open', side_effect=OSError('missing')):
            with contextlib.redirect_stdout(io.StringIO()):
                self.sounds.play('turn')
        file = Mock()
        with patch('builtins.open', return_value=file) as opening:
            with contextlib.redirect_stdout(io.StringIO()):
                self.sounds.play('turn')
        opening.assert_called_once_with('/se/turn.wav', 'rb')
        self.output.play.assert_called_once_with(self.wave)


class MainLoopTests(unittest.TestCase):
    def test_toio_posture_notifications_stop_pressed_buttons_and_keep_lamp_off(self):
        main = program['main']
        connection = types.SimpleNamespace(connected=True, disconnect=Mock())
        motor, lamp, sound = Mock(), Mock(), Mock()
        notifications = NotificationBuffer(b'\x01\x01\x00\x00\x01')
        clock = [0.0]

        def sleep(interval):
            clock[0] = round(clock[0] + interval, 2)
            if clock[0] == 0.05:
                notifications.queue.append(b'\x01\x00\x00\x00\x02')
            if clock[0] == 0.15:
                notifications.queue.append(b'\x01\x01\x00\x00\x01')
            if clock[0] >= 0.2:
                connection.connected = False

        with patch.dict(main.__globals__, {
            'connect_toio': lambda: (connection, 'lamp', 'motor', 'sensor'),
            '_bleio': types.SimpleNamespace(PacketBuffer=lambda char, **kw:
                {'motor': motor, 'lamp': lamp, 'sensor': notifications}[char]),
            'SoundEffects': lambda: sound,
            'time': types.SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
            'btn_a': types.SimpleNamespace(value=False), 'btn_b': types.SimpleNamespace(value=False),
            'btn_logo': None, 'get_accel': lambda reg: -16384 if reg == 0x2C else 0,
        }), contextlib.redirect_stdout(io.StringIO()):
            main()
        self.assertEqual([call.args[0] for call in motor.write.call_args_list],
                         [program['motor_packet'](112, 112), program['motor_packet'](0, 0),
                          program['motor_packet'](0, 0), program['motor_packet'](112, 112)])
        self.assertTrue(all(call.args[0] == bytes((3, 0, 1, 1, 0, 0, 0))
                            for call in lamp.write.call_args_list))
        notifications.write.assert_called_once_with(b'\x81')

    def test_collision_notification_reverses_for_one_second_and_plays_once(self):
        main = program['main']
        connection = types.SimpleNamespace(connected=True, disconnect=Mock())
        motor, lamp, sound = Mock(), Mock(), Mock()
        notifications = NotificationBuffer(b'\x01\x01\x00\x00\x01')
        clock = [0.0]

        def sleep(interval):
            clock[0] = round(clock[0] + interval, 2)
            if clock[0] in (0.05, 0.1):
                notifications.queue.append(b'\x01\x01\x01\x00\x01')
            if clock[0] == 0.5:
                notifications.queue.extend([b'\x01\x01\x00\x00\x01',
                                             b'\x01\x01\x01\x00\x01'])
            if clock[0] >= 1.15:
                connection.connected = False

        with patch.dict(main.__globals__, {
            'connect_toio': lambda: (connection, 'lamp', 'motor', 'sensor'),
            '_bleio': types.SimpleNamespace(PacketBuffer=lambda char, **kw:
                {'motor': motor, 'lamp': lamp, 'sensor': notifications}[char]),
            'SoundEffects': lambda: sound,
            'time': types.SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
            'btn_a': types.SimpleNamespace(value=False), 'btn_b': types.SimpleNamespace(value=False),
            'btn_logo': None, 'get_accel': lambda reg: -16384 if reg == 0x2C else 0,
        }), contextlib.redirect_stdout(io.StringIO()):
            main()
        packets = [call.args[0] for call in motor.write.call_args_list]
        self.assertEqual(packets[0], program['motor_packet'](112, 112))
        self.assertEqual(packets[1:21], [program['motor_packet'](-16, -16)] * 20)
        self.assertEqual(packets[21], program['motor_packet'](0, 0))
        self.assertEqual(packets[22], program['motor_packet'](112, 112))
        colors = [call.args[0][-3:] for call in lamp.write.call_args_list]
        self.assertEqual(colors[0], bytes((0, 0, 0)))
        self.assertEqual(colors[1], bytes((255, 0, 0)))
        self.assertEqual(colors[7], bytes((0, 0, 0)))
        self.assertEqual(colors[12], bytes((255, 0, 0)))
        self.assertEqual(colors[21], bytes((0, 0, 0)))
        self.assertEqual([call.args[0] for call in sound.play.call_args_list], ['forward', 'collision'])
        notifications.deinit.assert_called_once()

    def test_full_demo_and_startup_are_silent(self):
        main = program['main']
        connection = types.SimpleNamespace(connected=True, disconnect=Mock())
        motor, lamp, sound = Mock(), Mock(), Mock()
        clock = [0.0]
        logo = types.SimpleNamespace(value=True)

        def sleep(interval):
            clock[0] += 0.5
            logo.value = False
            if clock[0] >= 6:
                connection.connected = False

        with patch.dict(main.__globals__, {
            'connect_toio': lambda: (connection, 'lamp', 'motor', 'sensor'),
            'CollisionMonitor': lambda sensor: QuietCollisions(),
            '_bleio': types.SimpleNamespace(PacketBuffer=lambda char, **kw: motor if char == 'motor' else lamp),
            'SoundEffects': lambda: sound,
            'time': types.SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
            'btn_a': types.SimpleNamespace(value=True), 'btn_b': types.SimpleNamespace(value=True),
            'btn_logo': logo, 'get_accel': lambda reg: -16384 if reg == 0x2C else 0,
        }), contextlib.redirect_stdout(io.StringIO()):
            main()
        packets = [call.args[0] for call in motor.write.call_args_list]
        for left, right in ((16, 16), (32, 16), (-16, 16), (0, 0)):
            self.assertIn(program['motor_packet'](left, right), packets)
        sound.play.assert_not_called()

    def test_z_axis_stops_demo_through_ble_even_with_buttons_pressed(self):
        main = program['main']
        connection = types.SimpleNamespace(connected=True, disconnect=Mock())
        motor, lamp, sound = Mock(), Mock(), Mock()
        clock = [0.0]
        button = types.SimpleNamespace(value=True)
        logo = types.SimpleNamespace(value=True)

        def sleep(interval):
            clock[0] = round(clock[0] + interval, 2)
            button.value = False
            logo.value = False
            if clock[0] >= 0.15:
                connection.connected = False

        def accel(reg):
            if reg == 0x2C:
                return -16384 if clock[0] == 0 else 16384
            return 0

        with patch.dict(main.__globals__, {
            'connect_toio': lambda: (connection, 'lamp', 'motor', 'sensor'),
            'CollisionMonitor': lambda sensor: QuietCollisions(),
            '_bleio': types.SimpleNamespace(PacketBuffer=lambda char, **kw: motor if char == 'motor' else lamp),
            'SoundEffects': lambda: sound,
            'time': types.SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
            'btn_a': button, 'btn_b': button, 'btn_logo': logo, 'get_accel': accel,
        }), contextlib.redirect_stdout(io.StringIO()):
            main()
        self.assertEqual([call.args[0] for call in motor.write.call_args_list],
                         [program['motor_packet'](16, 16), program['motor_packet'](0, 0),
                          program['motor_packet'](0, 0)])
        self.assertEqual(lamp.write.call_args.args[0][-3:], bytes((0, 0, 0)))
        sound.play.assert_not_called()

    def test_real_controller_preempts_demo_through_shared_ble_path(self):
        main = program['main']
        connection = types.SimpleNamespace(connected=True, disconnect=Mock())
        motor, lamp, sound = Mock(), Mock(), Mock()
        clock = [0.0]
        button = types.SimpleNamespace(value=True)
        logo = types.SimpleNamespace(value=False)
        button_b = types.SimpleNamespace(value=True)

        def sleep(interval):
            clock[0] = round(clock[0] + interval, 2)
            button.value = clock[0] not in (10.05, 10.1)
            button_b.value = clock[0] != 10.1
            logo.value = clock[0] == 10.0
            if clock[0] >= 10.2:
                connection.connected = False

        replacements = {
            'connect_toio': lambda: (connection, 'lamp', 'motor', 'sensor'),
            'CollisionMonitor': lambda sensor: QuietCollisions(),
            '_bleio': types.SimpleNamespace(PacketBuffer=lambda char, **kw: motor if char == 'motor' else lamp),
            'SoundEffects': lambda: sound,
            'time': types.SimpleNamespace(monotonic=lambda: clock[0], sleep=sleep),
            'btn_a': button, 'btn_b': button_b,
            'btn_logo': logo, 'get_accel': lambda reg: -16384 if reg == 0x2C else 0,
        }
        with patch.dict(main.__globals__, replacements), contextlib.redirect_stdout(io.StringIO()):
            main()
        packets = [call.args[0] for call in motor.write.call_args_list]
        self.assertEqual(packets[200], bytes((1, 1, 1, 16, 2, 1, 16)))
        self.assertEqual(packets[201], bytes((1, 1, 2, 16, 2, 1, 16)))
        self.assertEqual(packets[202], program['motor_packet'](112, 112))
        self.assertEqual(packets[203], program['motor_packet'](0, 0))
        self.assertEqual([call.args[0] for call in sound.play.call_args_list], ['turn', 'forward'])
        sound.deinit.assert_called_once()

    def test_ble_error_attempts_stop_before_disconnect(self):
        main = program['main']
        connection = types.SimpleNamespace(connected=True, disconnect=Mock())
        motor, lamp, sound = Mock(), Mock(), Mock()
        lamp.write.side_effect = OSError('BLE write failed')
        with patch.dict(main.__globals__, {
            'connect_toio': lambda: (connection, 'lamp', 'motor', 'sensor'),
            'CollisionMonitor': lambda sensor: QuietCollisions(),
            '_bleio': types.SimpleNamespace(PacketBuffer=lambda char, **kw: motor if char == 'motor' else lamp),
            'SoundEffects': lambda: sound,
        }), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(OSError):
                main()
        self.assertEqual(motor.write.call_args.args[0], program['motor_packet'](0, 0))
        connection.disconnect.assert_called_once()
        sound.deinit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
