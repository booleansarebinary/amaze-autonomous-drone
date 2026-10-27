# Chunk 0 brief — reconnaissance and plan

Date: 2026-10-26. Starting commit: `a838533025480253e6a592baff163f98a1962208`.
Branch: `astrophage-collection`. Worktree: `C:/Users/victo/amaze-hula-hoop`.

## Scope and sources

Inventory repository conventions, branches and selected reuse sources; verify cflib APIs by reading source; check Docker availability and propose a digest-pinned Python base; refine the chunk plan. Authoritative behavior: `docs/mission1_astrophage_colony_design.md`, especially §§3, 9–12, 15–18. Victor's orchestrator prompt governs process and safety. Recon covers the whole design; no behavior is implemented now.

## Ownership and assignments

| Persistent role | Instance | Chunk 0 assignment | Files permitted to change |
|---|---|---|---|
| Scout | `/root/scout` | Sarah-first branch research, orbit comparison, Ansur and bridge references, Python/dependency/API evidence | `docs/implementation/scout_notes.md` |
| Builder | `/root/builder` | Read-only layout and implementation-sequence review; identify ambiguous behavior | None in Chunk 0; production ownership begins in Chunk 1 |
| Validator | `/root/validator` | Independent design, safety, test-gate and final report review | None in Chunk 0; owns `tests/mission1/` and fixtures in later chunks |
| Orchestrator | `/root` | Docker check, brief, decisions, progress, evidence review, local checkpoint commit | This brief, `PROGRESS.md`, `chunk_0_report.md` |

Exactly three agents were created at Chunk 0. Reuse these instances. No delegation beyond this roster.

## Acceptance criteria

Chunk 0 criterion from Victor's plan: "Recon report delivered; Sarah's orbit code summarized and compared with §9.2; refined plan proposed."

Applicable design constraints, copied from the design:

- §3: "port only reviewed, relevant code and tests into mission-specific modules; do not merge whole branches into the mission branch."
- §9.2: "The standoff distance is controlled from that beam's **measured range**, which is a direct relative measurement unaffected by position drift" — assess both orbit sources against this requirement.
- §15: "No automated test may open physical hardware."
- §16: "Simulation, synthetic feeds, or a successful radio handshake never satisfy this gate."

Evidence required: source paths/commits/authors; orbit inputs/outputs/frames/states/limitations; reuse adaptation requirements; branch inventory; declared versus installed versions; exact relevant cflib signatures, units and blocking behavior; log/parameter names; Docker client/engine and existing generic files; proposed pinned image; unresolved physical facts and behavior choices; refined implementation and testing gates.

## Explicitly out of scope

Production code, dependency changes, Docker image builds, hardware access of any kind, test execution on the host, teammate branch edits/checkouts/merges, pushes, and Chunk 1. No test suite or mission image exists yet: red/green, determinism runs and environment snapshots start in Chunk 1. Static documentation/source review is the Chunk 0 validation. Commit locally after review, then stop for Victor.
