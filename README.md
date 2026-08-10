# EUDIS Swarm

EUDIS Swarm is an early-stage resilience experiment for the EUDIS Defence
Hackathon 2026 (Autumn Edition), in the swarm coordination challenge area. The
eventual goal is a communications-aware autonomous UAV swarm. Prototype 0.1 is
deliberately much smaller: it proves, in a deterministic Python simulation,
that a swarm can detect one silent agent, recover its unfinished work, and
finish the mission without human intervention.

> **Simulation only:** Prototype 0.1 is an algorithmic, two-dimensional
> point-mass simulation. It does not model real flight dynamics, radios,
> network transport, autopilots, sensors, collision avoidance, or safety-critical
> operation. It must not be interpreted as flight-ready software.

## What Prototype 0.1 demonstrates

The default scenario runs four simulated UAV agents against 20 exploration
tasks in a 100 x 100 mission area. Agents receive tasks using a deterministic
nearest-distance baseline and move toward them at constant speed. They publish
periodic in-process heartbeats containing their position, state, current task,
and timestamp.

At 4.00 seconds of simulated time, UAV 2 is made silent and immobile. Once its
last heartbeat is strictly older than the configured timeout, the coordinator:

1. declares UAV 2 failed;
2. releases its unfinished task;
3. excludes the failed UAV from future allocation;
4. reallocates the orphaned task to an available healthy UAV; and
5. lets the surviving agents complete every task.

The seed, time step, heartbeat interval, timeout, movement speed, and task
completion tolerance are fixed by configuration, so the default demonstration
is reproducible.

## Architecture

The package keeps policy, state transitions, and simulation mechanics separate:

| Module | Responsibility |
| --- | --- |
| `agent.py` | UAV state, constant-speed 2D movement, and heartbeat generation |
| `task.py` | Task ownership and `UNASSIGNED` / `ASSIGNED` / `COMPLETED` states |
| `task_allocator.py` | Replaceable greedy nearest-pair allocation policy |
| `failure_manager.py` | Latest-heartbeat storage and strict timeout detection |
| `mission.py` | Authoritative task/agent transitions, recovery, events, and invariants |
| `simulation.py` | Deterministic scenario generation, logical clock, CLI, and run loop |
| `metrics.py` | Metrics derived from recorded mission events |
| `config.py` | Validated simulation defaults |
| `visualization.py` | Optional matplotlib rendering, isolated from the headless core |

The allocator proposes assignments without mutating mission state. `Mission`
applies them and checks bidirectional ownership, which keeps the simple baseline
replaceable by later communications-aware or QUBO policies.

See [docs/prototype_0_1.md](docs/prototype_0_1.md) for the detailed state model,
timing semantics, recovery sequence, configuration, and test coverage.

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

## Run the prototype

After installation, run the default failure/recovery demonstration:

```console
python -m eudis_swarm.simulation
```

The installed console entry point is equivalent:

```console
eudis-swarm
```

Useful options are:

```console
python -m eudis_swarm.simulation --help
python -m eudis_swarm.simulation --agents 6 --tasks 30 --seed 7 --failure-agent 4 --failure-time 5 --failure-timeout 3
python -m eudis_swarm.simulation --visualize
```

`--visualize` displays the final task states, UAV states, and recorded paths. It
requires the `visualization` extra; the normal command remains fully headless.

The process exits with status 0 when the mission completes, 1 when the simulated
mission reaches its time limit without completing, and 2 for command-line usage
errors or a requested visualisation whose dependency is unavailable.

## Expected default recovery

With the current defaults (`seed=2026`), UAV 2 initially owns Task 19. Failure is
injected at `t=4.00 s`; because injection occurs before that tick's heartbeat,
its last heartbeat is at `t=3.00 s`. The timeout check uses the required strict
comparison `now - last_heartbeat > 2.5 s`, so detection occurs on the next
eligible 0.25-second tick, at `t=5.75 s`.

Task 19 is released at detection. The three healthy UAVs are busy at that
instant, so reassignment correctly waits until one becomes available. UAV 1
receives Task 19 at `t=10.75 s`; all 20 tasks are complete at `t=17.25 s`.

A successful default run ends with a summary of event-derived simulated-time
metrics like this:

```text
[FAULT] Injecting failure into UAV 2 at t=4.00s
[HEARTBEAT] UAV 2 heartbeat timeout at t=5.75s
[FAILURE] UAV 2 declared FAILED
[RECOVERY] Releasing Task 19 from UAV 2
[ALLOC] Task 19 reassigned -> UAV 1
[MISSION] Mission completed at t=17.25s

PROTOTYPE 0.1 RESULT

Mission completed: YES
Tasks completed: 20 / 20
Agents started: 4
Agents failed: 1
Orphaned tasks: 1
Tasks reassigned: 1
Recovered tasks: 1
Simulation duration: 17.25 s
Failure detection latency: 1.75 s
Task reassignment latency: 5.00 s
Human interventions: 0
```

These are simulated-time values calculated from the run; they are not wall-clock
performance measurements.

## Run the tests

```console
python -m pytest
```

For more detail:

```console
python -m pytest -v
```

The tests prove that allocation is unique and excludes failed UAVs, timeout
detection uses strict threshold semantics and fires once, and a failed agent's
unfinished task is reassigned and completed by a survivor. The recovery test
also checks the event order and confirms that the injected agent stops moving.

## Current limitations

- All components execute in one Python process against one authoritative
  mission state; there is no distributed consensus or peer-to-peer protocol.
- Heartbeats are direct method calls. There is no packet loss, latency,
  bandwidth, RF propagation, link degradation, or changing topology.
- Agents are point masses with constant speed; there are no aircraft dynamics,
  vehicle constraints, terrain, collision avoidance, or energy limits.
- Tasks are independent points. The allocator is greedy Euclidean distance, not
  a globally optimal schedule, and each agent owns at most one task at a time.
- Failure injection models one fail-stop UAV. There is no recovery of the failed
  vehicle, partial failure, Byzantine behavior, or simultaneous-failure model.
- Failure detection is centralized and depends on a perfect simulation clock.
- The final visualisation is optional and is not a real-time control interface.
- This prototype is not integrated with ROS 2, ArduPilot, PX4, MAVLink, Gazebo,
  AirSim, SLAM, computer vision, a database, or a web application.

## Roadmap

- **Prototype 0.1 — implemented here:** basic swarm simulation and fail-stop task
  recovery.
- **Prototype 0.2:** explicit communications graph and link degradation.
- **Prototype 0.3:** communications-aware task allocation and behavior.
- **Prototype 0.4:** QUBO / quantum-simulated optimization experiments.
- **Prototype 0.5:** distributed ROS 2 implementation.
- **Prototype 0.6:** ArduPilot multi-UAV SITL integration.
- **Prototype 1.0:** EUDIS demonstration baseline.

Roadmap items are plans only; they are intentionally not part of Prototype 0.1.
