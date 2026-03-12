"""
Quantum-Inspired Scheduler
Maintains quantum-like probability amplitudes α, β and uses them
to decide whether a task runs on an edge node or the cloud.
"""

import math
import random
import threading

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from common.config import (
    EDGE_CPU, EDGE_MEMORY, EDGE_BANDWIDTH, EDGE_LATENCY,
    CLOUD_CPU, CLOUD_MEMORY, CLOUD_BANDWIDTH, CLOUD_LATENCY,
    INITIAL_ALPHA, INITIAL_BETA, ROTATION_THETA,
)
from common.task_model import Task


class QuantumScheduler:
    """Quantum-inspired probabilistic task scheduler."""

    def __init__(self):
        self.alpha = INITIAL_ALPHA
        self.beta = INITIAL_BETA
        self._lock = threading.Lock()
        # Live congestion modifiers (updated by congestion simulator)
        self.edge_latency_mod = 0.0
        self.cloud_latency_mod = 0.0
        self.edge_bw_factor = 1.0
        self.cloud_bw_factor = 1.0

    # ── Public API ──────────────────────────────────────────────────

    def schedule(self, task: Task) -> str:
        """Return 'EDGE' or 'CLOUD' for the given task."""
        with self._lock:
            edge_cost = self._edge_cost(task)
            cloud_cost = self._cloud_cost(task)

            edge_fitness = 1.0 / max(edge_cost, 1e-9)
            cloud_fitness = 1.0 / max(cloud_cost, 1e-9)

            p_edge = edge_fitness / (edge_fitness + cloud_fitness)

            if random.random() < p_edge:
                decision = "EDGE"
            else:
                decision = "CLOUD"

            return decision

    def update_after_completion(self):
        """Apply quantum rotation after a task completes."""
        with self._lock:
            theta = ROTATION_THETA
            new_alpha = self.alpha * math.cos(theta) - self.beta * math.sin(theta)
            new_beta = self.alpha * math.sin(theta) + self.beta * math.cos(theta)
            self.alpha = new_alpha
            self.beta = new_beta

    def get_probabilities(self) -> dict:
        """Return current scheduling probabilities and amplitudes."""
        with self._lock:
            p_edge = self.alpha ** 2
            p_cloud = self.beta ** 2
            return {
                "alpha": round(self.alpha, 4),
                "beta": round(self.beta, 4),
                "p_edge": round(p_edge, 4),
                "p_cloud": round(p_cloud, 4),
            }

    def set_congestion(self, edge_lat_mod, cloud_lat_mod, edge_bw, cloud_bw):
        with self._lock:
            self.edge_latency_mod = edge_lat_mod
            self.cloud_latency_mod = cloud_lat_mod
            self.edge_bw_factor = edge_bw
            self.cloud_bw_factor = cloud_bw

    # ── Cost helpers ────────────────────────────────────────────────

    def _edge_cost(self, task: Task) -> float:
        latency = EDGE_LATENCY + self.edge_latency_mod
        bandwidth = EDGE_BANDWIDTH * self.edge_bw_factor

        compute_time = task.cpu_cycles / EDGE_CPU
        transfer_time = task.data_size / max(bandwidth, 1)
        total_time = compute_time + transfer_time + latency

        penalty = max(0, total_time - task.deadline)
        priority_weight = 1 + task.priority * 0.2

        return total_time * priority_weight + penalty + task.memory / EDGE_MEMORY

    def _cloud_cost(self, task: Task) -> float:
        latency = CLOUD_LATENCY + self.cloud_latency_mod
        bandwidth = CLOUD_BANDWIDTH * self.cloud_bw_factor

        compute_time = task.cpu_cycles / CLOUD_CPU
        transfer_time = task.data_size / max(bandwidth, 1)
        total_time = compute_time + transfer_time + latency

        penalty = max(0, total_time - task.deadline)
        priority_weight = 1 + task.priority * 0.2

        return total_time * priority_weight + penalty + task.memory / CLOUD_MEMORY
