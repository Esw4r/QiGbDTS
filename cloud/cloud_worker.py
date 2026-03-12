"""
Cloud Worker — connects to the scheduler over the network and executes
tasks offloaded to the cloud.

Run on the cloud machine:
    python cloud/cloud_worker.py --scheduler-host 192.168.1.100 --scheduler-port 9000
"""

import sys
import os
import socket
import threading
import time
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.config import (
    SCHEDULER_HOST, SCHEDULER_PORT,
    CLOUD_CPU, CLOUD_BANDWIDTH, CLOUD_LATENCY,
)
from common.network_protocol import (
    send_message, recv_message,
    MSG_SCHEDULE_DECISION, MSG_TASK_COMPLETE, MSG_REGISTER,
)
from common.task_model import Task


class CloudWorker:
    def __init__(self, scheduler_host: str, scheduler_port: int):
        self.scheduler_host = scheduler_host
        self.scheduler_port = scheduler_port
        self.sock: socket.socket | None = None
        self.running = True

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print(f"[Cloud] Connecting to scheduler at "
              f"{self.scheduler_host}:{self.scheduler_port}...")
        self.sock.connect((self.scheduler_host, self.scheduler_port))
        send_message(self.sock, MSG_REGISTER, {"node_id": "cloud"})
        local_ip = self.sock.getsockname()[0]
        print(f"[Cloud] Connected! (local IP: {local_ip})")

        while self.running:
            msg = recv_message(self.sock)
            if msg is None:
                print("[Cloud] Disconnected from scheduler")
                break
            if msg["type"] == MSG_SCHEDULE_DECISION:
                payload = msg["payload"]
                if payload.get("decision") == "CLOUD":
                    threading.Thread(
                        target=self._execute_task, args=(payload,), daemon=True
                    ).start()

    def _execute_task(self, payload: dict):
        task = Task.from_dict(payload)
        compute_time = task.cpu_cycles / CLOUD_CPU
        transfer_time = task.data_size / CLOUD_BANDWIDTH
        total_time = compute_time + transfer_time + CLOUD_LATENCY

        print(f"[Cloud] Executing task {task.task_id} ({total_time:.3f}s)")
        time.sleep(total_time)
        print(f"[Cloud] Task {task.task_id} completed")

        try:
            send_message(self.sock, MSG_TASK_COMPLETE, {
                "task_id": task.task_id,
                "location": "CLOUD",
                "origin": task.origin_node,
                "exec_time": total_time,
            })
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cloud Worker")
    parser.add_argument("--scheduler-host", default=SCHEDULER_HOST,
                        help=f"Scheduler IP address (default: {SCHEDULER_HOST})")
    parser.add_argument("--scheduler-port", type=int, default=SCHEDULER_PORT,
                        help=f"Scheduler port (default: {SCHEDULER_PORT})")
    args = parser.parse_args()

    worker = CloudWorker(args.scheduler_host, args.scheduler_port)
    try:
        worker.start()
    except KeyboardInterrupt:
        worker.running = False
        print("\n[Cloud] Shutting down.")
