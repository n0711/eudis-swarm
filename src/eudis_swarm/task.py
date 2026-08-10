"""Mission task model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .agent import Position


class TaskStatus(str, Enum):
    UNASSIGNED = "UNASSIGNED"
    ASSIGNED = "ASSIGNED"
    COMPLETED = "COMPLETED"


@dataclass(slots=True)
class Task:
    """A point exploration task in the mission area."""

    task_id: int
    position: Position
    status: TaskStatus = TaskStatus.UNASSIGNED
    assigned_agent: int | None = None

    def __post_init__(self) -> None:
        if self.task_id <= 0:
            raise ValueError("task_id must be greater than zero")
        if len(self.position) != 2 or not all(isfinite(value) for value in self.position):
            raise ValueError("position must contain two finite coordinates")

    def assign(self, agent_id: int) -> None:
        if self.status is not TaskStatus.UNASSIGNED or self.assigned_agent is not None:
            raise ValueError(f"Task {self.task_id} is not unassigned")
        self.status = TaskStatus.ASSIGNED
        self.assigned_agent = agent_id

    def release(self) -> None:
        if self.status is not TaskStatus.ASSIGNED:
            raise ValueError(f"Task {self.task_id} is not assigned")
        self.status = TaskStatus.UNASSIGNED
        self.assigned_agent = None

    def complete(self, agent_id: int) -> None:
        if self.status is not TaskStatus.ASSIGNED or self.assigned_agent != agent_id:
            raise ValueError(f"Task {self.task_id} is not owned by UAV {agent_id}")
        self.status = TaskStatus.COMPLETED
