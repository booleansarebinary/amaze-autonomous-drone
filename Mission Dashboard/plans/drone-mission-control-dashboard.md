# Drone Mission Control Dashboard Implementation Plan

## Objective

Build a polished desktop-first React prototype of a 1440×900 drone mission-control dashboard. The app will keep the 3D quadcopter exactly centered as the visual hero, expose all five requested mission scenarios in light and dark themes, and provide interactive telemetry, warnings, mission controls, altitude motion, speed intensity, and attitude changes.

The repository is currently a blank React 19 + Vite 8 + Tailwind CSS 4 scaffold. It has no existing design system, component library, imagery, model assets, or font declarations. The implementation will therefore establish a small local token/component system rather than introducing a general-purpose UI framework.

## Confirmed Product Decisions

- Deliver the requested frames as one interactive dashboard rather than ten duplicated routes.
- Add an unobtrusive prototype-state control that switches among Normal Flight, Low Battery, Mission Failure, Telemetry Loss, and Mission Complete.
- Add a light/dark theme toggle and low/medium/high speed control so every requested variant is directly inspectable.
- Use **Inter** for headings and interface text and **Space Mono** for live numeric telemetry, loaded with a Google Fonts CSS import.
- Use a supplied, self-contained **GLB** quadcopter asset for the hero. Implementation is blocked on final 3D integration until the user uploads that file; it will be normalized and stored as `public/models/drone.glb`.
- Render the GLB with Three.js through React Three Fiber, rather than approximating the drone with CSS/SVG.
- Treat telemetry as deterministic prototype data, not a real backend or flight-controller integration.
- Use only the supplied palette as source colors. Alpha, gradients, and lighter/darker tonal derivatives will be generated from those colors in CSS; no unrelated source colors will be introduced.

## Dependencies and Asset Contract

1. Add compatible current versions of:
   - `three`
   - `@react-three/fiber`
   - `@react-three/drei`
2. Do not add a general component or icon library. Build a small set of local SVG icons with rounded strokes so the interface stays visually consistent with SF Symbols without relying on proprietary assets.
3. Place the uploaded model at `public/models/drone.glb`.
4. Validate the GLB before integration:
   - It must include all textures/materials or use texture paths supplied alongside it.
   - The model should be web-optimized; if it is excessively large, compress geometry/textures without visibly degrading the 1440×900 hero.
   - Identify its forward/up axes and propeller node names when present.
   - Recenter its bounding box at the scene origin and calculate a stable display scale in code so source-unit differences do not affect layout.
   - Preserve model attribution/license metadata outside the visual UI if the supplied asset requires it.

## Visual System

### Color tokens

Define semantic CSS variables in `src/index.css` for both themes:

- `--accent-primary: #5D3BC3`
- `--accent-secondary: #7F8FD4`
- `--accent-highlight: #B8A7E8`
- `--surface-base: #F1F0F5`
- `--status-warning: #F4C95D`
- `--status-critical: #E96A5B`
- `--status-success: #9BD6C0`
- `--tag-soft: #E8B6C7`

Add semantic derivatives for page background, primary/secondary text, glass fill, hairline border, elevation, grid dots, glow, and muted content. Light mode will use `#F1F0F5` as its base. Dark mode will derive deep values from `#5D3BC3` with CSS relative-color/brightness operations, while foregrounds and borders use permitted light palette values and opacity. Warning, error, and success colors will be reserved for their semantic states.

### Typography and spacing

- Import Inter and Space Mono before the Tailwind import in `src/index.css`.
- Map Tailwind v4 `--font-sans` to Inter and `--font-mono` to Space Mono.
- Use a compact but clear type hierarchy: strong display labels, smaller supporting labels, and monospaced telemetry values with tabular numerals.
- Use an 8 px spacing grid throughout, with 4 px only for optical/icon micro-adjustments.
- Use 20–28 px card radii, pill controls for status/actions, 1 px translucent hairlines, restrained shadows, and backdrop blur.
- Keep focus rings visible, meet readable contrast in both themes, and never communicate status by color alone.

### Background and depth

- Add a quiet dot-matrix/grid field behind the interface with low-opacity palette colors.
- Add a large radial lavender/purple glow behind the model and a soft elliptical ground-shadow ring below it.
- Keep side cards visually subordinate through lower contrast and restrained blur; the model remains the highest-contrast, largest element.

## Application State and Data Model

Create explicit TypeScript unions and configuration maps:

- `ThemeMode = "light" | "dark"`
- `Scenario = "normal" | "lowBattery" | "missionFailure" | "telemetryLoss" | "missionComplete"`
- `SpeedLevel = "low" | "medium" | "high"`
- `FlightControlState = "running" | "paused" | "returning" | "emergency"`
- `WarningState = "default" | "active" | "dismissed"`

Centralize deterministic scenario data rather than scattering literals through components. Each scenario defines battery state, telemetry availability, mission result/progress, active banners, altitude, velocity, attitude, and affected panels.

Scenario behavior:

- **Normal flight:** healthy battery, live GPS/IMU/radio, progress underway, no banner.
- **Low battery:** battery below 30%, warning banner active, amber gauge and pulse, otherwise live telemetry.
- **Mission failure:** critical banner with View details and Retry, failed mission summary, red mission panel state.
- **Telemetry loss:** banner names the lost stream (GPS by default); Position card dims, uses a striped no-signal layer, and replaces affected values with `--`.
- **Mission complete:** success mission summary with duration, distance, completed waypoints, and battery used; controls reflect completion.

The state switcher resets data to the selected scenario. Dismissed banners animate away and can be restored by reselecting the scenario. Retry returns mission failure to an active mission state. View details expands concise failure context inside the mission panel rather than opening a new route.

## Layout

### Desktop canvas

- Create a 1440×900 composition that fills the preview viewport and preserves the 16:10 dashboard layout.
- Use a full-bleed shell with an 88 px top region, side columns, and a bottom control safe area.
- Anchor the hero viewport to the literal 50%/50% of the canvas, independent of unequal side-column widths.
- Use approximately 280–304 px for the left stack and 320–344 px for the right stack, with generous gaps around a central clear zone.
- At narrower preview widths, proportionally tighten side widths and spacing while preserving usability; below the intended desktop breakpoint, allow a minimum canvas/controlled overflow rather than collapsing the mission-control composition into a phone layout.

### Top bar

Build a translucent top bar containing:

- Drone name and ID
- Connected status
- GPS fix/satellite status
- Signal strength
- Flight mode chip (Auto)
- Live clock
- Compact prototype controls for scenario and theme in a visually quiet trailing area

Use accessible labels/tooltips for icon-only controls and keep the bar on one line at the target size.

### Left column

1. **Battery card**
   - SVG ring gauge with percentage center label.
   - Voltage and estimated flight time below/beside it.
   - Healthy/success, below-30% warning, and below-15% critical semantics.
   - Low-battery scenario adds a soft amber pulse without harming text legibility.
2. **Position card**
   - Latitude, longitude, satellite count, fix quality, and home distance.
   - Rounded SVG mini-map with route path, waypoint dots, home marker, and drone marker.
   - Telemetry-loss state dims live content, outputs `--`, and overlays a labeled striped no-signal treatment.
3. **Mission statistics card**
   - A clean 2×3 grid for elapsed time, distance, waypoints, average speed, max altitude, plus a compact status/remaining metric to fill the sixth cell coherently.

### Center hero

Create `DroneViewport` as the focal region:

- R3F Canvas with transparent background, physically plausible soft key/fill/rim lights, contact shadow, and conservative DPR/performance settings.
- GLB centered and scaled from its bounding box.
- Apply roll, pitch, and yaw transforms from scenario telemetry and smoothly interpolate changes.
- If propeller nodes can be identified, rotate them independently; otherwise place four subtle translucent rotor-blur discs at measured rotor positions after inspecting the supplied model.
- Render three thin, distinct attitude arcs around the hero with labels for Roll `+4.2°`, Pitch `-1.8°`, and Yaw `128°`; keep them sparse and behind labels so they do not obscure the model.
- Add a compact axis gizmo in the lower corner of the viewport.
- Add a speed pill and motion streak layer. Low/medium/high speed modifies streak count, length, opacity, rotor blur, and movement cadence.
- Do not enable free orbit controls; this is an instrument panel, not a model viewer. A very subtle pointer-reactive parallax is acceptable if it does not conflict with telemetry attitude.
- Provide a palette-consistent loading indicator while the GLB initializes and a clear non-crashing asset error state if loading fails.

### Right column

1. **Altitude visualizer**
   - Tall glass card with a 0–40 cm scale, ticks every 5 cm, ground line, soft sky/cloud illustration, and live monospaced readout.
   - Flat SVG drone marker moves vertically according to altitude.
   - Running mode smoothly oscillates within a small realistic band around the scenario target with eased keyframes; paused mode freezes it.
   - Add a dotted trailing line whose length follows the marker and degrades gracefully with reduced motion.
2. **Mission panel**
   - Mission picker with Perimeter Scan, Waypoint Survey, and Return & Land; each option has a tiny route thumbnail.
   - Progress state includes percentage, ETA, linear bar, and waypoint stepper for complete/current/upcoming points.
   - Complete state uses success styling and key result metrics.
   - Failed state uses critical styling, failure context, View details, and Retry.

### Bottom dock

- Floating Apple Dock-inspired control bar centered at the bottom.
- Start, Pause, Return Home, and Emergency Stop controls with local rounded-line icons and text labels/tooltips.
- Controls update `FlightControlState`, altitude animation, status copy, and available actions.
- Emergency Stop is visually distinct with `#E96A5B`, requires a second confirmation click within a short interval to reduce accidental activation, and has a clear armed state.
- Keep the dock clear of the model and ground shadow.

## Reusable Component Library in Code

Create focused local primitives and dashboard components, using typed props and variants:

- `GlassCard`
- `IconButton` / `DockButton`
- `StatusChip`
- `SegmentedControl`
- `Metric`
- `GaugeRing`
- `WarningBanner`
- `SignalBars`
- `MiniMap`
- `NoSignalOverlay`
- `MissionStepper`
- `RouteThumbnail`
- `DroneViewport`
- `AltitudeVisualizer`

`WarningBanner` will explicitly support default/active/dismissed visual states and warning/critical severities. Cards, buttons, chips, and gauges will consume semantic CSS variables rather than hard-coded one-off colors. Keep components colocated under `src/components/` and shared scenario types/data under `src/data/` or `src/lib/`; do not add Storybook for this single-screen prototype.

## Animation and Interaction Details

- Use CSS transitions/keyframes for cards, banners, glows, rotor overlay, altitude marker, progress, and dock states.
- Use R3F frame interpolation for attitude and model motion.
- Warning banners slide down from beneath the top bar with opacity and spring-like easing; multiple banners stack with 8 px gaps.
- Scenario/theme changes crossfade surfaces and interpolate applicable gauges/progress/attitude rather than hard-cutting.
- Altitude movement uses a smooth rise/hold/descend loop with dotted trail.
- Speed-level changes smoothly alter streak intensity and rotor speed.
- Pause freezes altitude/propeller progression; Start resumes; Return Home changes mission selection/progress copy; Emergency Stop freezes motion and shows a critical status.
- Respect `prefers-reduced-motion`: disable looping parallax/streak movement and replace large slide/tilt transitions with short opacity changes while retaining current-state clarity.

## Accessibility

- Use semantic landmarks and real buttons/select controls with accessible names.
- Provide keyboard access and visible focus treatment for all scenario, theme, mission, warning, and flight controls.
- Add `aria-live` regions for warnings and mission/control status, without announcing continuously changing altitude every frame.
- Include text/icon labels alongside warning colors.
- Ensure touch/click targets are at least 40–44 px despite the dense desktop composition.
- Mark decorative SVG/grid/arc layers as hidden from assistive technology.

## Planned File Changes

- `package.json` / `pnpm-lock.yaml`: add the Three.js rendering dependencies.
- `public/models/drone.glb`: supplied user asset, normalized at runtime.
- `src/App.tsx`: top-level dashboard composition and prototype state orchestration.
- `src/components/ui/*`: shared card, button, chip, gauge, segmented control, metric, and banner primitives.
- `src/components/dashboard/*`: top bar, side cards, hero viewport, altitude visualizer, mission panel, and control dock.
- `src/components/icons.tsx`: local rounded-stroke SVG icon set.
- `src/data/scenarios.ts`: typed scenario fixtures and mission definitions.
- `src/types.ts`: shared state and component types.
- `src/index.css`: Google Font import, Tailwind import, theme tokens, global canvas rules, reusable effects, and animation/reduced-motion styles.

The exact number of component files may be consolidated where a split would add ceremony without improving reuse, but the state/data, hero renderer, and major dashboard regions should remain separate.

## Verification

After implementation and after the GLB is available:

1. Run the repository formatter through `pnpm format` and review that only intended files changed.
2. Run `pnpm build`; resolve all TypeScript and Vite errors.
3. Inspect the existing hot-reload preview at 1440×900; do not start another dev server.
4. Check each of the five scenarios in both light and dark modes.
5. Check low/medium/high speed variants and confirm streak/rotor intensity changes.
6. Confirm roll/pitch/yaw changes visibly affect the model and attitude labels/arcs.
7. Confirm altitude rise/descend, pause/resume, and dotted trail behavior.
8. Confirm banner activation, stacking, dismissal, Retry, and View details behavior.
9. Confirm telemetry loss replaces affected values with `--` and adds the correct no-signal overlay without affecting unrelated cards.
10. Confirm healthy/warning/critical battery thresholds and mission success/failure summaries.
11. Keyboard-test every interactive control and verify focus visibility and live-region behavior.
12. Emulate reduced motion and confirm loops/transforms are suppressed appropriately.
13. Inspect browser console only if a concrete preview failure appears; use `figma logs` only for such a failure.
14. Verify the model loads without missing texture requests and remains centered at the target aspect ratio.

## Implementation Gate

The UI structure, local design system, and prototype state logic are fully specified, but the hero cannot satisfy the confirmed “realistic 3D GLB” direction until the user uploads the GLB asset. Once supplied, fetch the attachment by its provided ID, place it at `public/models/drone.glb`, inspect its nodes/materials/bounds, and then implement the plan end to end.
