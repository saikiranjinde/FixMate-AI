"""Controller-side client for the Remote Diagnostic Agent."""
from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Any

from .protocol import recv_json, send_json


@dataclass
class RemoteConnection:
    host: str
    port: int
    pin: str
    timeout: float = 10.0

    def _request(self, command: str, timeout: float | None = None) -> dict[str, Any]:
        sock = socket.create_connection((self.host, self.port), timeout or self.timeout)
        try:
            sock.settimeout(timeout or self.timeout)
            send_json(sock, {"command": command, "pin": self.pin})
            return recv_json(sock)
        finally:
            sock.close()

    def ping(self) -> dict[str, Any]:
        return self._request("PING")

    def get_info(self) -> dict[str, Any]:
        return self._request("GET_INFO")

    def scan_status(self) -> dict[str, Any]:
        return self._request("SCAN_STATUS")

    def run_scan(self, timeout: float = 900.0, on_started=None) -> dict[str, Any]:
        sock = socket.create_connection((self.host, self.port), timeout=10)
        try:
            sock.settimeout(10)
            send_json(sock, {"command": "RUN_SCAN", "pin": self.pin})
            started = recv_json(sock)
            if not started.get("ok"):
                return started
            if on_started:
                on_started(started)

            sock.settimeout(1.0)
            # We intentionally wait in small timeout slices so Ctrl+C/app close can be handled by the GUI worker.
            import time
            deadline = time.monotonic() + timeout
            while True:
                try:
                    result = recv_json(sock)
                    return result
                except socket.timeout:
                    if time.monotonic() >= deadline:
                        return {"ok": False, "error": "Remote scan timed out."}
                    continue
        finally:
            sock.close()
