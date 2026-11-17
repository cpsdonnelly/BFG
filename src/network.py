"""Minimal LAN multiplayer transport for BFG:XR.

Protocol: each message is a 4-byte little-endian length prefix followed by
UTF-8-encoded JSON. Either side can send/receive; the active player sends
the full game state at phase end; the passive player receives and reloads.
"""
import json
import socket
import struct
import threading
from typing import Optional

from .game_state import GameState

_HEADER = struct.Struct("<I")   # 4-byte unsigned little-endian length
DEFAULT_PORT = 5775


# ── Low-level framing ────────────────────────────────────────────────────────

def _send_json(sock: socket.socket, data: dict) -> None:
    payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
    sock.sendall(_HEADER.pack(len(payload)) + payload)


def _recv_json(sock: socket.socket) -> dict:
    header = _recv_exact(sock, _HEADER.size)
    length = _HEADER.unpack(header)[0]
    payload = _recv_exact(sock, length)
    return json.loads(payload.decode("utf-8"))


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Peer disconnected")
        buf.extend(chunk)
    return bytes(buf)


# ── GameState serialisation ──────────────────────────────────────────────────

def _gs_to_dict(gs: GameState) -> dict:
    """Serialise the full game state to a plain dict."""
    import dataclasses, time as _time
    meta = dataclasses.asdict(gs)
    # artefact_token_pos is a tuple — JSON needs a list
    if meta.get("artefact_token_pos") is not None:
        meta["artefact_token_pos"] = list(meta["artefact_token_pos"])
    meta["timestamp"] = _time.time()
    return meta


def _dict_to_gs(data: dict) -> GameState:
    """Reconstruct a GameState from a serialised dict."""
    gs = GameState()
    for k, v in data.items():
        if k == "timestamp":
            continue
        if not hasattr(gs, k):
            continue
        if k == "artefact_token_pos" and v is not None:
            v = tuple(v)
        setattr(gs, k, v)
    return gs


# ── Host (server) ────────────────────────────────────────────────────────────

class GameServer:
    """Runs on the host machine.  Accepts exactly one client connection."""

    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self._server: Optional[socket.socket] = None
        self._client: Optional[socket.socket] = None
        self.connected = False

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def start(self, on_connect=None) -> str:
        """Bind and listen.  Returns the host LAN IP string.
        Blocks in a background thread until a client connects,
        then calls `on_connect()` on the calling thread via `after`."""
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("", self.port))
        self._server.listen(1)
        host_ip = _local_ip()

        def _accept():
            try:
                conn, _ = self._server.accept()
                self._client = conn
                self.connected = True
                if on_connect:
                    on_connect()
            except OSError:
                pass  # server was closed while waiting

        threading.Thread(target=_accept, daemon=True).start()
        return host_ip

    def send_state(self, gs: GameState) -> None:
        if self._client:
            _send_json(self._client, _gs_to_dict(gs))

    def recv_state(self) -> GameState:
        if not self._client:
            raise ConnectionError("No client connected")
        return _dict_to_gs(_recv_json(self._client))

    def close(self) -> None:
        for s in (self._client, self._server):
            if s:
                try:
                    s.close()
                except OSError:
                    pass
        self._client = self._server = None
        self.connected = False


# ── Client ───────────────────────────────────────────────────────────────────

class GameClient:
    """Runs on the joining machine."""

    def __init__(self, host: str, port: int = DEFAULT_PORT):
        self.host = host
        self.port = port
        self._sock: Optional[socket.socket] = None

    def connect(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.settimeout(10)
        self._sock.connect((self.host, self.port))
        self._sock.settimeout(None)

    def send_state(self, gs: GameState) -> None:
        if self._sock:
            _send_json(self._sock, _gs_to_dict(gs))

    def recv_state(self) -> GameState:
        if not self._sock:
            raise ConnectionError("Not connected")
        return _dict_to_gs(_recv_json(self._sock))

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None


# ── Helpers ──────────────────────────────────────────────────────────────────

def _local_ip() -> str:
    """Return the machine's LAN IP (best-effort)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
