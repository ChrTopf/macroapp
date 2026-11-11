"""
Main window: configures the serial connection, manages the macros and executes the
active macro whenever the buzzer is pressed.

The start command of the active macro runs once the buzzer is connected (or when a
macro is activated while connected); its stop command runs when the buzzer is
disconnected, another macro is activated, or the active macro is removed.
"""

from datetime import datetime

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from serial.tools.list_ports import comports

from buzzer_listener import BuzzerListener
from macros import Macro, execute, load_macros, save_macros

DEFAULT_BAUD_RATE = 9600
BAUD_RATES = [300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
PORT_KEY = "port"
BAUD_RATE_KEY = "baud_rate"
MAX_LOG_LINES = 1000


class MacroWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Buzzer Macros")
        self.resize(900, 600)

        self._settings = QSettings("macroapp", "macroapp")
        self._macros, self._active_index = load_macros(self._settings)
        self._listener: BuzzerListener | None = None
        self._connected = False
        self._session_active = False
        self._loading_editor = False

        self._build_ui()
        self._refresh_ports()
        self._port_combo.setEditText(self._settings.value(PORT_KEY, self._port_combo.currentText(), type=str))
        self._baud_combo.setEditText(str(self._settings.value(BAUD_RATE_KEY, DEFAULT_BAUD_RATE, type=int)))

        for row in range(len(self._macros)):
            self._macro_list.addItem(QListWidgetItem())
            self._update_list_item(row)
        if self._macros:
            self._macro_list.setCurrentRow(self._active_index if self._active_index is not None else 0)
        self._on_selection_changed(self._macro_list.currentRow())
        self._update_connection_widgets()

    # ---------------------------------------------------------------- UI setup

    def _build_ui(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self._build_connection_group())

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_macro_list_group())
        splitter.addWidget(self._build_editor_group())
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, stretch=1)

        layout.addWidget(self._build_log_group())
        self.setCentralWidget(central)

    def _build_connection_group(self) -> QGroupBox:
        group = QGroupBox("Connection")
        layout = QHBoxLayout(group)

        self._port_combo = QComboBox()
        self._port_combo.setEditable(True)
        self._port_combo.setMinimumWidth(200)
        self._refresh_button = QPushButton("Refresh")
        self._refresh_button.clicked.connect(self._refresh_ports)

        self._baud_combo = QComboBox()
        self._baud_combo.setEditable(True)
        self._baud_combo.addItems([str(rate) for rate in BAUD_RATES])
        self._baud_combo.setValidator(QIntValidator(1, 10_000_000, self))

        self._connect_button = QPushButton()
        self._connect_button.clicked.connect(self._toggle_connection)
        self._status_label = QLabel()

        layout.addWidget(QLabel("Port:"))
        layout.addWidget(self._port_combo, stretch=1)
        layout.addWidget(self._refresh_button)
        layout.addWidget(QLabel("Baud rate:"))
        layout.addWidget(self._baud_combo)
        layout.addWidget(self._connect_button)
        layout.addWidget(self._status_label)
        return group

    def _build_macro_list_group(self) -> QGroupBox:
        group = QGroupBox("Macros")
        layout = QVBoxLayout(group)

        self._macro_list = QListWidget()
        self._macro_list.currentRowChanged.connect(self._on_selection_changed)
        self._macro_list.itemDoubleClicked.connect(lambda _: self._activate_selected())
        layout.addWidget(self._macro_list)

        buttons = QHBoxLayout()
        add_button = QPushButton("Add")
        add_button.clicked.connect(self._add_macro)
        self._remove_button = QPushButton("Remove")
        self._remove_button.clicked.connect(self._remove_macro)
        self._activate_button = QPushButton("Set active")
        self._activate_button.clicked.connect(self._activate_selected)
        buttons.addWidget(add_button)
        buttons.addWidget(self._remove_button)
        buttons.addWidget(self._activate_button)
        layout.addLayout(buttons)
        return group

    def _build_editor_group(self) -> QGroupBox:
        self._editor_group = QGroupBox("Macro")
        layout = QFormLayout(self._editor_group)

        self._name_edit = QLineEdit()
        self._command_edit = QLineEdit()
        self._command_edit.setPlaceholderText("Required, e.g. xdotool key space")
        self._start_command_edit = QLineEdit()
        self._start_command_edit.setPlaceholderText("Optional")
        self._stop_command_edit = QLineEdit()
        self._stop_command_edit.setPlaceholderText("Optional")
        for edit in (self._name_edit, self._command_edit, self._start_command_edit, self._stop_command_edit):
            edit.textChanged.connect(self._on_editor_changed)

        test_button = QPushButton("Run main command")
        test_button.clicked.connect(lambda: self._run("Test", self._command_edit.text()))

        hint = QLabel(
            "The main command runs on every buzzer press. The start command runs when the macro "
            "becomes active on a connected buzzer, the stop command when it stops being active."
        )
        hint.setWordWrap(True)

        layout.addRow("Name:", self._name_edit)
        layout.addRow("Main command:", self._command_edit)
        layout.addRow("Start command:", self._start_command_edit)
        layout.addRow("Stop command:", self._stop_command_edit)
        layout.addRow("", test_button)
        layout.addRow(hint)
        return self._editor_group

    def _build_log_group(self) -> QGroupBox:
        group = QGroupBox("Log")
        layout = QVBoxLayout(group)
        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumBlockCount(MAX_LOG_LINES)
        self._log_view.setMaximumHeight(150)
        layout.addWidget(self._log_view)
        return group

    # ---------------------------------------------------------------- helpers

    def _log(self, message: str) -> None:
        self._log_view.appendPlainText(f"[{datetime.now():%H:%M:%S}] {message}")

    def _run(self, label: str, command: str) -> None:
        if not command.strip():
            self._log(f"{label}: no command configured")
            return
        try:
            execute(command)
        except OSError as e:
            self._log(f"{label}: failed to execute '{command}': {e}")
            return
        self._log(f"{label}: executed '{command}'")

    def _active_macro(self) -> Macro | None:
        return None if self._active_index is None else self._macros[self._active_index]

    def _save(self) -> None:
        save_macros(self._settings, self._macros, self._active_index)

    def _update_list_item(self, row: int) -> None:
        item = self._macro_list.item(row)
        macro = self._macros[row]
        is_active = row == self._active_index
        item.setText(f"{'▶ ' if is_active else ''}{macro.name or '(unnamed)'}")
        font = item.font()
        font.setBold(is_active)
        item.setFont(font)
        item.setToolTip(macro.command or "No main command configured")

    # ---------------------------------------------------------------- macro session

    def _begin_session(self) -> None:
        """Runs the start command of the active macro if the buzzer is connected."""
        macro = self._active_macro()
        if not self._connected or macro is None or self._session_active:
            return
        self._session_active = True
        self._log(f"Macro '{macro.name}' active")
        if macro.start_command.strip():
            self._run("Start", macro.start_command)

    def _end_session(self) -> None:
        """Runs the stop command of the active macro if its start command ran before."""
        if not self._session_active:
            return
        self._session_active = False
        macro = self._active_macro()
        if macro is not None and macro.stop_command.strip():
            self._run("Stop", macro.stop_command)

    # ---------------------------------------------------------------- macro list

    def _add_macro(self) -> None:
        self._macros.append(Macro(name=f"Macro {len(self._macros) + 1}"))
        row = len(self._macros) - 1
        self._macro_list.addItem(QListWidgetItem())
        if self._active_index is None:
            self._active_index = row
            self._begin_session()
        self._update_list_item(row)
        self._macro_list.setCurrentRow(row)
        self._name_edit.setFocus()
        self._name_edit.selectAll()
        self._save()

    def _remove_macro(self) -> None:
        row = self._macro_list.currentRow()
        if row < 0:
            return
        if row == self._active_index:
            self._end_session()
            self._active_index = None
        elif self._active_index is not None and row < self._active_index:
            self._active_index -= 1
        del self._macros[row]
        # The selection change is handled afterwards, once list and macros match again.
        self._macro_list.blockSignals(True)
        self._macro_list.takeItem(row)
        self._macro_list.blockSignals(False)
        self._on_selection_changed(self._macro_list.currentRow())
        self._save()

    def _activate_selected(self) -> None:
        row = self._macro_list.currentRow()
        if row < 0 or row == self._active_index:
            return
        self._end_session()
        previous = self._active_index
        self._active_index = row
        if previous is not None:
            self._update_list_item(previous)
        self._update_list_item(row)
        self._begin_session()
        self._save()

    def _on_selection_changed(self, row: int) -> None:
        has_selection = row >= 0
        self._editor_group.setEnabled(has_selection)
        self._remove_button.setEnabled(has_selection)
        self._activate_button.setEnabled(has_selection)

        macro = self._macros[row] if has_selection else Macro(name="")
        self._loading_editor = True
        self._name_edit.setText(macro.name)
        self._command_edit.setText(macro.command)
        self._start_command_edit.setText(macro.start_command)
        self._stop_command_edit.setText(macro.stop_command)
        self._loading_editor = False

    def _on_editor_changed(self) -> None:
        row = self._macro_list.currentRow()
        if self._loading_editor or row < 0:
            return
        macro = self._macros[row]
        macro.name = self._name_edit.text()
        macro.command = self._command_edit.text()
        macro.start_command = self._start_command_edit.text()
        macro.stop_command = self._stop_command_edit.text()
        self._update_list_item(row)
        self._save()

    # ---------------------------------------------------------------- connection

    def _refresh_ports(self) -> None:
        current = self._port_combo.currentText()
        self._port_combo.clear()
        for port_info in sorted(comports(), key=lambda info: info.device):
            self._port_combo.addItem(port_info.device)
            self._port_combo.setItemData(self._port_combo.count() - 1, port_info.description, Qt.ToolTipRole)
        if current:
            self._port_combo.setEditText(current)

    def _update_connection_widgets(self) -> None:
        listening = self._listener is not None
        self._port_combo.setEnabled(not listening)
        self._refresh_button.setEnabled(not listening)
        self._baud_combo.setEnabled(not listening)
        self._connect_button.setText("Disconnect" if listening else "Connect")
        if self._connected:
            self._status_label.setText("Connected")
        elif listening:
            self._status_label.setText("Connecting...")
        else:
            self._status_label.setText("Disconnected")

    def _toggle_connection(self) -> None:
        if self._listener is None:
            self._connect()
        else:
            self._disconnect()

    def _connect(self) -> None:
        port = self._port_combo.currentText().strip()
        baud_text = self._baud_combo.currentText().strip()
        if not port:
            QMessageBox.warning(self, "No port", "Please select or enter a serial port.")
            return
        if not baud_text.isdigit() or int(baud_text) <= 0:
            QMessageBox.warning(self, "Invalid baud rate", "Please enter a valid baud rate.")
            return
        baud_rate = int(baud_text)
        self._settings.setValue(PORT_KEY, port)
        self._settings.setValue(BAUD_RATE_KEY, baud_rate)

        self._log(f"Connecting to {port} at {baud_rate} baud...")
        self._listener = BuzzerListener(port, baud_rate, self)
        self._listener.connected.connect(self._on_connected)
        self._listener.pressed.connect(self._on_pressed)
        self._listener.failed.connect(self._on_listener_failed)
        self._listener.start()
        self._update_connection_widgets()

    def _disconnect(self) -> None:
        if self._listener is None:
            return
        self._end_session()
        self._listener.stop()
        self._listener.deleteLater()
        self._listener = None
        self._connected = False
        self._log("Disconnected")
        self._update_connection_widgets()

    def _on_connected(self) -> None:
        if self.sender() is not self._listener:
            return
        self._connected = True
        self._log("Connected")
        self._update_connection_widgets()
        self._begin_session()

    def _on_pressed(self, index: int) -> None:
        if self.sender() is not self._listener:
            return
        macro = self._active_macro()
        if macro is None:
            self._log(f"Buzzer {index} pressed, but no macro is active")
            return
        self._run(f"Buzzer {index} ({macro.name})", macro.command)

    def _on_listener_failed(self, message: str) -> None:
        if self.sender() is not self._listener:
            return
        self._log(f"Serial error: {message}")
        self._disconnect()

    def closeEvent(self, event) -> None:
        self._disconnect()
        self._save()
        super().closeEvent(event)
