"""
run_system.py — Launcher for the gossip-based distributed scheduler.
Starts the dashboard and edge nodes.

For multi-machine deployment, run each edge node on a separate computer.
See README.md for instructions.
"""

import subprocess
import sys
import time
import signal
import os
import socket

BASE = os.path.dirname(os.path.abspath(__file__))
PROCESSES: list[subprocess.Popen] = []


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def start(label: str, args: list[str]) -> subprocess.Popen:
    print(f"  Starting {label}...")
    proc = subprocess.Popen(
        [sys.executable] + args,
        cwd=BASE,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    PROCESSES.append(proc)
    return proc


def shutdown(*_):
    print("\n[Launcher] Shutting down...")
    for p in reversed(PROCESSES):
        try:
            p.terminate()
        except Exception:
            pass
    for p in PROCESSES:
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()
    print("[Launcher] Stopped.")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    ip = get_local_ip()
    dash_url = f"http://{ip}:5000"

    print("=" * 60)
    print("  Gossip-Based Distributed Task Scheduler")
    print("=" * 60)
    print(f"  Machine IP:   {ip}")
    print(f"  Dashboard:    {dash_url}")
    print("-" * 60)

    # 1. Dashboard
    start("Dashboard", ["visualization/dashboard.py", "--host", "0.0.0.0", "--port", "5000"])
    time.sleep(2)

    # 2. Edge Nodes (each on its own port, all as peers of each other)
    nodes = [
        ("edge1", 8001),
        ("edge2", 8002),
        ("edge3", 8003),
    ]

    for node_id, port in nodes:
        # Build peer list excluding self
        peers = [f"{pid}={ip}:{pp}" for pid, pp in nodes if pid != node_id]
        start(f"Edge {node_id}", [
            "edge_nodes/edge_node.py",
            "--id", node_id,
            "--host", "0.0.0.0",
            "--port", str(port),
            "--peers"] + peers + [
            "--dashboard-url", dash_url,
        ])
        time.sleep(0.5)

    print("-" * 60)
    print(f"  ✓ All nodes running")
    print(f"  ✓ Open {dash_url} in your browser")
    print()
    print("  To add an edge node from ANOTHER computer:")
    print(f"    python edge_nodes/edge_node.py --id edge4 --port 8004 \\")
    print(f"      --peers edge1={ip}:8001 edge2={ip}:8002 edge3={ip}:8003 \\")
    print(f"      --dashboard-url {dash_url}")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        while True:
            for p in PROCESSES:
                if p.poll() is not None:
                    print(f"[Launcher] Process exited (pid {p.pid}, code {p.returncode})")
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
