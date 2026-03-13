"""
Workload Generator — creates random Task instances
"""

import random
from common.task_model import Task


def generate_task(origin_node: str) -> Task:
    """Generate a random task originating from the given edge node."""
    return Task(
        task_id=Task.generate_id(),
        origin_node=origin_node,
        cpu_cycles=random.randint(200, 1500),
        memory=random.randint(32, 512),
        data_size=random.randint(5, 100),
        deadline=random.uniform(1.0, 8.0),
        priority=random.randint(1, 5),
        edge_preference=round(random.uniform(0.2, 0.9), 2),
    )
