# Astrophage Collection — Mission 1: Petrova Line Hunt

## Mission description

The Crazyflie represents a small fuel-harvesting probe sent into a field of Astrophage colonies. Its battery is its fuel supply, and it is limited. Several Astrophage colonies (tall, solid objects of different widths) stand at unknown locations inside a taped arena. Wider colonies are richer. The drone does not know how many colonies there are, where they are, or how rich they are when the mission starts.

The drone must take off, discover colonies with its own range sensors, build a map of the arena, choose which colonies are worth visiting, harvest them by orbiting at a safe standoff distance, and return to its home pad before its energy reserve runs out. The goal is to collect as much Astrophage as possible in one battery, with zero safety violations.

The technically ambitious part is **autonomous decision-making under uncertainty and an energy budget**, not any single maneuver:

- **Mapping from sparse sensors:** turning four single-point range beams into a map of discrete colonies, including estimates of their position, size, and confidence.
- **Explore vs. exploit:** deciding when to spend battery searching unseen space for new colonies versus harvesting colonies already found.
- **Foraging decisions:** colonies deplete as they are harvested, so collection slows over time. The drone must decide when to leave a colony for a better option, the classic patch-leaving problem from ecology (the marginal value theorem).
- **Budgeted route planning:** choosing which colonies to visit, and in what order, so that the total collected is maximized and the drone still makes it home. This is a variant of the orienteering problem.
- **Safe close-range flight:** orbiting each colony at a controlled standoff distance using direct range measurements, while a separate safety layer keeps the drone inside the arena and away from every surface.

To prove the planner is genuinely better than a scripted behavior, the mission is evaluated against simple baselines (for example, a lawnmower sweep and nearest-colony-first) on the same randomized layouts and battery budget.

## Why this replaces the hoop-centering mission

The earlier proposal (centering on a hand-moved hula hoop) depended on the Multi-ranger being able to estimate a moving hoop's center and orientation from a few horizontal distance beams. The original design document identified that as an unproven, high-risk assumption. This mission uses the sensors in the way they are designed to work, detecting solid objects at flight height, and moves the technical challenge into estimation and planning, which the team controls.

## Arena summary

- A taped arena on a textured floor (texture is needed by the Flow deck), with a marked home pad at one edge.
- Four to six colonies: solid, matte objects clearly taller than flight height, in two or three distinct width tiers.
- Colonies are spaced well apart and kept away from the tape line. Walls, furniture, and people stay outside the arena.
- Before each demo run, someone outside the team places the colonies, so the layout is not known in advance. At least one colony should be hidden behind another from the home pad's view, forcing the drone to explore.

All dimensions are proposals until measured. See the design document for starting values and the tests that will set the final numbers.

## Mission phases

1. **Safe setup:** verify the radio link, deck presence, and telemetry without arming or sending flight setpoints.
2. **Sensor characterization (no flight):** with propellers removed, carry the drone through the arena at flight height and record when and how reliably each colony is detected. This sets detection range, width-estimate accuracy, and spacing rules.
3. **Takeoff and initial scan:** take off to the agreed flight height and rotate in place so the side beams sweep the arena.
4. **Map:** convert beam returns into colony candidates; promote a candidate to a colony only after repeated, stable, correctly sized detections.
5. **Plan:** repeatedly choose the best next action (explore unseen space, travel to a colony, keep harvesting, or return home) based on expected gain, travel cost, and remaining battery.
6. **Harvest:** orbit the chosen colony at a fixed standoff distance. Collection is scored from the colony's estimated richness and time spent, with diminishing returns as it depletes. The orbit also refines the colony's size estimate.
7. **Return and land:** when the energy reserve is reached, or nothing else is worth the trip, fly home and land.
8. **Fallback:** on lost sensors, lost telemetry, unexpected obstacles, geofence breach, or low battery, stop the current task and execute the pre-agreed safe landing behavior while radio control is still available.

## Success means

- A no-flight sensor test shows colonies are detected repeatably at flight height, with measured detection range, width-estimate error, and minimum spacing.
- A simulation and replay harness shows correct coordinate transforms, correct colony detection, bounded finite commands, safe fallback behavior, and planner performance that beats the baselines across many randomized layouts.
- A real Crazyradio connection can receive and log telemetry without arming, taking off, or sending flight setpoints.
- Supervised flights progress step by step (hover and scan, single-colony orbit, full mission) and show that the drone discovers colonies, harvests, and returns home with its reserve intact, with zero safety violations. Every run produces a unique JSONL log containing telemetry, colony events, and planner decisions.

Numeric limits for flight height, standoff distance, speed, battery reserve, and colony dimensions must be agreed after measuring the actual aircraft, sensors, and battery behavior.

## Not part of Mission 1

- Flying over, through, or touching colonies.
- Assuming a camera, fiducial marker, motion-capture system, external positioning system, GPS, or additional sensor is installed.
- Changing Crazyflie firmware, onboard PID gains, or arming/failsafe settings before evidence and review.
- Treating simulation, dashboard mock data, or a successful radio connection as proof of safe flight.
- Multi-drone operation (listed as a stretch goal only).
