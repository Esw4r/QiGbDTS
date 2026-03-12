"""
Task Model for the Quantum-Inspired Edge-Cloud Distributed Task Scheduling System.
Defines the Task dataclass and serialization utilities.
"""

import json
import time
import uuid
from dataclasses import dataclass, field, asdict


@dataclass
class Task:
    """Represents a computational task in the distributed system."""
    task_id: str = ""
    origin_node: str = ""
    cpu_cycles: int = 0
    memory: int = 0
    data_size: int = 0
    deadline: float = 0.0
    priority: int = 0
    edge_preference: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, json_str: str) -> "Task":
        return cls.from_dict(json.loads(json_str))

    @staticmethod
    def generate_id() -> str:
        return f"T{uuid.uuid4().hex[:6].upper()}"
