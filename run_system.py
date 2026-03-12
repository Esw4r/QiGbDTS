"""
run_system.py — Launcher for local development / demo.
Starts all components on the SAME machine for quick testing.

For multi-machine deployment, run each component on a separate computer.
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
    """Get the LAN IP address of this machine."""
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
    print("\n[Launcher] Shutting down all components...")
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
    print("[Launcher] All components stopped.")
    sys.exit(0)


def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    local_ip = get_local_ip()
    dashboard_url = f"http://{local_ip}:5000"

    print("=" * 60)
    print("  Quantum Edge-Cloud Scheduler — Local Launcher")
    print("=" * 60)
    print(f"  Machine IP:     {local_ip}")
    print(f"  Dashboard:      http://{local_ip}:5000")
    print(f"  Scheduler:      {local_ip}:9000")
    print("-" * 60)

    # 1. Dashboard (must start first so scheduler can POST events)
    start("Dashboard", [
        "visualization/dashboard.py",
        "--host", "0.0.0.0",
        "--port", "5000",
    ])
    time.sleep(2)

    # 2. Scheduler
    start("Scheduler", [
        "scheduler/scheduler_server.py",
        "--host", "0.0.0.0",
        "--port", "9000",
        "--dashboard-url", dashboard_url,
    ])
    time.sleep(1)

    # 3. Cloud Worker
    start("Cloud Worker", [
        "cloud/cloud_worker.py",
        "--scheduler-host", local_ip,
        "--scheduler-port", "9000",
    ])
    time.sleep(0.5)

    # 4. Edge Nodes
    for i in range(1, 4):
        start(f"Edge Node {i}", [
            "edge_nodes/edge_node.py",
            "--id", f"edge{i}",
            "--scheduler-host", local_ip,
            "--scheduler-port", "9000",
        ])
        time.sleep(0.3)

    print("-" * 60)
    print(f"  ✓ All components running on {local_ip}")
    print(f"  ✓ Open http://{local_ip}:5000 in your browser")
    print()
    print("  To connect edge nodes from OTHER computers, run:")
    print(f"    python edge_nodes/edge_node.py --id edgeN --scheduler-host {local_ip}")
    print()
    print("  To connect a cloud worker from another computer, run:")
    print(f"    python cloud/cloud_worker.py --scheduler-host {local_ip}")
    print()
    print("  Press Ctrl+C to stop.")
    print("=" * 60)

    # Wait for any process to exit
    try:
        while True:
            for p in PROCESSES:
                if p.poll() is not None:
                    print(f"[Launcher] A component exited (pid {p.pid}, code {p.returncode})")
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown()


if __name__ == "__main__":
    main()
