"""One-hop graph-mediated state delivery for Prototype 0.2B."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .agent import Heartbeat
from .communication import CommunicationGraph
from .peer_state import PeerStateStore
from .validation import validate_timestamp


@dataclass(frozen=True, slots=True)
class DeliveryBatch:
    """Aggregate results for one deterministic state-publication batch."""

    attempted: int
    delivered: int
    undelivered: int
    refreshed_observations: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if min(self.attempted, self.delivered, self.undelivered) < 0:
            raise ValueError("delivery counts must be non-negative")
        if self.attempted != self.delivered + self.undelivered:
            raise ValueError("attempted deliveries must equal batch outcomes")


class PeerStateTransport:
    """Deliver immutable snapshots across active direct graph links only."""

    def __init__(
        self,
        graph: CommunicationGraph,
        stores: Mapping[int, PeerStateStore],
    ) -> None:
        if frozenset(stores) != frozenset(graph.agent_ids):
            raise ValueError("peer-state stores must match communication graph UAVs")
        for owner_agent_id, store in stores.items():
            if store.owner_agent_id != owner_agent_id:
                raise ValueError("peer-state store key must match its owner")
            expected_peers = tuple(
                agent_id for agent_id in graph.agent_ids if agent_id != owner_agent_id
            )
            if store.peer_agent_ids != expected_peers:
                raise ValueError("each peer-state store must contain every other UAV")
        self._graph = graph
        self._stores = dict(stores)
        self._agent_ids = frozenset(graph.agent_ids)
        self._last_timestamp: float | None = None

    def deliver(
        self, snapshots: Iterable[Heartbeat], timestamp: float
    ) -> DeliveryBatch:
        """Attempt one directed delivery from each source to every other UAV."""

        if not self._graph.initialized:
            raise RuntimeError(
                "communication graph must be initialized before delivery"
            )
        timestamp = validate_timestamp(
            timestamp,
            previous=self._last_timestamp,
            name="transport timestamp",
        )
        ordered_snapshots = tuple(sorted(snapshots, key=lambda item: item.agent_id))
        source_ids = tuple(snapshot.agent_id for snapshot in ordered_snapshots)
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("a delivery batch may contain one snapshot per source")
        unknown_sources = set(source_ids) - self._agent_ids
        if unknown_sources:
            raise ValueError(f"unknown snapshot source UAVs: {sorted(unknown_sources)}")
        if any(snapshot.timestamp > timestamp for snapshot in ordered_snapshots):
            raise ValueError("snapshot timestamp cannot follow delivery time")

        attempted = 0
        delivered = 0
        refreshed: list[tuple[int, int]] = []
        for snapshot in ordered_snapshots:
            # One neighbor lookup replaces a validated graph lookup per receiver.
            active_receivers = self._graph.neighbors(snapshot.agent_id)
            for receiver_agent_id in self._graph.agent_ids:
                if receiver_agent_id == snapshot.agent_id:
                    continue
                attempted += 1
                if receiver_agent_id not in active_receivers:
                    continue
                delivered += 1
                if self._stores[receiver_agent_id].receive(snapshot, timestamp):
                    refreshed.append((receiver_agent_id, snapshot.agent_id))

        self._last_timestamp = timestamp
        return DeliveryBatch(
            attempted=attempted,
            delivered=delivered,
            undelivered=attempted - delivered,
            refreshed_observations=tuple(refreshed),
        )


__all__ = ["DeliveryBatch", "PeerStateTransport"]
