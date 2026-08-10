"""Deterministic task-allocation policies."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from numbers import Real
from typing import Iterable, Mapping, Protocol

from .agent import Agent
from .peer_state import PeerKnowledgeState, PeerStateStore
from .task import Task, TaskStatus
from .validation import validate_positive_integer


@dataclass(frozen=True, slots=True)
class Allocation:
    agent_id: int
    task_id: int
    distance: float
    policy: str = "distance"
    predicted_peer_degree: int | None = None
    predicted_isolation: bool | None = None

    def __post_init__(self) -> None:
        validate_positive_integer(self.agent_id, name="allocation agent_id")
        validate_positive_integer(self.task_id, name="allocation task_id")
        if (
            not isinstance(self.distance, Real)
            or isinstance(self.distance, bool)
            or not isfinite(self.distance)
            or self.distance < 0.0
        ):
            raise ValueError("allocation distance must be finite and non-negative")
        if self.policy not in {"distance", "connectivity"}:
            raise ValueError("unknown allocation policy")
        if self.policy == "distance":
            if (
                self.predicted_peer_degree is not None
                or self.predicted_isolation is not None
            ):
                raise ValueError("distance allocations must not contain predictions")
            return
        if (
            not isinstance(self.predicted_peer_degree, int)
            or isinstance(self.predicted_peer_degree, bool)
            or self.predicted_peer_degree < 0
            or not isinstance(self.predicted_isolation, bool)
        ):
            raise ValueError("connectivity allocations require valid predictions")
        if self.predicted_isolation != (self.predicted_peer_degree == 0):
            raise ValueError("predicted isolation must match predicted peer degree")


class AllocationPolicy(Protocol):
    """Minimal proposal interface consumed by the authoritative Mission."""

    def allocate(
        self, agents: Iterable[Agent], tasks: Iterable[Task]
    ) -> list[Allocation]: ...


class TaskAllocator:
    """Greedily select globally nearest available UAV/task pairs."""

    def allocate(
        self, agents: Iterable[Agent], tasks: Iterable[Task]
    ) -> list[Allocation]:
        """Propose unique assignments without mutating mission state."""

        candidates_agents = {
            agent.agent_id: agent
            for agent in sorted(agents, key=lambda item: item.agent_id)
            if agent.available
        }
        candidates_tasks = {
            task.task_id: task
            for task in sorted(tasks, key=lambda item: item.task_id)
            if task.status is TaskStatus.UNASSIGNED and task.assigned_agent is None
        }
        allocations: list[Allocation] = []

        while candidates_agents and candidates_tasks:
            distance, agent_id, task_id = min(
                (
                    agent.distance_to(task.position),
                    agent.agent_id,
                    task.task_id,
                )
                for agent in candidates_agents.values()
                for task in candidates_tasks.values()
            )
            allocations.append(
                Allocation(agent_id=agent_id, task_id=task_id, distance=distance)
            )
            del candidates_agents[agent_id]
            del candidates_tasks[task_id]

        return allocations


class CommunicationAwareTaskAllocator:
    """Prefer assignments that local fresh peer knowledge predicts stay linked."""

    def __init__(
        self,
        peer_state_stores: Mapping[int, PeerStateStore],
        communication_range: float,
    ) -> None:
        if (
            not isinstance(communication_range, Real)
            or isinstance(communication_range, bool)
            or not isfinite(communication_range)
            or communication_range <= 0.0
        ):
            raise ValueError("communication_range must be finite and greater than zero")
        for owner_agent_id, store in peer_state_stores.items():
            if owner_agent_id != store.owner_agent_id:
                raise ValueError("peer-state store key must match its owner")
        self._peer_state_stores = dict(peer_state_stores)
        self._communication_range = float(communication_range)

    def _predicted_degree(self, agent_id: int, task: Task) -> int:
        try:
            store = self._peer_state_stores[agent_id]
        except KeyError as error:
            raise ValueError(f"missing peer-state store for UAV {agent_id}") from error

        predicted_degree = 0
        for peer_agent_id in store.peer_agent_ids:
            if store.state_for(peer_agent_id) is not PeerKnowledgeState.FRESH:
                continue
            observation = store.observation_for(peer_agent_id)
            if observation is None:
                raise RuntimeError("fresh peer state must contain an observation")
            peer_position = observation.snapshot.position
            distance = hypot(
                task.position[0] - peer_position[0],
                task.position[1] - peer_position[1],
            )
            if distance <= self._communication_range:
                predicted_degree += 1
        return predicted_degree

    def evaluate_candidate(self, agent: Agent, task: Task) -> Allocation:
        """Explain one candidate using only the UAV's local peer observations."""

        predicted_degree = self._predicted_degree(agent.agent_id, task)
        return Allocation(
            agent_id=agent.agent_id,
            task_id=task.task_id,
            distance=agent.distance_to(task.position),
            policy="connectivity",
            predicted_peer_degree=predicted_degree,
            predicted_isolation=predicted_degree == 0,
        )

    @staticmethod
    def _score(allocation: Allocation) -> tuple[int, int, float, int, int]:
        degree = allocation.predicted_peer_degree
        isolation = allocation.predicted_isolation
        if degree is None or isolation is None:
            raise ValueError("connectivity candidate is missing prediction metadata")
        return (
            int(isolation),
            -degree,
            allocation.distance,
            allocation.agent_id,
            allocation.task_id,
        )

    def allocate(
        self, agents: Iterable[Agent], tasks: Iterable[Task]
    ) -> list[Allocation]:
        """Propose unique pairs using local-knowledge connectivity first."""

        candidate_agents = {
            agent.agent_id: agent
            for agent in sorted(agents, key=lambda item: item.agent_id)
            if agent.available
        }
        candidate_tasks = {
            task.task_id: task
            for task in sorted(tasks, key=lambda item: item.task_id)
            if task.status is TaskStatus.UNASSIGNED and task.assigned_agent is None
        }
        allocations: list[Allocation] = []

        while candidate_agents and candidate_tasks:
            candidates = (
                self.evaluate_candidate(agent, task)
                for agent in candidate_agents.values()
                for task in candidate_tasks.values()
            )
            selected = min(
                candidates,
                key=self._score,
            )
            allocations.append(selected)
            del candidate_agents[selected.agent_id]
            del candidate_tasks[selected.task_id]

        return allocations


__all__ = [
    "Allocation",
    "AllocationPolicy",
    "CommunicationAwareTaskAllocator",
    "TaskAllocator",
]
