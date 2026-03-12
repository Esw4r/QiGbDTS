# Quantum-Inspired Edge–Cloud Distributed Task Scheduling System

A distributed system that uses **quantum-inspired probabilistic scheduling** to route tasks between edge nodes and a cloud node over **real TCP socket connections**. Includes a live animated visualization dashboard.

## Quick Start (Single Machine)

```bash
pip install flask flask-socketio networkx pyvis requests
python run_system.py
```

Open **http://YOUR_IP:5000** in your browser.

---

## Multi-Machine Deployment

Copy the entire `QiGbDTS/` folder to every machine. Install dependencies on each:

```bash
pip install flask flask-socketio networkx pyvis requests
```

### Step 1 — Dashboard + Scheduler (Machine A)

```bash
# Start the dashboard (accessible from any machine on the network)
python visualization/dashboard.py --host 0.0.0.0 --port 5000

# In another terminal, start the scheduler
python scheduler/scheduler_server.py --host 0.0.0.0 --port 9000 --dashboard-url http://MACHINE_A_IP:5000
```

Replace `MACHINE_A_IP` with Machine A's actual IP (e.g. `192.168.1.100`).

### Step 2 — Cloud Worker (Machine B)

```bash
python cloud/cloud_worker.py --scheduler-host MACHINE_A_IP --scheduler-port 9000
```

### Step 3 — Edge Nodes (Machines C, D, E...)

On each edge machine:

```bash
python edge_nodes/edge_node.py --id edge1 --scheduler-host MACHINE_A_IP --scheduler-port 9000
```

Use a unique `--id` for each edge (e.g. `edge1`, `edge2`, `edge3`).

### Step 4 — View Dashboard

Open `http://MACHINE_A_IP:5000` in any browser on the network.

The dashboard will show:
- **Real IP addresses** of every connected node
- **Animated task dots** moving between nodes
- **Live scheduler state** (α, β, P(edge), P(cloud))
- **System metrics** (latency, utilization, distribution)
- **Event log** with all task lifecycle events

---

## Architecture

```
Edge Node 1 (Machine C)  ──TCP──┐
Edge Node 2 (Machine D)  ──TCP──┤
Edge Node 3 (Machine E)  ──TCP──┼──▶  Scheduler (Machine A:9000)  ──TCP──▶  Cloud Worker (Machine B)
                                │              │
                                │              │ HTTP POST events
                                │              ▼
                                │     Dashboard (Machine A:5000)
                                │              │
                                │              │ WebSocket
                                │              ▼
                                └───  Browser (any machine)
```

## CLI Reference

| Component | Flag | Default | Description |
|-----------|------|---------|-------------|
| Scheduler | `--host` | `0.0.0.0` | Bind address |
| Scheduler | `--port` | `9000` | Bind port |
| Scheduler | `--dashboard-url` | `http://127.0.0.1:5000` | Dashboard endpoint |
| Edge Node | `--id` | *(required)* | Unique node ID |
| Edge Node | `--scheduler-host` | `127.0.0.1` | Scheduler IP |
| Edge Node | `--scheduler-port` | `9000` | Scheduler port |
| Cloud Worker | `--scheduler-host` | `127.0.0.1` | Scheduler IP |
| Cloud Worker | `--scheduler-port` | `9000` | Scheduler port |
| Dashboard | `--host` | `0.0.0.0` | Bind address |
| Dashboard | `--port` | `5000` | Bind port |

## Troubleshooting

- **"Connection refused"** — Ensure the scheduler is running and the IP/port are correct. Check your firewall allows TCP port 9000 and 5000.
- **Dashboard not showing nodes** — Make sure `--dashboard-url` points to the machine running the dashboard.
- **Windows Firewall** — You may need to allow Python through Windows Defender Firewall for incoming connections.
