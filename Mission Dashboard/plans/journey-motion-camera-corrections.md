# Mission Journey Motion and Camera Corrections

## Objective

Correct the cinematic journey’s spatial storytelling so celestial bodies remain fixed, spacecraft motion is visually unambiguous, the rendezvous and ship handoff are believable, waypoint labels always face the viewer, users can inspect the full route with 360° camera control, and waypoint 4 contains a clear comet-field evasive sequence.

## Confirmed Behavior

- The spacecraft, not the sun, visibly moves around Tau Ceti.
- Spacecraft perform holding orbits only at:
  - waypoint 0 / launch,
  - waypoint 1 / Tau Ceti,
  - waypoint 5 / final planet.
- Camera drag supports full 360° horizontal rotation at every waypoint.
- At waypoint 2, Rocky’s ship and the Hail Mary sit side by side with subtle synchronized movement.
- The active craft changes to the Hail Mary only when departing waypoint 2 for waypoint 3.
- Rocky’s ship remains parked at waypoint 2 after the handoff instead of disappearing.
- Waypoint 4 uses evasive flying and close comet passes only; there are no weapons, shields, projectiles, or energy pulses.
- Maximum zoom-out must show the complete mission route.

## Current-State Findings

- `TauCeti` is already at a fixed world position; the “moving sun” impression comes from `CameraRig` following and looking at the ship during the orbit preset.
- `JourneyShips` currently overlaps the two ships at waypoint 2, scales Rocky down, and hides it when handoff reaches completion.
- Waypoint labels use transformed Drei `Html` without billboard/sprite behavior, so labels on the back half of the route can face away from the camera.
- Zoom only multiplies a short local follow distance over the range `0.72–1.45`; it has no route-overview focus or route-fit calculation.
- Horizontal look input is clamped to a small offset instead of represented as an azimuth angle.
- Waypoint 4 currently applies only a sinusoidal vertical dodge while the comet group rotates and advances uniformly.
- The working tree contains the previously accepted journey improvements. These changes must build on them without reverting the STL ship, arrival-gated names, dark palette, or dashboard transition.

## Implementation Plan

### 1. Introduce explicit world anchors and orbital helpers

In `src/components/journey/MissionJourneyScene.tsx`:

- Define named constants for the launch point and all mission progress values instead of repeating raw values throughout scene logic.
- Define stable world-space centers for Tau Ceti and the final planet using their existing route anchor plus their visual center offsets.
- Add reusable helpers for:
  - route position and tangent,
  - a normalized side vector perpendicular to the route,
  - circular/elliptical orbital positions around a world anchor,
  - route bounds and center derived from sampled route points.
- Keep Tau Ceti and the planet group positions fixed. Their meshes may rotate around their own axes, but their group origins must never follow a ship or camera.
- Keep orbital offsets in ship motion only. Do not animate the star or planet position to simulate orbit.

### 2. Make waypoint 0, 1, and 5 true spacecraft holding orbits

Extend `JourneyShips` with `selectedIndex` and `arrived` so it can distinguish travel from an arrived/idle hold:

- **Waypoint 0 / launch:** Rocky’s ship slowly orbits the final planet’s world center while no mission is selected.
- **Waypoint 1 / Tau Ceti:** after Rocky reaches the exact waypoint-1 insertion point and arrival is reported, it follows a visible elliptical orbit around the fixed sun center.
- **Waypoint 5 / final planet:** after arrival, the Hail Mary follows a slow orbital hold around the fixed planet center.
- Use world-space orbital positions with a slight inclination so depth is visually readable.
- Orient the active ship along the orbit tangent and add restrained banking appropriate to the orbit direction.
- Damp an `orbitBlend` value when entering or leaving a holding orbit. This prevents a snap when the user selects the next destination and the craft transitions back onto the spline route.
- Do not orbit at waypoints 2, 3, or 4; those use rendezvous/mission-specific idle movement only.
- Respect reduced motion by slowing the holding orbit substantially and suppressing banking, without freezing the mission state.

### 3. Anchor the Tau Ceti camera so the ship visibly circles the sun

Refactor `CameraRig` from a pure chase camera into a focus-based orbital camera:

- Select a semantic focus point for each scene:
  - waypoint 0: planet center/launching ship composition,
  - waypoint 1: Tau Ceti center while arrived or approaching orbital insertion,
  - waypoint 2: midpoint between both ships,
  - waypoints 3 and 4: active ship/mission encounter center,
  - waypoint 5: midpoint between the final planet and orbiting Hail Mary.
- For waypoint 1, keep Tau Ceti near a stable screen position while the Rocky ship moves around it. The camera can ease slightly for composition but must not chase the ship so tightly that the stationary sun appears to travel.
- Continue using damped camera motion and cinematic preset defaults, then add user orbit input on top of those defaults.
- Keep the existing trench camera shake only for timed near misses and disable it for reduced-motion users.

### 4. Rebuild waypoint-2 rendezvous and handoff state

Replace the current scale-and-hide handoff in `JourneyShips` with explicit rendezvous positions:

- Compute left and right ship slots from the route tangent and side vector at waypoint 2.
- Before waypoint 2:
  - Rocky follows the route toward its rendezvous slot.
  - The Hail Mary waits at the opposite slot with subtle idle drift and becomes visible early enough to establish the approach.
- At waypoint 2 arrival:
  - both ships are full-size and clearly separated side by side,
  - both share the same slow vertical drift, slight yaw, and small roll phase so they read as synchronized rather than independently bobbing,
  - the camera targets their midpoint.
- When the user selects waypoint 3:
  - the Hail Mary eases from its rendezvous slot onto the route and becomes the moving craft,
  - Rocky eases into a persistent parked transform at the waypoint-2 slot,
  - Rocky remains visible there for the rest of the forward journey with a restrained idle motion.
- Do not scale either ship to imply replacement and do not set Rocky’s visibility to false after handoff.
- When navigating backward, keep transforms continuous: the Hail Mary returns to its rendezvous slot, both ships synchronize again at waypoint 2, and Rocky resumes as the route craft only after departing backward toward waypoint 1.

### 5. Make all waypoint labels camera-facing

Update `JourneyRoute` label rendering:

- Enable Drei `Html` billboard/sprite behavior for every waypoint label, not only waypoints 3–5, so orientation remains correct from any camera azimuth.
- Keep label position anchored above its waypoint and preserve arrival-gated mission names.
- Ensure the HTML surface is never mirrored or back-facing after a 180°/360° camera rotation.
- Retain pointer interaction and readable distance scaling.
- Add only minimal CSS changes if necessary for backface visibility or transform stability; do not redesign the label cards.

### 6. Replace offset look controls with true 360° camera orbit

Coordinate `src/components/HomePage.tsx` and `MissionJourneyScene.tsx`:

- Replace `dragOffset` with a camera-control ref such as `{ azimuth, elevation }`.
- Convert horizontal pointer movement to an unbounded azimuth angle, normalized modulo `2π`, so users can rotate continuously through 360° in either direction.
- Convert vertical movement to elevation and clamp it to a safe range (approximately `-75°` to `75°`) to prevent camera inversion and disorienting pole flips.
- Preserve one-pointer drag and two-pointer pinch separation so pinching never rotates the camera accidentally.
- In `CameraRig`, calculate the camera position from spherical coordinates around the current semantic focus point, then apply preset-specific default azimuth/elevation as a base composition.
- Preserve the chosen camera angle while moving between nearby missions where possible; blend preset offsets rather than resetting user input abruptly.
- Update the interaction hint from generic “Drag to look” to “Drag to orbit” while retaining keyboard and zoom guidance.

### 7. Add full-route zoom-out and overview blending

Expand the existing zoom model instead of merely increasing the chase distance:

- Increase the zoom-out range substantially while preserving the current close-up minimum.
- Sample the route and compute a `THREE.Box3`/bounding sphere that includes all route waypoints and major celestial bodies.
- Calculate the overview camera distance from the route bounding-sphere radius and the perspective camera FOV, including margin for the header, mission panel, bottom controls, and zoom buttons.
- Use two zoom regimes:
  - local/cinematic zoom follows the current semantic focus and mission preset,
  - overview zoom gradually blends the focus point toward the route center and the camera distance toward the route-fit distance.
- At maximum zoom-out, the entire route, all waypoint markers, Tau Ceti, and the final planet must fit on screen.
- Keep 360° azimuth control active in overview mode, orbiting the route center rather than the local ship.
- Retain buttons, wheel, trackpad, and pinch input with clamping. Adjust steps so buttons remain useful across the expanded range.
- Keep camera transitions damped and avoid clipping by confirming the perspective camera near/far range covers the overview distance.

### 8. Choreograph waypoint-4 comet evasive animation

Refactor `CometTrench` and the waypoint-4 branch of `JourneyShips` into a shared deterministic sequence:

- Give comet instances stable IDs, base positions, speeds, crossing offsets, and phase values rather than advancing every child identically.
- When waypoint 4 is selected, schedule several readable near-miss beats around the active Hail Mary:
  1. a comet crosses from upper-left and the ship banks/downshifts right,
  2. a second crosses low from the opposite side and the ship rolls upward/left,
  3. a tighter central pass produces the strongest bank and brief camera shake.
- Move the ship laterally and vertically around the route centerline while preserving forward route progress; compose the dodge offset with its route position rather than modifying the route itself.
- Orient/bank the ship into each evasive move using damped quaternions so the motion reads as intentional piloting.
- Give close comets elongated trails and higher relative speed to communicate proximity. Comets continue past the ship; they are not destroyed or physically redirected.
- Continue a subdued looping evasive pattern while parked at waypoint 4 so the requested animation remains visible after arrival, but keep the mission marker and detail panel stable.
- Limit camera shake to the instant of close passes.
- For reduced motion, replace the loop with a small slow bank and remove camera shake/rapid comet crossings.

### 9. Preserve existing journey behavior

- Keep arc-length waypoint alignment and exact arrival snapping.
- Keep the supplied Rocky STL assembly and Hail Mary GLB.
- Keep arrival-gated mission names.
- Keep Start Mission opening the dashboard and the dashboard home control returning to mission selection.
- Keep the dark journey palette and purple-only journey action-button rule.
- Do not introduce a router, physics engine, or new dependency; Three.js, React Three Fiber, and Drei already provide the required primitives.

## State and Data Flow

- `HomePage` remains responsible for pointer/wheel/pinch input and stores:
  - selected mission,
  - arrival state,
  - zoom value,
  - mutable camera azimuth/elevation.
- `MissionJourneyScene` passes selection, arrival, zoom, reduced-motion, and camera-control refs to scene components.
- `FlightController` remains the only owner of normalized route progress and arrival callbacks.
- `JourneyShips` derives active craft and hold behavior from route progress plus selection/arrival state:
  - Rocky active before handoff,
  - both synchronized at waypoint 2,
  - Hail Mary active after forward departure from waypoint 2,
  - Rocky parked at waypoint 2 thereafter.
- `CameraRig` derives its focus from the same ship/anchor positions used by `JourneyShips`, avoiding duplicated approximations. If necessary, expose current ship and rendezvous positions through shared refs updated per frame.
- Comet and dodge choreography share one normalized phase so the ship reacts to the same near-miss timing that positions the comets.

## Edge Cases

- Rapidly selecting another waypoint must cancel/blend the current orbit or evasive hold without teleporting a ship.
- Selecting waypoint 2 from either direction must end with both ships in their stable side-by-side slots.
- Reverse navigation across waypoint 2 must transfer route motion back to Rocky without hiding or duplicating either ship.
- Repeated horizontal dragging must wrap cleanly without numerical growth or a hard stop.
- Vertical drag must not flip the camera upside down.
- Maximum zoom-out must not clip the route or lose HTML labels behind the camera.
- Pinch gestures must not create rotation deltas when one finger is released.
- Billboard labels must remain clickable and must not reveal mission names before arrival.
- Orbit and waypoint-4 idle loops must stop contributing offsets as soon as travel to another waypoint begins.
- Reduced-motion mode must preserve all mission states and controls while removing rapid banks, shakes, and high-speed loops.

## Expected Files

- `src/components/journey/MissionJourneyScene.tsx` — primary ship, camera, label, orbit, rendezvous, and comet work.
- `src/components/HomePage.tsx` — 360° camera input and expanded zoom range.
- `src/journey.css` — interaction-hint or label stability adjustments only if needed.
- `src/data/journeyMissions.ts` — only if camera preset naming needs clarification; mission content does not otherwise need to change.

## Verification

1. Run `pnpm format`, restore any unrelated formatter-only changes, and confirm `git diff --check` passes.
2. Run `pnpm build` and require a zero exit status.
3. At 1440×900, manually verify each phase:
   - waypoint 0: Rocky orbits the planet; the planet remains fixed,
   - waypoint 1: Rocky visibly circles fixed Tau Ceti and the camera does not make the sun appear to travel,
   - waypoint 2: both full-size ships are separated, synchronized, and visible,
   - departure to waypoint 3: Hail Mary leaves; Rocky remains parked at waypoint 2,
   - waypoints 3–5: all labels face the camera from front and rear views,
   - waypoint 4: multiple obvious evasive near misses occur without weapon/shield effects,
   - waypoint 5: Hail Mary holds a visible orbit around the fixed planet.
4. Drag continuously left/right through more than one full revolution at every waypoint and confirm there is no clamp, snap, or mirrored text.
5. Test zoom buttons, mouse wheel, trackpad, and pinch from minimum to maximum; at maximum zoom-out confirm the entire map fits in frame.
6. Verify reverse navigation across waypoint 2 and rapid waypoint changes for ship continuity.
7. Verify reduced-motion mode removes camera shake and aggressive evasive/orbit movement while retaining controls.
8. Confirm Start Mission still opens the dashboard and return-to-home still restores the journey.
