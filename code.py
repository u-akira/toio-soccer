import time
import _bleio
import board
import busio
import digitalio
import touchio
from accel_i2c import create_i2c
from toio_connection import connect_toio, ToioPostureMonitor
from tilt_drive import posture_aware_speeds, motor_packet
from tilt_display import TiltDisplay
from sound_effects import SoundEffects
from mode_controller import ModeController

display = TiltDisplay(board, digitalio)
btn_a = digitalio.DigitalInOut(board.BTN_A)
btn_a.switch_to_input(pull=digitalio.Pull.UP)
btn_b = digitalio.DigitalInOut(board.BTN_B)
btn_b.switch_to_input(pull=digitalio.Pull.UP)
btn_logo = None
try:
    btn_logo = touchio.TouchIn(board.LOGO, pull=digitalio.Pull.UP)
except (TypeError, ValueError) as error:
    print("Logo touch disabled:", error)
mode_controller = ModeController()
sounds = SoundEffects(board)
connection = None
motor_packets = None
posture_monitor = None
i2c = create_i2c(board, busio)
accel_address = None
while not i2c.try_lock():
    pass
try:
    devices = i2c.scan()
    for address in (0x19, 0x18, 0x1D):
        if address in devices:
            accel_address = address
            break
    if accel_address is None:
        raise RuntimeError("micro:bit accelerometer not found")
    i2c.writeto(accel_address, bytes((0x20, 0x57)))
finally:
    i2c.unlock()


def read_accel(register):
    if not i2c.try_lock():
        return 0
    try:
        result = bytearray(2)
        i2c.writeto_then_readfrom(accel_address, bytes((register | 0x80,)), result)
        value = (result[1] << 8) | result[0]
        return value - 65536 if value > 32767 else value
    finally:
        i2c.unlock()


try:
    target_confirmed = False
    while True:
        connection, motor, posture_characteristic, initial_posture = connect_toio(
            not target_confirmed)
        if connection is None:
            print("No eligible toio; retrying in 2 seconds.")
            time.sleep(2.0)
            continue

        target_confirmed = True
        motor_packets = _bleio.PacketBuffer(motor, buffer_size=2)
        posture_monitor = ToioPostureMonitor(
            posture_characteristic, initial_posture)
        print("TOIO CONNECTED. Tilt micro:bit to move; Ctrl+C to stop.")
        next_report = time.monotonic()
        next_control = next_report
        next_display = next_report
        while connection.connected:
            now = time.monotonic()
            if now >= next_display:
                display.refresh()
                next_display = now + 0.001
            if now >= next_control:
                posture_monitor.poll()
                x = read_accel(0x28)
                y = read_accel(0x2A)
                logo = btn_logo.value if btn_logo is not None else False
                tilt_left, tilt_right = posture_aware_speeds(
                    posture_monitor.posture, x, y)
                left, right, display_mode, event = mode_controller.update(
                    now, logo, posture_monitor.posture,
                    not btn_a.value, not btn_b.value, tilt_left, tilt_right)
                if event in ("demo_start", "demo_stop"):
                    print("DEMO", event)
                    sounds.play_turn(now)
                elif event == "button_turn":
                    sounds.play_turn(now)
                if display_mode == "demo":
                    display.show_demo()
                else:
                    display.show_tilt(x, y)
                sounds.poll(now)
                motor_packets.write(motor_packet(left, right))
                if now >= next_report:
                    print("toio posture:", posture_monitor.posture,
                          "tilt raw:", x, y, "motor:", left, right)
                    next_report = now + 1.0
                next_control = now + 0.05
            time.sleep(0.001)

        motor_packets.deinit()
        motor_packets = None
        posture_monitor.deinit()
        posture_monitor = None
        connection = None
        print("Connection lost; retrying in 2 seconds.")
        time.sleep(2.0)
finally:
    if motor_packets is not None:
        motor_packets.write(motor_packet(0, 0))
        motor_packets.deinit()
    if posture_monitor is not None:
        posture_monitor.deinit()
    sounds.deinit()
    if connection is not None and connection.connected:
        connection.disconnect()
    display.deinit()
