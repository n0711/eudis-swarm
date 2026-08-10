"""Abstract distance-based communication topology for Prototype 0.2A.

This module models potential peer-to-peer links, not RF propagation or packet
delivery.  A link is available when its endpoints are within the configured
Euclidean range and neither endpoint is explicitly blocked by a communication
fault.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import combinations
from math import hypot, isfinite
from numbers import Real
from typing import Iterable, Mapping

from .agent import Position


class CommunicationState(str, Enum):
    """Whether a UAV currently has at least one available peer link."""

    REACHABLE = "REACHABLE"
    UNREACHABLE = "UNREACHABLE"


@dataclass(frozen=True, slots=True)
class CommunicationLink:
    """One canonical undirected UAV pair and its current link state."""

    source_agent_id: int
    destination_agent_id: int
    distance: float
    available: bool

    def __post_init__(self) -> None:
        if self.source_agent_id <= 0 or self.destination_agent_id <= 0:
            raise ValueError("communication link UAV IDs must be positive")
        if self.source_agent_id >= self.destination_agent_id:
            raise ValueError(
                "communication link endpoints must use increasing canonical order"
            )
        if not isfinite(self.distance) or self.distance < 0.0:
            raise ValueError("communication link distance must be finite and non-negative")
        if not isinstance(self.available, bool):
            raise TypeError("communication link availability must be boolean")

    @property
    def key(self) -> tuple[int, int]:
        """Return the canonical pair key for deterministic comparisons."""

        return (self.source_agent_id, self.destination_agent_id)


@dataclass(frozen=True, slots=True)
class CommunicationUpdate:
    """Deterministic topology differences produced by one graph update."""

    is_initial: bool
    lost_links: tuple[CommunicationLink, ...]
    restored_links: tuple[CommunicationLink, ...]
    newly_isolated_agent_ids: tuple[int, ...]
    newly_reachable_agent_ids: tuple[int, ...]
    previous_component_count: int | None
    component_count: int
    was_fully_connected: bool | None
    is_fully_connected: bool

    @property
    def network_partitioned(self) -> bool:
        """Whether this update changed a connected graph into a partition."""

        return self.was_fully_connected is True and not self.is_fully_connected

    @property
    def network_reconnected(self) -> bool:
        """Whether this update restored one fully connected component."""

        return self.was_fully_connected is False and self.is_fully_connected


class CommunicationGraph:
    """A fixed-vertex, time-varying undirected communication graph.

    The first :meth:`update` establishes the baseline topology.  It deliberately
    reports no transitions, so initial links are not counted as restorations and
    initially isolated UAVs are not counted as new isolation events.
    """

    def __init__(
        self, agent_ids: Iterable[int], communication_range: float
    ) -> None:
        supplied_ids = tuple(agent_ids)
        if not supplied_ids:
            raise ValueError("communication graph requires at least one UAV")
        if any(
            not isinstance(agent_id, int)
            or isinstance(agent_id, bool)
            or agent_id <= 0
            for agent_id in supplied_ids
        ):
            raise ValueError("communication graph UAV IDs must be positive integers")
        if len(set(supplied_ids)) != len(supplied_ids):
            raise ValueError("communication graph UAV IDs must be unique")
        if (
            not isinstance(communication_range, Real)
            or isinstance(communication_range, bool)
            or not isfinite(communication_range)
            or communication_range <= 0.0
        ):
            raise ValueError("communication_range must be finite and greater than zero")

        self._agent_ids = tuple(sorted(supplied_ids))
        self._agent_id_set = frozenset(self._agent_ids)
        self._communication_range = float(communication_range)
        self._blocked_agent_ids: frozenset[int] = frozenset()
        self._links: dict[tuple[int, int], CommunicationLink] = {}
        self._neighbors: dict[int, frozenset[int]] = {}
        self._components: tuple[frozenset[int], ...] = ()
        self._isolated_agent_ids: frozenset[int] = frozenset()
        self._initialized = False

    @property
    def agent_ids(self) -> tuple[int, ...]:
        return self._agent_ids

    @property
    def communication_range(self) -> float:
        return self._communication_range

    @property
    def blocked_agent_ids(self) -> frozenset[int]:
        return self._blocked_agent_ids

    @property
    def initialized(self) -> bool:
        return self._initialized

    @property
    def links(self) -> tuple[CommunicationLink, ...]:
        """Return all canonical UAV pairs, including unavailable links."""

        self._require_initialized()
        return tuple(self._links[key] for key in sorted(self._links))

    @property
    def active_links(self) -> tuple[CommunicationLink, ...]:
        """Return only currently available links in canonical order."""

        return tuple(link for link in self.links if link.available)

    @property
    def link_count(self) -> int:
        return len(self.active_links)

    def link_between(self, left_agent_id: int, right_agent_id: int) -> CommunicationLink:
        """Return the current canonical pair record for two distinct UAVs."""

        self._require_initialized()
        self._require_known_agent(left_agent_id)
        self._require_known_agent(right_agent_id)
        if left_agent_id == right_agent_id:
            raise ValueError("a UAV does not have a communication link to itself")
        key = tuple(sorted((left_agent_id, right_agent_id)))
        return self._links[key]

    def neighbors(self, agent_id: int) -> frozenset[int]:
        """Return the currently available one-hop peers for a UAV."""

        self._require_initialized()
        self._require_known_agent(agent_id)
        return self._neighbors[agent_id]

    @property
    def connected_components(self) -> tuple[frozenset[int], ...]:
        self._require_initialized()
        return self._components

    @property
    def isolated_agent_ids(self) -> frozenset[int]:
        self._require_initialized()
        return self._isolated_agent_ids

    @property
    def is_fully_connected(self) -> bool:
        self._require_initialized()
        return len(self._components) == 1

    def communication_state(self, agent_id: int) -> CommunicationState:
        """Report peer reachability independently of physical UAV state."""

        self._require_initialized()
        self._require_known_agent(agent_id)
        if agent_id in self._isolated_agent_ids:
            return CommunicationState.UNREACHABLE
        return CommunicationState.REACHABLE

    def update(
        self,
        positions: Mapping[int, Position],
        *,
        blocked_agent_ids: Iterable[int] = (),
    ) -> CommunicationUpdate:
        """Recompute all links and return changes from the previous topology."""

        self._validate_positions(positions)
        blocked = frozenset(blocked_agent_ids)
        unknown_blocked = blocked - self._agent_id_set
        if unknown_blocked:
            raise ValueError(
                "blocked_agent_ids contains unknown UAV IDs: "
                f"{sorted(unknown_blocked)}"
            )

        new_links: dict[tuple[int, int], CommunicationLink] = {}
        for source_agent_id, destination_agent_id in combinations(self._agent_ids, 2):
            source = positions[source_agent_id]
            destination = positions[destination_agent_id]
            distance = hypot(
                destination[0] - source[0],
                destination[1] - source[1],
            )
            available = (
                distance <= self._communication_range
                and source_agent_id not in blocked
                and destination_agent_id not in blocked
            )
            link = CommunicationLink(
                source_agent_id=source_agent_id,
                destination_agent_id=destination_agent_id,
                distance=distance,
                available=available,
            )
            new_links[link.key] = link

        new_active_keys = {
            key for key, link in new_links.items() if link.available
        }
        new_neighbors, new_components = self._build_topology(new_active_keys)
        new_isolated = frozenset(
            agent_id
            for agent_id, peers in new_neighbors.items()
            if not peers
        )
        new_fully_connected = len(new_components) == 1

        if self._initialized:
            previous_active_keys = {
                key for key, link in self._links.items() if link.available
            }
            lost_links = tuple(
                new_links[key]
                for key in sorted(previous_active_keys - new_active_keys)
            )
            restored_links = tuple(
                new_links[key]
                for key in sorted(new_active_keys - previous_active_keys)
            )
            newly_isolated = tuple(sorted(new_isolated - self._isolated_agent_ids))
            newly_reachable = tuple(sorted(self._isolated_agent_ids - new_isolated))
            previous_component_count: int | None = len(self._components)
            was_fully_connected: bool | None = len(self._components) == 1
            is_initial = False
        else:
            lost_links = ()
            restored_links = ()
            newly_isolated = ()
            newly_reachable = ()
            previous_component_count = None
            was_fully_connected = None
            is_initial = True

        self._blocked_agent_ids = blocked
        self._links = new_links
        self._neighbors = new_neighbors
        self._components = new_components
        self._isolated_agent_ids = new_isolated
        self._initialized = True

        return CommunicationUpdate(
            is_initial=is_initial,
            lost_links=lost_links,
            restored_links=restored_links,
            newly_isolated_agent_ids=newly_isolated,
            newly_reachable_agent_ids=newly_reachable,
            previous_component_count=previous_component_count,
            component_count=len(new_components),
            was_fully_connected=was_fully_connected,
            is_fully_connected=new_fully_connected,
        )

    def _build_topology(
        self, active_keys: set[tuple[int, int]]
    ) -> tuple[dict[int, frozenset[int]], tuple[frozenset[int], ...]]:
        mutable_neighbors: dict[int, set[int]] = {
            agent_id: set() for agent_id in self._agent_ids
        }
        for source_agent_id, destination_agent_id in active_keys:
            mutable_neighbors[source_agent_id].add(destination_agent_id)
            mutable_neighbors[destination_agent_id].add(source_agent_id)

        remaining = set(self._agent_ids)
        components: list[frozenset[int]] = []
        while remaining:
            root = min(remaining)
            stack = [root]
            component: set[int] = set()
            while stack:
                agent_id = stack.pop()
                if agent_id in component:
                    continue
                component.add(agent_id)
                stack.extend(
                    sorted(mutable_neighbors[agent_id] - component, reverse=True)
                )
            remaining -= component
            components.append(frozenset(component))

        neighbors = {
            agent_id: frozenset(peers)
            for agent_id, peers in mutable_neighbors.items()
        }
        return neighbors, tuple(components)

    def _validate_positions(self, positions: Mapping[int, Position]) -> None:
        supplied_ids = frozenset(positions)
        if supplied_ids != self._agent_id_set:
            missing = sorted(self._agent_id_set - supplied_ids)
            extra = sorted(supplied_ids - self._agent_id_set, key=repr)
            raise ValueError(
                "positions must contain exactly the graph UAV IDs; "
                f"missing={missing}, extra={extra}"
            )

        for agent_id in self._agent_ids:
            position = positions[agent_id]
            if len(position) != 2 or any(
                not isinstance(coordinate, Real)
                or isinstance(coordinate, bool)
                or not isfinite(coordinate)
                for coordinate in position
            ):
                raise ValueError(
                    f"position for UAV {agent_id} must contain two finite coordinates"
                )

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("communication graph has not been updated")

    def _require_known_agent(self, agent_id: int) -> None:
        if agent_id not in self._agent_id_set:
            raise KeyError(f"unknown UAV ID {agent_id}")


__all__ = [
    "CommunicationGraph",
    "CommunicationLink",
    "CommunicationState",
    "CommunicationUpdate",
]
