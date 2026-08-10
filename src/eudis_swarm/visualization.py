"""Optional matplotlib rendering kept outside the headless core."""

from __future__ import annotations

from .agent import AgentStatus
from .config import SimulationConfig
from .simulation import SimulationResult
from .task import TaskStatus


def show_result(result: SimulationResult, config: SimulationConfig) -> None:
    """Display paths, final UAV states, and task completion state."""

    import matplotlib.pyplot as plt

    figure, axes = plt.subplots(figsize=(8, 8))
    communication_graph = result.communication_graph
    if communication_graph is not None:
        for index, link in enumerate(communication_graph.active_links):
            source = result.mission.agents[link.source_agent_id].position
            destination = result.mission.agents[link.destination_agent_id].position
            axes.plot(
                [source[0], destination[0]],
                [source[1], destination[1]],
                color="slategray",
                linewidth=0.8,
                alpha=0.45,
                zorder=0,
                label="Final communication links" if index == 0 else None,
            )
    for agent_id, history in sorted(result.position_history.items()):
        axes.plot(
            [entry[1][0] for entry in history],
            [entry[1][1] for entry in history],
            linewidth=1.0,
            alpha=0.55,
            label=f"UAV {agent_id} path",
        )

    completed = [
        task
        for task in result.mission.tasks.values()
        if task.status is TaskStatus.COMPLETED
    ]
    incomplete = [
        task
        for task in result.mission.tasks.values()
        if task.status is not TaskStatus.COMPLETED
    ]
    if completed:
        axes.scatter(
            [task.position[0] for task in completed],
            [task.position[1] for task in completed],
            marker="o",
            color="forestgreen",
            label="Completed tasks",
        )
    if incomplete:
        axes.scatter(
            [task.position[0] for task in incomplete],
            [task.position[1] for task in incomplete],
            marker="o",
            facecolors="none",
            edgecolors="darkorange",
            label="Incomplete tasks",
        )

    for agent in sorted(result.mission.agents.values(), key=lambda item: item.agent_id):
        failed = agent.status is AgentStatus.FAILED
        unreachable = (
            not failed
            and communication_graph is not None
            and agent.agent_id in communication_graph.isolated_agent_ids
        )
        axes.scatter(
            [agent.position[0]],
            [agent.position[1]],
            marker="X" if failed else ("s" if unreachable else "^"),
            s=120,
            color=(
                "firebrick" if failed else ("darkorange" if unreachable else "royalblue")
            ),
            zorder=3,
        )
        axes.annotate(
            (
                f"UAV {agent.agent_id}"
                f"{' FAILED' if failed else (' UNREACHABLE' if unreachable else '')}"
            ),
            agent.position,
            xytext=(5, 5),
            textcoords="offset points",
        )

    axes.set_xlim(0.0, config.area_width)
    axes.set_ylim(0.0, config.area_height)
    axes.set_aspect("equal", adjustable="box")
    axes.set_title("EUDIS Swarm Prototype 0.2A")
    axes.set_xlabel("x")
    axes.set_ylabel("y")
    axes.grid(alpha=0.2)
    axes.legend(loc="best", fontsize="small")
    figure.tight_layout()
    plt.show()
