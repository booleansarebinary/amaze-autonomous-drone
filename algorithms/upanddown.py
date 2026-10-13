"""Make a Crazyflie take off, hover briefly, and land.

This Python script runs on a computer connected to a Crazyradio; it is not
installed on the Crazyflie's flight controller. A Flow deck is required for
stable position hold while hovering.
"""

from __future__ import annotations

import argparse
import sys
import time

DEFAULT_URI = "radio://0/80/2M/E7E7E7E7E7"
DEFAULT_HEIGHT_METERS = 0.61  # approximately 2 feet
DEFAULT_HOVER_SECONDS = 3.0


def main(argv: list[str] | None = None) -> int:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--uri", default=DEFAULT_URI, help="Crazyflie radio URI")
	parser.add_argument(
		"--height",
		type=float,
		default=DEFAULT_HEIGHT_METERS,
		help="target height in meters (default: 0.61, about 2 feet)",
	)
	parser.add_argument(
		"--hover-seconds",
		type=float,
		default=DEFAULT_HOVER_SECONDS,
		help="seconds to hover at the target height (default: 3)",
	)
	parser.add_argument(
		"--dry-run",
		action="store_true",
		help="show the flight plan without connecting to the Crazyflie",
	)
	args = parser.parse_args(argv)

	if not 0.1 <= args.height <= 1.0:
		parser.error("--height must be between 0.1 and 1.0 meters")
	if not 0.0 <= args.hover_seconds <= 30.0:
		parser.error("--hover-seconds must be between 0 and 30")

	print("Flight plan:")
	print(f"  Take off to {args.height:.2f} m ({args.height / 0.5:.1f} s approx.)")
	print(f"  Hover at the top for {args.hover_seconds:.1f} s")
	print("  Land")
	print(f"  Radio: {args.uri}")

	if args.dry_run:
		print("Dry run: no radio connection or flight commands were made.")
		return 0

	try:
		import cflib.crtp
		from cflib.crazyflie import Crazyflie
		from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
		from cflib.positioning.motion_commander import MotionCommander
	except ImportError:
		print(
			"cflib is not installed. Install the project dependency with: "
			"python -m pip install cflib",
			file=sys.stderr,
		)
		return 1

	print(
		"\nBefore flying: use a clear indoor area, check the propellers and battery, "
		"and keep people clear."
	)
	try:
		confirmation = input("Type 'fly' to connect and begin: ").strip().lower()
	except (EOFError, KeyboardInterrupt):
		print("\nCancelled.")
		return 1
	if confirmation != "fly":
		print("Cancelled; no flight commands were sent.")
		return 1

	cflib.crtp.init_drivers()
	try:
		with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache="./cache")) as scf:
			print("Connected.")

			# Flow deck parameter names differ between the original and v2
			# decks. Require a confirmed deck rather than risk drifting flight.
			flow_deck_detected = False
			for parameter in ("deck.bcFlow2", "deck.bcFlow"):
				try:
					if int(scf.cf.param.get_value(parameter, timeout=2.0)):
						print(f"Flow deck detected ({parameter}).")
						flow_deck_detected = True
						break
				except Exception:
					continue
			if not flow_deck_detected:
				print(
					"No Flow deck detected. Position hold needs a Flow deck; "
					"aborting before takeoff.",
					file=sys.stderr,
				)
				return 1

			try:
				scf.cf.platform.send_arming_request(True)
				time.sleep(1.0)
			except AttributeError:
				# Older firmware does not expose an explicit arming request.
				pass

			# Entering MotionCommander takes off; leaving it lands, including
			# when the hover is interrupted with Ctrl+C.
			with MotionCommander(scf, default_height=args.height):
				print(f"Hovering at about {args.height:.2f} m...")
				time.sleep(args.hover_seconds)
				print("Landing...")
	except KeyboardInterrupt:
		print("\nInterrupted; the flight context is landing if the link is active.")
		return 130
	except Exception as exc:
		print(f"\nFlight error: {exc}", file=sys.stderr)
		print(
			"Keep clear of the aircraft. If it is still airborne, use the "
			"Crazyflie emergency procedure for your setup.",
			file=sys.stderr,
		)
		return 1

	print("Flight complete.")
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
