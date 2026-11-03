"""Show tilt direction and magnitude on the micro:bit LED matrix."""

DEADZONE_X = 1400
DEADZONE_Y = 2240
STEP_X = 6000
STEP_Y = 6000


def tilt_to_led(x, y):
    column_offset = 0
    row_offset = 0
    if abs(x) > DEADZONE_X:
        column_offset = 1 + (abs(x) - DEADZONE_X) // STEP_X
        if x < 0:
            column_offset = -column_offset
    if abs(y) > DEADZONE_Y:
        row_offset = 1 + (abs(y) - DEADZONE_Y) // STEP_Y
        if y > 0:
            row_offset = -row_offset
    column = 2 + max(-2, min(2, column_offset))
    row = 2 + max(-2, min(2, row_offset))
    return row, column


class TiltDisplay:
    def __init__(self, board, digitalio):
        self.rows = [digitalio.DigitalInOut(getattr(board, "ROW" + str(i)))
                     for i in range(1, 6)]
        self.columns = [digitalio.DigitalInOut(getattr(board, "COL" + str(i)))
                        for i in range(1, 6)]
        for pin in self.rows:
            pin.switch_to_output(value=False)
        for pin in self.columns:
            pin.switch_to_output(value=True)
        self.point = (2, 2)

    def poll(self, x, y):
        self.point = tilt_to_led(x, y)
        for pin in self.rows:
            pin.value = False
        for pin in self.columns:
            pin.value = True
        row, column = self.point
        self.columns[column].value = False
        self.rows[row].value = True

    def deinit(self):
        for pin in self.rows:
            pin.value = False
            pin.deinit()
        for pin in self.columns:
            pin.value = True
            pin.deinit()
