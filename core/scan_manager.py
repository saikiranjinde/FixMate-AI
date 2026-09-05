"""Background scan manager for FixMate-AI.

The diagnostic engine is kept intact. This adapter:
- runs the existing full scan in QThread
- forwards stdout live instead of buffering it until the end
- converts actual diagnostic section headers into progress milestones
- keeps progress monotonic
"""

from __future__ import annotations

import sys
import time
import traceback

from PySide6.QtCore import QThread, Signal

from core.full_scan import run_full_scan


class LiveOutput:
    """stdout-compatible stream that forwards every printed line."""

    def __init__(self, worker: "ScanWorker") -> None:
        self.worker = worker
        self._partial = ""

    def write(self, text: str) -> int:
        if not text:
            return 0

        self._partial += str(text)

        while "\n" in self._partial:
            line, self._partial = self._partial.split(
                "\n",
                1,
            )
            self.worker.handle_output_line(line)

        return len(text)

    def flush(self) -> None:
        if self._partial.strip():
            self.worker.handle_output_line(self._partial)
            self._partial = ""


class ScanWorker(QThread):
    progress = Signal(int, str)
    output = Signal(str)
    finished = Signal(object)
    failed = Signal(str)

    # Progress represents completed diagnostic phases, not elapsed time.
    PHASES = (
        ("system information", 8, "Checking System Information"),
        ("hardware information", 16, "Checking Hardware"),
        ("system diagnostics", 24, "Analyzing System Resources"),
        ("process analysis", 32, "Analyzing Running Processes"),
        ("gpu diagnostics", 42, "Diagnosing GPU"),
        ("thermal diagnostics", 50, "Checking Thermal Sensors"),
        ("storage diagnostics", 60, "Scanning Storage"),
        ("battery diagnosis", 70, "Checking Battery"),
        ("driver", 78, "Checking Drivers"),
        ("network", 84, "Testing Network"),
        ("windows health", 90, "Checking Windows Health"),
        ("startup", 94, "Checking Startup"),
        ("report", 98, "Generating Diagnosis Report"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._last_progress = 0
        self._last_stage = ""
        self._phase_times: dict[str, float] = {}
        self._last_phase_time = time.monotonic()

    def run(self) -> None:
        try:
            self.progress.emit(
                2,
                "Starting full system diagnosis...",
            )

            stream = LiveOutput(self)

            # Save the original stdout because the worker is running in
            # a background thread. We restore it immediately afterwards.
            original_stdout = sys.stdout
            sys.stdout = stream

            try:
                result = run_full_scan()
            finally:
                stream.flush()
                sys.stdout = original_stdout

            self.progress.emit(
                100,
                "Diagnosis completed",
            )
            self.finished.emit(result)

        except Exception:
            self.failed.emit(traceback.format_exc())

    def handle_output_line(self, line: str) -> None:
        text = str(line).strip()

        if not text:
            return

        self.output.emit(text)

        lower = text.lower()

        # Only section/header-like lines are allowed to advance progress.
        # This avoids random diagnostic text containing "cpu"/"memory"
        # from incorrectly jumping the progress bar.
        for keyword, value, stage in self.PHASES:
            if keyword not in lower:
                continue

            # Require a reasonably header-like line for generic keywords.
            if keyword in ("driver", "network", "startup", "report"):
                if not (
                    "=" in text
                    or text.startswith("#")
                    or "diagnos" in lower
                    or "checking" in lower
                    or "testing" in lower
                ):
                    continue

            if value > self._last_progress:
                now = time.monotonic()
                self._phase_times[stage] = now - self._last_phase_time
                self._last_phase_time = now
                self._last_progress = value
                self._last_stage = stage
                self.progress.emit(value, stage)

            break


class ScanManager:
    def __init__(self) -> None:
        self.worker: ScanWorker | None = None

    def start(self) -> bool:
        if self.worker is not None and self.worker.isRunning():
            return False

        self.worker = ScanWorker()
        return True
