# EUDIS Swarm

EUDIS Swarm is an early-stage resilience experiment for the EUDIS Defence
Hackathon 2026 (Autumn Edition), in the swarm coordination challenge area. The
eventual goal is a communications-aware autonomous UAV swarm. The repository
now contains two incremental, deterministic simulation prototypes:

- **Prototype 0.1** detects one fail-stop UAV, releases its unfinished task,
  reallocates that task, and finishes the mission without human intervention.
- **Prototype 0.2A** adds an explicit, time-varying communications graph and a
  deterministic communication outage/restoration experiment without changing
  physical failure recovery or task decisions.

> **Simulation only:** these prototypes are algorithmic, two-dimensional
> point-mass simulations. The Prototype 0.2A distance threshold is an abstract
> topology model, not an RF propagation result. Nothing here models real flight
> dynamics, radios, network transport, autopilots, sensors, collision avoidance,
> or safety-critical operation, and it must not be interpreted as flight-ready
> software.

## What Prototype 0.1 still demonstrates

The original scenario remains intact. Four simulated UAV agents service 20
exploration tasks in a 100 x 100 mission area. Agents receive tasks using a
deterministic nearest-distance baseline and move toward them at constant speed.
They publish periodic in-process heartbeats containing position, physical
state, current task, and logical timestamp.

At `t=4.00 s`, UAV 2 is made silent and immobile. Once its last heartbeat is
strictly older than the configured timeout, the coordinator declares it
`FAILED`, releases Task 19, later assigns that task to UAV 1, and completes all
20 tasks at `t=17.25 s`.

See [the Prototype 0.1 technical design](docs/prototype_0_1.md) for the preserved
physical state model, scheduler, failure recovery sequence, and original test
coverage.

## What Prototype 0.2A adds

Prototype 0.2A derives an undirected graph from current UAV positions:

```text
G(t) = (V, E(t))

V    = every configured UAV ID
E(t) = every currently available undirected UAV pair
```

For a canonical pair `i < j`, its Euclidean distance is:

```text
d(i, j) = sqrt((x_j - x_i)^2 + (y_j - y_i)^2)
```

The pair is available exactly when `d(i, j) <= communication_range` and neither
endpoint is blocked by the explicit communication fault. The graph reports all
pair records, active links, neighbors, connected components, isolated UAVs, and
whether the network is fully connected. Updates compare consecutive snapshots
and emit only meaningful link, isolation, partition, and reconnection
transitions.

Physical and communication states are deliberately independent:

| Dimension | States and meaning |
| --- | --- |
| Physical agent state | `IDLE`, `ACTIVE`, or `FAILED` |
| Communication state | `REACHABLE` when the UAV has at least one active peer link; `UNREACHABLE` when it is isolated |

`STALE` is not modeled because Prototype 0.2A has no packet-freshness or
delivery model. A UAV in a disconnected component of two or more UAVs remains
reachable to peers in that component even though the whole network is
partitioned.

Most importantly:

```text
COMMUNICATION LOSS != UAV FAILURE
```

A blocked UAV remains physically responsive, continues moving and completing
tasks, keeps sending direct in-process heartbeats, and retains its work. The
communications graph is observational in 0.2A: it does not affect heartbeat
delivery, failure detection, allocation, or path planning. Those boundaries
prevent an outage from being mistaken for a physical failure.

See [the Prototype 0.2A technical design](docs/prototype_0_2a.md) for the exact
graph contract, timing semantics, metrics, deterministic trace, and limitations.

## Architecture

| Module | Responsibility |
| --- | --- |
| `agent.py` | Physical UAV state, constant-speed 2D movement, and direct heartbeat generation |
| `task.py` | Task ownership and `UNASSIGNED` / `ASSIGNED` / `COMPLETED` states |
| `task_allocator.py` | Replaceable greedy nearest-pair allocation policy |
| `failure_manager.py` | Latest-heartbeat storage and strict physical-failure timeout detection |
| `communication.py` | Abstract links, communication state, dynamic graph topology, and graph transitions |
| `mission.py` | Authoritative task/agent transitions, physical recovery, events, and invariants |
| `simulation.py` | Scenario generation, logical clock, movement, fault schedules, graph updates, and CLI |
| `metrics.py` | Separate physical-mission and network metrics derived from transitions |
| `config.py` | Validated physical and communication configuration |
| `visualization.py` | Optional final matplotlib rendering, isolated from the headless core |

The allocator still proposes assignments using only task distance and physical
availability. `Mission` applies them and checks bidirectional ownership. The
communication graph neither mutates agents/tasks nor participates in that
policy in Prototype 0.2A.

## Requirements and installation

- Python 3.11 or newer
- `pytest` only for development/tests
- `matplotlib` only for the optional visualisation

The headless simulator has no third-party runtime dependencies. From the
repository root, create an isolated environment and install the package with its
test dependency.

PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

POSIX shell:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

To include the optional visualisation dependency, install both extras:

```console
python -m pip install -e ".[dev,visualization]"
```

## Run the prototypes

The original command remains the deterministic Prototype 0.1 physical-failure
regression. Communication fault injection is disabled by default, so this
command preserves the original recovery path:

```console
python -m eudis_swarm.simulation
```

The installed console entry point is equivalent:

```console
eudis-swarm
```

### Prototype 0.2A communications demonstration

Use this command to postpone physical failure beyond the seeded mission and
isolate the otherwise healthy UAV 2 from `t=4.00 s` through `t=8.00 s`:

```console
python -m eudis_swarm.simulation --failure-time 100 --communication-range 130 --comm-fault-agent 2 --comm-fault-start 4 --comm-fault-end 8
```

The 130-unit range exceeds the initial corner-layout diagonal of approximately
127.28 units and keeps all six pairs active throughout this seeded trace. The
explicit fault removes only UAV 2's three incident links, so injected
degradation is easy to distinguish from movement across the distance threshold.

Expected deterministic result:

| Observation | Expected value |
| --- | ---: |
| Tasks completed | `20 / 20` |
| Mission duration | `11.75 s` |
| Physically failed agents | `0` |
| Orphaned/reassigned tasks | `0 / 0` |
| Initial/minimum communication links | `6 / 3` |
| Maximum connected components | `2` |
| Isolation events | `1` |
| Link losses/restorations | `3 / 3` |
| Communication-degraded duration | `4.00 s` |
| Healthy-but-unreachable events | `1` |
| Network ended connected | `YES` |

UAV 2 completes Task 19 at `t=4.00 s`, Task 15 at `t=4.75 s`, and
Task 20 at `t=7.50 s` while its communication is blocked. It remains responsive,
is never declared `FAILED`, and causes no task release. At `t=8.00 s`, its three
links return and the graph reconnects.

### Communication CLI options

| Argument | Default | Meaning |
| --- | ---: | --- |
| `--communication-range` | `130.0` | Inclusive Euclidean link threshold |
| `--comm-fault-agent` | omitted | UAV whose incident links are blocked; omission disables the communication fault |
| `--comm-fault-start` | `4.0` | Logical time at which blocking starts |
| `--comm-fault-end` | `8.0` | Logical time at which blocking ends; must be later than the start |

The existing `--agents`, `--tasks`, `--seed`, `--failure-agent`,
`--failure-time`, `--failure-timeout`, `--visualize`, and `--log-level` options
remain available. View the authoritative help with:

```console
python -m eudis_swarm.simulation --help
```

`--visualize` requires the `visualization` extra. The process exits with status
0 when the mission completes, 1 on simulated mission timeout, and 2 for a
command-line error or unavailable requested visualization.

## Preserved Prototype 0.1 recovery

With the default seed, UAV 2 initially owns Task 19. Physical failure is
injected at `t=4.00 s`; because injection precedes that tick's heartbeat, its
last heartbeat remains `t=3.00 s`. Timeout detection uses the strict rule:

```text
now - last_heartbeat > 2.5 s
```

Equality at `t=5.50 s` does not fire. Detection and Task 19 release occur at
`t=5.75 s`. UAV 1 receives the task at `t=10.75 s`, and all 20 tasks complete at
`t=17.25 s`. Communication observations do not alter those values.

## Run the tests

```console
python -m pytest
```

For individual test names:

```console
python -m pytest -v
```

Coverage includes the preserved allocation and fail-stop recovery tests plus:

- inclusive distance-based link creation and rejection outside range;
- neighbor sets, components, isolation, and connectivity;
- deterministic loss/restoration when positions cross the range boundary;
- one-shot transition reporting without repeated steady-state logs;
- exact communication fault scheduling and restoration;
- proof that an unreachable healthy UAV continues moving and working;
- proof that communication loss does not release tasks or trigger physical
  failure recovery; and
- exact regression of the original `4.00 -> 5.75 -> 10.75 -> 17.25` physical
  recovery sequence.

### Six-agent smoke scenario

```console
python -m eudis_swarm.simulation --agents 6 --tasks 30 --seed 7 --failure-agent 4 --failure-time 100 --communication-range 130 --comm-fault-agent 6 --comm-fault-start 3 --comm-fault-end 6
```

The deterministic smoke run completes `30 / 30` tasks at `t=12.00 s`, with no
physical failure or orphaned work. It begins with 15 links, falls to 10 while
UAV 6 is isolated, loses and restores five links, remains degraded for 3.00
seconds, and ends connected. UAV 6 completes Tasks 23, 20, and 27 during its
communication outage.

## Network metrics

The physical mission summary remains separate from a Prototype 0.2A network
block containing:

- initial and minimum active-link counts;
- maximum connected-component count;
- isolation, link-loss, and link-restoration event counts;
- total logical time for which the network is not fully connected;
- whether the final graph is connected; and
- transitions in which a physically healthy UAV becomes unreachable.

Initial links are a baseline, not restoration events. A sustained loss or
isolation is counted once when the state changes, not once per simulation tick.
Physical `Agents failed` and network `Healthy but unreachable UAV events` are
never merged.

## Current limitations

- The link model is only an inclusive Euclidean distance threshold plus an
  explicit per-UAV block. It is not RF propagation and does not calculate RSSI,
  SINR, interference, antenna effects, terrain, or weather.
- Heartbeats are still direct in-process method calls. Links carry no packets,
  so there is no delivery, loss, latency, jitter, bandwidth, routing, or stale
  communication state.
- Communication state is observational. Allocation, path planning, movement,
  task ownership, and failure detection do not consume graph state.
- The graph is centralized, recomputed from authoritative positions, and has no
  ground-station or coordinator-reachability anchor. In this prototype,
  `UNREACHABLE` specifically means isolated from every peer.
- All components execute in one Python process. There is no distributed
  consensus or peer-to-peer protocol.
- Agents remain point masses without aircraft dynamics, vehicle constraints,
  terrain, collision avoidance, or energy limits.
- Tasks remain independent points and allocation remains greedy Euclidean
  distance rather than global route optimization.
- Physical failure injection still models one fail-stop UAV; there is no
  rejoin, intermittent, Byzantine, or simultaneous-failure model.
- The optional visualization is a final debugging view, not a live dashboard or
  control interface.
- There is no ROS 2, MAVLink, ArduPilot, PX4, Gazebo, AirSim, SLAM, computer
  vision, database, web application, or real-time guarantee.

## Roadmap

- **Prototype 0.1 — implemented:** basic swarm simulation and fail-stop task
  recovery.
- **Prototype 0.2A — implemented:** explicit dynamic communication graph,
  abstract link degradation, partition, isolation, restoration, and metrics.
- **Prototype 0.2B — not implemented:** route heartbeat/message delivery through
  links and introduce communication-aware decisions and behavior.
- **Prototype 0.3 — planned:** communications-aware task allocation and path
  planning experiments.
- **Prototype 0.4 — planned:** QUBO / quantum-simulated optimization experiments.
- **Prototype 0.5 — planned:** distributed ROS 2 implementation.
- **Prototype 0.6 — planned:** ArduPilot multi-UAV SITL integration.
- **Prototype 1.0 — planned:** EUDIS demonstration baseline.
