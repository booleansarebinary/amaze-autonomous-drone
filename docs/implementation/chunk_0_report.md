# Chunk 0 report — reconnaissance and plan

Date: 2026-10-26. Branch: `astrophage-collection`.

## Verdict

PASS WITH CAVEATS — reconnaissance is complete; hardware facts and the behavior/transport decisions below remain unresolved, so this is not authorization to implement those choices or fly.

## What changed

- `docs/implementation/chunk_0_brief.md` — scope, ownership and acceptance criteria.
- `docs/implementation/scout_notes.md` — persistent branch, algorithm, dependency and cflib source evidence.
- `docs/implementation/PROGRESS.md` — chunk status, persistent agent roster and decisions.
- `docs/implementation/chunk_0_report.md` — this checkpoint and refined plan.
- No production, test, dependency, root Docker or hardware configuration files changed.

Commits: reconnaissance starts at `a838533025480253e6a592baff163f98a1962208` (`Remove superseded hoop-centering mission docs`). The local checkpoint is the commit containing this report, message `mission1(chunk 0): document reconnaissance and implementation gates`; resolve its hash with `git log -1 --format="%H %s" -- docs/implementation/chunk_0_report.md`. Its hash is also reported to Victor after committing; it cannot be embedded in its own contents. No push is authorized yet.

## What was implemented

Documentation only. The brief, Scout cache and tables below cover the Chunk 0 recon requirements. Software behavior and its proving tests begin in Chunk 1.

| Requirement | Evidence | Verification |
|---|---|---|
| Persistent Scout, Builder, Validator | Roster in `PROGRESS.md` | Exactly three instances, all created at Chunk 0 |
| Branch/source inventory and reuse boundaries (§3) | Scout branch and source tables | Read-only git history, show and diff; no checkout or merge |
| Sarah and experimental orbit comparison (§9.2) | Scout orbit findings; reuse section below | Measured-range control, frames, units, target loss and safety reviewed |
| Ansur safety reuse (§9.3) | Scout reactive-navigation findings | Pure math separated from flight adapter and writer |
| Repository conventions and dependencies (§15, §18) | Scout environment notes | Manifest, lockfile, existing files inspected |
| Exact transport API research (§10–12) | Scout API inventory | Installed cflib 0.1.33 source and official firmware reference read, never connected |
| Docker readiness and base proposal | Environment section below | Engine query and registry manifest inspection succeeded |
| Refined plan, missing facts and approval stop | Remaining sections and progress file | Builder and Validator independent reviews; orchestrator review |

## Validation evidence

- `git status --short`, `git branch --show-current`, `git worktree list`: initial worktree clean on the correct branch. Other worktrees left untouched.
- `git fetch origin --prune` and read-only branch/history inspections: Scout records exact results in its cache.
- `docker version`: first sandboxed invocation failed on Docker config/named-pipe permissions; approved elevated retry succeeded. This was an access restriction, not an unavailable engine.
- `docker buildx imagetools inspect python:3.10-slim-bookworm`: first sandboxed invocation failed on Docker configuration access; approved retry resolved the digest below. No image built or container started.
- Tests: **N/A; 0 run, 0 passed, 0 failed, 0 skipped.** No mission suite exists yet. `algorithms/test.py` is four print statements, not a unit-test suite. No host test fallback used.
- Determinism check: N/A in Chunk 0. From Chunk 1, Validator runs the suite in two fresh containers from the same tagged image; orchestrator independently repeats it in a third fresh container.
- Safety scan: documentation-only scope; no executable files added or modified, no cflib imports/calls introduced, no hardware commands run. Source strings quoted in the cache are research evidence, not executed commands.
- Conformance: 8 of 8 recon requirements above have documentary evidence; 0 software requirements implemented/tested in Chunk 0. Physical gates remain unverified.
- Validator reviewed all four documents: PASS WITH CAVEATS after correcting the passive-cleanup recommendation and setting progress to awaiting approval. Builder's independent source review confirmed why a no-op commander facade is insufficient. Orchestrator read the full staged diff, personally checked the critical cflib source and firmware frame reference, and ran `git diff --cached --check` successfully. Only the four listed Markdown files are in the checkpoint.

## Environment snapshot

- Docker client and engine: **29.8.0**, API **1.56**. Docker Desktop **4.92.0 (240144)**; host Windows/amd64, engine Linux/amd64 (`desktop-linux`).
- Repository target: `.python-version` = **3.10**; project requires **>=3.10**. Adjacent installed environment inspected by Scout is Python **3.14.7**, so it is source evidence, not the target test environment.
- Proposed base: `python:3.10-slim-bookworm@sha256:5be5aaecb962a41567bc8041f1e9e3432cb085b037fe057f9a562630b2e4b370`.
- Registry index above includes Linux/amd64 manifest `sha256:db6ee5170ebce0f4d165af242e8e77addc08bd9ffc37e8b1815752cf027aa4f8`; registry annotation identifies **Python 3.10.22**. Actual container Python version must be measured in Chunk 1.
- Existing root `Dockerfile` uses `python:3.9-slim` and `uv:latest`; generic compose builds it. Both remain untouched and will not be used for mission verification.
- Dependency: project declares `cflib>=0.1.33`, `uv.lock` pins **0.1.33**, and inspected installation is **0.1.33**. Pin the existing dependency graph for Linux and Windows host use; no new direct dependency proposed.
- Mission image tag/ID, lockfile hash, pip freeze and `docker/mission1/snapshots/chunk_0.json`: **N/A**. The prompt creates the environment and first snapshot in Chunk 1; no fabricated Chunk 0 snapshot.
- Build/test commands run: none. Proposed one-command entry from root: `bash docker/mission1/run.sh 1` (to be implemented and verified). Wrapper will build `amaze-mission1:chunk-1`, then run `python -m unittest discover -s tests/mission1 -v` with `docker run --rm --network none`, repository mount, no privileged/device/USB mounts. Preserve dependency-layer caching, pin the base digest and every dependency, and record the exact executed commands in each snapshot. No registry push.

## Reused teammate code

**No code ported in Chunk 0.** Exact source commits, author emails and line references are in Scout's cache; future ports require source headers and verified `Co-authored-by` trailers.

Branch inventory after fetch (all remote/local branch names are in `scout_notes.md`):

| Reference | Commit | Purpose |
|---|---|---|
| `astrophage-collection` | `a838533` before checkpoint | Only branch modified |
| `origin/main` | `9a056e0` | Base reference |
| `origin/sarah` | `64b37c5` | Sarah orbit scripts |
| `origin/test_drone_flight` | `2d77814` | Ansur safety and orbit prototype |
| local `test_drone_flight` | `80561d1` | Separate worktree; later telemetry changes excluded |
| `origin/feature/autonomous-object-orbit` | `222b304` | Original prototype |
| `origin/dashboard_main` | `04fc3a3` | Logging API reference |

**Sarah:** `origin/sarah` exists at `64b37c5`. Its newer reactive orbit uses the nearest of four measured beams, a radial correction with the right toward/away sign, and tangential velocity. It is a useful mathematical starting point, but switches target implicitly, lacks the required dedicated side-beam/yaw tracking, harvest band, bounded reacquisition/exit and independent supervisor. Its callback incorrectly labels raw `uint16_t` ranges as meters; cflib's helper converts millimeters to meters. Sarah's other orbit implementation uses fixed map coordinates, which conflicts with the authoritative measured-side-range behavior. Prefer the reviewed reactive math only, subject to Victor's reuse decision.

**Experimental prototype:** `algorithms/object_orbit/prototype.py` on `test_drone_flight` matches the feature branch version; it is older, separately authored work using ideal full-circle sensor sweeps. Target-state/reacquisition ideas are useful, but its observability is stronger than the real four-beam sensor. It is not Sarah's newer implementation. See Scout's comparison for individual commits/tests.

Sarah paths: `algorithms/orbit_reactive.py`, `algorithms/potential_field_orbit.py`, `algorithms/orbit.py`; source head `64b37c53218b21a70e5032a4a6e3b8d8ec59ce93`, reactive introduction `e5c890e`. Attribution: Sarah Nguyen `<sttnguyen1@gmail.com>`. Her CCW rotation of the inward beam vector gives backward tangent for a left-side target, opposite the design's forward tangent; adapt this sign explicitly. Prototype source: `222b304`, Victor Van `<victorvantx2007@gmail.com>`. Ansur source history: `eff9058`, `3217689`, `047b500`, ansur `<ansurfnt@gmail.com>`.

**Ansur:** selected coordinate rotations, damping, saturation, repulsion and pure tests from `algorithms/reactive_nav.py` are relevant to §9.3. Exclude its flight path, synchronous JSON output and unrelated files. Adapt hard-clearance handling to every return including the orbited colony, and add mission geofence, altitude, freshness, reserve and finite-output enforcement. Do not carry across its velocity-frame assumption.

**Dashboard:** bridge is API reference only. Its hard-coded URI, unconditional radio ownership and server behavior will not be copied or run.

## cflib findings and implications

The cache records exact constructors/methods, callbacks, logging limits, parameters, units and blocking behavior for the proposed adapter, including rejected convenience APIs.

- `Crazyflie.close_link()` sends `commander.send_setpoint(0, 0, 0, 0)` before closing the driver. Ordinary context-manager cleanup therefore violates passive-mode zero-setpoint requirements. A passive cleanup boundary must be reviewed and tested against the actual library over fake link internals, not hidden by an oversimplified mock.
- Recommended implementation proposal: a transport-local, pinned-version passive subclass preserves driver/thread/callback/state cleanup while omitting the commander call; a packet guard adds defense in depth. A no-op commander facade alone is rejected because it still invokes a commander method. Never patch the installed library or claim suppressed transmission means zero calls.
- `Param.get_value(self, complete_name, timeout=60)` in 0.1.33 internally waits a fixed 60 seconds if parameters are uninitialized, ignoring the supplied timeout. Synchronous connection helpers also have unbounded waits. Prefer asynchronous connection/log/parameter callbacks plus explicit fake-clock-testable deadlines; avoid these blocking paths in control/abort handling.
- `MotionCommander` context entry takes off, and convenience setup resets estimator parameters. Do not reuse it for passive modes or adopt its implicit flight behavior; a supervised low-level flight adapter is proposed.
- Design §11.2 describes `kalman.statePX/PY` as world-local velocity, but the official firmware reference identifies them as **body-frame** velocity. `stateEstimate.vx/vy` offers global-frame velocity. This discrepancy requires an explicit corrected boundary contract, not a silent port. See [Bitcraze logging reference](https://www.bitcraze.io/documentation/repository/crazyflie-firmware/master/api/logs/).
- Telemetry schema must keep raw device time, monotonic receipt time and UTC separate, explicitly convert millimeters/degrees at the boundary, distinguish valid no-return from invalid/dropout, and check actual TOC/decks/rates before use.
- Process-local locks alone cannot establish that arbitrary other programs do not own the dongle. Combine a mission ownership lock with device-claim failure handling and a runbook preflight; verifying the actual Windows driver exclusivity belongs to Victor's live gate.

## Deviations from the design

No behavior changed. Docker development isolation deliberately supersedes §18 per Victor's process instruction. Physical Stage A evidence is unavailable, so simulation parameters remain PROPOSED until measured. No superseded hoop behavior is implemented. The velocity-frame discrepancy is reported for resolution, not silently corrected in code.

## Missing / not yet done

- Hardware identity/decks/firmware, footprint, batteries, arena and materials: unconfirmed. Static code references do not prove installed hardware.
- Runtime log-variable availability, beam sentinel interpretation/reliability, actual rates, drift, battery model and onboard link-loss response: require Victor's Stage A/C/D evidence.
- Reproducible mission image, executable tests, implementation and hardware runbooks: scheduled for later chunks. Chunk 0 does not claim these exist.

## Decisions needed from Victor

These are proposed choices, not defaults already authorized. Approving progression does not silently resolve unanswered behavior questions; affected implementation stops until resolved.

1. **Sarah reuse (before Chunk 6):** adapt her measured-range radial/tangential math and credit it (**recommended**), or request a different source. Do not adopt the fixed-center controller as the §9.2 controller.
2. **Hardware facts (now if known; mandatory before live gates):** confirm exact Crazyflie model/firmware, Flow v2, Multi-ranger, prop guards/footprint, battery type/count; otherwise explicitly leave pending Stage A. Also identify available arena and colony objects. Only Victor performs physical checks.
3. **Foundational range contract (before Chunk 1):** separate `HIT`, trustworthy `NO_RETURN`, and `INVALID` (**recommended**); invalid/dropout must never clear cells. Raw sentinel decoding stays pending firmware/Stage A evidence. Ambiguous readings fail closed.
4. **Layout spacing (before Chunk 2):** surface-to-surface and surface-to-tape spacing (**recommended, conservative**) or center-based spacing. Feasibility of 4–6 colonies in the proposed 4 m arena must be checked; fail clearly on impossible layouts rather than relax spacing.
5. **Colony loss and box geometry (before Chunk 3):** resolve §6.6 `count > L_max` versus §15's boundary wording (recommend strict `>`); approve a conservative enclosing-circle/uncertainty policy for boxes, because a least-squares circle alone is not guaranteed to enclose them.
6. **Width refinement and score (before Chunk 5):** preserve fractional depletion and rescale the estimate of collected/remaining mass, or preserve awarded score and revise only remaining mass. Recommend the latter for stable scores, with logged estimation adjustments and a defined rule when revised total is below already-awarded score. Exact accounting must be agreed; fixed-width analytic tests do not resolve this.
7. **Safety priority and landing (before Chunk 6):** recommend stale-data stop/soft abort followed by landing in place; hard kill overrides landing. Define whether emergency stops may override nominal acceleration limits, and how simultaneous retreat/geofence conflicts fail closed. Neither navigation to an unverified safe point nor acceleration exceptions will be assumed.
8. **Transport contract (before Chunk 9):** retain zero commander/setpoint calls in passive modes using an isolated, source-verified cleanup strategy (**recommended**) rather than relaxing the rule. Resolve body-to-world rotation of `kalman.statePX/PY` (**orchestrator recommendation, retaining requested variables**) versus requiring `stateEstimate.vx/vy` (Scout's preferred alternative); actual firmware TOC remains a gate. Choose config/CLI URI initially (already allowed), so automatic scanning is optional. Require verified OS/driver exclusivity for arbitrary competing radio users, or explicitly approve a narrower mission-lock/known-process/device-busy guarantee; do not claim universal detection from cooperative locks.

## Risks and known limitations

Reference code contains executable flight paths; it was read only. Firmware documentation describes a reference build, not the unknown installed aircraft. cflib host calls returning do not establish vehicle action or safe landing after link loss. Direct driver cleanup and ownership need careful pinned-version tests before they are used. Python 3.10 follows the repository target; an upgrade would be a deliberate environment decision. Fixed PROPOSED physical values cannot satisfy any flight gate. General claims that arbitrary noise/moving objects are never promoted apply to the specified adversarial test suite, not an unprovable universal sensor guarantee.

## Proposed follow-ups (not implemented)

Resolve behavior decisions at or before their owning chunk; maintain the decisions log. Have Victor provide inventory and later measured logs. Keep optional dashboard, landmark correction, moving/contested colonies and multi-drone work outside this implementation.

## Next chunk plan

Preserve chunks 1–10 and ownership from Victor's prompt. The proposed root layout fits current repository conventions; there is no conflicting mission package, lint configuration or substantive current test suite.

| Chunk | Refined gate / ordering |
|---|---|
| 1 | Digest-pinned Python 3.10 image and lock first; agree minimal importable interfaces with Validator, then assertion-level red tests for config/types/frames/clock/logger/exporter. Every physical tunable PROPOSED with Stage A reference. Add run-output ignore, README test command and first real snapshot. |
| 2 | Hand-computed ray/shape fixtures; seeded spacing and occlusion including impossible-layout rejection; invalid timing inputs. Keep sensor/battery parameters explicitly unmeasured. |
| 3 | Boundary promotion/loss, moving/noise/wall cases, robust fit versus conservative box enclosure; resolve geometry decisions first. |
| 4 | Distinct no-return/dropout semantics, ray-cell fixtures, occlusion frontiers and viewpoint scoring. |
| 5 | Analytic depletion, approved width-update accounting and exact reserve feasibility boundaries. |
| 6 | Approved Sarah/Ansur ports only, with attribution; radial sign, target-loss/reacquisition, simultaneous hazard priorities, finite/capped outputs and emergency behavior. |
| 7 | Hand-optimal route examples, tie toward lower energy, deterministic fallback and poor-colony departure. |
| 8 | Every state transition and mandatory safety path; at least 100 paired seeds against all three baselines. **Zero violations and mean score greater than each baseline are mandatory**; explanation alone cannot pass. |
| 9 | API-shaped fake transport plus actual cflib adapter over fake internals; passive zero-call assertions include cleanup, parameters and failures. Replay synthetic logs, analysis tool, Stage A/C runbook and host lockfile setup. |
| 10 | Interactive confirmation, all progression steps, duration, supervisor, soft abort/hard kill, and cleanup; injected link loss/staleness/clearance/battery/Ctrl+C during takeoff, orbit and landing. CLI/runbook command parity. |

From Chunk 1: all build/test work inside the pinned mission environment; `--network none`, no device mounts; Validator's two fresh-container runs plus orchestrator's independent full-suite run; full diff review and safety scan; immutable local image tag and snapshot per chunk; no-cache rebuild when dependencies change; maximum four build/validate cycles. Builder never edits Validator's tests. Scope-specific briefs will quote the applicable design acceptance criteria. Each checkpoint is locally committed and stops for approval.

## Approval

Reply with one of:

- **APPROVE** — push this chunk and continue to the next.
- **APPROVE, DON'T PUSH** — continue without pushing yet.
- **CHANGES: <instructions>** — revise this chunk and report again.
- **STOP** — halt the run.

Please also answer decision 3 before foundational range types are implemented; later unresolved decisions remain explicit gates. No hardware will be run by the agents under any approval option.
