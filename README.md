# EUDIS Swarm

EUDIS Swarm is an early-stage resilience experiment for the EUDIS Defence
Hackathon 2026 (Autumn Edition), in the swarm coordination challenge area. The
eventual goal is a communications-aware autonomous UAV swarm. The repository
contains incremental, deterministic simulation prototypes:

- **Prototype 0.1** detects one fail-stop UAV, releases its unfinished task,
  reallocates that task, and finishes the mission without human intervention.
- **Prototype 0.2A** adds an explicit, time-varying communications graph and a
  deterministic communication outage/restoration experiment without changing
  physical failure recovery or task decisions.
- **Prototype 0.2A.1** hardens configuration, logical-time, mission-lifecycle,
  invariant testing, and automated quality checks without adding swarm behavior.
- **Prototype 0.2B** uses active one-hop graph links to deliver immutable state
  snapshots into receiver-local `UNKNOWN` / `FRESH` / `STALE` peer views.
- **Prototype 0.3A** adds an optional connectivity-aware greedy allocator that
  evaluates task endpoints using each candidate UAV's `FRESH` peer snapshots.

> **Simulation only:** these prototypes are algorithmic, two-dimensional
> point-mass simulations. The distance threshold and instantaneous one-hop state
> delivery are abstract models, not RF or network-protocol results. Nothing
> models real flight dynamics, radios, network transport, autopilots, sensors,
> collision avoidance,
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
| Receiver-local peer knowledge | `UNKNOWN`, `FRESH`, or `STALE` independently for each remote UAV |

Topology itself still does not use `STALE`; Prototype 0.2B models that separately
as receiver-local information freshness. A UAV in a disconnected component of two or more UAVs remains
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

## What Prototype 0.2B adds

At each existing heartbeat publication time, every responsive UAV produces an
immutable state snapshot. The one-hop transport attempts to deliver that snapshot
to each other UAV and succeeds only when their direct `CommunicationGraph` link
is active. There is no routing, forwarding, retry, queue, latency, or stochastic
loss model.

Each receiver owns an independent peer-state store. An observation is `UNKNOWN`
before first delivery, `FRESH` while its strict age is at most
`peer_state_stale_after`, and `STALE` when:

```text
current_time - received_at > peer_state_stale_after
```

Physical ground truth, graph reachability, and peer-information freshness remain
separate. `STALE`, `UNKNOWN`, and `UNREACHABLE` never imply `FAILED`. Peer views
do not release or reassign tasks in 0.2B. The original failure detector remains
a transitional centralized mission mechanism and does not consume peer stores.

See [the Prototype 0.2B technical design](docs/prototype_0_2b.md) for the transport
contract, deterministic outage trace, tests, metrics, and deferred work.

## What Prototype 0.3A adds

The nearest-distance `TaskAllocator` remains the default experimental baseline.
Selecting `--allocation-policy connectivity` uses a second greedy policy. For
each candidate UAV/task pair it predicts direct endpoint connectivity from that
UAV's own `FRESH` peer observations and minimizes:

```text
(predicted_isolation, -predicted_peer_degree, distance, agent_id, task_id)
```

`STALE` and `UNKNOWN` peers contribute no predicted links. The allocator never
reads another UAV's authoritative current position for this prediction. If all
peer knowledge is initially unknown, every predicted degree is zero and the
score naturally falls back to the existing distance and ID ordering.

The policy affects only new task proposals. `Mission` remains the centralized
authoritative owner of assignment, and active work is never preempted. See
[the Prototype 0.3A technical design](docs/prototype_0_3a.md) for the exact
policy, knowledge boundary, measured comparison, and limitations.

## Architecture

| Module | Responsibility |
| --- | --- |
| `agent.py` | Physical UAV state, constant-speed 2D movement, and direct heartbeat generation |
| `task.py` | Task ownership and `UNASSIGNED` / `ASSIGNED` / `COMPLETED` states |
| `task_allocator.py` | Distance baseline, minimal policy protocol, and local-knowledge connectivity allocator |
| `failure_manager.py` | Latest-heartbeat storage and strict physical-failure timeout detection |
| `communication.py` | Abstract links, communication state, dynamic graph topology, and graph transitions |
| `messaging.py` | Instantaneous one-hop delivery of immutable snapshots across active direct links |
| `peer_state.py` | Receiver-local last-known observations and strict freshness transitions |
| `mission.py` | Authoritative task/agent transitions, physical recovery, events, and invariants |
| `simulation.py` | Scenario generation, logical clock, movement, fault schedules, graph updates, and CLI |
| `metrics.py` | Separate physical-mission and network metrics derived from transitions |
| `config.py` | Validated physical and communication configuration |
| `validation.py` | Shared finite, monotonic logical-time and identifier validation |
| `visualization.py` | Optional final matplotlib rendering, isolated from the headless core |

Allocators only propose assignments; `Mission` applies them and checks
bidirectional ownership. The optional 0.3A policy reads receiver-local peer
stores, but neither allocator mutates agents or tasks directly.

## Requirements and installation

- Python 3.11 or newer
- `pytest`, coverage, Ruff, Pyright, and build tooling in the `dev` extra
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

### Prototype 0.3A policy comparison

These commands use identical mission inputs and differ only by allocation
policy:

```console
python -m eudis_swarm.simulation --seed 1 --failure-time 100 --communication-range 35 --allocation-policy distance
python -m eudis_swarm.simulation --seed 1 --failure-time 100 --communication-range 35 --allocation-policy connectivity
```

Both policies make the same first 11 assignments. At `t=4.50 s`, the distance
baseline selects UAV 2 -> Task 2 at `11.18` distance units. UAV 2's local peer
store predicts zero reliable links there. The connectivity policy instead
selects UAV 2 -> Task 3 at `24.20` units because its `FRESH` snapshots predict
one direct peer link.

| Result | Distance | Connectivity |
| --- | ---: | ---: |
| Tasks completed | `20 / 20` | `20 / 20` |
| Mission duration | `12.00 s` | `17.25 s` |
| Isolation events | `4` | `1` |
| Minimum links | `0` | `0` |
| Maximum components | `4` | `4` |
| Degraded duration | `8.25 s` | `8.25 s` |
| Link losses/restorations | `4 / 5` | `5 / 8` |

This is a measured tradeoff: fewer isolation transitions and more travel/mission
time. It does not establish global optimality, and several network metrics are
unchanged or mixed.

### Prototype 0.2A communications demonstration

Use this command to postpone physical failure beyond the seeded mission and
isolate the otherwise healthy UAV 2 from `t=4.00 s` through `t=8.00 s`:

```console
python -m eudis_swarm.simulation --failure-time 100 --communication-range 130 --comm-fault-agent 2 --comm-fault-start 4 --comm-fault-end 8 --peer-state-stale-after 2.5
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
| Peer messages attempted/delivered/undelivered | `144 / 120 / 24` |
| Peer stale/refresh transitions | `6 / 6` |

UAV 2 completes Task 19 at `t=4.00 s`, Task 15 at `t=4.75 s`, and
Task 20 at `t=7.50 s` while its communication is blocked. It remains responsive,
is never declared `FAILED`, and causes no task release. At `t=8.00 s`, its three
links return and the graph reconnects.

The last pre-fault snapshots involving UAV 2 arrive at `t=3.00 s`. At `t=5.75 s`,
strict freshness expiry makes the three other UAVs' views of UAV 2 stale and also
makes UAV 2's three remote peer views stale. Restoration occurs before the
`t=8.00 s` delivery batch, so all six observations refresh immediately. None of
these information transitions changes physical status or task ownership.

### Communication CLI options

| Argument | Default | Meaning |
| --- | ---: | --- |
| `--communication-range` | `130.0` | Inclusive Euclidean link threshold |
| `--comm-fault-agent` | omitted | UAV whose incident links are blocked; omission disables the communication fault |
| `--comm-fault-start` | `4.0` | Logical time at which blocking starts |
| `--comm-fault-end` | `8.0` | Logical time at which blocking ends; must be later than the start |
| `--peer-state-stale-after` | `2.5` | Strict receiver-local snapshot freshness threshold |
| `--allocation-policy` | `distance` | `distance` baseline or `connectivity` local-knowledge policy |

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

Run the complete local quality baseline with:

```console
python -m ruff check .
python -m ruff format --check .
python -m pyright
python -m pytest --cov=eudis_swarm --cov-report=term-missing
python -m build
```

Coverage has an initial 85% branch-aware threshold. GitHub Actions runs the
same lint, formatting, type, test, coverage, build, and installed-CLI checks on
Python 3.11 and 3.13 for pushes and pull requests involving `main`.

Configuration rejects booleans where integer counts or UAV IDs are required,
non-finite numeric values, invalid ranges, and illogical fault windows. Mission
operations are legal only while the lifecycle is `RUNNING`, and timestamps must
remain finite and monotonic. Tasks already satisfied at mission start complete
at `t=0.00 s` without an artificial movement tick.

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
  recovery sequence;
- proof that only fresh delivered peer positions affect connectivity scores;
- proof that authoritative peer movement is invisible until a new snapshot is
  delivered; and
- deterministic baseline-versus-connectivity decision and outcome comparison.

### Six-agent smoke scenario

```console
python -m eudis_swarm.simulation --agents 6 --tasks 30 --seed 7 --failure-agent 4 --failure-time 100 --communication-range 130 --comm-fault-agent 6 --comm-fault-start 3 --comm-fault-end 6 --peer-state-stale-after 2.5
```

The deterministic smoke run completes `30 / 30` tasks at `t=12.00 s`, with no
physical failure or orphaned work. It begins with 15 links, falls to 10 while
UAV 6 is isolated, loses and restores five links, remains degraded for 3.00
seconds, and ends connected. UAV 6 completes Tasks 23, 20, and 27 during its
communication outage. Ten directed peer observations become stale at `t=4.75 s`
and refresh at `t=6.00 s`; no false physical failure is introduced.

## Network and peer-state metrics

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

The separate `PEER STATE (PROTOTYPE 0.2B)` block reports directed delivery
attempts, successful and link-gated undelivered messages, stale and refresh
transitions, and the maximum number of simultaneous stale receiver-local
observations. It does not feed mission decisions.

The `ALLOCATION (PROTOTYPE 0.3A)` block reports the selected policy,
connectivity-aware assignment count, assignments predicting isolation, and mean
and minimum predicted fresh-peer degree. Applied decision records retain the
timestamp, selected IDs, distance, policy, degree, and isolation prediction.

## Current limitations

- The link model is only an inclusive Euclidean distance threshold plus an
  explicit per-UAV block. It is not RF propagation and does not calculate RSSI,
  SINR, interference, antenna effects, terrain, or weather.
- Peer snapshots use instantaneous one-hop in-process delivery. There are no
  queues, retries, forwarding, multi-hop routing, latency, jitter, bandwidth, or
  stochastic packet loss.
- Peer knowledge affects only new allocations when the connectivity policy is
  explicitly selected. It does not affect path planning, movement, existing
  task ownership, or physical failure recovery.
- Physical fail-stop recovery still uses the transitional centralized heartbeat
  manager; only the new receiver-local peer knowledge is graph-mediated.
- The graph is centralized, recomputed from authoritative positions, and has no
  ground-station or coordinator-reachability anchor. In this prototype,
  `UNREACHABLE` specifically means isolated from every peer.
- All components execute in one Python process. There is no distributed
  consensus or peer-to-peer protocol.
- Agents remain point masses without aircraft dynamics, vehicle constraints,
  terrain, collision avoidance, or energy limits.
- Tasks remain independent points. Both policies are centralized greedy pairing,
  not joint trajectory prediction or global optimization.
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
- **Prototype 0.2B — implemented:** active direct links mediate immutable peer
  state delivery and receiver-local freshness, without adaptive behavior.
- **Prototype 0.3A — implemented:** optional connectivity-aware allocation from
  receiver-local fresh peer snapshots.
- **Later Prototype 0.3 milestones — planned:** communications-aware path
  planning, relay, and distributed allocation experiments.
- **Prototype 0.4 — planned:** QUBO / quantum-simulated optimization experiments.
- **Prototype 0.5 — planned:** distributed ROS 2 implementation.
- **Prototype 0.6 — planned:** ArduPilot multi-UAV SITL integration.
- **Prototype 1.0 — planned:** EUDIS demonstration baseline.
