"""Replaceable nearest-distance task allocation policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .agent import Agent
from .task import Task, TaskStatus


@dataclass(frozen=True, slots=True)
class Allocation:
    agent_id: int
    task_id: int
    distance: float


class TaskAllocator:
    """Greedily select globally nearest available UAV/task pairs."""

    def allocate(self, agents: Iterable[Agent], tasks: Iterable[Task]) -> list[Allocation]:
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
