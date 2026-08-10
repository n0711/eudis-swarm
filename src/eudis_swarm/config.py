"""Central configuration for the Prototype 0.2A simulation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    """Validated parameters for a deterministic simulation run."""

    agent_count: int = 4
    task_count: int = 20
    random_seed: int = 2026
    area_width: float = 100.0
    area_height: float = 100.0
    agent_speed: float = 10.0
    time_step: float = 0.25
    completion_tolerance: float = 0.75
    heartbeat_interval: float = 1.0
    failure_timeout: float = 2.5
    failure_agent_id: int = 2
    failure_time: float = 4.0
    max_simulation_time: float = 300.0
    communication_range: float = 130.0
    comm_fault_agent_id: int | None = None
    comm_fault_start: float = 4.0
    comm_fault_end: float = 8.0

    def __post_init__(self) -> None:
        positive_ints = {
            "agent_count": self.agent_count,
            "task_count": self.task_count,
        }
        for name, value in positive_ints.items():
            if value <= 0:
                raise ValueError(f"{name} must be greater than zero")

        positive_floats = {
            "area_width": self.area_width,
            "area_height": self.area_height,
            "agent_speed": self.agent_speed,
            "time_step": self.time_step,
            "heartbeat_interval": self.heartbeat_interval,
            "failure_timeout": self.failure_timeout,
            "max_simulation_time": self.max_simulation_time,
            "communication_range": self.communication_range,
        }
        for name, value in positive_floats.items():
            if not isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and greater than zero")

        if not isfinite(self.completion_tolerance) or self.completion_tolerance < 0.0:
            raise ValueError("completion_tolerance must be finite and non-negative")
        if not isfinite(self.failure_time) or self.failure_time < 0.0:
            raise ValueError("failure_time must be finite and non-negative")
        if not isfinite(self.comm_fault_start) or self.comm_fault_start < 0.0:
            raise ValueError("comm_fault_start must be finite and non-negative")
        if not isfinite(self.comm_fault_end) or self.comm_fault_end < 0.0:
            raise ValueError("comm_fault_end must be finite and non-negative")
        if self.comm_fault_end <= self.comm_fault_start:
            raise ValueError("comm_fault_end must be greater than comm_fault_start")
        if self.failure_timeout < self.heartbeat_interval:
            raise ValueError("failure_timeout must be at least heartbeat_interval")
        if not 1 <= self.failure_agent_id <= self.agent_count:
            raise ValueError("failure_agent_id must identify a configured agent")
        if self.comm_fault_agent_id is not None and not (
            1 <= self.comm_fault_agent_id <= self.agent_count
        ):
            raise ValueError("comm_fault_agent_id must identify a configured agent")
