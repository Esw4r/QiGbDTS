"""
Dashboard — simplified Flask + SocketIO server for the graph-only frontend.
Only shows the network graph with nodes and animated task movement.
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO
from common.config import DASHBOARD_PORT

app = Flask(__name__)
app.config["SECRET_KEY"] = "quantum-gossip-secret"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


# ── Pages ───────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


# ── REST API (called by edge nodes) ────────────────────────────────

@app.route("/api/event", methods=["POST"])
def api_event():
    data = request.json
    socketio.emit("event", data)
    return jsonify({"ok": True})


@app.route("/api/node_status", methods=["POST"])
def api_node_status():
    socketio.emit("node_status", request.json)
    return jsonify({"ok": True})


# ── Start ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualization Dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=DASHBOARD_PORT, help="Bind port")
    args = parser.parse_args()

    print(f"[Dashboard] Starting on http://{args.host}:{args.port}")
    socketio.run(app, host=args.host, port=args.port, debug=False,
                 allow_unsafe_werkzeug=True)
