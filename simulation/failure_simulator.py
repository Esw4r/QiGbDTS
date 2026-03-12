"""
Failure Simulator — randomly takes edge nodes offline and brings them back.
"""

import random
import threading
import time

from common.config import NODE_FAILURE_PROBABILITY, EDGE_NODE_IDS


class FailureSimulator:
    """Background thread that randomly simulates edge node failures."""

    def __init__(self, scheduler_server):
        self.server = scheduler_server
        self._failed: set[str] = set()
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while True:
            time.sleep(8)  # check every 8 seconds
            for node_id in EDGE_NODE_IDS:
                if node_id in self._failed:
                    # 30 % chance to recover
                    if random.random() < 0.30:
                        self._failed.discard(node_id)
                        self.server.mark_node_online(node_id)
                        print(f"[Failure] {node_id} recovered")
                else:
                    if random.random() < NODE_FAILURE_PROBABILITY:
                        self._failed.add(node_id)
                        self.server.mark_node_offline(node_id)
                        print(f"[Failure] {node_id} went OFFLINE")
