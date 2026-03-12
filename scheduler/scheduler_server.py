"""
Scheduler Server — the central coordinator.
Accepts TCP connections from edge nodes and the cloud worker on any network.
Routes tasks via the QuantumScheduler and emits events to the dashboard.

Run on the scheduler machine:
    python scheduler/scheduler_server.py --port 9000 --dashboard-url http://DASHBOARD_IP:5000
"""

import sys
import os
import socket
import threading
import time
import json
import argparse
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.config import (
    SCHEDULER_BIND_HOST, SCHEDULER_PORT, DASHBOARD_URL, EDGE_NODE_IDS,
)
from common.network_protocol import (
    send_message, recv_message,
    MSG_TASK_SUBMIT, MSG_SCHEDULE_DECISION, MSG_TASK_COMPLETE,
    MSG_NODE_STATUS, MSG_REGISTER,
)
from common.task_model import Task
from scheduler.quantum_scheduler import QuantumScheduler
from scheduler.task_queue import TaskQueue
from simulation.congestion_simulator import CongestionSimulator
from simulation.failure_simulator import FailureSimulator


class SchedulerServer:
    def __init__(self, bind_host: str, port: int, dashboard_url: str):
        self.bind_host = bind_host
        self.port = port
        self.dashboard_url = dashboard_url

        self.scheduler = QuantumScheduler()
        self.task_queue = TaskQueue()
        self.clients: dict[str, socket.socket] = {}   # node_id -> socket
        self.client_addrs: dict[str, str] = {}         # node_id -> "IP:port"
        self.edge_tasks: dict[str, int] = {}
        self.cloud_tasks = 0
        self.completed = 0
        self.total_latency = 0.0
        self.edge_completed = 0
        self.cloud_completed = 0
        self.online_nodes: set[str] = set()
        self._lock = threading.Lock()

        # Simulators
        self.congestion = CongestionSimulator(self.scheduler)
        self.failure = FailureSimulator(self)

    # ── Networking ──────────────────────────────────────────────────

    def start(self):
        self.congestion.start()
        self.failure.start()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((self.bind_host, self.port))
        server.listen(10)
        print(f"[Scheduler] Listening on {self.bind_host}:{self.port}")
        print(f"[Scheduler] Dashboard URL: {self.dashboard_url}")
        self._emit_event("system", "Scheduler started — waiting for nodes to connect")

        while True:
            conn, addr = server.accept()
            threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True).start()

    def _handle_client(self, conn: socket.socket, addr):
        node_id = None
        addr_str = f"{addr[0]}:{addr[1]}"
        try:
            # First message should be REGISTER
            msg = recv_message(conn)
            if msg and msg["type"] == MSG_REGISTER:
                node_id = msg["payload"]["node_id"]
                with self._lock:
                    self.clients[node_id] = conn
                    self.client_addrs[node_id] = addr_str
                    self.online_nodes.add(node_id)
                    if node_id.startswith("edge") and node_id not in self.edge_tasks:
                        self.edge_tasks[node_id] = 0
                print(f"[Scheduler] {node_id} connected from {addr_str}")
                self._emit_event("connection",
                                 f"{node_id} connected from {addr[0]}",
                                 {"node_id": node_id, "ip": addr[0], "port": addr[1]})
                self._emit_node_status()

            while True:
                msg = recv_message(conn)
                if msg is None:
                    break
                self._process_message(node_id, msg)
        except Exception as e:
            print(f"[Scheduler] Error with {node_id} ({addr_str}): {e}")
        finally:
            with self._lock:
                self.online_nodes.discard(node_id)
                self.clients.pop(node_id, None)
                self.client_addrs.pop(node_id, None)
            if node_id:
                print(f"[Scheduler] {node_id} disconnected")
                self._emit_event("connection", f"{node_id} disconnected")
                self._emit_node_status()

    def _process_message(self, node_id: str, msg: dict):
        msg_type = msg["type"]
        payload = msg["payload"]

        if msg_type == MSG_TASK_SUBMIT:
            task = Task.from_dict(payload)
            self._emit_event("task_created", f"Task {task.task_id} created at {task.origin_node}",
                             {"task_id": task.task_id, "origin": task.origin_node})

            # Check if origin edge is still online
            with self._lock:
                origin_online = task.origin_node in self.online_nodes

            decision = self.scheduler.schedule(task)

            # If decision is EDGE but origin is offline, reroute to cloud
            if decision == "EDGE" and not origin_online:
                decision = "CLOUD"
                self._emit_event("reroute", f"Task {task.task_id} rerouted to CLOUD (node offline)")

            self._emit_event("task_scheduled",
                             f"Task {task.task_id} scheduled to {decision}",
                             {"task_id": task.task_id, "origin": task.origin_node,
                              "decision": decision, "priority": task.priority})

            # Send probabilities update
            self._emit_metrics()

            if decision == "EDGE":
                # Tell the originating edge to execute locally
                with self._lock:
                    self.edge_tasks[task.origin_node] = self.edge_tasks.get(task.origin_node, 0) + 1
                    sock = self.clients.get(task.origin_node)
                if sock:
                    send_message(sock, MSG_SCHEDULE_DECISION,
                                 {"task_id": task.task_id, "decision": "EDGE"})
            else:
                with self._lock:
                    self.cloud_tasks += 1
                    sock = self.clients.get("cloud")
                if sock:
                    send_message(sock, MSG_SCHEDULE_DECISION,
                                 {**task.to_dict(), "decision": "CLOUD"})
                else:
                    print("[Scheduler] Cloud worker not connected!")

            self._emit_node_status()

        elif msg_type == MSG_TASK_COMPLETE:
            task_id = payload["task_id"]
            exec_location = payload.get("location", "unknown")
            exec_time = payload.get("exec_time", 0)

            with self._lock:
                self.completed += 1
                self.total_latency += exec_time
                if exec_location == "EDGE":
                    origin = payload.get("origin", node_id)
                    self.edge_tasks[origin] = max(0, self.edge_tasks.get(origin, 1) - 1)
                    self.edge_completed += 1
                else:
                    self.cloud_tasks = max(0, self.cloud_tasks - 1)
                    self.cloud_completed += 1

            self.scheduler.update_after_completion()

            self._emit_event("task_completed",
                             f"Task {task_id} completed on {exec_location} ({exec_time:.3f}s)",
                             {"task_id": task_id, "location": exec_location, "exec_time": exec_time})
            self._emit_node_status()
            self._emit_metrics()

    # ── Dashboard helpers ───────────────────────────────────────────

    def _emit_event(self, event_type: str, message: str, data: dict = None):
        try:
            requests.post(f"{self.dashboard_url}/api/event", json={
                "event_type": event_type,
                "message": message,
                "data": data or {},
                "timestamp": time.time(),
            }, timeout=2)
        except Exception:
            pass

    def _emit_node_status(self):
        with self._lock:
            status = {
                "edge_tasks": dict(self.edge_tasks),
                "cloud_tasks": self.cloud_tasks,
                "online_nodes": list(self.online_nodes),
                "node_ips": dict(self.client_addrs),
            }
        try:
            requests.post(f"{self.dashboard_url}/api/node_status", json=status, timeout=2)
        except Exception:
            pass

    def _emit_metrics(self):
        with self._lock:
            avg_latency = (self.total_latency / self.completed) if self.completed else 0
            edge_count = max(len(self.edge_tasks), 1)
            metrics = {
                "avg_latency": round(avg_latency, 4),
                "tasks_completed": self.completed,
                "edge_completed": self.edge_completed,
                "cloud_completed": self.cloud_completed,
                "edge_utilization": round(sum(self.edge_tasks.values()) / edge_count, 2),
                "cloud_utilization": round(self.cloud_tasks / 5, 2),
                "distribution_ratio": round(
                    self.edge_completed / max(self.edge_completed + self.cloud_completed, 1), 4
                ),
            }
        probs = self.scheduler.get_probabilities()
        metrics.update(probs)
        try:
            requests.post(f"{self.dashboard_url}/api/metrics", json=metrics, timeout=2)
        except Exception:
            pass

    # ── Failure handling ────────────────────────────────────────────

    def mark_node_offline(self, node_id: str):
        with self._lock:
            self.online_nodes.discard(node_id)
            sock = self.clients.pop(node_id, None)
            self.client_addrs.pop(node_id, None)
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        self._emit_event("failure", f"{node_id} went OFFLINE")
        self._emit_node_status()

    def mark_node_online(self, node_id: str):
        with self._lock:
            self.online_nodes.add(node_id)
        self._emit_event("recovery", f"{node_id} back ONLINE")
        self._emit_node_status()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quantum Scheduler Server")
    parser.add_argument("--host", default=SCHEDULER_BIND_HOST,
                        help=f"Bind address (default: {SCHEDULER_BIND_HOST})")
    parser.add_argument("--port", type=int, default=SCHEDULER_PORT,
                        help=f"Bind port (default: {SCHEDULER_PORT})")
    parser.add_argument("--dashboard-url", default=DASHBOARD_URL,
                        help=f"Dashboard URL (default: {DASHBOARD_URL})")
    args = parser.parse_args()

    server = SchedulerServer(args.host, args.port, args.dashboard_url)
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n[Scheduler] Shutting down.")
