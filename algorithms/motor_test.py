"""Spin each motor on its own, to find which one is dead.

    *** TAKE THE PROPELLERS OFF BEFORE RUNNING THIS. ***

Three motors spinning means one of four things, and this tells them apart:

  * debris wound round the shaft      -> motor spins by hand with grit/resistance
  * worn-out motor                    -> fault follows the MOTOR when you swap arms
  * broken solder joint / dead driver -> fault stays on the ARM when you swap
  * firmware not commanding it        -> this script would also fail to spin it

The parameter names are read from the Crazyflie's own table rather than
assumed, so it reports what your firmware actually offers.

    python motor_test.py                 spin m1..m4 in turn (direct drive)
    python motor_test.py --power 16000   harder, if a motor is sticky
    python motor_test.py --motor 3       just one
    python motor_test.py --pwm 6         arm and take off for 6 s, logging what
                                         PWM the firmware sends to each motor

The two modes answer different questions. Direct drive asks "can this motor
turn at all". The --pwm mode asks "is the firmware even telling it to" -- if
all four get PWM but only three spin, the fault is electrical or mechanical;
if one stays at zero, the fault is in the firmware or its build.
"""

from __future__ import annotations

import argparse
import sys
import time

URI = 'radio://0/80/2M'
DEFAULT_POWER = 12000      # of 65535. Enough to spin freely, no props fitted.
SPIN_SECONDS = 1.5


def toc_has(cf, name: str) -> bool:
    try:
        return cf.param.toc.get_element_by_complete_name(name) is not None
    except Exception:                               # noqa: BLE001
        return False


def discover(cf) -> dict:
    """Report which test parameters this firmware exposes."""
    found = {
        'enable': 'motorPowerSet.enable' if toc_has(cf, 'motorPowerSet.enable') else None,
        'motors': [f'motorPowerSet.m{i}' for i in range(1, 5)
                   if toc_has(cf, f'motorPowerSet.m{i}')],
        'proptest': 'health.startPropTest' if toc_has(cf, 'health.startPropTest') else None,
    }
    print('  Firmware offers:')
    print(f"    motorPowerSet.enable : {'yes' if found['enable'] else 'NO'}")
    print(f"    motorPowerSet.m1-m4  : {len(found['motors'])} of 4 present")
    print(f"    health.startPropTest : {'yes' if found['proptest'] else 'no'}")
    return found


def spin(cf, found: dict, which: list[int], power: int) -> None:
    enable = found['enable']
    if not enable or len(found['motors']) < 4:
        print('\n  This firmware does not expose motorPowerSet, so individual')
        print('  motors cannot be driven from here. Use cfclient instead.')
        return

    print(f'\n  Spinning each motor at {power} / 65535 for {SPIN_SECONDS:.1f} s.')
    print('  Watch and listen. Note any that stay silent, buzz, or sound rough.\n')
    try:
        cf.param.set_value(enable, '1')
        time.sleep(0.2)
        for i in which:
            name = f'motorPowerSet.m{i}'
            print(f'    M{i} ... ', end='', flush=True)
            cf.param.set_value(name, str(power))
            time.sleep(SPIN_SECONDS)
            cf.param.set_value(name, '0')
            time.sleep(0.4)
            print('done')
    finally:
        for i in range(1, 5):
            try:
                cf.param.set_value(f'motorPowerSet.m{i}', '0')
            except Exception:                       # noqa: BLE001
                pass
        try:
            cf.param.set_value(enable, '0')
        except Exception:                           # noqa: BLE001
            pass
        print('\n  motorPowerSet disabled again.')


def watch_pwm(scf, seconds: float) -> None:
    """Arm, take off (props off!) and log what PWM each motor is commanded.

    This is the test that separates a dead motor from a firmware that never
    asks it to turn.
    """
    from cflib.crazyflie.log import LogConfig
    from cflib.positioning.motion_commander import MotionCommander

    state = {f'm{i}': None for i in range(1, 5)}
    cfg = LogConfig(name='motors', period_in_ms=100)
    present = 0
    for i in range(1, 5):
        try:
            element = scf.cf.log.toc.get_element_by_complete_name(f'motor.m{i}')
        except Exception:                           # noqa: BLE001
            element = None
        if element is not None:
            cfg.add_variable(f'motor.m{i}', element.ctype)
            present += 1
    if present < 4:
        print(f'  only {present} of the 4 motor.mN log variables exist; skipping')
        return

    def on_data(_ts, data, _c):
        for i in range(1, 5):
            state[f'm{i}'] = data.get(f'motor.m{i}')

    scf.cf.log.add_config(cfg)
    cfg.data_received_cb.add_callback(on_data)
    cfg.start()

    print(f'\n  Arming and taking off for {seconds:.0f} s with NO PROPELLERS.')
    print('  Watching the PWM the firmware sends to each motor.\n')
    try:
        with MotionCommander(scf, default_height=0.3):
            finish = time.monotonic() + seconds
            while time.monotonic() < finish:
                row = '  '.join(
                    f"M{i}={state[f'm{i}']:>6}" if state[f'm{i}'] is not None
                    else f'M{i}=  ----' for i in range(1, 5))
                print(f'\r    {row}', end='')
                time.sleep(0.1)
    except KeyboardInterrupt:
        print('\n  interrupted')
    finally:
        cfg.stop()
        print()

    values = [state[f'm{i}'] for i in range(1, 5)]
    if all(v is not None for v in values):
        dead = [i for i, v in enumerate(values, 1) if v == 0]
        if dead:
            print(f'\n  Motors commanded ZERO while the others were driven: '
                  f"{', '.join('M%d' % i for i in dead)}")
            print('  The firmware is not asking them to turn. That is a firmware or')
            print('  build problem, not a dead motor. Check you flashed the official')
            print('  release for the right platform, and both MCUs.')
        else:
            print('\n  All four motors were commanded. If one still did not turn,')
            print('  the fault is mechanical or electrical on that arm.')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--uri', default=URI)
    ap.add_argument('--power', type=int, default=DEFAULT_POWER,
                    help=f'PWM out of 65535 (default {DEFAULT_POWER})')
    ap.add_argument('--motor', type=int, choices=[1, 2, 3, 4],
                    help='test only this motor')
    ap.add_argument('--pwm', type=float, default=0.0, metavar='SECONDS',
                    help='arm and take off (props off) logging commanded motor PWM')
    ap.add_argument('--yes', action='store_true', help='skip the propeller prompt')
    args = ap.parse_args(argv)

    if not args.yes:
        reply = input('Are the PROPELLERS OFF? [y/N] ').strip().lower()
        if reply != 'y':
            print('Take them off first.')
            return 1

    try:
        import cflib.crtp
        from cflib.crazyflie import Crazyflie
        from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    except ImportError:
        print('cflib is not installed:  pip install cflib', file=sys.stderr)
        return 1

    cflib.crtp.init_drivers()
    print(f'Connecting to {args.uri} ...')
    try:
        with SyncCrazyflie(args.uri, cf=Crazyflie(rw_cache='./cache')) as scf:
            cf = scf.cf
            print('  connected')
            found = discover(cf)

            # Some firmware gates the motors behind arming even for this.
            try:
                cf.supervisor.send_arming_request(True)
            except Exception:                       # noqa: BLE001
                try:
                    cf.platform.send_arming_request(True)
                except Exception:                   # noqa: BLE001
                    pass
            time.sleep(1.0)

            if args.pwm > 0:
                watch_pwm(scf, args.pwm)
            else:
                which = [args.motor] if args.motor else [1, 2, 3, 4]
                spin(cf, found, which, args.power)

            try:
                cf.supervisor.send_arming_request(False)
            except Exception:                       # noqa: BLE001
                pass
    except Exception as exc:                        # noqa: BLE001 - operator facing
        print(f'\nCould not talk to the Crazyflie: {exc}', file=sys.stderr)
        return 1

    print("""
  Reading the result
  ------------------
  One motor silent while the other three spin:
      Turn that motor by hand. Grit or resistance means debris on the shaft --
      hair and carpet fibre are the usual culprits, and a pair of tweezers
      fixes it. If it turns freely, swap that motor onto a different arm:
          fault follows the motor  -> the motor is worn out, replace it
          fault stays on the arm   -> broken solder joint or a dead driver
                                      transistor on the board
  A motor that buzzes but does not turn:
      Usually jammed. Same check as above.
  All four spin here but only three spin when flying:
      Not a dead motor. More likely the battery sagging under load, or one
      motor drawing far more current than the others.
""")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
