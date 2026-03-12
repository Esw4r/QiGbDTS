"""
Edge Node with Gossip-Based Distributed Task Scheduling.

Each edge node:
 - Runs a TCP server to accept peer connections
 - Connects to all peer edge nodes
 - Gossips its load state to random peers every GOSSIP_INTERVAL seconds
 - Generates tasks and decides via quantum-inspired probability whether to
   execute locally or offload to the least-loaded peer
 - Reports events to the dashboard via HTTP POST

Usage (multi-machine):
    python edge_nodes/edge_node.py --id edge1 --host 0.0.0.0 --port 8001 \
        --peers edge2=192.168.1.102:8002 edge3=192.168.1.103:8003 \
        --dashboard-url http://192.168.1.100:5000
"""

import sys
import os
import socket
import threading
import time
import random
import argparse
import math
import json
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.config import (
    EDGE_CPU, EDGE_MEMORY, EDGE_BANDWIDTH,
    DEFAULT_PEERS, DASHBOARD_URL,
    GOSSIP_INTERVAL, GOSSIP_FANOUT, PEER_TIMEOUT,
    TASK_GEN_MIN_INTERVAL, TASK_GEN_MAX_INTERVAL,
    INITIAL_ALPHA, INITIAL_BETA, ROTATION_THETA,
)
from common.network_protocol import (
    send_message, recv_message,
    MSG_GOSSIP_STATE, MSG_TASK_OFFLOAD, MSG_TASK_RESULT, MSG_REGISTER,
)
from edge_nodes.workload_generator import generate_task


class EdgeNode:
    def __init__(self, node_id: str, host: str, port: int,
                 peers: dict, dashboard_url: str):
        self.node_id = node_id
        self.host = host
        self.port = port
        self.peers = peers          # {peer_id: (host, port)}
        self.dashboard_url = dashboard_url
        self.running = True

        # ── Local state ─────────────────────────────────────────────
        self.tasks_running = 0
        self.tasks_completed = 0
        self.total_exec_time = 0.0
        self._lock = threading.Lock()

        # ── Peer state (from gossip) ────────────────────────────────
        self.peer_states: dict[str, dict] = {}  # peer_id -> {load, tasks, last_seen}
        self._peer_lock = threading.Lock()

        # ── Peer connections ────────────────────────────────────────
        self.peer_socks: dict[str, socket.socket] = {}  # peer_id -> socket
        self._sock_lock = threading.Lock()

        # ── Quantum amplitudes ──────────────────────────────────────
        self.alpha = INITIAL_ALPHA
        self.beta = INITIAL_BETA

    # ═══════════════════════════════════════════════════════════════
    # Startup
    # ═══════════════════════════════════════════════════════════════

    def start(self):
        print(f"[{self.node_id}] Starting on {self.host}:{self.port}")
        print(f"[{self.node_id}] Peers: {self.peers}")
        print(f"[{self.node_id}] Dashboard: {self.dashboard_url}")

        self._emit_event("system", f"{self.node_id} started on port {self.port}")

        # Start TCP server (accept incoming peer connections)
        threading.Thread(target=self._server_loop, daemon=True).start()

        # Wait a moment for servers to start, then connect to peers
        time.sleep(1)
        threading.Thread(target=self._connect_to_peers, daemon=True).start()

        # Start gossip thread
        threading.Thread(target=self._gossip_loop, daemon=True).start()

        # Start status reporting thread
        threading.Thread(target=self._status_loop, daemon=True).start()

        # Task generation loop (main thread)
        self._generate_loop()

    # ═══════════════════════════════════════════════════════════════
    # TCP Server — accept incoming peer connections
    # ═══════════════════════════════════════════════════════════════

    def _server_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.host, self.port))
        server.listen(10)
        print(f"[{self.node_id}] Listening for peers on {self.host}:{self.port}")

        while self.running:
            try:
                conn, addr = server.accept()
                threading.Thread(target=self._handle_peer, args=(conn, addr),
                                 daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"[{self.node_id}] Accept error: {e}")

    def _handle_peer(self, conn: socket.socket, addr):
        """Handle an incoming peer connection."""
        peer_id = None
        try:
            msg = recv_message(conn)
            if msg and msg["type"] == MSG_REGISTER:
                peer_id = msg["payload"]["node_id"]
                with self._sock_lock:
                    self.peer_socks[peer_id] = conn
                print(f"[{self.node_id}] Peer {peer_id} connected from {addr[0]}:{addr[1]}")
                self._emit_event("connection",
                                 f"{peer_id} connected to {self.node_id}",
                                 {"from": peer_id, "to": self.node_id,
                                  "ip": addr[0]})

                # Handle messages from this peer
                while self.running:
                    msg = recv_message(conn)
                    if msg is None:
                        break
                    self._process_message(peer_id, msg)
        except Exception as e:
            if self.running:
                print(f"[{self.node_id}] Peer {peer_id} error: {e}")
        finally:
            with self._sock_lock:
                self.peer_socks.pop(peer_id, None)
            if peer_id:
                print(f"[{self.node_id}] Peer {peer_id} disconnected")

    # ═══════════════════════════════════════════════════════════════
    # Connect to peers (outgoing)
    # ═══════════════════════════════════════════════════════════════

    def _connect_to_peers(self):
        """Try to connect to all peers. Retry until successful."""
        for peer_id, (peer_host, peer_port) in self.peers.items():
            threading.Thread(target=self._connect_one_peer,
                             args=(peer_id, peer_host, peer_port),
                             daemon=True).start()

    def _connect_one_peer(self, peer_id: str, peer_host: str, peer_port: int):
        """Keep trying to connect to one peer until successful."""
        while self.running:
            with self._sock_lock:
                if peer_id in self.peer_socks:
                    return  # already connected (they connected to us)

            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((peer_host, peer_port))
                sock.settimeout(None)
                send_message(sock, MSG_REGISTER, {"node_id": self.node_id})

                with self._sock_lock:
                    if peer_id in self.peer_socks:
                        sock.close()
                        return
                    self.peer_socks[peer_id] = sock

                print(f"[{self.node_id}] Connected to peer {peer_id} at {peer_host}:{peer_port}")
                self._emit_event("connection",
                                 f"{self.node_id} connected to {peer_id}",
                                 {"from": self.node_id, "to": peer_id})

                # Listen for messages from this peer
                while self.running:
                    msg = recv_message(sock)
                    if msg is None:
                        break
                    self._process_message(peer_id, msg)
            except Exception:
                pass  # retry silently

            # Clean up and retry
            with self._sock_lock:
                self.peer_socks.pop(peer_id, None)
            if self.running:
                time.sleep(2)

    # ═══════════════════════════════════════════════════════════════
    # Message processing
    # ═══════════════════════════════════════════════════════════════

    def _process_message(self, peer_id: str, msg: dict):
        msg_type = msg["type"]
        payload = msg["payload"]

        if msg_type == MSG_GOSSIP_STATE:
            with self._peer_lock:
                self.peer_states[peer_id] = {
                    "tasks_running": payload["tasks_running"],
                    "tasks_completed": payload["tasks_completed"],
                    "load": payload["load"],
                    "last_seen": time.time(),
                }

        elif msg_type == MSG_TASK_OFFLOAD:
            # A peer is offloading a task to us
            from common.task_model import Task
            task = Task.from_dict(payload)
            print(f"[{self.node_id}] Received offloaded task {task.task_id} from {peer_id}")
            self._emit_event("task_received",
                             f"{self.node_id} received task {task.task_id} from {peer_id}",
                             {"task_id": task.task_id, "from": peer_id,
                              "to": self.node_id})
            threading.Thread(target=self._execute_task,
                             args=(task, peer_id), daemon=True).start()

        elif msg_type == MSG_TASK_RESULT:
            task_id = payload["task_id"]
            exec_time = payload["exec_time"]
            executor = payload["executor"]
            print(f"[{self.node_id}] Task {task_id} completed by {executor} ({exec_time:.3f}s)")
            self._emit_event("task_completed",
                             f"Task {task_id} completed by {executor} ({exec_time:.3f}s)",
                             {"task_id": task_id, "executor": executor,
                              "origin": self.node_id, "exec_time": exec_time})
            self._quantum_rotate()

    # ═══════════════════════════════════════════════════════════════
    # Gossip protocol
    # ═══════════════════════════════════════════════════════════════

    def _gossip_loop(self):
        """Periodically gossip own state to random peers."""
        while self.running:
            time.sleep(GOSSIP_INTERVAL)
            with self._lock:
                state = {
                    "node_id": self.node_id,
                    "tasks_running": self.tasks_running,
                    "tasks_completed": self.tasks_completed,
                    "load": self.tasks_running / max(EDGE_CPU / 200, 1),
                }

            # Pick random peers to gossip to
            with self._sock_lock:
                available = list(self.peer_socks.keys())
            if not available:
                continue

            targets = random.sample(available, min(GOSSIP_FANOUT, len(available)))
            for peer_id in targets:
                with self._sock_lock:
                    sock = self.peer_socks.get(peer_id)
                if sock:
                    try:
                        send_message(sock, MSG_GOSSIP_STATE, state)
                    except Exception:
                        with self._sock_lock:
                            self.peer_socks.pop(peer_id, None)

    # ═══════════════════════════════════════════════════════════════
    # Task generation & scheduling
    # ═══════════════════════════════════════════════════════════════

    def _generate_loop(self):
        """Generate tasks at random intervals."""
        time.sleep(2)  # wait for peer connections
        while self.running:
            interval = random.uniform(TASK_GEN_MIN_INTERVAL, TASK_GEN_MAX_INTERVAL)
            time.sleep(interval)
            task = generate_task(self.node_id)
            self._schedule_task(task)

    def _schedule_task(self, task):
        """Decide: execute locally or offload to the least-loaded peer."""
        with self._lock:
            local_load = self.tasks_running

        # Find least-loaded peer from gossip state
        best_peer = None
        best_load = float("inf")
        with self._peer_lock:
            for pid, state in self.peer_states.items():
                if time.time() - state.get("last_seen", 0) > PEER_TIMEOUT:
                    continue
                if state["tasks_running"] < best_load:
                    best_load = state["tasks_running"]
                    best_peer = pid

        # Quantum-inspired decision
        if best_peer and best_load < local_load:
            # Peer is less loaded — use quantum probability to decide
            local_cost = 1 + local_load * 0.5
            peer_cost = 1 + best_load * 0.5
            local_fitness = 1.0 / max(local_cost, 0.01)
            peer_fitness = 1.0 / max(peer_cost, 0.01)
            p_local = local_fitness / (local_fitness + peer_fitness)

            if random.random() > p_local:
                # Offload to peer
                self._offload_task(task, best_peer)
                return

        # Execute locally
        print(f"[{self.node_id}] Executing task {task.task_id} locally")
        self._emit_event("task_local",
                         f"{self.node_id} executing task {task.task_id} locally",
                         {"task_id": task.task_id, "node": self.node_id})
        threading.Thread(target=self._execute_task,
                         args=(task, None), daemon=True).start()

    def _offload_task(self, task, peer_id: str):
        """Send a task to a peer node for execution."""
        print(f"[{self.node_id}] Offloading task {task.task_id} to {peer_id}")
        self._emit_event("task_offload",
                         f"{self.node_id} offloading task {task.task_id} to {peer_id}",
                         {"task_id": task.task_id, "from": self.node_id,
                          "to": peer_id})

        with self._sock_lock:
            sock = self.peer_socks.get(peer_id)
        if sock:
            try:
                send_message(sock, MSG_TASK_OFFLOAD, task.to_dict())
            except Exception as e:
                print(f"[{self.node_id}] Failed to offload to {peer_id}: {e}")
                # Fall back to local execution
                threading.Thread(target=self._execute_task,
                                 args=(task, None), daemon=True).start()
        else:
            # Peer disconnected, execute locally
            threading.Thread(target=self._execute_task,
                             args=(task, None), daemon=True).start()

    def _execute_task(self, task, reply_to: str | None):
        """Execute a task locally."""
        with self._lock:
            self.tasks_running += 1

        compute_time = task.cpu_cycles / EDGE_CPU + task.data_size / EDGE_BANDWIDTH
        time.sleep(compute_time)

        with self._lock:
            self.tasks_running -= 1
            self.tasks_completed += 1
            self.total_exec_time += compute_time

        if reply_to:
            # This was an offloaded task — send result back
            with self._sock_lock:
                sock = self.peer_socks.get(reply_to)
            if sock:
                try:
                    send_message(sock, MSG_TASK_RESULT, {
                        "task_id": task.task_id,
                        "executor": self.node_id,
                        "exec_time": compute_time,
                    })
                except Exception:
                    pass
            self._emit_event("task_completed",
                             f"Task {task.task_id} completed by {self.node_id} (for {reply_to}) ({compute_time:.3f}s)",
                             {"task_id": task.task_id, "executor": self.node_id,
                              "origin": reply_to, "exec_time": compute_time})
        else:
            # Local task
            self._emit_event("task_completed",
                             f"Task {task.task_id} completed by {self.node_id} ({compute_time:.3f}s)",
                             {"task_id": task.task_id, "executor": self.node_id,
                              "origin": self.node_id, "exec_time": compute_time})

        self._quantum_rotate()

    # ═══════════════════════════════════════════════════════════════
    # Quantum rotation
    # ═══════════════════════════════════════════════════════════════

    def _quantum_rotate(self):
        theta = ROTATION_THETA
        a = self.alpha
        b = self.beta
        self.alpha = a * math.cos(theta) - b * math.sin(theta)
        self.beta = a * math.sin(theta) + b * math.cos(theta)

    # ═══════════════════════════════════════════════════════════════
    # Dashboard reporting
    # ═══════════════════════════════════════════════════════════════

    def _status_loop(self):
        """Periodically send full status to the dashboard."""
        while self.running:
            time.sleep(2)
            with self._lock:
                status = {
                    "node_id": self.node_id,
                    "tasks_running": self.tasks_running,
                    "tasks_completed": self.tasks_completed,
                    "load": self.tasks_running,
                    "alpha": round(self.alpha, 4),
                    "beta": round(self.beta, 4),
                }
            with self._sock_lock:
                status["connected_peers"] = list(self.peer_socks.keys())
            with self._peer_lock:
                status["peer_states"] = {
                    k: {"tasks_running": v["tasks_running"], "load": v["load"]}
                    for k, v in self.peer_states.items()
                }
            try:
                requests.post(f"{self.dashboard_url}/api/node_status",
                              json=status, timeout=1)
            except Exception:
                pass

    def _emit_event(self, event_type: str, message: str, data: dict = None):
        try:
            requests.post(f"{self.dashboard_url}/api/event", json={
                "event_type": event_type,
                "message": message,
                "data": data or {},
                "timestamp": time.time(),
            }, timeout=1)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════

def parse_peers(peer_args: list[str], my_id: str) -> dict:
    """Parse 'edgeN=host:port' strings into a dict."""
    peers = {}
    for p in peer_args:
        parts = p.split("=")
        if len(parts) == 2:
            pid = parts[0]
            host_port = parts[1].rsplit(":", 1)
            peers[pid] = (host_port[0], int(host_port[1]))
    return peers


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edge Node (Gossip-Based)")
    parser.add_argument("--id", required=True, help="Node ID (e.g. edge1)")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=None,
                        help="Bind port (default: from config)")
    parser.add_argument("--peers", nargs="*", default=[],
                        help="Peer addresses: edge2=host:port edge3=host:port")
    parser.add_argument("--dashboard-url", default=DASHBOARD_URL,
                        help=f"Dashboard URL (default: {DASHBOARD_URL})")
    args = parser.parse_args()

    # Resolve port
    if args.port is None:
        args.port = DEFAULT_PEERS.get(args.id, (None, 8001))[1]

    # Resolve peers
    if args.peers:
        peers = parse_peers(args.peers, args.id)
    else:
        # Use defaults from config, excluding self
        peers = {k: v for k, v in DEFAULT_PEERS.items() if k != args.id}

    node = EdgeNode(args.id, args.host, args.port, peers, args.dashboard_url)
    try:
        node.start()
    except KeyboardInterrupt:
        node.running = False
        print(f"\n[{args.id}] Shutting down.")
