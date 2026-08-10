from eudis_swarm.communication import (
    CommunicationGraph,
    CommunicationState,
)


def test_links_use_inclusive_euclidean_range() -> None:
    graph = CommunicationGraph(agent_ids=[3, 1, 2], communication_range=5.0)

    update = graph.update(
        {
            1: (0.0, 0.0),
            2: (3.0, 4.0),
            3: (6.0, 8.0),
        }
    )

    assert graph.agent_ids == (1, 2, 3)
    assert update.is_initial is True
    assert update.lost_links == ()
    assert update.restored_links == ()
    assert [link.key for link in graph.links] == [(1, 2), (1, 3), (2, 3)]
    assert graph.link_between(2, 1).key == (1, 2)
    assert graph.link_between(1, 2).distance == 5.0
    assert graph.link_between(1, 2).available is True
    assert graph.link_between(1, 3).distance == 10.0
    assert graph.link_between(1, 3).available is False
    assert [link.key for link in graph.active_links] == [(1, 2), (2, 3)]


def test_components_neighbors_and_isolation_are_deterministic() -> None:
    graph = CommunicationGraph(agent_ids=[5, 3, 1, 4, 2], communication_range=1.1)
    graph.update(
        {
            1: (0.0, 0.0),
            2: (1.0, 0.0),
            3: (10.0, 0.0),
            4: (11.0, 0.0),
            5: (30.0, 0.0),
        }
    )

    assert graph.neighbors(1) == frozenset({2})
    assert graph.neighbors(3) == frozenset({4})
    assert graph.neighbors(5) == frozenset()
    assert graph.connected_components == (
        frozenset({1, 2}),
        frozenset({3, 4}),
        frozenset({5}),
    )
    assert graph.isolated_agent_ids == frozenset({5})
    assert graph.is_fully_connected is False
    assert graph.communication_state(1) is CommunicationState.REACHABLE
    assert graph.communication_state(5) is CommunicationState.UNREACHABLE


def test_movement_emits_one_loss_and_one_restoration() -> None:
    graph = CommunicationGraph(agent_ids=[1, 2], communication_range=5.0)
    initial = graph.update({1: (0.0, 0.0), 2: (4.0, 0.0)})

    assert initial.is_initial is True
    assert graph.is_fully_connected is True

    lost = graph.update({1: (0.0, 0.0), 2: (6.0, 0.0)})

    assert [link.key for link in lost.lost_links] == [(1, 2)]
    assert lost.lost_links[0].available is False
    assert lost.restored_links == ()
    assert lost.newly_isolated_agent_ids == (1, 2)
    assert lost.newly_reachable_agent_ids == ()
    assert lost.previous_component_count == 1
    assert lost.component_count == 2
    assert lost.network_partitioned is True
    assert lost.network_reconnected is False

    unchanged = graph.update({1: (0.0, 0.0), 2: (6.0, 0.0)})

    assert unchanged.lost_links == ()
    assert unchanged.restored_links == ()
    assert unchanged.newly_isolated_agent_ids == ()
    assert unchanged.newly_reachable_agent_ids == ()
    assert unchanged.network_partitioned is False

    restored = graph.update({1: (0.0, 0.0), 2: (5.0, 0.0)})

    assert [link.key for link in restored.restored_links] == [(1, 2)]
    assert restored.restored_links[0].available is True
    assert restored.lost_links == ()
    assert restored.newly_reachable_agent_ids == (1, 2)
    assert restored.component_count == 1
    assert restored.network_partitioned is False
    assert restored.network_reconnected is True


def test_fault_block_disables_only_incident_links_and_restores_them() -> None:
    positions = {
        1: (0.0, 0.0),
        2: (1.0, 0.0),
        3: (0.0, 1.0),
    }
    graph = CommunicationGraph(agent_ids=positions, communication_range=2.0)
    graph.update(positions)

    blocked = graph.update(positions, blocked_agent_ids={2})

    assert [link.key for link in blocked.lost_links] == [(1, 2), (2, 3)]
    assert [link.key for link in graph.active_links] == [(1, 3)]
    assert graph.blocked_agent_ids == frozenset({2})
    assert graph.neighbors(1) == frozenset({3})
    assert graph.neighbors(2) == frozenset()
    assert graph.isolated_agent_ids == frozenset({2})
    assert graph.communication_state(2) is CommunicationState.UNREACHABLE
    assert blocked.newly_isolated_agent_ids == (2,)

    repeated = graph.update(positions, blocked_agent_ids={2})

    assert repeated.lost_links == ()
    assert repeated.restored_links == ()

    restored = graph.update(positions)

    assert [link.key for link in restored.restored_links] == [(1, 2), (2, 3)]
    assert graph.blocked_agent_ids == frozenset()
    assert graph.link_count == 3
    assert graph.is_fully_connected is True
    assert graph.communication_state(2) is CommunicationState.REACHABLE
    assert restored.newly_reachable_agent_ids == (2,)
