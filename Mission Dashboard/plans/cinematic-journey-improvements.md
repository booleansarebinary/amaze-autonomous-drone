# Cinematic Mission Journey Improvements

## Objective

Finish the second-round improvements to the full-screen mission-selection journey while preserving the existing dashboard and telemetry architecture. The journey should align ships exactly with checkpoints, use the supplied Eridian/Rocky ship geometry, remain dark-only, reserve purple for journey buttons, reveal mission names only after arrival, support accessible zoom controls, and open the dashboard when a mission starts.

## Confirmed Product Decisions

- The final **Classroom** waypoint is an orbital arrival, not a landing.
- A mission’s visual name remains hidden while it is upcoming or in transit and is revealed only once that checkpoint has been reached. Previously reached mission names may remain visible.
- Zoom supports visible buttons and wheel/pinch gestures.
- The purple-only-for-buttons rule applies to the **journey page only**; the dashboard keeps its established purple identity.
- The app remains dark-only.

## Current-State Findings

- `App.tsx` already fixes the dashboard theme to `"dark"`, renders `HomePage` first, switches to the dashboard from `HomePage.onStart`, and provides a dashboard home button that returns to mission selection.
- `HomePage.tsx` already delays `onStart` briefly for button acknowledgement, but its navigation controls expose adjacent mission titles before arrival.
- `MissionJourneyScene.tsx` samples checkpoint and environment positions with `routeCurve.getPoint(...)`, while ship and camera motion use `getPointAt(...)`; this parameterization mismatch causes visible overshoot/misalignment.
- Three supplied STL parts are available under `public/models/journey/` (`rocky-center.stl`, `rocky-connectors.stl`, and `rocky-wings.stl`) but the current Rocky ship is procedural and does not use them.
- The final mission data still uses a `landing` camera preset and landing copy.
- Journey waypoint cards and previous/next controls currently use purple backgrounds, so non-button waypoint labels need a neutral treatment while the clickable journey controls may remain purple.

## Implementation Plan

### 1. Make route progress use one coordinate system

Update `src/components/journey/MissionJourneyScene.tsx` so every progress value in `journeyMissions` and `LAUNCH_PROGRESS` is interpreted as normalized arc length:

- Introduce small shared route helpers for positions and tangents based on `routeCurve.getPointAt(progress)` and `routeCurve.getTangentAt(progress)`.
- Replace `getPoint(...)` calls used by Rocky’s planet, Tau Ceti, the astrophage field, the comet trench, waypoint markers, active route rendering, and any other progress-derived placement.
- Keep route drawing and ship/camera movement on the same helpers so the ship’s settled position, marker center, environment center, and camera target agree exactly.
- Clamp helper input to `[0, 1]` to prevent navigation or interpolation edge cases.
- Preserve the existing easing and arrival threshold, but ensure `FlightController` snaps to the exact target before firing `onArrival`.

### 2. Replace the procedural Rocky ship with the supplied STL assembly

In `MissionJourneyScene.tsx`:

- Load the three local STL parts with React Three Fiber’s `useLoader` and Three’s `STLLoader`; do not add a new dependency.
- Clone/prepare geometries once, compute normals where needed, and center/scale the assembled model as a unit rather than mutating loader-owned geometry repeatedly.
- Assemble the center, connectors, and mirrored/repeated wing components to match the reference: a broad two-level horizontal silhouette, dark central hexagonal body, dense gold ribbed wings, and tall central dorsal/ventral fins.
- Use dark bronze/black metallic materials with restrained warm-gold highlights. Keep warm emissive/light accents subtle enough to preserve surface detail.
- Correct STL axis orientation and model forward direction so the ship follows the route tangent without appearing sideways or inverted.
- Retain the lightweight `ShipFallback` during asset loading and preload all three STL files alongside the existing Hail Mary preload.
- Keep the rendezvous handoff behavior: Rocky’s ship leads initially, scales/fades out near mission 02, and the Hail Mary becomes the active craft.

### 3. Change the final mission from landing to orbit

Update `src/data/journeyMissions.ts` and scene camera behavior:

- Replace the `landing` camera mode with an orbital/arrival mode appropriate for the planet; reuse the existing `orbit` mode if its composition works for both Tau Ceti and the final planet, otherwise add a clearly named `planetOrbit` preset.
- Rewrite the Classroom description to describe arrival in stable orbit rather than atmospheric descent and landing.
- Keep the final checkpoint above the planet’s surface and frame both ship and planet on arrival.
- Add only a subtle post-arrival orbital drift/hold if needed for cinematic life; it must not move the ship away from the selected marker before arrival is registered.
- Update the launch/default camera preset so it no longer relies on a semantically incorrect `landing` value.

### 4. Enforce arrival-gated mission-name visibility

Coordinate `HomePage.tsx` and `MissionJourneyScene.tsx` with explicit arrival state:

- Pass the current `arrived` state into the scene.
- Treat a mission name as revealed when its index is lower than the selected index, or when it is the selected mission and `arrived` is true.
- Before reveal, waypoint markers remain selectable and show only a neutral identifier such as `WAYPOINT 01` plus status; do not include the title in visible text or an exposing tooltip.
- Keep accessible labels meaningful without prematurely announcing hidden story names; use generic waypoint labels before reveal and include the title once revealed.
- In the previous/next dock, replace unrevealed adjacent mission titles with generic labels such as `Waypoint 03`; completed/revealed destinations may show their real titles.
- Keep the mission detail panel entirely arrival-gated as it is now.
- Update the visible progress header and screen-reader live status so travel announcements do not reveal the selected title until arrival.

### 5. Add button, wheel, and pinch zoom

Implement zoom as controlled journey state in `HomePage.tsx`, passed to `MissionJourneyScene`/`CameraRig`:

- Define a bounded zoom range and a stable default, with a small fixed step for buttons.
- Add visible zoom-in and zoom-out buttons in a compact journey overlay, with clear `aria-label`s and disabled states at the limits. Extend the project icon set with matching plus/minus icons if needed rather than using text glyphs.
- Handle wheel zoom only over the 3D canvas, normalize delta direction, clamp the result, and prevent page scrolling while interacting with the canvas.
- Extend pointer tracking from one drag pointer to an active-pointer map so two-pointer distance controls pinch zoom while one pointer continues to rotate/look around.
- Prevent pinch movement from also producing drag rotation or accidental waypoint activation.
- Pass zoom into `CameraRig` and apply it as a multiplier/offset to camera follow distance, with damping so button and gesture changes remain cinematic rather than snapping.
- Preserve the current camera presets and reduced-motion behavior; reduced motion shortens/suppresses animation but does not disable zoom.
- Update the interaction hint to mention zoom without overcrowding the bottom controls.

### 6. Finish dark-only and journey color cleanup

Update `src/journey.css` and the minimal global theme declarations needed in `src/index.css`:

- Remove redundant light-theme assumptions from the journey variables and retain one dark palette.
- Set the root color scheme to dark so browser-native controls and initial paint agree with the app’s fixed theme.
- Keep the journey’s space/environment colors in near-black, cyan/teal, warm gold, coral, and muted glass neutrals.
- Remove purple from non-button journey surfaces, especially waypoint label cards and passive chrome.
- Purple may remain on clickable journey buttons, including Start Mission, previous/next controls, and zoom buttons; states such as success/acknowledgement may continue to use semantic green.
- Preserve contrast, focus-visible outlines, glass separation, and legibility at the project’s minimum 1180×720 viewport and target 1440×900 viewport.
- Remove now-unnecessary journey `[data-theme="dark"]` overrides after consolidating the palette, without changing dashboard-specific purple styling.

### 7. Preserve dashboard transition behavior

In `HomePage.tsx` and `App.tsx`:

- Retain the current Start Mission acknowledgement transition and `onStart` callback into the dashboard.
- Ensure every arrived mission’s Start Mission button opens the dashboard and starts the normal scenario exactly once.
- Preserve the dashboard’s existing return-to-mission-select control and dark theme.
- Avoid introducing routing or changing telemetry/scenario behavior; the existing local `view` state is sufficient.

## Edge Cases and Interaction Rules

- Selecting the current mission after arrival does nothing; selecting another mission immediately clears arrival details and hides that destination’s name until the new arrival.
- Reverse travel uses the same exact arc-length targets and reveals names according to reached history represented by journey position; it must not leak titles for later unreached waypoints.
- Rapid previous/next selections update the flight target safely; only the final active target may trigger the arrival UI.
- Zoom remains clamped under repeated wheel events, trackpad input, button clicks, and pinch gestures.
- Pointer cancellation/loss clears drag and pinch state to avoid a stuck grabbing interaction.
- Reduced-motion users get short/direct travel and camera settling while retaining all selection, reveal, and zoom functionality.
- Asset-load fallback remains usable if an STL or GLB is still loading; failures should not break the HTML controls.

## Verification

Because this is a broad scene and interaction change, run the repository’s prescribed build command after implementation:

1. Run `pnpm build` and require a zero exit status.
2. At 1440×900, manually verify:
   - Rocky’s ship resembles the supplied reference and is correctly oriented.
   - Each craft stops centered on every waypoint with no overshoot.
   - Mission names are absent before arrival and appear only at/after the reached checkpoint.
   - The final Classroom scene holds in orbit and contains no landing language.
   - Start Mission opens the dashboard, and the dashboard home control returns to mission selection.
   - Journey chrome is dark/teal/gold/coral, with purple confined to journey buttons.
3. Verify mouse wheel, zoom buttons, drag, and trackpad/pinch behavior; confirm zoom limits and no accidental page scrolling.
4. Verify keyboard previous/next navigation, button focus styles, generic pre-arrival accessible labels, and arrival live-region text.
5. Verify reduced-motion mode and the minimum supported 1180×720 viewport for overlap or inaccessible controls.

## Expected Files

- `src/components/journey/MissionJourneyScene.tsx`
- `src/components/HomePage.tsx`
- `src/data/journeyMissions.ts`
- `src/journey.css`
- `src/index.css`
- `src/components/Icons.tsx` (only if plus/minus icons are added)
- `src/App.tsx` only if a small transition safeguard is needed; no routing or telemetry redesign is planned.
