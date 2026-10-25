import time
import _bleio
import board
import digitalio

ADDRESS_FILE = "toioaddres.json"
SERVICE_UUID = _bleio.UUID("10b20100-5b3b-4571-9508-cf3efcd7bbae")
LAMP_UUID = _bleio.UUID("10b20103-5b3b-4571-9508-cf3efcd7bbae")
MOTOR_UUID = _bleio.UUID("10b20102-5b3b-4571-9508-cf3efcd7bbae")
POSTURE_UUID = _bleio.UUID("10b20106-5b3b-4571-9508-cf3efcd7bbae")
CONFIG_UUID = _bleio.UUID("10b201ff-5b3b-4571-9508-cf3efcd7bbae")

row = digitalio.DigitalInOut(board.ROW3)
column = digitalio.DigitalInOut(board.COL3)
row.switch_to_output(value=False)
column.switch_to_output(value=True)
connection = None


def load_address():
    try:
        with open(ADDRESS_FILE, "r") as file:
            values = eval(file.read())
        return _bleio.Address(bytes(values["address_bytes"]),
                              values.get("address_type", 1))
    except Exception:
        return None


def save_address(address):
    data = "[" + ", ".join(str(b) for b in address.address_bytes) + "]"
    with open(ADDRESS_FILE, "w") as file:
        file.write('{"address_bytes": ' + data +
                   ', "address_type": ' + str(address.type) + '}')


def find_toio(adapter):
    addresses = []
    try:
        for entry in adapter.start_scan(timeout=5.0):
            if entry.address not in addresses:
                addresses.append(entry.address)
    finally:
        adapter.stop_scan()

    for address in addresses:
        candidate = None
        try:
            candidate = adapter.connect(address, timeout=5)
            time.sleep(1.0)
            characteristics = discover_characteristics(candidate)
            posture_char = characteristics[2]
            data = posture_char.value if posture_char is not None else None
            posture_value = data[4] if data and len(data) >= 5 and data[0] == 0x01 else None
            if posture_char is not None:
                print("toio posture:", posture_value)
                if posture_value is not None and posture_value != 0x01:
                    return candidate, address, characteristics, posture_value
        except Exception as error:
            print("Candidate failed:", error)
        if candidate is not None and candidate.connected:
            candidate.disconnect()
    return None, None, None, None


def discover_characteristics(connection):
    found = [None, None, None, None]
    for service in connection.discover_remote_services():
        if service.uuid == SERVICE_UUID:
            for characteristic in service.characteristics:
                if characteristic.uuid == LAMP_UUID:
                    found[0] = characteristic
                elif characteristic.uuid == MOTOR_UUID:
                    found[1] = characteristic
                elif characteristic.uuid == POSTURE_UUID:
                    found[2] = characteristic
                elif characteristic.uuid == CONFIG_UUID:
                    found[3] = characteristic
    return found


try:
    adapter = _bleio.adapter
    saved_address = load_address()
    target_confirmed = False
    while True:
        characteristics = None
        posture_value = None
        if saved_address is not None:
            try:
                print("Connecting to saved toio...")
                connection = adapter.connect(saved_address, timeout=8)
            except Exception as error:
                print("Saved address failed; scanning:", error)
                saved_address = None

        if connection is None:
            print("Scanning for toio (5 seconds)...")
            connection, found_address, characteristics, posture_value = find_toio(adapter)
            if connection is not None:
                saved_address = found_address
                try:
                    save_address(found_address)
                    print("Saved toio address:", ADDRESS_FILE)
                except Exception as error:
                    print("Address not saved:", error)

        if connection is None:
            print("No eligible toio found. Retrying in 2 seconds...")
            time.sleep(2.0)
            continue

        time.sleep(1.5)
        if characteristics is None:
            characteristics = discover_characteristics(connection)
        lamp, motor, posture, config = characteristics
        if lamp is None or motor is None or posture is None:
            print("Connected, but required toio characteristics are missing.")
            connection.disconnect()
            connection = None
            time.sleep(2.0)
            continue

        if not target_confirmed:
            data = posture.value
            posture_value = data[4] if data and len(data) >= 5 and data[0] == 0x01 else None
            print("BLE connected; toio posture:", posture_value)
            if posture_value == 0x01:
                print("Waiting: flip the toio to the non-normal posture.")
                connection.disconnect()
                connection = None
                time.sleep(2.0)
                continue
            target_confirmed = True

        row.value = True
        column.value = False
        print("TOIO CONNECTED. Posture changes will not end this test.")
        print("Center LED is on. Press Ctrl+C to stop.")
        while connection.connected:
            time.sleep(0.2)
        print("Connection lost. Retrying in 2 seconds...")
        connection = None
        row.value = False
        column.value = True
        time.sleep(2.0)
finally:
    if connection is not None and connection.connected:
        connection.disconnect()
    row.value = False
    column.value = True
    row.deinit()
    column.deinit()
