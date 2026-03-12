"""
Thread-safe priority task queue for the scheduler.
"""

import queue
from common.task_model import Task


class TaskQueue:
    """Priority queue wrapper — lower priority number = higher urgency."""

    def __init__(self):
        self._q: queue.PriorityQueue = queue.PriorityQueue()
        self._counter = 0  # tie-breaker

    def put(self, task: Task):
        # Negate priority so higher numeric priority = dequeued first
        self._q.put((-task.priority, self._counter, task))
        self._counter += 1

    def get(self, timeout: float = None) -> Task:
        _, _, task = self._q.get(timeout=timeout)
        return task

    def empty(self) -> bool:
        return self._q.empty()

    def qsize(self) -> int:
        return self._q.qsize()
