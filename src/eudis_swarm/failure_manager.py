"""Heartbeat storage and strict timeout detection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .agent import Agent, AgentStatus, Heartbeat
from .validation import validate_positive_real, validate_timestamp


@dataclass(frozen=True, slots=True)
class HeartbeatTimeout:
    agent_id: int
    detected_at: float
    last_heartbeat: float
    task_id: int | None


class FailureManager:
    """Detect silent agents without owning mission/task transitions."""

    def __init__(self, heartbeat_timeout: float) -> None:
        self.heartbeat_timeout = validate_positive_real(
            heartbeat_timeout, name="heartbeat_timeout"
        )
        self._heartbeats: dict[int, Heartbeat] = {}
        self._detected_agents: set[int] = set()
        self._last_detection_time: float | None = None

    @property
    def heartbeats(self) -> dict[int, Heartbeat]:
        return dict(self._heartbeats)

    def record_heartbeat(self, heartbeat: Heartbeat) -> None:
        previous = self._heartbeats.get(heartbeat.agent_id)
        validate_timestamp(
            heartbeat.timestamp,
            previous=None if previous is None else previous.timestamp,
            name="heartbeat timestamp",
        )
        self._heartbeats[heartbeat.agent_id] = heartbeat

    def detect_timeouts(
        self, agents: Iterable[Agent], timestamp: float
    ) -> list[HeartbeatTimeout]:
        """Return each newly stale agent once, using strict ``>`` semantics."""

        timestamp = validate_timestamp(
            timestamp,
            previous=self._last_detection_time,
            name="failure detection timestamp",
        )
        latest_heartbeat = max(
            (heartbeat.timestamp for heartbeat in self._heartbeats.values()),
            default=None,
        )
        validate_timestamp(
            timestamp,
            previous=latest_heartbeat,
            name="failure detection timestamp",
        )
        self._last_detection_time = timestamp
        timeouts: list[HeartbeatTimeout] = []
        for agent in sorted(agents, key=lambda item: item.agent_id):
            if (
                agent.status is AgentStatus.FAILED
                or agent.agent_id in self._detected_agents
            ):
                continue
            heartbeat = self._heartbeats.get(agent.agent_id)
            if heartbeat is None:
                continue
            if timestamp - heartbeat.timestamp > self.heartbeat_timeout:
                self._detected_agents.add(agent.agent_id)
                timeouts.append(
                    HeartbeatTimeout(
                        agent_id=agent.agent_id,
                        detected_at=timestamp,
                        last_heartbeat=heartbeat.timestamp,
                        task_id=agent.current_task,
                    )
                )
        return timeouts
