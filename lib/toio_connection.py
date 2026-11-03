import time
import _bleio

ADDRESS_FILE = "toioaddres.json"
SERVICE_UUID = _bleio.UUID("10b20100-5b3b-4571-9508-cf3efcd7bbae")
LAMP_UUID = _bleio.UUID("10b20103-5b3b-4571-9508-cf3efcd7bbae")
MOTOR_UUID = _bleio.UUID("10b20102-5b3b-4571-9508-cf3efcd7bbae")
POSTURE_UUID = _bleio.UUID("10b20106-5b3b-4571-9508-cf3efcd7bbae")
CONFIG_UUID = _bleio.UUID("10b201ff-5b3b-4571-9508-cf3efcd7bbae")


def _load_address():
    try:
        with open(ADDRESS_FILE, "r") as file:
            values = eval(file.read())
        return _bleio.Address(bytes(values["address_bytes"]),
                              values.get("address_type", 1))
    except Exception:
        return None


def _save_address(address):
    data = "[" + ", ".join(str(b) for b in address.address_bytes) + "]"
    with open(ADDRESS_FILE, "w") as file:
        file.write('{"address_bytes": ' + data +
                   ', "address_type": ' + str(address.type) + '}')


def _characteristics(connection):
    lamp = motor = posture = None
    for service in connection.discover_remote_services():
        if service.uuid == SERVICE_UUID:
            for characteristic in service.characteristics:
                if characteristic.uuid == LAMP_UUID:
                    lamp = characteristic
                elif characteristic.uuid == MOTOR_UUID:
                    motor = characteristic
                elif characteristic.uuid == POSTURE_UUID:
                    posture = characteristic
    return lamp, motor, posture


def _posture_value(characteristic):
    data = characteristic.value
    if data and len(data) >= 5 and data[0] == 0x01:
        return data[4]
    return None


def _blink_identification(lamp):
    if lamp is None:
        return
    packets = _bleio.PacketBuffer(lamp, buffer_size=2)
    yellow = bytes((0x03, 0x01, 0x01, 0x01, 0xFF, 0xFF, 0x00))
    off = bytes((0x03, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00))
    try:
        for _ in range(6):
            packets.write(yellow)
            time.sleep(0.25)
            packets.write(off)
            time.sleep(0.25)
    finally:
        packets.deinit()


class ToioPostureMonitor:
    def __init__(self, characteristic, initial_posture=None):
        self._packets = _bleio.PacketBuffer(
            characteristic, buffer_size=8, max_packet_size=20)
        self._data = bytearray(20)
        self.posture = initial_posture
        self._packets.write(b"\x81")

    def poll(self):
        changed = False
        for _ in range(8):
            length = self._packets.readinto(self._data)
            if not length:
                break
            if length >= 5 and self._data[0] == 0x01:
                value = self._data[4]
                if value != self.posture:
                    self.posture = value
                    changed = True
                    print("toio posture:", value)
        return changed

    def deinit(self):
        self._packets.deinit()


def connect_toio(require_non_normal=True):
    adapter = _bleio.adapter
    address = _load_address()
    if address is not None:
        try:
            connection = adapter.connect(address, timeout=8)
            time.sleep(1.0)
            lamp, motor, posture = _characteristics(connection)
            value = _posture_value(posture) if posture is not None else None
            if motor is not None and (not require_non_normal or value not in (None, 0x01)):
                _blink_identification(lamp)
                print("Connected to saved toio; posture:", value)
                return connection, motor, posture, value
            connection.disconnect()
            if require_non_normal and value == 0x01:
                print("Saved toio is upright; waiting for non-normal posture.")
                return None, None, None, None
        except Exception as error:
            print("Saved address failed:", error)

    print("Scanning for toio (5 seconds)...")
    addresses = []
    try:
        for entry in adapter.start_scan(timeout=5.0):
            if entry.address not in addresses:
                addresses.append(entry.address)
    finally:
        adapter.stop_scan()

    for address in addresses:
        connection = None
        try:
            connection = adapter.connect(address, timeout=5)
            time.sleep(1.0)
            lamp, motor, posture = _characteristics(connection)
            value = _posture_value(posture) if posture is not None else None
            if motor is not None and (not require_non_normal or value not in (None, 0x01)):
                _blink_identification(lamp)
                try:
                    _save_address(address)
                except Exception as error:
                    print("Address not saved:", error)
                print("Connected to toio; posture:", value)
                return connection, motor, posture, value
        except Exception as error:
            print("Candidate failed:", error)
        if connection is not None and connection.connected:
            connection.disconnect()
    return None, None, None, None
