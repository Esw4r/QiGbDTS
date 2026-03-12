"""
Animation Engine — manages the state of animated task dots and
emits SocketIO events so the browser can render movement.
"""

import time
import threading


class AnimationEngine:
    """Track moving task dots and broadcast frames via SocketIO."""

    def __init__(self, socketio):
        self.socketio = socketio
        self.active_dots: list[dict] = []
        self._lock = threading.Lock()

    def add_task_dot(self, task_id: str, origin: str, decision: str, priority: int):
        """Register a new animated dot that will travel origin → scheduler → target."""
        color = "red" if priority >= 4 else ("orange" if decision == "CLOUD" else "#00bfff")
        dot = {
            "task_id": task_id,
            "origin": origin,
            "decision": decision.lower(),
            "color": color,
            "phase": "to_scheduler",   # then "to_target", then removed
            "progress": 0.0,
            "start_time": time.time(),
        }
        with self._lock:
            self.active_dots.append(dot)
        self.socketio.emit("dot_add", dot)

    def tick(self):
        """Advance all dots — called ~20× per second by a background thread."""
        dt = 0.05  # each tick advances by 5 %
        remove = []
        with self._lock:
            for dot in self.active_dots:
                dot["progress"] += dt
                if dot["progress"] >= 1.0:
                    if dot["phase"] == "to_scheduler":
                        dot["phase"] = "to_target"
                        dot["progress"] = 0.0
                    else:
                        remove.append(dot)
            for d in remove:
                self.active_dots.remove(d)
                self.socketio.emit("dot_remove", {"task_id": d["task_id"]})

        # Broadcast current state
        with self._lock:
            snapshot = [dict(d) for d in self.active_dots]
        if snapshot:
            self.socketio.emit("dots_update", snapshot)

    def start(self):
        """Run the tick loop in a background thread."""
        def loop():
            while True:
                self.tick()
                time.sleep(0.05)
        threading.Thread(target=loop, daemon=True).start()
