"""
Network Protocol for gossip-based peer-to-peer communication over TCP sockets.
Uses length-prefixed JSON messages.
"""

import json
import struct
import socket

# ── Message Types ───────────────────────────────────────────────────
MSG_GOSSIP_STATE = "GOSSIP_STATE"       # periodic state broadcast
MSG_TASK_OFFLOAD = "TASK_OFFLOAD"       # offload a task to a peer
MSG_TASK_RESULT = "TASK_RESULT"         # result of an offloaded task
MSG_REGISTER = "REGISTER"              # initial handshake


def build_message(msg_type: str, payload: dict) -> dict:
    """Wrap a payload in a typed message envelope."""
    return {"type": msg_type, "payload": payload}


def send_message(sock: socket.socket, msg_type: str, payload: dict) -> None:
    """Send a length-prefixed JSON message over a TCP socket."""
    message = json.dumps(build_message(msg_type, payload)).encode("utf-8")
    length = struct.pack("!I", len(message))
    sock.sendall(length + message)


def recv_message(sock: socket.socket) -> dict | None:
    """Receive a length-prefixed JSON message. Returns None on disconnect."""
    raw_len = _recv_exact(sock, 4)
    if raw_len is None:
        return None
    msg_len = struct.unpack("!I", raw_len)[0]
    raw_msg = _recv_exact(sock, msg_len)
    if raw_msg is None:
        return None
    return json.loads(raw_msg.decode("utf-8"))


def _recv_exact(sock: socket.socket, num_bytes: int) -> bytes | None:
    """Read exactly num_bytes from a socket."""
    data = b""
    while len(data) < num_bytes:
        try:
            chunk = sock.recv(num_bytes - len(data))
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            return None
        if not chunk:
            return None
        data += chunk
    return data
