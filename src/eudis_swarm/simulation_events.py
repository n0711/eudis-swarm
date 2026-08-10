"""Structured communication and peer-knowledge events shared with trace tooling."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CommunicationEventKind(str, Enum):
    """Observable communication transitions kept separate from mission events."""

    NETWORK_INITIALIZED = "NETWORK_INITIALIZED"
    FAULT_STARTED = "FAULT_STARTED"
    FAULT_ENDED = "FAULT_ENDED"
    LINK_LOST = "LINK_LOST"
    LINK_RESTORED = "LINK_RESTORED"
    NETWORK_PARTITIONED = "NETWORK_PARTITIONED"
    NETWORK_RECONNECTED = "NETWORK_RECONNECTED"
    AGENT_UNREACHABLE = "AGENT_UNREACHABLE"
    AGENT_REACHABLE = "AGENT_REACHABLE"


@dataclass(frozen=True, slots=True)
class CommunicationEvent:
    kind: CommunicationEventKind
    timestamp: float
    agent_id: int | None = None
    peer_agent_id: int | None = None
    component_count: int | None = None


class PeerStateEventKind(str, Enum):
    """Meaningful receiver-local peer-knowledge transitions."""

    STALE = "STALE"
    REFRESHED = "REFRESHED"


@dataclass(frozen=True, slots=True)
class PeerStateEvent:
    kind: PeerStateEventKind
    timestamp: float
    observer_agent_id: int
    peer_agent_id: int


__all__ = [
    "CommunicationEvent",
    "CommunicationEventKind",
    "PeerStateEvent",
    "PeerStateEventKind",
]
