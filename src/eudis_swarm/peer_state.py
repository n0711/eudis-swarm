"""Receiver-local peer observations for Prototype 0.2B."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from math import isfinite
from numbers import Real
from typing import Iterable

from .agent import Heartbeat
from .validation import validate_positive_integer, validate_timestamp


class PeerKnowledgeState(str, Enum):
    """Freshness of one receiver's last successfully delivered peer snapshot."""

    UNKNOWN = "UNKNOWN"
    FRESH = "FRESH"
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class PeerObservation:
    """An immutable delivered snapshot and its receiver-local arrival time."""

    snapshot: Heartbeat
    received_at: float

    def __post_init__(self) -> None:
        received_at = validate_timestamp(self.received_at, name="received_at")
        if received_at < self.snapshot.timestamp:
            raise ValueError("received_at cannot precede the snapshot timestamp")


class PeerStateStore:
    """Last-known peer state owned by one UAV and changed only by delivery."""

    def __init__(
        self,
        owner_agent_id: int,
        peer_agent_ids: Iterable[int],
        stale_after: float,
    ) -> None:
        self._owner_agent_id = validate_positive_integer(
            owner_agent_id, name="owner_agent_id"
        )
        supplied_peer_ids = tuple(peer_agent_ids)
        for peer_agent_id in supplied_peer_ids:
            validate_positive_integer(peer_agent_id, name="peer_agent_id")
        if len(set(supplied_peer_ids)) != len(supplied_peer_ids):
            raise ValueError("peer_agent_ids must be unique")
        if owner_agent_id in supplied_peer_ids:
            raise ValueError("a peer-state store must not contain self-state")
        if (
            not isinstance(stale_after, Real)
            or isinstance(stale_after, bool)
            or not isfinite(stale_after)
            or stale_after <= 0.0
        ):
            raise ValueError("stale_after must be finite and greater than zero")

        self._peer_agent_ids = tuple(sorted(supplied_peer_ids))
        self._peer_agent_id_set = frozenset(self._peer_agent_ids)
        self._stale_after = float(stale_after)
        self._observations: dict[int, PeerObservation] = {}
        self._states = {
            peer_agent_id: PeerKnowledgeState.UNKNOWN
            for peer_agent_id in self._peer_agent_ids
        }
        self._last_timestamp: float | None = None

    @property
    def owner_agent_id(self) -> int:
        return self._owner_agent_id

    @property
    def peer_agent_ids(self) -> tuple[int, ...]:
        return self._peer_agent_ids

    @property
    def stale_after(self) -> float:
        return self._stale_after

    @property
    def stale_peer_ids(self) -> frozenset[int]:
        return frozenset(
            peer_agent_id
            for peer_agent_id, state in self._states.items()
            if state is PeerKnowledgeState.STALE
        )

    def state_for(self, peer_agent_id: int) -> PeerKnowledgeState:
        self._require_peer(peer_agent_id)
        return self._states[peer_agent_id]

    def observation_for(self, peer_agent_id: int) -> PeerObservation | None:
        self._require_peer(peer_agent_id)
        return self._observations.get(peer_agent_id)

    def receive(self, snapshot: Heartbeat, received_at: float) -> bool:
        """Store one delivered snapshot and report refresh-after-stale."""

        self._require_peer(snapshot.agent_id)
        received_at = validate_timestamp(
            received_at,
            previous=self._last_timestamp,
            name="peer-state receipt timestamp",
        )
        previous = self._observations.get(snapshot.agent_id)
        if previous is not None and snapshot.timestamp < previous.snapshot.timestamp:
            raise ValueError("peer snapshots must not move backwards")
        observation = PeerObservation(snapshot=snapshot, received_at=received_at)
        refreshed = self._states[snapshot.agent_id] is PeerKnowledgeState.STALE
        self._observations[snapshot.agent_id] = observation
        self._states[snapshot.agent_id] = PeerKnowledgeState.FRESH
        self._last_timestamp = received_at
        return refreshed

    def advance_time(self, timestamp: float) -> tuple[int, ...]:
        """Apply strict freshness expiry and return newly stale peer IDs."""

        timestamp = validate_timestamp(
            timestamp,
            previous=self._last_timestamp,
            name="peer-state timestamp",
        )
        newly_stale: list[int] = []
        for peer_agent_id in self._peer_agent_ids:
            if self._states[peer_agent_id] is not PeerKnowledgeState.FRESH:
                continue
            observation = self._observations[peer_agent_id]
            if timestamp - observation.received_at > self._stale_after:
                self._states[peer_agent_id] = PeerKnowledgeState.STALE
                newly_stale.append(peer_agent_id)
        self._last_timestamp = timestamp
        return tuple(newly_stale)

    def _require_peer(self, peer_agent_id: int) -> None:
        if peer_agent_id not in self._peer_agent_id_set:
            raise KeyError(
                f"UAV {peer_agent_id} is not a peer of UAV {self._owner_agent_id}"
            )


__all__ = ["PeerKnowledgeState", "PeerObservation", "PeerStateStore"]
