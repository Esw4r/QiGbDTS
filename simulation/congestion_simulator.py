"""
Congestion Simulator — periodically modifies network latency and bandwidth.
"""

import random
import threading
import time

from common.config import CONGESTION_EXTRA_LATENCY_MAX, CONGESTION_UPDATE_INTERVAL


class CongestionSimulator:
    """Background thread that injects random congestion into the scheduler."""

    def __init__(self, scheduler):
        self.scheduler = scheduler
        self._thread: threading.Thread | None = None

    def start(self):
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        while True:
            time.sleep(CONGESTION_UPDATE_INTERVAL)
            edge_lat = random.uniform(0, CONGESTION_EXTRA_LATENCY_MAX)
            cloud_lat = random.uniform(0, CONGESTION_EXTRA_LATENCY_MAX)
            edge_bw = random.uniform(0.6, 1.0)
            cloud_bw = random.uniform(0.7, 1.0)
            self.scheduler.set_congestion(edge_lat, cloud_lat, edge_bw, cloud_bw)
            print(f"[Congestion] edge_lat_mod={edge_lat:.3f}s  cloud_lat_mod={cloud_lat:.3f}s  "
                  f"edge_bw_factor={edge_bw:.2f}  cloud_bw_factor={cloud_bw:.2f}")
