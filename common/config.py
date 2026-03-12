"""
Configuration constants for the Quantum-Inspired Edge-Cloud Scheduler.

All network addresses default to 0.0.0.0 (accept from any interface) for
servers and 127.0.0.1 for clients. Override at runtime via CLI arguments
or environment variables so each machine can point to the correct host.
"""

import os

# ── Edge Node Capacity ──────────────────────────────────────────────
EDGE_CPU = 800          # CPU cycles capacity
EDGE_MEMORY = 256       # MB
EDGE_BANDWIDTH = 100    # Mbps
EDGE_LATENCY = 0.010    # seconds (10 ms)

# ── Cloud Node Capacity ────────────────────────────────────────────
CLOUD_CPU = 3000        # CPU cycles capacity
CLOUD_MEMORY = 4096     # MB
CLOUD_BANDWIDTH = 1000  # Mbps
CLOUD_LATENCY = 0.060   # seconds (60 ms)

# ── Network Addresses (defaults — override via CLI / env vars) ─────
# Server bind address (0.0.0.0 = accept connections from any machine)
SCHEDULER_BIND_HOST = os.environ.get("SCHEDULER_BIND_HOST", "0.0.0.0")
SCHEDULER_PORT = int(os.environ.get("SCHEDULER_PORT", "9000"))

# Where clients connect (set to scheduler machine's IP when distributed)
SCHEDULER_HOST = os.environ.get("SCHEDULER_HOST", "127.0.0.1")

DASHBOARD_BIND_HOST = os.environ.get("DASHBOARD_BIND_HOST", "0.0.0.0")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "5000"))
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_URL = f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"

# ── Quantum Scheduler Parameters ───────────────────────────────────
INITIAL_ALPHA = 0.707
INITIAL_BETA = 0.707
ROTATION_THETA = 0.05

# ── Simulation Parameters ──────────────────────────────────────────
TASK_GEN_MIN_INTERVAL = 1.0   # seconds
TASK_GEN_MAX_INTERVAL = 4.0   # seconds
NODE_FAILURE_PROBABILITY = 0.05
CONGESTION_EXTRA_LATENCY_MAX = 0.030   # 30 ms
CONGESTION_UPDATE_INTERVAL = 5.0       # seconds

# ── Edge Node IDs ──────────────────────────────────────────────────
EDGE_NODE_IDS = ["edge1", "edge2", "edge3"]
