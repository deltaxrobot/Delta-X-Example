import sys
import threading
import time
from typing import List, Optional, Tuple

import serial
from serial.tools import list_ports

from PyQt5.QtCore import Qt, QObject, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


DEFAULT_BAUD = 115200


class SerialManager(QObject):
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()
    error = pyqtSignal(str)
    lineReceived = pyqtSignal(str)
    lineSent = pyqtSignal(str)
    portsRefreshed = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()
        self._serial: Optional[serial.Serial] = None
        self._reader_thread: Optional[threading.Thread] = None
        self._reader_running: bool = False
        self._lock = threading.Lock()

    # ---------- Discovery ----------
    def refresh_ports(self) -> None:
        ports = [p.device for p in list_ports.comports()]
        self.portsRefreshed.emit(ports)

    def autoscan_and_connect(self, baud: int = DEFAULT_BAUD) -> bool:
        for port_info in list_ports.comports():
            port_name = port_info.device
            try:
                trial = serial.Serial(port_name, baud, timeout=1)
                time.sleep(0.3)
                try:
                    trial.reset_input_buffer()
                except Exception:
                    pass
                trial.write(b"IsDelta\n")
                reply = trial.readline().decode("utf-8", errors="ignore").strip()
                if "YesDelta" in reply:
                    trial.close()
                    return self.open_port(port_name, baud)
                trial.close()
            except Exception:
                # Ignore ports that cannot be opened/read
                continue
        self.error.emit("Không tìm thấy robot Delta X qua Auto-Scan.")
        return False

    # ---------- Connection ----------
    def open_port(self, port_name: str, baud: int = DEFAULT_BAUD) -> bool:
        self.close_port()
        try:
            self._serial = serial.Serial(port_name, baud, timeout=1)
            # Give the device a moment to reset (common on Arduino-like boards)
            time.sleep(0.3)
            self._start_reader()
            self.connected.emit(port_name)
            return True
        except Exception as exc:
            self._serial = None
            self.error.emit(f"Không thể mở cổng {port_name}: {exc}")
            return False

    def close_port(self) -> None:
        with self._lock:
            if self._serial is None:
                return
            self._stop_reader()
            try:
                self._serial.close()
            except Exception:
                pass
            finally:
                self._serial = None
                self.disconnected.emit()

    # ---------- IO ----------
    def send_line(self, command: str) -> None:
        with self._lock:
            if self._serial is None:
                self.error.emit("Chưa kết nối cổng COM.")
                return
            try:
                normalized = command.strip()
                data = (normalized.rstrip("\r\n") + "\n").encode("utf-8")
                self._serial.write(data)
                self.lineSent.emit(normalized)
            except Exception as exc:
                self.error.emit(f"Lỗi gửi lệnh: {exc}")

    def _start_reader(self) -> None:
        if self._reader_running:
            return
        self._reader_running = True

        def _read_loop() -> None:
            while self._reader_running:
                ser_ref: Optional[serial.Serial]
                with self._lock:
                    ser_ref = self._serial
                if ser_ref is None:
                    break
                try:
                    line = ser_ref.readline()
                    if not line:
                        continue
                    decoded = line.decode("utf-8", errors="ignore").rstrip("\r\n")
                    if decoded:
                        self.lineReceived.emit(decoded)
                except Exception:
                    # Short sleep to avoid tight error loops
                    time.sleep(0.05)

        self._reader_thread = threading.Thread(target=_read_loop, daemon=True)
        self._reader_thread.start()

    def _stop_reader(self) -> None:
        if not self._reader_running:
            return
        self._reader_running = False
        if self._reader_thread is not None:
            try:
                self._reader_thread.join(timeout=0.5)
            except Exception:
                pass
            self._reader_thread = None


class TerminalTab(QWidget):
    def __init__(self, serial_manager: SerialManager) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Log view
        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Robot responses will appear here…")
        layout.addWidget(self.log_view)

        # Input line and send
        input_bar = QHBoxLayout()
        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("Nhập G-code, ví dụ: G28 hoặc Position …")
        self.send_button = QPushButton("Send", self)
        self.clear_button = QPushButton("Clear", self)
        input_bar.addWidget(self.input_edit, 1)
        input_bar.addWidget(self.send_button)
        input_bar.addWidget(self.clear_button)
        layout.addLayout(input_bar)

    def _connect_signals(self) -> None:
        self.send_button.clicked.connect(self._on_send)
        self.clear_button.clicked.connect(self.log_view.clear)
        self.input_edit.returnPressed.connect(self._on_send)

        self.serial_manager.lineReceived.connect(self._append_line)
        self.serial_manager.lineSent.connect(lambda s: self._append_line(f">> {s}"))
        self.serial_manager.error.connect(lambda msg: self._append_line(f"[Error] {msg}"))
        self.serial_manager.connected.connect(lambda p: self._append_line(f"[Connected] {p}"))
        self.serial_manager.disconnected.connect(lambda: self._append_line("[Disconnected]"))

    def _append_line(self, text: str) -> None:
        self.log_view.append(text)
        self.log_view.moveCursor(self.log_view.textCursor().End)

    def _on_send(self) -> None:
        text = self.input_edit.text().strip()
        if not text:
            return
        self.serial_manager.send_line(text)
        self.input_edit.clear()


class JoggingTab(QWidget):
    def __init__(self, serial_manager: SerialManager) -> None:
        super().__init__()
        self.serial_manager = serial_manager
        self.current_x: Optional[float] = None
        self.current_y: Optional[float] = None
        self.current_z: Optional[float] = None
        self._pending_after_position: Optional[Tuple[str, float]] = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)

        # Step and feed settings
        settings_group = QGroupBox("Jog Settings", self)
        settings_layout = QGridLayout(settings_group)
        self.xy_step = QDoubleSpinBox(self)
        self.xy_step.setDecimals(3)
        self.xy_step.setRange(0.001, 1000.0)
        self.xy_step.setValue(10.0)

        self.z_step = QDoubleSpinBox(self)
        self.z_step.setDecimals(3)
        self.z_step.setRange(0.001, 1000.0)
        self.z_step.setValue(10.0)

        self.feedrate = QDoubleSpinBox(self)
        self.feedrate.setDecimals(0)
        self.feedrate.setRange(1, 100000)
        self.feedrate.setValue(1000)

        self.accel = QDoubleSpinBox(self)
        self.accel.setDecimals(0)
        self.accel.setRange(1, 100000)
        self.accel.setValue(500)

        self.apply_params_btn = QPushButton("Apply F/A", self)

        settings_layout.addWidget(QLabel("XY step (mm):", self), 0, 0)
        settings_layout.addWidget(self.xy_step, 0, 1)
        settings_layout.addWidget(QLabel("Z step (mm):", self), 1, 0)
        settings_layout.addWidget(self.z_step, 1, 1)
        settings_layout.addWidget(QLabel("Velocity F (mm/min):", self), 2, 0)
        settings_layout.addWidget(self.feedrate, 2, 1)
        settings_layout.addWidget(QLabel("Acceleration A (mm/s^2):", self), 3, 0)
        settings_layout.addWidget(self.accel, 3, 1)
        settings_layout.addWidget(self.apply_params_btn, 4, 0, 1, 2)
        root_layout.addWidget(settings_group)

        # Jog buttons
        jog_group = QGroupBox("Jog Controls (Relative)", self)
        jog_layout = QGridLayout(jog_group)

        self.btn_home = QPushButton("Home (G28)", self)
        self.btn_pos = QPushButton("Read Position", self)

        self.btn_x_neg = QPushButton("X-", self)
        self.btn_x_pos = QPushButton("X+", self)
        self.btn_y_neg = QPushButton("Y-", self)
        self.btn_y_pos = QPushButton("Y+", self)
        self.btn_z_up = QPushButton("Z Up", self)
        self.btn_z_down = QPushButton("Z Down", self)

        # Layout grid
        jog_layout.addWidget(self.btn_home, 0, 0, 1, 2)
        jog_layout.addWidget(self.btn_pos, 0, 2, 1, 2)

        jog_layout.addWidget(self.btn_y_pos, 1, 1)
        jog_layout.addWidget(self.btn_z_up, 1, 3)

        jog_layout.addWidget(self.btn_x_neg, 2, 0)
        jog_layout.addWidget(QLabel("XY", self), 2, 1)
        jog_layout.addWidget(self.btn_x_pos, 2, 2)
        jog_layout.addWidget(self.btn_z_down, 2, 3)

        jog_layout.addWidget(self.btn_y_neg, 3, 1)

        root_layout.addWidget(jog_group)

        # Current position panel
        pos_group = QGroupBox("Current Position", self)
        pos_layout = QGridLayout(pos_group)
        self.lbl_x_val = QLabel("--", self)
        self.lbl_y_val = QLabel("--", self)
        self.lbl_z_val = QLabel("--", self)
        pos_layout.addWidget(QLabel("X (mm):", self), 0, 0)
        pos_layout.addWidget(self.lbl_x_val, 0, 1)
        pos_layout.addWidget(QLabel("Y (mm):", self), 1, 0)
        pos_layout.addWidget(self.lbl_y_val, 1, 1)
        pos_layout.addWidget(QLabel("Z (mm):", self), 2, 0)
        pos_layout.addWidget(self.lbl_z_val, 2, 1)
        root_layout.addWidget(pos_group)

        # Wire actions
        self.btn_home.clicked.connect(self._on_home)
        self.btn_pos.clicked.connect(self._on_read_position)
        self.btn_x_neg.clicked.connect(lambda: self._jog("X", -self.xy_step.value()))
        self.btn_x_pos.clicked.connect(lambda: self._jog("X", self.xy_step.value()))
        self.btn_y_neg.clicked.connect(lambda: self._jog("Y", -self.xy_step.value()))
        self.btn_y_pos.clicked.connect(lambda: self._jog("Y", self.xy_step.value()))
        self.btn_z_up.clicked.connect(lambda: self._jog("Z", abs(self.z_step.value())))
        self.btn_z_down.clicked.connect(lambda: self._jog("Z", -abs(self.z_step.value())))

    def _connect_signals(self) -> None:
        self.serial_manager.lineReceived.connect(self._on_line_received)
        self.apply_params_btn.clicked.connect(self._apply_motion_params)
        # Auto-apply when the user commits changes in fields
        self.feedrate.editingFinished.connect(self._apply_velocity_only)
        self.accel.editingFinished.connect(self._apply_acceleration_only)

    def _send(self, cmd: str) -> None:
        self.serial_manager.send_line(cmd)

    def _on_home(self) -> None:
        self._send("G28")
        # Unknown absolute after homing until we read Position; leave values as-is

    def _on_read_position(self) -> None:
        self._send("Position")

    def _jog(self, axis: str, delta_mm: float) -> None:
        axis = axis.upper()
        if axis not in ("X", "Y", "Z"):
            return
        # If current pos is unknown, request Position and defer this jog once
        if self._get_current(axis) is None:
            self._pending_after_position = (axis, delta_mm)
            self._send("Position")
            return
        target = self._get_current(axis) + delta_mm  # type: ignore[operator]
        self._send_abs_move(axis, target)

    def _get_current(self, axis: str) -> Optional[float]:
        if axis == "X":
            return self.current_x
        if axis == "Y":
            return self.current_y
        if axis == "Z":
            return self.current_z
        return None

    def _send_abs_move(self, axis: str, target_mm: float) -> None:
        # Send absolute target for the selected axis (do not force G90)
        feed = int(self.feedrate.value())
        value_str = ("%0.3f" % target_mm).rstrip("0").rstrip(".")
        # Only send the moving axis as absolute target
        self._send(f"G1 {axis}{value_str} F{feed}")
        # Optimistically update displayed current pos immediately
        if axis == "X":
            self.current_x = target_mm
            self.lbl_x_val.setText(("%0.3f" % target_mm).rstrip("0").rstrip("."))
        elif axis == "Y":
            self.current_y = target_mm
            self.lbl_y_val.setText(("%0.3f" % target_mm).rstrip("0").rstrip("."))
        elif axis == "Z":
            self.current_z = target_mm
            self.lbl_z_val.setText(("%0.3f" % target_mm).rstrip("0").rstrip("."))

    def _apply_motion_params(self) -> None:
        # Apply velocity (F) and acceleration (A) to controller
        f_val = int(self.feedrate.value())
        a_val = int(self.accel.value())
        self._send(f"G1 F{f_val}")
        self._send(f"M204 A{a_val}")

    def _apply_velocity_only(self) -> None:
        f_val = int(self.feedrate.value())
        self._send(f"G1 F{f_val}")

    def _apply_acceleration_only(self) -> None:
        a_val = int(self.accel.value())
        self._send(f"M204 A{a_val}")

    def _on_line_received(self, line: str) -> None:
        # Expect formats like: "X:100.000 Y:0.000 Z:-291.280" or "100.00,0.00,-291.28"
        text = line.strip()
        if not text:
            return
        # CSV-style
        if "," in text and all(part.strip().replace("-", "").replace(".", "").isdigit() for part in text.split(",")):
            try:
                x_str, y_str, z_str = [p.strip() for p in text.split(",")[:3]]
                self.current_x = float(x_str)
                self.current_y = float(y_str)
                self.current_z = float(z_str)
                self.lbl_x_val.setText(x_str)
                self.lbl_y_val.setText(y_str)
                self.lbl_z_val.setText(z_str)
                # If a jog is pending (waiting for fresh position), perform it now
                if self._pending_after_position is not None:
                    axis, delta = self._pending_after_position
                    self._pending_after_position = None
                    self._jog(axis, delta)
                return
            except Exception:
                pass
        # Labeled style
        up = text.upper()
        if ("X:" in up) and ("Y:" in up) and ("Z:" in up):
            try:
                def extract(after: str) -> str:
                    s = up.split(after, 1)[1].strip()
                    # take until space or end
                    token = s.split()[0]
                    return token
                x_val = extract("X:")
                y_val = extract("Y:")
                z_val = extract("Z:")
                self.current_x = float(x_val)
                self.current_y = float(y_val)
                self.current_z = float(z_val)
                self.lbl_x_val.setText(x_val)
                self.lbl_y_val.setText(y_val)
                self.lbl_z_val.setText(z_val)
                if self._pending_after_position is not None:
                    axis, delta = self._pending_after_position
                    self._pending_after_position = None
                    self._jog(axis, delta)
            except Exception:
                pass


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Delta X - G-code Terminal & Jogging")
        self.resize(900, 600)

        self.serial_manager = SerialManager()
        self._build_ui()
        self._connect_signals()

        # Initial ports refresh
        self.serial_manager.refresh_ports()

    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        # Connection bar
        conn_group = QGroupBox("Connection", self)
        conn_layout = QHBoxLayout(conn_group)
        self.ports_combo = QComboBox(self)
        self.refresh_ports_btn = QPushButton("Refresh", self)
        self.baud_combo = QComboBox(self)
        for b in (9600, 19200, 38400, 57600, 115200, 230400):
            self.baud_combo.addItem(str(b))
        self.baud_combo.setCurrentText(str(DEFAULT_BAUD))
        self.connect_btn = QPushButton("Connect", self)
        self.disconnect_btn = QPushButton("Disconnect", self)
        self.disconnect_btn.setEnabled(False)
        self.autoscan_btn = QPushButton("Auto-Scan", self)

        conn_layout.addWidget(QLabel("Port:", self))
        conn_layout.addWidget(self.ports_combo, 1)
        conn_layout.addWidget(self.refresh_ports_btn)
        conn_layout.addWidget(QLabel("Baud:", self))
        conn_layout.addWidget(self.baud_combo)
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.disconnect_btn)
        conn_layout.addWidget(self.autoscan_btn)

        outer.addWidget(conn_group)

        # Tabs
        self.tabs = QTabWidget(self)
        self.terminal_tab = TerminalTab(self.serial_manager)
        self.jogging_tab = JoggingTab(self.serial_manager)
        self.tabs.addTab(self.jogging_tab, "Jogging")
        self.tabs.addTab(self.terminal_tab, "Terminal")
        outer.addWidget(self.tabs, 1)

    def _connect_signals(self) -> None:
        self.refresh_ports_btn.clicked.connect(self.serial_manager.refresh_ports)
        self.autoscan_btn.clicked.connect(self._on_autoscan)
        self.connect_btn.clicked.connect(self._on_connect)
        self.disconnect_btn.clicked.connect(self._on_disconnect)

        self.serial_manager.portsRefreshed.connect(self._on_ports_refreshed)
        self.serial_manager.connected.connect(self._on_connected)
        self.serial_manager.disconnected.connect(self._on_disconnected)
        self.serial_manager.error.connect(self._on_error)

    # ---------- Connection handlers ----------
    def _on_ports_refreshed(self, ports: List[str]) -> None:
        current = self.ports_combo.currentText()
        self.ports_combo.blockSignals(True)
        self.ports_combo.clear()
        self.ports_combo.addItems(ports)
        # Try to keep previous selection
        if current and current in ports:
            self.ports_combo.setCurrentText(current)
        self.ports_combo.blockSignals(False)

    def _on_autoscan(self) -> None:
        baud = int(self.baud_combo.currentText())
        self.serial_manager.autoscan_and_connect(baud)

    def _on_connect(self) -> None:
        port = self.ports_combo.currentText()
        if not port:
            self._on_error("Không có cổng nào được chọn.")
            return
        baud = int(self.baud_combo.currentText())
        self.serial_manager.open_port(port, baud)

    def _on_disconnect(self) -> None:
        self.serial_manager.close_port()

    def _on_connected(self, port: str) -> None:
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(True)
        # Try a small greeting/readiness check
        self.serial_manager.send_line("Position")
        # Optionally sync default motion params to controller at connect time
        try:
            f_init = int(self.jogging_tab.feedrate.value())
            a_init = int(self.jogging_tab.accel.value())
            self.serial_manager.send_line(f"G1 F{f_init}")
            self.serial_manager.send_line(f"M204 A{a_init}")
        except Exception:
            pass

    def _on_disconnected(self) -> None:
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)

    def _on_error(self, message: str) -> None:
        # Also echo errors to terminal tab log for visibility
        self.terminal_tab._append_line(f"[Error] {message}")

    # ---------- Window lifecycle ----------
    def closeEvent(self, event) -> None:  # type: ignore[override]
        try:
            self.serial_manager.close_port()
        except Exception:
            pass
        super().closeEvent(event)


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()


