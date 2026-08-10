from __future__ import annotations

from eudis_swarm.agent import AgentStatus
from eudis_swarm.config import SimulationConfig
from eudis_swarm.peer_state import PeerKnowledgeState
from eudis_swarm.simulation import PeerStateEventKind, Simulation


def _communication_scenario() -> SimulationConfig:
    return SimulationConfig(
        failure_time=100.0,
        communication_range=130.0,
        comm_fault_agent_id=2,
        comm_fault_start=4.0,
        comm_fault_end=8.0,
        peer_state_stale_after=2.5,
    )


def _peer_signature(result: object) -> list[tuple[object, float, int, int]]:
    return [
        (
            event.kind,
            event.timestamp,
            event.observer_agent_id,
            event.peer_agent_id,
        )
        for event in result.peer_state_events  # type: ignore[attr-defined]
    ]


def test_outage_stales_and_restores_independent_peer_views_without_failure() -> None:
    result = Simulation(_communication_scenario()).run()
    metrics = result.metrics
    isolated_agent = result.mission.agents[2]

    assert metrics.mission_completed is True
    assert metrics.completed_task_count == 20
    assert metrics.simulation_duration == 11.75
    assert metrics.failed_agent_count == 0
    assert metrics.orphaned_task_count == 0
    assert metrics.reassigned_task_count == 0
    assert isolated_agent.responsive is True
    assert isolated_agent.status is AgentStatus.IDLE
    assert isolated_agent.current_task is None

    assert metrics.peer_messages_attempted == 144
    assert metrics.peer_messages_delivered == 120
    assert metrics.peer_messages_undelivered == 24
    assert metrics.peer_state_stale_transition_count == 6
    assert metrics.peer_state_refresh_transition_count == 6
    assert metrics.maximum_simultaneous_stale_peer_observations == 6

    stale_events = [
        event
        for event in result.peer_state_events
        if event.kind is PeerStateEventKind.STALE
    ]
    refresh_events = [
        event
        for event in result.peer_state_events
        if event.kind is PeerStateEventKind.REFRESHED
    ]
    assert {event.timestamp for event in stale_events} == {5.75}
    assert {event.timestamp for event in refresh_events} == {8.0}
    assert {
        (event.observer_agent_id, event.peer_agent_id) for event in stale_events
    } == {
        (1, 2),
        (2, 1),
        (2, 3),
        (2, 4),
        (3, 2),
        (4, 2),
    }
    assert {
        (event.observer_agent_id, event.peer_agent_id) for event in refresh_events
    } == {
        (1, 2),
        (2, 1),
        (2, 3),
        (2, 4),
        (3, 2),
        (4, 2),
    }

    assert result.peer_state_stores is not None
    for observer_agent_id in (1, 3, 4):
        store = result.peer_state_stores[observer_agent_id]
        observation = store.observation_for(2)
        assert store.state_for(2) is PeerKnowledgeState.FRESH
        assert observation is not None
        assert observation.snapshot.timestamp == 11.0
        assert observation.snapshot.current_task == 2


def test_peer_state_transitions_are_deterministic() -> None:
    first = Simulation(_communication_scenario()).run()
    second = Simulation(_communication_scenario()).run()

    assert _peer_signature(first) == _peer_signature(second)
    assert (
        first.metrics.peer_messages_attempted == second.metrics.peer_messages_attempted
    )
    assert (
        first.metrics.peer_messages_delivered == second.metrics.peer_messages_delivered
    )
    assert (
        first.metrics.peer_messages_undelivered
        == second.metrics.peer_messages_undelivered
    )
