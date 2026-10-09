# Add autonomous object-orbit concept and simulation demo

The algorithms team needs a starting point for finding an object and traveling
around it without a supplied target location. This change adds a self-contained
concept package under `algorithms/object_orbit/`.

## Changes

- Document the search, approach, boundary-following and recovery design.
- Add a controller that receives range sweeps and local pose rather than object
  coordinates.
- Add circle, box and empty-area scenarios with optional plots and CSV traces.
- Include a presentation walkthrough, test plan and staged integration roadmap.

## Validation

- Eight focused automated tests pass.
- Circle example: approximate loop closure in 36.6 simulated seconds.
- Box example: approximate loop closure in 39.8 simulated seconds.
- Empty example: mission timeout reported as ABORT.

## Limits and review focus

This is a simulation concept, with no hardware connection or flight commands.
It assumes full instantaneous range sweeps, ideal pose and immediate velocity
response. Actual Multi-ranger acquisition, target identity, realistic dynamics
and flight supervision remain future work.

Please review the mission interpretation—boundary following versus a strict
circular orbit—and the proposed transition to four-beam sensing. This branch
adds one module and does not require changes to the existing Docker setup.
