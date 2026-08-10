"""Central configuration for the Prototype 0.2A simulation."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from numbers import Real

from .validation import validate_positive_integer


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
        validate_positive_integer(self.agent_count, name="agent_count")
        validate_positive_integer(self.task_count, name="task_count")
        validate_positive_integer(self.failure_agent_id, name="failure_agent_id")
        if not isinstance(self.random_seed, int) or isinstance(self.random_seed, bool):
            raise ValueError("random_seed must be an integer")
        if self.comm_fault_agent_id is not None:
            validate_positive_integer(
                self.comm_fault_agent_id, name="comm_fault_agent_id"
            )

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
            if (
                not isinstance(value, Real)
                or isinstance(value, bool)
                or not isfinite(value)
                or value <= 0.0
            ):
                raise ValueError(f"{name} must be finite and greater than zero")

        non_negative_floats = {
            "completion_tolerance": self.completion_tolerance,
            "failure_time": self.failure_time,
            "comm_fault_start": self.comm_fault_start,
            "comm_fault_end": self.comm_fault_end,
        }
        for name, value in non_negative_floats.items():
            if (
                not isinstance(value, Real)
                or isinstance(value, bool)
                or not isfinite(value)
                or value < 0.0
            ):
                raise ValueError(f"{name} must be finite and non-negative")

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
