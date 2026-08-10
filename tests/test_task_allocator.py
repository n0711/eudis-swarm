from eudis_swarm.agent import Agent
from eudis_swarm.failure_manager import FailureManager
from eudis_swarm.metrics import SimulationMetrics
from eudis_swarm.mission import Mission
from eudis_swarm.task import Task, TaskStatus
from eudis_swarm.task_allocator import TaskAllocator


def test_allocator_assigns_unique_tasks_and_excludes_failed_uav() -> None:
    healthy_left = Agent(agent_id=1, position=(0.0, 0.0), speed=1.0)
    failed = Agent(agent_id=2, position=(10.0, 0.0), speed=1.0)
    healthy_right = Agent(agent_id=3, position=(20.0, 0.0), speed=1.0)
    failed.declare_failed()
    tasks = [Task(task_id=1, position=(1.0, 0.0)), Task(task_id=2, position=(11.0, 0.0))]
    metrics = SimulationMetrics(total_task_count=2, agents_started=3)
    mission = Mission(
        agents=[healthy_left, failed, healthy_right],
        tasks=tasks,
        allocator=TaskAllocator(),
        failure_manager=FailureManager(heartbeat_timeout=2.0),
        metrics=metrics,
    )

    mission.start(0.0)

    owners = [task.assigned_agent for task in mission.tasks.values()]
    assert owners == [1, 3]
    assert len(owners) == len(set(owners))
    assert failed.current_task is None
    assert failed.available is False
    assert all(task.status is TaskStatus.ASSIGNED for task in mission.tasks.values())
    assert mission.allocate_tasks(0.5) == []
    mission.assert_consistent()


def test_allocator_has_deterministic_id_tie_breaking() -> None:
    agents = [
        Agent(agent_id=2, position=(0.0, 0.0), speed=1.0),
        Agent(agent_id=1, position=(0.0, 0.0), speed=1.0),
    ]
    tasks = [Task(task_id=2, position=(1.0, 0.0)), Task(task_id=1, position=(1.0, 0.0))]

    allocations = TaskAllocator().allocate(agents, tasks)

    assert [(item.agent_id, item.task_id) for item in allocations] == [(1, 1), (2, 2)]
