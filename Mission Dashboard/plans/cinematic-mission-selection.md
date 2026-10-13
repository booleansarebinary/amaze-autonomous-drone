# Cinematic Mission Selection Journey — Implementation Plan

## Objective

Replace the current card-list mission selector with a full-screen, 1440×900-first, cinematic 3D journey map inspired by *Project Hail Mary*. The selector remains a standalone prototype surface: users fly between the fixed story waypoints, inspect each mission, and can press a visually responsive **Start Mission** button, but that button does not transition into the existing telemetry dashboard yet.

The existing dashboard, Crazyflie WebSocket integration, dummy feed, telemetry types, scenario fixtures, and server code must remain intact.

## Confirmed Product Decisions

- **Navigation model:** free cinematic navigation. The experience opens at the launch point on Rocky’s planet. Any mission waypoint may be selected directly.
- **Waypoint states:** missions before the selected destination are `completed`, the selected destination is `current`, and later missions are `upcoming`. At the start point, all five missions are upcoming.
- **Dashboard handoff:** none for this iteration. Preserve dashboard code for future reconnection, but do not enter it from the mission selector.
- **Start Mission action:** visual-only. It provides polished press/acknowledgement feedback but does not change persistent state or navigate away.
- **Theme behavior:** both light and dark modes receive distinct 3D scene treatments, not just different UI chrome. Theme selection continues to use the existing App-owned theme state.
- **Story order is fixed:** launch point → Orbit Tau Ceti → Rocky & Ryland rendezvous → Collect the astrophage → Eridian Trench Run → Classroom. The first and last locations use the same planet.

## Repository Findings and Constraints

- React 19, Vite 8, TypeScript, Tailwind CSS v4, Three.js, React Three Fiber, and Drei are already installed.
- `src/components/HomePage.tsx` is the current mission selector and maps mission cards directly to telemetry scenarios.
- `src/App.tsx` owns the `home | dashboard` view, theme, scenario, telemetry, and dashboard control state.
- The dashboard’s 3D conventions live in `src/components/DroneScene.tsx`; reuse its normalized-model, Suspense, lighting, DPR, and material-cloning patterns where useful.
- The local visual system is implemented through CSS variables in `src/index.css`; there is no external component design system. Extend the existing purple palette, glass surfaces, Inter/Space Mono typography, radius, focus, and theme conventions rather than introducing a UI library.
- The supplied Hail Mary share resolves to `Project Hail Mary.glb`, a 29.4 MB GLB with three meshes, 18 materials, no textures, no built-in animation, and `KHR_materials_specular`.
- Rocky’s ship share contains three public STL files: `EridianShipCenterx2V2.stl` (~0.9 MB), `EridianShipConnectorsV2.stl` (~1.2 MB), and `EridianShipWingsx4 v3.stl` (~3.3 MB). These are print-kit parts and need assembly/orientation before use as an in-scene ship.

## Experience and Visual Direction

### Overall composition

- Make the WebGL canvas fill the entire selector with no dashboard grid behind it.
- Use restrained HIG-style interface chrome over the cinematic scene:
  - a compact top-left identity block with product name and journey context;
  - a top-center route/progress readout;
  - a top-right theme toggle;
  - previous/next controls anchored near the lower center;
  - an arrival mission panel in the lower-left or lower-right safe area chosen per waypoint camera framing;
  - a subtle interaction hint for arrows, drag, and click that fades after first input.
- Keep panel density low so the scene remains the hero. Use translucent purple glass, thin hairlines, backdrop blur, and Space Mono for mission numbers/status/route readouts.
- Use the supplied palette as semantic accents: primary/secondary/highlight for route and focus, yellow for star/caution energy, coral for trench danger, mint for completed status, and rose for astrophage/planet warmth.

### Dark theme

- Deep indigo/black-violet space, dense cool stars, saturated purple route glow, strong corona and bloom-like sprite effects, bright warm planet rim light, and dark glass panels.

### Light theme

- Pale lavender/pearl space with a softly luminous nebula/fog field, lower-contrast stars, iridescent route glow, brighter atmospheric scattering, and frosted light glass panels.
- Keep sufficient contrast and depth so light mode still reads as space rather than a flat white canvas.

### Page-load intro

1. Start from near-black/near-white theme field with a centered loading/mission mark while essential launch-point assets resolve.
2. Fade in the starfield and planet atmosphere.
3. Draw the route progressively from the launch point.
4. Bring Rocky’s ship up from the planet surface with a short lift and roll stabilization.
5. Stagger in node labels and interface chrome.
6. Finish at an idle launch-point composition with all five missions marked upcoming.

## Data Model

Create `src/data/journeyMissions.ts` as the source of truth for the selector. Do not reuse telemetry `Scenario` as a mission identity.

Define:

- `JourneyMissionId = "orbit-tau-ceti" | "rendezvous" | "astrophage" | "trench-run" | "classroom"`
- `JourneyWaypointState = "completed" | "current" | "upcoming"`
- `JourneyMission` with:
  - stable ID;
  - numeric order and two-digit display code;
  - title;
  - short arrival description;
  - status label text;
  - normalized route position / route progress value;
  - scene type;
  - camera preset key;
  - arrival cinematic key;
  - panel placement preference.

Use these mission descriptions so implementation does not require copy decisions:

1. **Orbit Tau Ceti** — “Reach Tau Ceti and establish a stable observation orbit around the star.”
2. **Rocky & Ryland rendezvous** — “Match velocity with the Hail Mary, align both ships, and complete the navigation handoff.”
3. **Collect the astrophage** — “Enter the drifting astrophage bloom and draw a viable sample stream into containment.”
4. **Eridian Trench Run** — “Thread the comet corridor at speed, banking through the only stable line home.”
5. **Classroom** — “Return to Erid, descend through the warm atmosphere, and complete the final landing.”

Derive waypoint state from the selected destination index rather than storing duplicated status:

- no selected mission / launch point: all upcoming;
- index lower than selected: completed;
- selected index: current;
- higher index: upcoming.

Keep transient interaction state separate:

- current path progress;
- target path progress;
- selected destination;
- flight phase;
- arrival cinematic state;
- active ship/handoff blend;
- drag orbit offsets;
- intro complete;
- temporary Start Mission acknowledgement.

## Component Architecture

### `src/components/HomePage.tsx`

Refactor into the top-level mission journey controller rather than a card list.

Responsibilities:

- own selected waypoint and transition state;
- coordinate keyboard, previous/next, node click, and mission panel controls;
- derive waypoint statuses;
- render the full-screen scene and DOM overlay;
- keep the existing `theme` and `setTheme` props;
- remove the telemetry-scenario dependency and stop invoking `onStart`.

### `src/components/journey/MissionJourneyScene.tsx`

Own the R3F `Canvas`, scene-level theme values, Suspense boundary, camera rig, route, environments, ships, particles, lighting, and pointer drag/orbit behavior.

Recommended canvas settings:

- DPR capped around 1.5;
- antialiasing enabled;
- high-performance power preference;
- cinematic tone mapping/exposure tuned per theme;
- fog color and density animated between theme variants;
- shadows only where they materially improve planet/landing shots.

### `src/components/journey/JourneyCameraRig.tsx`

Implement camera movement independently from scene content.

- Interpolate camera position, look target, FOV, and roll using damped easing in `useFrame`.
- Blend between per-leg camera presets rather than snapping.
- Add bounded pointer/touch orbit offsets on top of the authored camera pose.
- Return drag offsets toward neutral after release using spring-like damping.
- Suppress camera shake and large roll when reduced motion is requested.

### `src/components/journey/JourneyRoute.tsx`

- Use one fixed `THREE.CatmullRomCurve3` that begins near Rocky’s planet, travels through all five mission markers, and returns to the same planet from a different approach vector.
- Render a dim full route plus a brighter completed/current segment.
- Animate route reveal during the intro.
- Use a lightweight glow approach (layered tube/line materials or sprites) rather than a mandatory postprocessing package.
- Render each node as an interactive 3D beacon with hover/focus scale, pulse, halo, number, mission name, and state treatment.
- Use semantic DOM buttons through Drei `Html` for labels and keyboard focus while keeping the 3D beacon as the visual target.

### `src/components/journey/JourneyShips.tsx`

- Normalize both supplied ship assets to a common logical length and forward axis.
- Keep ship transforms under a shared flight group controlled by route tangent, bank, pitch, and phase.
- Rocky’s ship is visible from launch through rendezvous.
- Hail Mary appears ahead during the rendezvous approach.
- During the waypoint-2 cinematic, align both ships, orbit the camera around them, then blend control/follow emphasis to Hail Mary.
- After waypoint 2, Hail Mary is the active route-following ship.
- When navigating backward across waypoint 2, reverse the handoff visually so free navigation remains coherent.

### `src/components/journey/JourneyEnvironments.tsx`

Split internally by scene for maintainability, while keeping one scene/canvas:

- `RockyPlanetEnvironment`
- `TauCetiEnvironment`
- `RendezvousEnvironment`
- `AstrophageField`
- `CometTrench`
- shared `Starfield` and `AmbientDust`

Keep distant environments lightweight and lower their animation/detail when outside the active camera neighborhood.

### `src/components/journey/MissionInfoPanel.tsx`

- Reveal only after arrival alignment completes.
- Show mission number, title, short description, derived status, and Start Mission.
- Animate with blur/opacity/translation, respecting reduced motion.
- The Start Mission button produces press feedback, a short “Mission ready” acknowledgement, and then returns to its default label without changing route state or navigating.

### `src/components/journey/JourneyControls.tsx`

- Previous/next buttons with explicit text and directional icons.
- Disable Previous at the launch point and Next at mission 5.
- Show current location as `LAUNCH` or `01 / 05` through `05 / 05`.
- Add an understated keyboard/drag instruction that disappears after the first interaction.

### `src/components/Icons.tsx`

Add local `arrowLeft`, `arrowRight`, and any minimal route/target icon needed by the overlay. Continue using the project icon component; do not introduce an icon package or emoji.

## Asset Pipeline

### Local asset placement

Add optimized, locally served assets under `public/models/journey/`:

- `hail-mary.glb`
- `rocky-ship.glb`
- `ATTRIBUTION.md` or an equivalent update to the existing attribution file with supplied source URLs and any available creator/license information.

Do not fetch assets from Google Drive at runtime.

### Hail Mary preparation

- Download the supplied GLB once during implementation.
- Normalize origin, forward axis, and scale without destroying material groups.
- Deduplicate/prune unused data and apply mesh optimization/compression compatible with Drei/Three’s GLTF loader.
- Preserve the specular material extension and verify all three meshes remain present.
- If compression tooling is added, keep it as a development-only dependency and document a reproducible package script rather than relying on an untracked manual command.

### Rocky ship preparation

- Download all three STL files once.
- Use an offline preparation script to split disconnected print-kit components, orient the two center pieces, four wings, and connector pieces into a symmetric ship assembly, calculate normals, merge compatible geometry, assign a small number of materials, center the finished ship, and export GLB.
- Keep assembly transforms in the preparation script so the asset can be regenerated and visually tuned without hand-editing binary output.
- Use project colors/material intent: dark metallic body, warm Eridian accents, subtle purple reflections, and emissive engine elements added in the R3F scene if not baked into the model.
- Verify silhouette and part placement in a temporary inspection scene before using it in the final journey.

### Loading behavior

- Show the intro loader until Rocky’s ship and launch environment are ready.
- Load/preload Hail Mary early enough that waypoint 2 never reveals a missing model, but avoid blocking the first paint on it if the optimized asset remains relatively large.
- Provide a simple geometric ship fallback inside the Suspense boundary so a model failure does not blank the scene.

## Route and Flight State Machine

Represent travel as path progress moving toward a target progress value. This supports direct selection, forward travel, and reverse travel without teleporting.

### Phases

1. **Acceleration**
   - Ease velocity up from idle.
   - Pitch the ship slightly into the tangent.
   - Extend engine glow and speed streaks.
   - Move camera from arrival framing into the leg’s travel preset.

2. **Banking / cruise**
   - Orient the ship to the spline tangent.
   - Calculate bank from local curve change/curvature and clamp it to a readable maximum.
   - Increase parallax and environmental motion according to leg intensity.

3. **Deceleration**
   - Ease speed down near the target.
   - Reduce bank and streak length.
   - Begin blending toward the waypoint arrival camera.

4. **Alignment**
   - Settle ship orientation and framing with damped motion.
   - Run the waypoint-specific cinematic.
   - Mark the controller arrived and reveal the mission panel.

If a new waypoint is selected during flight, update the target progress and continue smoothly from the current path position. Do not reset to the previous waypoint or hard-cut. Reverse ship/camera travel coherently when the new target lies behind the current position.

Use bounded authored durations rather than a single constant duration: nearby legs should feel responsive, while multi-waypoint jumps should remain cinematic but not force the user through every intermediate arrival pause.

## Per-Waypoint Scene and Arrival Direction

### Launch point — Rocky’s planet

- One rotating planet is reused for both launch and final return.
- Layer a surface sphere, cloud/noise layer, soft back-face atmospheric shell, rim light, and sparse orbital dust.
- Intro cinematic: Rocky’s ship lifts from the warm horizon, stabilizes, and points toward the route.
- Camera: low close-up rising into an over-shoulder departure framing.

### 1 — Orbit Tau Ceti

- Bright emissive star with animated corona shells, lens-glare sprites, and a tilted orbital ring.
- Arrival: Rocky’s ship decelerates, crosses the ring, and settles into a slow partial orbit.
- Camera: wide orbital angle that arcs around the star while keeping the ship readable.

### 2 — Rocky & Ryland rendezvous

- Deep-space pocket with Hail Mary ahead and subtle navigation lights.
- Arrival: Rocky’s ship approaches from behind/side, matches velocity, aligns, and holds formation.
- Camera then makes a controlled orbit around both ships and hands off to a Hail Mary chase composition.
- This cinematic also drives the active-ship blend for later route positions.

### 3 — Collect the astrophage

- Dark localized volume with hundreds of glowing drifting particles in rose, violet, and warm gold.
- Arrival: Hail Mary dips into the field; nearby particles curve into a stream toward a containment point on the ship.
- Camera: close three-quarter fly-by that reveals both the particle field and collection motion.

### 4 — Eridian Trench Run

- Dense but instanced comet field with tapered additive tails and layered speed streaks.
- Hail Mary banks aggressively and dodges by applying authored lateral offsets around the route spine without changing logical path progress.
- Camera: tight chase with restrained procedural shake, FOV widening, and brief side fly-by moments.
- Coral/yellow hazard light can accent the purple palette without overwhelming it.

### 5 — Classroom

- Return to the original planet object from a different route angle, now much closer with warmer surface light.
- Hail Mary decelerates dramatically, descends through the atmospheric shell, and settles onto/above a landing area.
- Reduce particles, shake, streaks, and music-like visual rhythm; shift to slower planet rotation and calm dust.
- Camera: close descending profile that eases into a stable landed hero shot.

## Animation Systems

- **Starfield:** layered `Points` buffers with depth bands, slow drift, camera-relative parallax, and theme-specific color/opacity.
- **Ambient dust:** sparse local points around the active environment; lower density outside the current neighborhood.
- **Planet/star rotation:** continuous delta-time animation, not CSS timing tied to frame rate.
- **Route glow:** pulsing opacity/scale plus animated progress reveal.
- **Speed streaks:** pooled line/mesh instances whose length and opacity derive from flight speed.
- **Comets:** instanced meshes with deterministic seeded positions and wrapped movement.
- **Astrophage:** GPU-friendly points; a subset follows curved collection paths during the arrival cinematic.
- **Nodes:** idle pulse, halo rotation, hover/focus lift, status-color interpolation, and selected ripple.
- **Panels/chrome:** CSS transitions/keyframes scoped under journey-specific classes.
- **Theme transitions:** interpolate fog, background, lights, planet atmosphere, star colors, and route material colors instead of remounting the Canvas.

## Interaction Details

### Click and pointer

- Clicking/focusing a node selects its mission and starts travel.
- Distinguish click from drag using a small movement threshold so orbit gestures do not accidentally select nodes.
- Pointer/touch drag adjusts a limited yaw/pitch camera offset only; it must never move the ship off the authored route.
- Add mild inertial settling after release.

### Keyboard

- `ArrowRight`: select the next mission; from launch, select mission 1.
- `ArrowLeft`: select the previous mission; from mission 1, return to launch.
- `Enter`/`Space`: activate a focused waypoint or control through native button behavior.
- Do not hijack arrows while a native interactive control requires them.

### Focus and accessibility

- All waypoint labels and previous/next/theme/Start Mission controls are real semantic buttons with visible focus states.
- Provide an offscreen polite live region announcing departure, arrival, and the selected mission/status; do not continuously announce animation progress.
- Canvas decorative content is hidden from the accessibility tree; provide an accessible journey label and DOM controls for all actions.
- Maintain readable panel contrast in both themes.
- Honor `prefers-reduced-motion`: shorten travel, remove shake and aggressive banking, reduce parallax/particle motion, and replace long cinematic camera arcs with brief eased transitions while preserving all content and navigation.

## App Integration

### `src/App.tsx`

- Keep dashboard components, telemetry hook usage, scenarios, and server-facing behavior unchanged.
- Render the refactored HomePage with only theme ownership for this iteration.
- Do not start a telemetry scenario or switch `view` when Start Mission is pressed.
- Preserve the dashboard branch rather than deleting it, so a later task can reconnect story missions to operations without rebuilding dashboard logic.
- Avoid broad telemetry/type changes; journey mission types belong in the journey data module, not `src/telemetry/types.ts`.

### `src/index.css`

- Preserve existing dashboard styles.
- Add journey-specific theme tokens under a `.journey-page` scope to prevent collisions.
- Add styles for glass overlays, node labels, arrival panel, controls, loading/intro states, theme transitions, responsive tightening, and reduced-motion overrides.
- Retain Inter and Space Mono wiring and existing palette variables.

## Responsive and Layout Behavior

- Primary target is 1440×900.
- Preserve a cinematic full-screen composition at the repository’s existing desktop minimums.
- At narrower desktop/tablet widths, tighten overlay spacing, reduce panel width, and move node labels to avoid major overlaps without collapsing into a generic vertical card list.
- Touch/coarse-pointer environments receive larger control targets and slightly reduced particle/DPR settings.
- Ensure safe positioning when browser chrome reduces available height; no essential control may sit outside the viewport.

## Performance and Failure Handling

- Cap DPR and particle counts; use instancing for comets and reusable buffer geometry for stars/astrophage.
- Avoid per-frame React state updates. Keep high-frequency flight, camera, particles, and theme interpolation in refs/useFrame; update React state only at phase/arrival boundaries.
- Memoize curves, route samples, random buffers, cloned scenes, and materials.
- Dispose generated geometries/materials when components unmount.
- Use deterministic seeded distributions to avoid hydration/remount visual jumps.
- Keep off-camera environments mounted only if needed for uninterrupted direct travel; otherwise lower detail/animation rather than recreating expensive assets every frame.
- Add a graceful WebGL/model fallback overlay with mission navigation still available if the scene fails to initialize.

## Verification Plan

### Automated checks

1. Run the repository formatter with `pnpm format` after edits and inspect the diff for unintended formatting changes.
2. Run `pnpm build` and require a successful production build.
3. Confirm no TypeScript errors, missing asset URLs, or unsupported GLTF extensions are reported by the build/runtime.

### Manual preview checks at 1440×900

1. Initial load displays the themed loader, intro, launch planet, Rocky ship, route, and all five upcoming nodes.
2. Selecting mission 1 runs acceleration, banking, deceleration, alignment, star orbit cinematic, and then reveals the correct panel.
3. Selecting mission 2 shows Hail Mary ahead, matching/alignment, camera orbit, and handoff.
4. Mission 3 shows drifting astrophage and an arrival collection stream.
5. Mission 4 shows fast comet motion, ship banking/dodging, streaks, and controlled camera shake.
6. Mission 5 returns to the same planet, slows visibly, descends, and lands in a calm close-up.
7. Direct jumps (for example launch → mission 4), backward travel, and retargeting during flight remain smooth and use the correct active ship around waypoint 2.
8. Node status labels always reflect completed/current/upcoming relative to the selected destination.
9. Previous/next controls, arrow keys, node clicks, focus activation, touch drag, and mouse drag all work without accidental selections.
10. The mission panel appears only after arrival; Start Mission gives visual acknowledgement and does not navigate or alter persistent state.
11. Light/dark toggle smoothly changes the entire scene and overlay while preserving camera/mission state.
12. Reduced-motion mode removes shake/aggressive movement and keeps navigation usable.
13. No selector changes regress dashboard source, telemetry adapter, Crazyflie bridge, dummy server, battery formula, or scenario data.

## Out of Scope

- Connecting Start Mission to the existing dashboard.
- Mapping story missions to telemetry prototype scenarios.
- Persisting campaign progress across reloads.
- Changing Crazyflie radio/backend behavior or addressing the current packet-loss issue.
- Adding audio, music, narration, or copyrighted movie assets beyond the user-supplied ship models and the requested thematic inspiration.
