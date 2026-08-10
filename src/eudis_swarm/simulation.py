"""Deterministic Prototype 0.1 simulation and command-line entry point."""

from __future__ import annotations

import argparse
import logging
import math
import random
from dataclasses import dataclass
from typing import Sequence

from .agent import Agent, AgentStatus, Position
from .config import SimulationConfig
from .failure_manager import FailureManager
from .metrics import SimulationMetrics
from .mission import Mission
from .task import Task
from .task_allocator import TaskAllocator


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SimulationResult:
    mission: Mission
    metrics: SimulationMetrics
    position_history: dict[int, tuple[tuple[float, Position], ...]]


def _initial_positions(config: SimulationConfig) -> list[Position]:
    margin = min(config.area_width, config.area_height) * 0.05
    corners = [
        (margin, margin),
        (config.area_width - margin, margin),
        (margin, config.area_height - margin),
        (config.area_width - margin, config.area_height - margin),
    ]
    if config.agent_count <= len(corners):
        return corners[: config.agent_count]

    positions = list(corners)
    center = (config.area_width / 2.0, config.area_height / 2.0)
    radius = min(config.area_width, config.area_height) * 0.35
    for index in range(config.agent_count - len(corners)):
        angle = 2.0 * math.pi * index / (config.agent_count - len(corners))
        positions.append(
            (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
        )
    return positions


def build_scenario(config: SimulationConfig) -> tuple[list[Agent], list[Task]]:
    """Create reproducible UAV and task positions from the configured seed."""

    agents = [
        Agent(agent_id=index + 1, position=position, speed=config.agent_speed)
        for index, position in enumerate(_initial_positions(config))
    ]
    randomizer = random.Random(config.random_seed)
    x_margin = config.area_width * 0.1
    y_margin = config.area_height * 0.1
    tasks = [
        Task(
            task_id=index + 1,
            position=(
                randomizer.uniform(x_margin, config.area_width - x_margin),
                randomizer.uniform(y_margin, config.area_height - y_margin),
            ),
        )
        for index in range(config.task_count)
    ]
    return agents, tasks


class Simulation:
    """Own the logical clock, failure injection, and movement mechanics."""

    def __init__(
        self,
        config: SimulationConfig,
        *,
        agents: Sequence[Agent] | None = None,
        tasks: Sequence[Task] | None = None,
    ) -> None:
        self.config = config
        scenario_agents, scenario_tasks = build_scenario(config)
        selected_agents = list(agents) if agents is not None else scenario_agents
        selected_tasks = list(tasks) if tasks is not None else scenario_tasks
        if len(selected_agents) != config.agent_count:
            raise ValueError("provided agents must match config.agent_count")
        if len(selected_tasks) != config.task_count:
            raise ValueError("provided tasks must match config.task_count")
        if config.failure_agent_id not in {agent.agent_id for agent in selected_agents}:
            raise ValueError("failure_agent_id is not present in provided agents")

        metrics = SimulationMetrics(
            total_task_count=len(selected_tasks),
            agents_started=len(selected_agents),
        )
        self.mission = Mission(
            agents=selected_agents,
            tasks=selected_tasks,
            allocator=TaskAllocator(),
            failure_manager=FailureManager(config.failure_timeout),
            metrics=metrics,
        )
        self._history: dict[int, list[tuple[float, Position]]] = {
            agent.agent_id: [(0.0, agent.position)] for agent in selected_agents
        }
        self._has_run = False

    def _record_positions(self, timestamp: float) -> None:
        for agent in sorted(self.mission.agents.values(), key=lambda item: item.agent_id):
            self._history[agent.agent_id].append((timestamp, agent.position))

    def _advance_agents(self, elapsed: float) -> None:
        for agent in sorted(self.mission.agents.values(), key=lambda item: item.agent_id):
            if (
                agent.status is not AgentStatus.ACTIVE
                or agent.current_task is None
                or not agent.responsive
            ):
                continue
            task = self.mission.tasks[agent.current_task]
            agent.move_toward(task.position, elapsed)

    def _complete_arrivals(self, timestamp: float) -> None:
        for agent in sorted(self.mission.agents.values(), key=lambda item: item.agent_id):
            if (
                agent.status is not AgentStatus.ACTIVE
                or agent.current_task is None
                or not agent.responsive
            ):
                continue
            task = self.mission.tasks[agent.current_task]
            if agent.distance_to(task.position) <= self.config.completion_tolerance:
                self.mission.complete_task(agent.agent_id, task.task_id, timestamp)

    def run(self) -> SimulationResult:
        if self._has_run:
            raise RuntimeError("a Simulation instance can only run once")
        self._has_run = True
        self.mission.start(0.0)
        failure_injected = False
        current_time = 0.0
        motion_step = 1
        next_motion = self.config.time_step
        next_heartbeat = self.config.heartbeat_interval
        epsilon = 1e-12

        if self.config.failure_time <= epsilon:
            failure_injected = self.mission.inject_failure(
                self.config.failure_agent_id, 0.0
            )

        while current_time < self.config.max_simulation_time - epsilon:
            event_times = [
                next_motion,
                next_heartbeat,
                self.config.max_simulation_time,
            ]
            if not failure_injected and self.config.failure_time > current_time + epsilon:
                event_times.append(self.config.failure_time)
            timestamp = round(
                min(
                    value
                    for value in event_times
                    if value > current_time + epsilon
                ),
                12,
            )
            elapsed = timestamp - current_time
            self._advance_agents(elapsed)
            current_time = timestamp

            # A failure scheduled on a boundary wins over heartbeat emission and
            # task completion at that same timestamp.
            if (
                not failure_injected
                and timestamp + epsilon >= self.config.failure_time
            ):
                failure_injected = self.mission.inject_failure(
                    self.config.failure_agent_id, timestamp
                )

            if timestamp + epsilon >= next_heartbeat:
                self.mission.exchange_heartbeats(timestamp)
                while next_heartbeat <= timestamp + epsilon:
                    next_heartbeat += self.config.heartbeat_interval

            self.mission.detect_and_recover(timestamp)
            self._complete_arrivals(timestamp)
            self.mission.allocate_tasks(timestamp)
            self._record_positions(timestamp)
            self.mission.assert_consistent()

            if self.mission.all_tasks_completed:
                self.mission.finish(timestamp, True)
                break
            if timestamp + epsilon >= next_motion:
                while next_motion <= timestamp + epsilon:
                    motion_step += 1
                    next_motion = round(motion_step * self.config.time_step, 12)
        else:
            self.mission.finish(current_time, False)

        result = SimulationResult(
            mission=self.mission,
            metrics=self.mission.metrics,
            position_history={
                agent_id: tuple(entries) for agent_id, entries in self._history.items()
            },
        )
        LOGGER.info("\n%s", result.metrics.format_summary())
        return result


def run_simulation(config: SimulationConfig | None = None) -> SimulationResult:
    return Simulation(config or SimulationConfig()).run()


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=level, format="%(message)s", force=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the EUDIS resilient swarm Prototype 0.1 simulation."
    )
    parser.add_argument("--agents", type=int, default=4, help="number of UAV agents")
    parser.add_argument("--tasks", type=int, default=20, help="number of mission tasks")
    parser.add_argument("--seed", type=int, default=2026, help="random seed")
    parser.add_argument(
        "--failure-agent", type=int, default=2, help="UAV ID to fail"
    )
    parser.add_argument(
        "--failure-time", type=float, default=4.0, help="failure injection time"
    )
    parser.add_argument(
        "--failure-timeout", type=float, default=2.5, help="heartbeat timeout"
    )
    parser.add_argument(
        "--visualize", action="store_true", help="show an optional final matplotlib view"
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    arguments = parser.parse_args(argv)
    try:
        config = SimulationConfig(
            agent_count=arguments.agents,
            task_count=arguments.tasks,
            random_seed=arguments.seed,
            failure_agent_id=arguments.failure_agent,
            failure_time=arguments.failure_time,
            failure_timeout=arguments.failure_timeout,
        )
    except ValueError as error:
        parser.error(str(error))

    configure_logging(arguments.log_level)
    result = run_simulation(config)
    if arguments.visualize:
        try:
            from .visualization import show_result

            show_result(result, config)
        except ImportError:
            LOGGER.error(
                "[VIS] matplotlib is not installed; use the 'visualization' extra"
            )
            return 2
    return 0 if result.metrics.mission_completed else 1


if __name__ == "__main__":
    raise SystemExit(main())
