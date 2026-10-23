# Astrophage Collection — Mission 1: Adaptive Hoop Lock

## Mission description

The Crazyflie represents a small spacecraft collecting Astrophage inside a moving collection aperture. A person holds an upright hula hoop and moves it gently through a defined test area. The Crazyflie’s objective is to remain near the hoop’s center while the hoop moves, using the drone’s own motion estimates to compensate for its movement and its range sensors to observe the hoop. It should remain inside a validated speed-and-clearance envelope rather than chase every motion regardless of risk.

The technically ambitious part is **adaptive, target-relative flight**: the system must distinguish motion of the hoop from motion of the Crazyflie, estimate the target’s changing position, predict a short distance ahead to account for sensing and radio delay, and maintain a safe centered position. It should also recognize when its measurements are no longer trustworthy, stop tracking rather than continue on stale data, and reacquire the hoop only after observations are consistent again.

This is a proposed mission, not a claim that the current sensors can already observe an arbitrary hoop pose. The first engineering milestone is to prove that the onboard range sensors can reliably detect enough of the hoop to estimate its center and relevant orientation. The Flow deck can estimate the Crazyflie’s motion; it cannot sense the hoop’s motion by itself. If the existing range sensors cannot observe the hoop adequately, the team must constrain the hoop’s orientation/size or add an onboard marker/camera sensor before flight tracking is feasible.

## Mission phases

1. **Safe setup:** verify the radio link and available deck telemetry without arming or sending flight setpoints.
2. **Observe:** while stationary and then in a controlled non-flight sensor test, collect time-stamped range readings as a person moves the hoop. Check whether the readings identify the hoop consistently.
3. **Acquire:** accept a hoop estimate only after enough valid, geometrically consistent observations; record its estimated center, orientation if observable, confidence, and age.
4. **Adaptive center lock:** when explicitly enabled for a supervised test, use the newest hoop estimate and Crazyflie motion telemetry to make bounded corrections toward the hoop center.
5. **Reacquire or safe exit:** if the hoop is lost, stale, too uncertain, too close, or moving beyond the verified envelope, stop chasing it. Attempt bounded reacquisition; if tracking cannot be safely resumed, use the pre-agreed landing/fallback behavior while radio control is still available.

## Success means

- A sensor-only bench test can identify the hoop’s center with repeatable error bounds across the agreed hoop orientations and movement envelope.
- Offline tests show correct coordinate transforms, finite bounded commands, and predictable stale-target and reacquisition behavior.
- A real Crazyradio connection can receive and log telemetry without arming, taking off, or sending flight setpoints.
- A supervised short flight remains within an agreed center-error and clearance limit while the hoop moves within the validated envelope, with timestamps and failures captured in a unique JSONL run log.

Numeric limits for hoop size, center error, speed, acceleration, clearance, and tracking update rate must be agreed after measuring the actual aircraft, hoop, sensor return quality, and control-loop latency. “Adapt regardless of size or motion” is not a safe or technically supportable requirement; this mission adapts within a measured envelope and enters fallback outside it.

## Not part of Mission 1

- Flying through the hoop or crossing its plane.
- Assuming a camera, fiducial marker, motion-capture system, GPS, or additional sensor is installed.
- Changing Crazyflie firmware, onboard PID gains, or arming/failsafe settings before evidence and review.
- Treating simulation, dashboard mock data, or a successful radio connection as proof of safe flight.
