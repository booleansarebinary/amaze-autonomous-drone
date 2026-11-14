
"""

TWO MODES
---------
  --mode motion   (default)  MotionCommander. Relative moves. Needs a Flow deck.
                             Best first flight: nothing depends on a world frame.

  --mode hlc                 High-level commander. Same API the trajectory
                             planner uses. Needs Lighthouse or Loco for
                             reliable absolute positioning, though the relative
                             go_to used here is forgiving.

FIRST FLIGHT CHECKLIST
----------------------
  1. Run with --dry-run first. Nothing connects; it just prints the sequence.
  2. Then run for real WITH THE PROPELLERS REMOVED. Motors should spin up,
     vary, and stop. This catches radio and deck problems safely.
  3. Fit propellers. Clear a 2 x 2 m area. Fly.

    python3 hop.py --dry-run
    python3 hop.py --uri radio://0/80/2M/E7E7E7E7E7
"""

from __future__ import annotations

import argparse
import sys
import time

DEFAULT_URI = "radio://0/80/2M/E7E7E7E7E7"


def describe(height: float, distance: float, speed: float) -> None:
    """Print the sequence without touching hardware."""
    climb = height / 0.5  # MotionCommander climbs at ~0.5 m/s by default
    cruise = distance / speed
    print("\nFlight sequence:")
    print(f"  1. take off  ->  {height:.2f} m            (~{climb:.1f} s)")
    print(f"  2. hover     ->  settle                 (1.0 s)")
    print(f"  3. forward   ->  {distance:.2f} m at {speed:.2f} m/s   (~{cruise:.1f} s)")
    print(f"  4. hover     ->  settle                 (1.0 s)")
    print(f"  5. land      ->  0.00 m                 (~{climb:.1f} s)")
    print(f"\n  total airtime ~{climb * 2 + cruise + 2.0:.1f} s")
    print(f"  clear space needed: {distance + 1.0:.1f} m ahead, {height + 0.5:.1f} m overhead\n")


def check_deck(scf, param_name: str, friendly: str) -> bool:
    """Read a deck-detection parameter. Returns True if the deck is attached."""
    try:
        value = int(scf.cf.param.get_value(param_name, timeout=2.0))
    except Exception:
        print(f"  ! could not read {param_name}; continuing without the check")
        return True
    if value:
        print(f"  {friendly}: detected")
        return True
    print(f"  {friendly}: NOT DETECTED")
    return False


def arm(scf) -> None:
    """Newer firmware requires an explicit arming request; older ignores it."""
    try:
        scf.cf.platform.send_arming_request(True)
        time.sleep(1.0)
        print("  armed")
    except AttributeError:
        pass  # firmware predates the arming API


def fly_motion(scf, height: float, distance: float, speed: float) -> None:
    """Relative flight via MotionCommander.

    Taking off happens on entering the context manager and landing happens on
    exit -- including if an exception is raised, which is the main reason to
    prefer this for a first flight.
    """
    from cflib.positioning.motion_commander import MotionCommander

    if not check_deck(scf, "deck.bcFlow2", "Flow deck v2"):
        print("\n  MotionCommander needs a Flow deck to hold position.")
        print("  Without it the Crazyflie will drift immediately. Aborting.")
        return

    arm(scf)

    with MotionCommander(scf, default_height=height) as mc:
        print(f"  climbing to {height:.2f} m")
        time.sleep(1.0)

        print(f"  forward {distance:.2f} m")
        mc.forward(distance, velocity=speed)
        time.sleep(1.0)

        print("  landing")
    # land() already ran here, on context exit
    time.sleep(1.0)


def fly_hlc(scf, height: float, distance: float, speed: float) -> None:
    """Same maneuver through the high-level commander.

    This is the API the trajectory planner targets, so it is worth confirming it
    works before moving up to polynomial trajectories. Each call is
    fire-and-forget, so we sleep for the duration ourselves.
    """
    cf = scf.cf

    # Older firmware keeps the high-level commander off until asked.
    try:
        cf.param.set_value("commander.enHighLevel", "1")
        time.sleep(0.2)
    except Exception:
        pass

    arm(scf)
    hlc = cf.high_level_commander

    climb_time = max(height / 0.5, 1.5)
    cruise_time = max(distance / speed, 1.0)

    print(f"  taking off to {height:.2f} m over {climb_time:.1f} s")
    hlc.takeoff(height, climb_time)
    time.sleep(climb_time + 0.5)

    print(f"  forward {distance:.2f} m over {cruise_time:.1f} s")
    hlc.go_to(distance, 0.0, 0.0, 0.0, cruise_time, relative=True)
    time.sleep(cruise_time + 0.5)

    print(f"  landing over {climb_time:.1f} s")
    hlc.land(0.0, climb_time)
    time.sleep(climb_time + 0.5)

    hlc.stop()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--uri", default=DEFAULT_URI, help="Crazyflie radio URI")
    ap.add_argument("--mode", choices=["motion", "hlc"], default="motion")
    ap.add_argument("--height", type=float, default=0.4, help="hover height [m]")
    ap.add_argument("--distance", type=float, default=0.5, help="forward distance [m]")
    ap.add_argument("--speed", type=float, default=0.3, help="forward speed [m/s]")
    ap.add_argument("--dry-run", action="store_true", help="print the sequence, do not connect")
    args = ap.parse_args(argv)

    describe(args.height, args.distance, args.speed)

    if args.dry_run:
        print("Dry run -- nothing was sent to any hardware.")
        return 0

    try:
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    except ImportError:
        print("cflib is not installed.  pip install cflib", file=sys.stderr)
        return 1

    print(f"Connecting to {args.uri} ...")
    cflib.crtp.init_drivers()

    try:
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
            print("  connected")
            if args.mode == "motion":
                fly_motion(scf, args.height, args.distance, args.speed)
            else:
                fly_hlc(scf, args.height, args.distance, args.speed)
    except Exception as exc:
        # A crash mid-flight leaves the motors spinning, so say so loudly.
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("If the Crazyflie is airborne, kill power at the battery.", file=sys.stderr)
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())