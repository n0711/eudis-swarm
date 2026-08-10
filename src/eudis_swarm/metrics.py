"""Event-derived Prototype 0.1 metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import fmean

from .agent import Position


@dataclass(slots=True)
class FailureRecord:
    agent_id: int
    injected_at: float | None = None
    injection_position: Position | None = None
    detected_at: float | None = None
    last_heartbeat: float | None = None


@dataclass(slots=True)
class RecoveryRecord:
    task_id: int
    failed_agent_id: int
    orphaned_at: float
    reassigned_agent_id: int | None = None
    reassigned_at: float | None = None
    completed_at: float | None = None


@dataclass(slots=True)
class SimulationMetrics:
    """Metrics calculated from real state transitions in simulated time."""

    total_task_count: int
    agents_started: int
    start_time: float = 0.0
    end_time: float | None = None
    mission_completed: bool = False
    human_interventions: int = 0
    completed_task_ids: set[int] = field(default_factory=set)
    failures: dict[int, FailureRecord] = field(default_factory=dict)
    recoveries: dict[int, RecoveryRecord] = field(default_factory=dict)

    def record_failure_injection(
        self, agent_id: int, timestamp: float, position: Position
    ) -> None:
        record = self.failures.setdefault(agent_id, FailureRecord(agent_id=agent_id))
        if record.injected_at is None:
            record.injected_at = timestamp
            record.injection_position = position

    def record_failure_detection(
        self, agent_id: int, timestamp: float, last_heartbeat: float
    ) -> None:
        record = self.failures.setdefault(agent_id, FailureRecord(agent_id=agent_id))
        if record.detected_at is None:
            record.detected_at = timestamp
            record.last_heartbeat = last_heartbeat

    def record_orphan(self, task_id: int, failed_agent_id: int, timestamp: float) -> None:
        self.recoveries.setdefault(
            task_id,
            RecoveryRecord(
                task_id=task_id,
                failed_agent_id=failed_agent_id,
                orphaned_at=timestamp,
            ),
        )

    def record_reassignment(self, task_id: int, agent_id: int, timestamp: float) -> None:
        recovery = self.recoveries[task_id]
        if recovery.reassigned_agent_id is None:
            if agent_id == recovery.failed_agent_id:
                raise ValueError("an orphaned task cannot return to its failed owner")
            recovery.reassigned_agent_id = agent_id
            recovery.reassigned_at = timestamp

    def record_task_completion(self, task_id: int, timestamp: float) -> None:
        self.completed_task_ids.add(task_id)
        recovery = self.recoveries.get(task_id)
        if recovery is not None and recovery.completed_at is None:
            recovery.completed_at = timestamp

    def finish(self, timestamp: float, mission_completed: bool) -> None:
        self.end_time = timestamp
        self.mission_completed = mission_completed

    @property
    def simulation_duration(self) -> float:
        if self.end_time is None:
            return 0.0
        return self.end_time - self.start_time

    @property
    def completed_task_count(self) -> int:
        return len(self.completed_task_ids)

    @property
    def failed_agent_count(self) -> int:
        return sum(record.detected_at is not None for record in self.failures.values())

    @property
    def orphaned_task_count(self) -> int:
        return len(self.recoveries)

    @property
    def reassigned_task_count(self) -> int:
        return sum(
            recovery.reassigned_agent_id is not None
            for recovery in self.recoveries.values()
        )

    @property
    def recovered_task_count(self) -> int:
        """Count orphaned tasks completed after assignment to a survivor."""

        return sum(
            recovery.reassigned_agent_id is not None
            and recovery.completed_at is not None
            for recovery in self.recoveries.values()
        )

    @property
    def failure_detection_latencies(self) -> dict[int, float]:
        return {
            agent_id: record.detected_at - record.injected_at
            for agent_id, record in self.failures.items()
            if record.injected_at is not None and record.detected_at is not None
        }

    @property
    def heartbeat_detection_delays(self) -> dict[int, float]:
        return {
            agent_id: record.detected_at - record.last_heartbeat
            for agent_id, record in self.failures.items()
            if record.detected_at is not None and record.last_heartbeat is not None
        }

    @property
    def task_reassignment_latencies(self) -> dict[int, float]:
        return {
            task_id: recovery.reassigned_at - recovery.orphaned_at
            for task_id, recovery in self.recoveries.items()
            if recovery.reassigned_at is not None
        }

    @staticmethod
    def _mean_or_na(values: list[float]) -> str:
        return "N/A" if not values else f"{fmean(values):.2f} s"

    def format_summary(self) -> str:
        """Build the concise terminal result block from recorded values."""

        return "\n".join(
            [
                "PROTOTYPE 0.1 RESULT",
                "",
                f"Mission completed: {'YES' if self.mission_completed else 'NO'}",
                f"Tasks completed: {self.completed_task_count} / {self.total_task_count}",
                f"Agents started: {self.agents_started}",
                f"Agents failed: {self.failed_agent_count}",
                f"Orphaned tasks: {self.orphaned_task_count}",
                f"Tasks reassigned: {self.reassigned_task_count}",
                f"Recovered tasks: {self.recovered_task_count}",
                f"Simulation duration: {self.simulation_duration:.2f} s",
                "Failure detection latency: "
                + self._mean_or_na(list(self.failure_detection_latencies.values())),
                "Task reassignment latency: "
                + self._mean_or_na(list(self.task_reassignment_latencies.values())),
                f"Human interventions: {self.human_interventions}",
            ]
        )
