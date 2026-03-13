# Quantum-Inspired Gossip-Based Distributed Task Scheduling System

A fully decentralized distributed task scheduling system where **edge nodes communicate via gossip protocol** and use **quantum-inspired probabilistic scheduling** to decide whether to execute tasks locally or offload to peers. No central scheduler — every node is equal.

## Architecture

```
┌──────────┐     gossip/TCP     ┌──────────┐
│  Edge 1  │◄──────────────────►│  Edge 2  │
│ (Machine A)                    (Machine B)│
└────┬─────┘                    └────┬─────┘
     │              gossip/TCP       │
     │          ┌──────────┐         │
     └─────────►│  Edge 3  │◄────────┘
                │(Machine C)│
                └──────────┘
                     │
              HTTP POST events
                     ▼
              ┌──────────────┐
              │  Dashboard   │   ← browser on any machine
              │  (port 5000) │
              └──────────────┘
```

- **No central scheduler** — each edge node makes its own scheduling decisions 
- **Gossip protocol** — nodes share load state with random peers every 2 seconds
- **Quantum-inspired** — offloading decisions use α/β probability amplitudes
- **Real TCP sockets** — nodes connect to each other over the network

## Quick Start (single machine)

```bash
pip install flask flask-socketio requests
python run_system.py
```

Open **http://YOUR_IP:5000** in your browser.

## Multi-Machine Deployment

Copy the project to each machine. Install dependencies:

```bash
pip install flask flask-socketio requests
```

### Machine A — Dashboard + Edge 1

```bash
python visualization/dashboard.py --host 0.0.0.0 --port 5000

python edge_nodes/edge_node.py --id edge1 --port 8001 --peers edge2=MACHINE_B_IP:8002 edge3=MACHINE_C_IP:8003 --dashboard-url http://MACHINE_A_IP:5000
```

### Machine B — Edge 2

```bash
python edge_nodes/edge_node.py --id edge2 --port 8002 --peers edge1=MACHINE_A_IP:8001 edge3=MACHINE_C_IP:8003 --dashboard-url http://MACHINE_A_IP:5000
```

### Machine C — Edge 3

```bash
python edge_nodes/edge_node.py --id edge3 --port 8003 --peers edge1=MACHINE_A_IP:8001 edge2=MACHINE_B_IP:8002 --dashboard-url http://MACHINE_A_IP:5000
```

## Project Structure

```
QiGbDTS/
├── common/
│   ├── config.py              # Node capacities, peer addresses, gossip params
│   ├── network_protocol.py    # Length-prefixed TCP messaging
│   └── task_model.py          # Task dataclass
├── edge_nodes/
│   ├── edge_node.py           # Gossip-based edge node (TCP server+client)
│   └── workload_generator.py  # Random task generation
├── visualization/
│   ├── dashboard.py           # Flask+SocketIO server
│   └── templates/
│       └── dashboard.html     # Full-screen network graph
├── run_system.py              # Local launcher
└── README.md
```

## How It Works

1. Each edge node starts a **TCP server** and connects to all peers
2. Every 2 seconds, each node **gossips** its load to random peers  
3. When a task is generated, the node compares its load with peers'
4. If a peer is less loaded → **quantum-inspired probability** decides:
   - Offload to the least-loaded peer, OR
   - Execute locally
5. Offloaded tasks are sent as `TASK_OFFLOAD` messages; results come back as `TASK_RESULT`
6. The **dashboard** graph shows nodes, connections, and animated dots for offloaded tasks

## CLI Reference

| Flag | Default | Description |
|------|---------|-------------|
| `--id` | *(required)* | Unique node ID (e.g. `edge1`) |
| `--host` | `0.0.0.0` | Bind address |
| `--port` | from config | TCP port for peer connections |
| `--peers` | from config | Peer list: `edge2=host:port edge3=host:port` |
| `--dashboard-url` | `http://127.0.0.1:5000` | Dashboard endpoint |
