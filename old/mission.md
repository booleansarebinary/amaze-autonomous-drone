# Astrophage collection mission

## Objective

The Crazyflie visits stationary candidate astrophages while navigating around obstacles. An upward-facing ultrasonic sensor at the real astrophage detects an object overhead and reports to the computer through a microcontroller. The computer confirms collection eligibility, stops translational movement while maintaining flight, holds above the station, records collection, triggers a dashboard animation, and returns the drone to its starting position.

This mission replaces the earlier moving-hula-hoop mission. Candidate colors are for human visualization only; the drone does not classify targets by color. Collection is simulated through a dwell and dashboard animation; no physical pickup is required.

## Mission sequence

1. Verify sensor communication, radio connectivity and usable localization.
2. Record a valid measured home position and start a uniquely identified run.
3. Choose and visit candidate stations without using hidden real/fake identity to shortcut the search.
4. Navigate around obstacles and approach each station's designated detection zone.
5. Validate fresh detection evidence from the real station against the expected visit and measured drone position.
6. Cancel search movement, command a position hold, and verify settling above the station.
7. Maintain the configured collection dwell within position and velocity tolerances.
8. Record one authoritative collection event and animate collection on the dashboard.
9. Follow an obstacle-aware route to the recorded home position and complete the configured landing procedure.

## Requirements

- The first engineering milestone is actual sensor measurements and presence status in a terminal, before autonomous mission integration.
- Physical Crazyradio integration is required; simulation alone does not demonstrate the complete mission.
- Positioning must support approach, centering, hold and return. Commanded targets are not evidence of measured position.
- An ultrasonic hit establishes object presence in a beam, not drone identity or precise horizontal centering. Station identity and localization provide context.
- Detection, receipt, commanded hold, verified hold and completed collection remain distinct states.
- Stale, invalid, duplicated or unrelated station events cannot authorize collection.
- A collection requires a continuous qualifying dwell; loss of qualifying evidence interrupts or cancels it according to the documented policy.
- The dashboard displays mission state and cannot authorize collection itself.
- Each mission can produce at most one successful collection event. A no-target result or fault cannot be presented as collection success.
- Measurement, telemetry, command and event data must be recordable and exportable as valid JSON.
- Sensor, communication and localization failures have documented, state-dependent responses.

## Initial operating assumptions and unknowns

The initial navigation design assumes supplied candidate coordinates and a static obstacle map, with a fixed altitude only if the operating volume permits a 2D model. Autonomous discovery of unknown obstacles or stations is additional scope.

The sensor model, microcontroller, electrical interface, usable range, mounting geometry, Crazyflie positioning hardware and flight tolerances remain unconfirmed. Hardware-specific wiring and flight claims depend on verification. The real/fake station arrangement and how station identity is communicated also require confirmation.

## Acceptance evidence

- Repeatable sensor detection of the actual drone at the intended height and offsets, including separately evaluated flight conditions.
- Rejected invalid readings and measured misses, false detections and latency.
- A verified physical radio connection and usable measured localization.
- Obstacle-aware navigation, collection hold/dwell, a single collection animation, and return home demonstrated together.
- Reproducible logs distinguishing automated, simulated, operator-reported and physically verified results.

Numerical acceptance thresholds must be established before acceptance trials. The project is a proposed design; no hardware or full mission verification is implied by this document.
