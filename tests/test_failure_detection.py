from eudis_swarm.agent import Agent, AgentStatus
from eudis_swarm.config import SimulationConfig
from eudis_swarm.failure_manager import FailureManager
from eudis_swarm.metrics import SimulationMetrics
from eudis_swarm.mission import Mission, MissionEventKind
from eudis_swarm.simulation import Simulation
from eudis_swarm.task import Task, TaskStatus
from eudis_swarm.task_allocator import TaskAllocator


def test_strict_heartbeat_timeout_declares_failure_once() -> None:
    agent = Agent(agent_id=1, position=(0.0, 0.0), speed=1.0)
    task = Task(task_id=1, position=(100.0, 0.0))
    mission = Mission(
        agents=[agent],
        tasks=[task],
        allocator=TaskAllocator(),
        failure_manager=FailureManager(heartbeat_timeout=3.0),
        metrics=SimulationMetrics(total_task_count=1, agents_started=1),
    )
    mission.start(5.0)

    assert mission.detect_and_recover(7.999) == []
    assert mission.detect_and_recover(8.0) == []
    assert agent.status is AgentStatus.ACTIVE

    detected = mission.detect_and_recover(8.001)

    assert [event.agent_id for event in detected] == [1]
    assert agent.status is AgentStatus.FAILED
    assert agent.available is False
    assert agent.current_task is None
    assert task.status is TaskStatus.UNASSIGNED
    assert mission.metrics.failed_agent_count == 1
    assert mission.metrics.orphaned_task_count == 1
    assert mission.detect_and_recover(20.0) == []
    assert (
        sum(event.kind is MissionEventKind.FAILURE_DECLARED for event in mission.events)
        == 1
    )


def test_coarse_movement_step_does_not_skip_scheduled_heartbeats() -> None:
    config = SimulationConfig(
        agent_count=2,
        task_count=2,
        agent_speed=0.1,
        time_step=5.0,
        heartbeat_interval=1.0,
        failure_timeout=2.5,
        failure_agent_id=2,
        failure_time=5.0,
        max_simulation_time=10.0,
    )
    agents = [
        Agent(agent_id=1, position=(0.0, 0.0), speed=0.1),
        Agent(agent_id=2, position=(100.0, 0.0), speed=0.1),
    ]
    tasks = [
        Task(task_id=1, position=(0.0, 100.0)),
        Task(task_id=2, position=(100.0, 100.0)),
    ]

    result = Simulation(config, agents=agents, tasks=tasks).run()
    failure = result.metrics.failures[2]

    assert failure.injected_at == 5.0
    assert failure.last_heartbeat == 4.0
    assert failure.detected_at == 7.0
    assert result.metrics.failure_detection_latencies[2] == 2.0
