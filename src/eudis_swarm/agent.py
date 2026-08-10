"""UAV agent state and simple two-dimensional movement."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import hypot, isfinite
from typing import TypeAlias


Position: TypeAlias = tuple[float, float]


class AgentStatus(str, Enum):
    """Coordinator-visible UAV states."""

    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"


@dataclass(frozen=True, slots=True)
class Heartbeat:
    """A timestamped state snapshot advertised by one UAV."""

    agent_id: int
    position: Position
    status: AgentStatus
    current_task: int | None
    timestamp: float


@dataclass(slots=True)
class Agent:
    """A point-mass UAV abstraction with no aircraft dynamics."""

    agent_id: int
    position: Position
    speed: float
    status: AgentStatus = AgentStatus.IDLE
    current_task: int | None = None
    last_heartbeat: float = 0.0
    responsive: bool = True
    failure_injected_at: float | None = None

    def __post_init__(self) -> None:
        if self.agent_id <= 0:
            raise ValueError("agent_id must be greater than zero")
        if len(self.position) != 2 or not all(isfinite(value) for value in self.position):
            raise ValueError("position must contain two finite coordinates")
        if not isfinite(self.speed) or self.speed <= 0.0:
            raise ValueError("speed must be finite and greater than zero")

    @property
    def available(self) -> bool:
        """Whether the coordinator currently considers this UAV allocatable."""

        return self.status is AgentStatus.IDLE and self.current_task is None

    def distance_to(self, target: Position) -> float:
        return hypot(target[0] - self.position[0], target[1] - self.position[1])

    def assign_task(self, task_id: int) -> None:
        if not self.available:
            raise ValueError(f"UAV {self.agent_id} is not available")
        self.current_task = task_id
        self.status = AgentStatus.ACTIVE

    def release_task(self, task_id: int) -> None:
        if self.current_task != task_id:
            raise ValueError(f"UAV {self.agent_id} does not own Task {task_id}")
        self.current_task = None
        if self.status is not AgentStatus.FAILED:
            self.status = AgentStatus.IDLE

    def complete_task(self, task_id: int) -> None:
        self.release_task(task_id)

    def move_toward(self, target: Position, elapsed: float) -> None:
        """Advance toward a target using a constant-speed point update."""

        if elapsed < 0.0:
            raise ValueError("elapsed must be non-negative")
        if not self.responsive or self.status is AgentStatus.FAILED:
            return

        distance = self.distance_to(target)
        if distance == 0.0:
            return
        travel = min(self.speed * elapsed, distance)
        ratio = travel / distance
        self.position = (
            self.position[0] + (target[0] - self.position[0]) * ratio,
            self.position[1] + (target[1] - self.position[1]) * ratio,
        )

    def send_heartbeat(self, timestamp: float) -> Heartbeat | None:
        """Return a state snapshot, or nothing after a physical failure."""

        if not self.responsive or self.status is AgentStatus.FAILED:
            return None
        self.last_heartbeat = timestamp
        return Heartbeat(
            agent_id=self.agent_id,
            position=self.position,
            status=self.status,
            current_task=self.current_task,
            timestamp=timestamp,
        )

    def inject_failure(self, timestamp: float) -> bool:
        """Make the UAV silent and immobile without declaring it failed."""

        if not self.responsive or self.status is AgentStatus.FAILED:
            return False
        self.responsive = False
        self.failure_injected_at = timestamp
        return True

    def declare_failed(self) -> None:
        """Apply the coordinator's failure decision after a timeout."""

        self.responsive = False
        self.status = AgentStatus.FAILED
