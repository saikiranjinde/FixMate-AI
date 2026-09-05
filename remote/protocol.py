"""Small, dependency-free JSON-over-TCP protocol for Remote Diagnostic Mode."""
from __future__ import annotations

import json
import socket
import struct
from typing import Any

MAX_PACKET = 8 * 1024 * 1024


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < size:
        chunk = sock.recv(size - len(chunks))
        if not chunk:
            raise ConnectionError("Remote connection closed unexpectedly")
        chunks.extend(chunk)
    return bytes(chunks)


def send_json(sock: socket.socket, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
    if len(raw) > MAX_PACKET:
        raise ValueError("Payload is too large")
    sock.sendall(struct.pack("!I", len(raw)) + raw)


def recv_json(sock: socket.socket) -> dict[str, Any]:
    header = _recv_exact(sock, 4)
    size = struct.unpack("!I", header)[0]
    if size <= 0 or size > MAX_PACKET:
        raise ValueError("Invalid remote payload size")
    raw = _recv_exact(sock, size)
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Remote payload must be a JSON object")
    return value
