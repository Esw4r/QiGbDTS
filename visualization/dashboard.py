"""
Dashboard — Flask + Flask-SocketIO server for the visualization frontend.
Binds to 0.0.0.0 so it can be accessed from any machine on the network.

Run on the dashboard machine (or same as scheduler):
    python visualization/dashboard.py --host 0.0.0.0 --port 5000
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from visualization.animation_engine import AnimationEngine
from common.config import DASHBOARD_BIND_HOST, DASHBOARD_PORT

app = Flask(__name__)
app.config["SECRET_KEY"] = "quantum-scheduler-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

animation = AnimationEngine(socketio)


# ── Pages ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


# ── REST API (called by scheduler_server) ───────────────────────────

@app.route("/api/event", methods=["POST"])
def api_event():
    data = request.json
    socketio.emit("event", data)

    # If this is a scheduling decision, create an animated dot
    if data.get("event_type") == "task_scheduled":
        d = data.get("data", {})
        animation.add_task_dot(
            task_id=d.get("task_id", ""),
            origin=d.get("origin", "edge1"),
            decision=d.get("decision", "EDGE"),
            priority=d.get("priority", 1),
        )

    return jsonify({"ok": True})


@app.route("/api/node_status", methods=["POST"])
def api_node_status():
    socketio.emit("node_status", request.json)
    return jsonify({"ok": True})


@app.route("/api/metrics", methods=["POST"])
def api_metrics():
    socketio.emit("metrics", request.json)
    return jsonify({"ok": True})


# ── Start ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualization Dashboard")
    parser.add_argument("--host", default=DASHBOARD_BIND_HOST,
                        help=f"Bind address (default: {DASHBOARD_BIND_HOST})")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT,
                        help=f"Bind port (default: {DASHBOARD_PORT})")
    args = parser.parse_args()

    animation.start()
    print(f"[Dashboard] Starting on http://{args.host}:{args.port}")
    print(f"[Dashboard] Open in browser on any machine on the network")
    socketio.run(app, host=args.host, port=args.port, debug=False, allow_unsafe_werkzeug=True)
