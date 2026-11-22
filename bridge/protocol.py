"""NDJSON-over-TCP framing + envelope validation (stdlib only).

Wire format
-----------
One JSON object per line, UTF-8, no embedded newlines. Max line 64 KiB.
Every message carries: {"v":1, "type": "...", "seq": n, "token": "..."}

Types:
  hello    sidecar -> game    {"type":"hello","token":..,"profile":{...}}
  welcome  game -> sidecar    {"type":"welcome","pid":..,"version":"2.7.2.0"}
  state    game -> sidecar    {"player":{..},"enemy":{..},"events":[..]}
  weights  sidecar -> game    {"weights":{..},"strategy":".."}
  command  sidecar -> game    {"cmd":"set_equipment","args":{..}}
  ack      game -> sidecar    {"ok":true,"cmd":".."}
  ping/pong
"""

from __future__ import annotations

import json
import socket
import time

MAX_LINE = 64 * 1024
PROTOCOL_VERSION = 1


class ProtocolError(Exception):
    pass


def dumps(msg: dict) -> bytes:
    msg = dict(msg)
    msg.setdefault("v", PROTOCOL_VERSION)
    raw = json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(raw) > MAX_LINE:
        raise ProtocolError(f"message too large: {len(raw)}")
    return raw + b"\n"


class LineReader:
    """Incremental line reader over a blocking socket."""

    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.buf = bytearray()

    def read_line(self, timeout: float = 0.0) -> dict | None:
        if timeout:
            self.sock.settimeout(timeout)
        try:
            chunk = self.sock.recv(65536)
        except socket.timeout:
            return None
        if not chunk:
            raise ConnectionError("peer closed")
        self.buf.extend(chunk)
        if b"\n" not in self.buf:
            if len(self.buf) > MAX_LINE:
                raise ProtocolError("line too long")
            return None
        line, _, rest = self.buf.partition(b"\n")
        self.buf = bytearray(rest)
        try:
            msg = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProtocolError(f"bad json: {exc}") from exc
        if not isinstance(msg, dict):
            raise ProtocolError("message must be an object")
        return msg


def recv_json(reader: LineReader, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        msg = reader.read_line(timeout=0.25)
        if msg is not None:
            return msg
    raise TimeoutError("no message")


def check(msg: dict, token: str, want_type: str | None = None) -> dict:
    if msg.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(f"protocol version {msg.get('v')!r} != {PROTOCOL_VERSION}")
    if msg.get("token") != token:
        raise ProtocolError("bad token")
    if want_type and msg.get("type") != want_type:
        raise ProtocolError(f"expected {want_type}, got {msg.get('type')!r}")
    return msg


def clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if value != value:  # NaN
        raise ProtocolError("NaN weight")
    return max(lo, min(hi, value))


def connect(host: str, port: int, token: str, timeout: float = 5.0) -> tuple[socket.socket, LineReader]:
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    reader = LineReader(sock)
    sock.sendall(dumps({"type": "hello", "token": token, "client": "er-echo-director"}))
    welcome = check(recv_json(reader, timeout=timeout), token, "welcome")
    return sock, reader


def listen(host: str, port: int, token: str, timeout: float = 900.0) -> tuple[socket.socket, LineReader]:
    """DLL 是 client：它每 2 秒重连一次，所以 Python 侧当 server 等它上门。"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((host, port))
    server.listen(1)
    server.settimeout(timeout)
    try:
        conn, _ = server.accept()
    finally:
        server.close()
    conn.settimeout(timeout)
    reader = LineReader(conn)
    hello = check(recv_json(reader, timeout=10.0), token, "hello")
    print(f"[ok] DLL connected: {hello.get('client')} v{hello.get('version')}")
    conn.sendall(dumps({"type": "welcome", "token": token, "pid": 0, "server": "python"}))
    return conn, reader
