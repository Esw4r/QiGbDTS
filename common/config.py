"""
Configuration for the Gossip-Based Distributed Task Scheduling System.

Each edge node runs on a unique port and discovers peers by their addresses.
All addresses configurable via CLI arguments for multi-machine deployment.
"""

import os

# ── Edge Node Capacity ──────────────────────────────────────────────
EDGE_CPU = 800          # CPU cycles capacity
EDGE_MEMORY = 256       # MB
EDGE_BANDWIDTH = 100    # Mbps

# ── Edge Node Network (defaults for local testing) ─────────────────
# Map of node_id -> (host, port)
# Override via CLI args when running on real separate machines
DEFAULT_PEERS = {
    "edge1": ("127.0.0.1", 8001),
    "edge2": ("127.0.0.1", 8002),
    "edge3": ("127.0.0.1", 8003),
}

# ── Dashboard ──────────────────────────────────────────────────────
DASHBOARD_HOST = os.environ.get("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "5000"))
DASHBOARD_URL = f"http://{DASHBOARD_HOST}:{DASHBOARD_PORT}"

# ── Gossip Parameters ─────────────────────────────────────────────
GOSSIP_INTERVAL = 2.0      # seconds between gossip rounds
GOSSIP_FANOUT = 2          # number of random peers to gossip to each round
PEER_TIMEOUT = 10.0        # seconds before considering a peer dead

# ── Task Generation ───────────────────────────────────────────────
TASK_GEN_MIN_INTERVAL = 1.0
TASK_GEN_MAX_INTERVAL = 4.0

# ── Quantum Scheduler Parameters ─────────────────────────────────
INITIAL_ALPHA = 0.707
INITIAL_BETA = 0.707
ROTATION_THETA = 0.05
