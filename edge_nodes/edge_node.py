"""
Edge Node — connects to the scheduler over the network, generates tasks,
and executes tasks locally when instructed.

Run on each edge machine:
    python edge_nodes/edge_node.py --id edge1 --scheduler-host 192.168.1.100 --scheduler-port 9000
"""

import sys
import os
import socket
import threading
import time
import random
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.config import (
    SCHEDULER_HOST, SCHEDULER_PORT,
    EDGE_CPU, EDGE_BANDWIDTH, EDGE_LATENCY,
    TASK_GEN_MIN_INTERVAL, TASK_GEN_MAX_INTERVAL,
)
from common.network_protocol import (
    send_message, recv_message,
    MSG_TASK_SUBMIT, MSG_SCHEDULE_DECISION, MSG_TASK_COMPLETE, MSG_REGISTER,
)
from edge_nodes.workload_generator import generate_task


class EdgeNode:
    def __init__(self, node_id: str, scheduler_host: str, scheduler_port: int):
        self.node_id = node_id
        self.scheduler_host = scheduler_host
        self.scheduler_port = scheduler_port
        self.sock: socket.socket | None = None
        self.running = True

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[{self.node_id}] Connecting to scheduler at "
              f"{self.scheduler_host}:{self.scheduler_port}...")
        self.sock.connect((self.scheduler_host, self.scheduler_port))
        send_message(self.sock, MSG_REGISTER, {"node_id": self.node_id})
        local_ip = self.sock.getsockname()[0]
        print(f"[{self.node_id}] Connected! (local IP: {local_ip})")

        # Start receiver thread
        threading.Thread(target=self._receive_loop, daemon=True).start()

        # Task generation loop
        self._generate_loop()

    def _generate_loop(self):
        while self.running:
            interval = random.uniform(TASK_GEN_MIN_INTERVAL, TASK_GEN_MAX_INTERVAL)
            time.sleep(interval)
            task = generate_task(self.node_id)
            print(f"[{self.node_id}] Submitting task {task.task_id}")
            try:
                send_message(self.sock, MSG_TASK_SUBMIT, task.to_dict())
            except Exception as e:
                print(f"[{self.node_id}] Send error: {e}")
                break

    def _receive_loop(self):
        while self.running:
            msg = recv_message(self.sock)
            if msg is None:
                print(f"[{self.node_id}] Disconnected from scheduler")
                self.running = False
                break
            if msg["type"] == MSG_SCHEDULE_DECISION:
                payload = msg["payload"]
                if payload["decision"] == "EDGE":
                    threading.Thread(
                        target=self._execute_task, args=(payload["task_id"],), daemon=True
                    ).start()

    def _execute_task(self, task_id: str):
        """Simulate local task execution."""
        compute_time = random.uniform(0.3, 1.5)
        print(f"[{self.node_id}] Executing task {task_id} locally ({compute_time:.2f}s)")
        time.sleep(compute_time)
        print(f"[{self.node_id}] Task {task_id} completed")
        try:
            send_message(self.sock, MSG_TASK_COMPLETE, {
                "task_id": task_id,
                "location": "EDGE",
                "origin": self.node_id,
                "exec_time": compute_time,
            })
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Edge Node")
    parser.add_argument("--id", required=True, help="Edge node ID (e.g. edge1)")
    parser.add_argument("--scheduler-host", default=SCHEDULER_HOST,
                        help=f"Scheduler IP address (default: {SCHEDULER_HOST})")
    parser.add_argument("--scheduler-port", type=int, default=SCHEDULER_PORT,
                        help=f"Scheduler port (default: {SCHEDULER_PORT})")
    args = parser.parse_args()

    node = EdgeNode(args.id, args.scheduler_host, args.scheduler_port)
    try:
        node.start()
    except KeyboardInterrupt:
        node.running = False
        print(f"\n[{args.id}] Shutting down.")
