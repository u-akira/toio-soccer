import time
import _bleio
import board
import busio
import digitalio
from accel_i2c import create_i2c
from toio_connection import connect_toio, ToioPostureMonitor
from tilt_drive import posture_aware_speeds, motor_packet
from tilt_display import TiltDisplay
from button_control import ButtonControl
from sound_effects import SoundEffects

display = TiltDisplay(board, digitalio)
btn_a = digitalio.DigitalInOut(board.BTN_A)
btn_a.switch_to_input(pull=digitalio.Pull.UP)
btn_b = digitalio.DigitalInOut(board.BTN_B)
btn_b.switch_to_input(pull=digitalio.Pull.UP)
button_control = ButtonControl()
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
        while connection.connected:
            posture_monitor.poll()
            x = read_accel(0x28)
            y = read_accel(0x2A)
            tilt_left, tilt_right = posture_aware_speeds(
                posture_monitor.posture, x, y)
            left, right, turn_started, show_tilt = button_control.update(
                time.monotonic(),
                posture_monitor.posture == 0x01 and not btn_a.value,
                posture_monitor.posture == 0x01 and not btn_b.value,
                tilt_left, tilt_right)
            if show_tilt:
                display.poll(x, y)
            if turn_started:
                sounds.play_turn(time.monotonic())
            sounds.poll(time.monotonic())
            motor_packets.write(motor_packet(left, right))
            now = time.monotonic()
            if now >= next_report:
                print("toio posture:", posture_monitor.posture,
                      "tilt raw:", x, y, "motor:", left, right)
                next_report = now + 1.0
            time.sleep(0.05)

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
