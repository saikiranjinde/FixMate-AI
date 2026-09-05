"""Standalone Qt controller window for Remote Diagnostic Mode."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from .client import RemoteConnection


class RemoteWorker(QThread):
    finished = Signal(object)
    failed = Signal(str)
    status = Signal(str)

    def __init__(self, connection: RemoteConnection, action: str, parent=None):
        super().__init__(parent)
        self.connection = connection
        self.action = action

    def run(self) -> None:
        try:
            if self.action == "ping":
                self.status.emit("Testing remote connection...")
                self.finished.emit(self.connection.ping())
            elif self.action == "info":
                self.status.emit("Fetching remote system information...")
                self.finished.emit(self.connection.get_info())
            elif self.action == "scan":
                self.status.emit("Remote diagnosis is running. Please keep the agent open...")
                self.finished.emit(self.connection.run_scan())
            else:
                raise ValueError(f"Unknown action: {self.action}")
        except Exception as exc:
            self.failed.emit(str(exc))


class RemoteDiagnosticWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FixMate-AI — Remote Diagnostic Mode")
        self.resize(920, 680)
        self.worker: RemoteWorker | None = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Remote Diagnostic Mode")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        root.addWidget(title)

        subtitle = QLabel("Connect to another trusted Windows PC running the FixMate-AI Remote Agent.")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        box = QGroupBox("Connect to Target PC")
        form = QFormLayout(box)
        self.host = QLineEdit()
        self.host.setPlaceholderText("Example: 192.168.1.25")
        self.port = QLineEdit("47821")
        self.pin = QLineEdit()
        self.pin.setPlaceholderText("6-digit pairing PIN")
        self.pin.setMaxLength(6)
        form.addRow("Target IP:", self.host)
        form.addRow("Port:", self.port)
        form.addRow("Pairing PIN:", self.pin)
        root.addWidget(box)

        actions = QHBoxLayout()
        self.connect_btn = QPushButton("Test Connection")
        self.info_btn = QPushButton("Fetch System Info")
        self.scan_btn = QPushButton("Run Remote Diagnosis")
        self.connect_btn.clicked.connect(lambda: self._start("ping"))
        self.info_btn.clicked.connect(lambda: self._start("info"))
        self.scan_btn.clicked.connect(lambda: self._start("scan"))
        actions.addWidget(self.connect_btn)
        actions.addWidget(self.info_btn)
        actions.addWidget(self.scan_btn)
        root.addLayout(actions)

        self.status = QLabel("Not connected")
        root.addWidget(self.status)

        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        root.addWidget(self.output, 1)

    def _connection(self) -> RemoteConnection:
        host = self.host.text().strip()
        if not host:
            raise ValueError("Enter the target PC IP address.")
        try:
            port = int(self.port.text().strip())
        except ValueError as exc:
            raise ValueError("Port must be a number.") from exc
        pin = self.pin.text().strip()
        if len(pin) != 6 or not pin.isdigit():
            raise ValueError("Pairing PIN must be exactly 6 digits.")
        return RemoteConnection(host, port, pin)

    def _start(self, action: str) -> None:
        try:
            connection = self._connection()
        except ValueError as exc:
            QMessageBox.warning(self, "Remote Diagnostic", str(exc))
            return

        self._set_busy(True)
        self.worker = RemoteWorker(connection, action, self)
        self.worker.status.connect(self.status.setText)
        self.worker.finished.connect(self._finished)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self._worker_done)
        self.worker.failed.connect(lambda _msg: self._worker_done())
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        for button in (self.connect_btn, self.info_btn, self.scan_btn):
            button.setEnabled(not busy)

    def _worker_done(self, *_args) -> None:
        self._set_busy(False)

    def _failed(self, message: str) -> None:
        self.status.setText("Connection/diagnosis failed")
        self.output.appendPlainText(f"ERROR: {message}\n")

    def _finished(self, result: object) -> None:
        if not isinstance(result, dict):
            return
        self.status.setText("Connected / response received" if result.get("ok") else "Remote operation failed")
        self.output.setPlainText(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        if result.get("ok") and result.get("command") == "SCAN_RESULT":
            QMessageBox.information(self, "Remote Diagnosis Complete", "Remote PC diagnosis completed successfully.")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("FixMate-AI Remote Diagnostic Mode")
    window = RemoteDiagnosticWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
