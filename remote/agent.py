"""Remote Diagnostic Agent.

Run this on the PC that should be diagnosed. It exposes a tiny LAN-only
protocol and delegates diagnosis to the existing FixMate-AI core modules.
No existing FixMate-AI source files are modified.
"""
from __future__ import annotations

import argparse
import getpass
import ipaddress
import os
import platform
import secrets
import socket
import threading
import traceback
from pathlib import Path

from .protocol import recv_json, send_json


def _local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def _pin() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


class RemoteAgent:
    def __init__(self, host: str = "0.0.0.0", port: int = 47821, pin: str | None = None):
        self.host = host
        self.port = port
        self.pin = pin or _pin()
        self.server: socket.socket | None = None
        self._stop = threading.Event()
        self._scan_lock = threading.Lock()
        self._scan_running = False

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[1]

    def _collect_info(self) -> dict:
        """Run the existing fast informational snapshot on the target machine."""
        import sys

        root = self._project_root()
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from system_info import get_system_info

        info = get_system_info()
        return {
            "hostname": socket.gethostname(),
            "username": getpass.getuser(),
            "platform": platform.platform(),
            "system_info": info,
        }

    def _run_scan(self) -> dict:
        if not self._scan_lock.acquire(blocking=False):
            raise RuntimeError("A remote diagnosis is already running on this PC.")
        self._scan_running = True
        try:
            import sys

            root = self._project_root()
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            from core.full_scan import run_full_scan

            result = run_full_scan()
            return {
                "hostname": socket.gethostname(),
                "scan_result": result,
            }
        finally:
            self._scan_running = False
            self._scan_lock.release()

    def _handle(self, conn: socket.socket, addr: tuple[str, int]) -> None:
        try:
            request = recv_json(conn)
            if request.get("pin") != self.pin:
                send_json(conn, {"ok": False, "error": "Pairing PIN rejected."})
                return

            command = request.get("command")
            if command == "PING":
                send_json(conn, {"ok": True, "command": "PONG", "hostname": socket.gethostname()})
                return

            if command == "GET_INFO":
                send_json(conn, {"ok": True, "command": command, "data": self._collect_info()})
                return

            if command == "SCAN_STATUS":
                send_json(conn, {"ok": True, "command": command, "running": self._scan_running})
                return

            if command == "RUN_SCAN":
                if self._scan_running:
                    send_json(conn, {"ok": False, "error": "A scan is already running."})
                    return
                send_json(conn, {"ok": True, "command": "SCAN_STARTED", "message": "Remote diagnosis started."})
                try:
                    payload = self._run_scan()
                    # Reconnects are not needed; return final result in same TCP session.
                    send_json(conn, {"ok": True, "command": "SCAN_RESULT", "data": payload})
                except Exception as exc:
                    send_json(conn, {"ok": False, "error": str(exc), "trace": traceback.format_exc(limit=4)})
                return

            send_json(conn, {"ok": False, "error": f"Unknown command: {command!r}"})
        except Exception as exc:
            try:
                send_json(conn, {"ok": False, "error": str(exc)})
            except Exception:
                pass
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def serve_forever(self) -> None:
        family = socket.AF_INET
        server = socket.socket(family, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(8)
        server.settimeout(1.0)
        self.server = server

        print("=" * 68)
        print(" FixMate-AI Remote Diagnostic Agent")
        print("=" * 68)
        print(f"Computer : {socket.gethostname()}")
        print(f"IP       : {_local_ip()}")
        print(f"Port     : {self.port}")
        print(f"Pair PIN : {self.pin}")
        print("")
        print("Keep this window open while the controller connects.")
        print("For safety, use this only on your trusted local network.")
        print("Press Ctrl+C to stop the agent.")
        print("=" * 68)

        try:
            while not self._stop.is_set():
                try:
                    conn, addr = server.accept()
                except socket.timeout:
                    continue
                client_ip = addr[0]
                # Refuse clearly non-private clients.  This is a safety layer, not internet security.
                try:
                    if not ipaddress.ip_address(client_ip).is_private and client_ip != "127.0.0.1":
                        conn.close()
                        continue
                except ValueError:
                    conn.close()
                    continue
                threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()
        finally:
            server.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="FixMate-AI Remote Diagnostic Agent")
    parser.add_argument("--port", type=int, default=47821)
    parser.add_argument("--pin", default=None, help="Optional fixed 6-digit pairing PIN")
    args = parser.parse_args()
    if args.pin is not None and (not args.pin.isdigit() or len(args.pin) != 6):
        raise SystemExit("--pin must be exactly 6 digits")
    RemoteAgent(port=args.port, pin=args.pin).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
