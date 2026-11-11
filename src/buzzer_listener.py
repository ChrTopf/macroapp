"""
Background thread that reads button presses from the Arduino buzzer.

The Arduino sends one line per button press:

    KEY:<index>
"""

from PyQt5.QtCore import QThread, pyqtSignal
from serial import Serial, SerialException

KEY_PREFIX = "KEY:"
READ_TIMEOUT = 0.1


def parse_key_line(line: str) -> int | None:
    """Returns the button index of a 'KEY:<index>' line, or None for any other line."""
    if not line.startswith(KEY_PREFIX):
        return None
    index = line[len(KEY_PREFIX):].strip()
    return int(index) if index.isdigit() else None


class BuzzerListener(QThread):
    connected = pyqtSignal()
    pressed = pyqtSignal(int)
    failed = pyqtSignal(str)

    def __init__(self, port: str, baud_rate: int, parent=None):
        super().__init__(parent)
        self._port = port
        self._baud_rate = baud_rate
        self._running = True

    def stop(self) -> None:
        """Stops reading and blocks until the serial port is closed."""
        self._running = False
        self.wait()

    def run(self) -> None:
        try:
            with Serial(self._port, self._baud_rate, timeout=READ_TIMEOUT) as connection:
                self.connected.emit()
                buffer = b""
                while self._running:
                    # Reads with a timeout so that stop() is noticed even without input.
                    buffer += connection.read(connection.in_waiting or 1)
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        index = parse_key_line(line.decode("ascii", errors="ignore").strip())
                        if index is not None:
                            self.pressed.emit(index)
        except (SerialException, OSError, ValueError) as e:
            self.failed.emit(str(e))
