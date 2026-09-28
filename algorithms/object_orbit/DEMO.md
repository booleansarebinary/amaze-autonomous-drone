# Team Presentation and Demo

## A 60-second explanation

The goal is for our Crazyflie to find an object and travel around it without
being given the object's location. This prototype separates that into search,
approach, boundary following, reacquisition and completion.

The main control idea combines motion along the object's surface with a
correction that maintains distance from it. The simulator knows where the
object is so it can generate sensor readings, but the controller only receives
those readings and an estimated drone position.

The current demo completes a loop around a circular object and a box. It also
stops the attempt when no object is found before the time limit. These are
simulation results using ideal scans, not real flight results. The next major
step is adapting the sensing and control loop to the Crazyflie's actual
Multi-ranger and Flow deck.

## Three-minute walkthrough

| Time | Show | Explain |
| --- | --- | --- |
| 0:00–0:30 | README and orbit image | Mission, unknown target location, current scope |
| 0:30–1:00 | DESIGN state diagram | How observation changes mission state |
| 1:00–1:45 | Circle and box command output | Discovery, following and approximate closure |
| 1:45–2:15 | Empty scenario | Failure is handled by timeout, not assumed success |
| 2:15–3:00 | Limitations and milestones | Four-beam sensing and hardware adapter remain |

From the repository root:

```bash
python algorithms/object_orbit/prototype.py
python algorithms/object_orbit/prototype.py --scenario box
python algorithms/object_orbit/prototype.py --scenario empty
```

The demo runs faster than real time and prints state transitions. Open
`assets/orbit_demo.png` and `assets/box_demo.png` alongside the output. No drone
needs to be connected. The plotted object is visible to the audience so the
path can be understood; its geometry is hidden from the controller.

## Questions to be ready for

**How does it find the object?**

It searches for repeated nearby range returns, approaches the closest candidate,
and follows the detected surface. This version assumes only one isolated object.
Distinguishing a mission object from room walls is not implemented.

**Are we hardcoding the object's location?**

Only the simulator stores geometry, just as a simulator needs a world to render.
`OrbitController.step()` receives a scan and local pose. It has no object
coordinate, radius or world object argument.

**Is it really a circle?**

For a round target the path is approximately circular. For a box it follows
the boundary with rounded corners. A strict circular orbit would require
estimating a center and choosing a radius.

**How does it know it went all the way around?**

It combines traveled distance, leaving and returning near the entry point, and
a large net change in the observed surface direction. This is approximate loop
closure; it is not proven object-specific completion.

**Can we run this on the drone today?**

No. It has no radio or motor code. The simulator's full range sweep is richer
than the hardware's four horizontal readings, and it assumes perfect odometry
and immediate motion. The next implementation milestone is realistic sensing.

**What code is worth reviewing first?**

Read `OrbitController.step()` for the decisions, then `DemoWorld.scan()` for the
observation assumptions. The `simulate()` function connects them without giving
the controller access to the world's object geometry.

## Describe progress accurately

Say: “A documented concept with working idealized simulation examples.”

Avoid claiming tested real flight, robust recognition, guaranteed collision
avoidance, exact 360-degree completion or successful Docker/radio integration.
