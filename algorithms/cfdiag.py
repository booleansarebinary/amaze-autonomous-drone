#!/usr/bin/env python3
"""
cfdiag.py -- find out WHICH layer of the Crazyflie connection is broken.

"It won't connect" covers at least six different failures that need different
fixes. This walks them in order and stops at the first one that breaks, so you
get a specific cause instead of a timeout.

    python3 cfdiag.py
    python3 cfdiag.py --uri radio://0/80/2M/E7E7E7E7E7

Layers tested:
    1. cflib importable
    2. USB: is a Crazyradio dongle visible to the OS at all?
    3. Driver init
    4. Scan: which Crazyflies are on the air?
    5. Connect to one
    6. Read firmware, battery and deck parameters
"""

from __future__ import annotations

import argparse
import sys
import time

BITCRAZE_VID = 0x1915

OK = "  [ ok ]"
NO = "  [FAIL]"
HM = "  [ ?? ]"


def layer_1_import():
    print("\n1. cflib import")
    try:
        import cflib
        import cflib.crtp  # noqa: F401
        ver = getattr(cflib, "__version__", "unknown")
        print(f"{OK} cflib {ver}")
        return True
    except ImportError as exc:
        print(f"{NO} {exc}")
        print("       pip install cflib")
        print("       If you installed it, check you are in the same venv:")
        print(f"       current interpreter is {sys.executable}")
        return False


def layer_2_usb():
    """Is the dongle physically visible? This separates 'no radio' from
    'radio present but no permission', which look identical from a scan."""
    print("\n2. Crazyradio USB visibility")
    try:
        import usb.core
    except ImportError:
        print(f"{HM} pyusb not importable, skipping this check")
        print("       pip install pyusb   (macOS also needs: brew install libusb)")
        return None

    try:
        devices = list(usb.core.find(find_all=True, idVendor=BITCRAZE_VID))
    except Exception as exc:
        print(f"{HM} USB enumeration unavailable: {exc}")
        if "backend" in str(exc).lower():
            print("       pyusb is installed but libusb is not, so pyusb has")
            print("       nothing to talk to. This does NOT affect cflib, which")
            print("       has its own backend -- layers 3-6 below are what")
            print("       matter. To silence it:")
            print("         macOS:  brew install libusb")
            print("         Debian: sudo apt install libusb-1.0-0")
        return None

    if not devices:
        print(f"{NO} no Bitcraze USB device (vendor 0x1915) found")
        print("       The dongle is unplugged, in a dead port, or the OS")
        print("       has not bound a driver to it.")
        print("       Windows: install the driver with Zadig.")
        return False

    print(f"{OK} {len(devices)} Bitcraze device(s) on USB")
    for d in devices:
        try:
            # Reading the manufacturer string requires permission. If this is
            # the step that fails, the dongle is present but your user cannot
            # talk to it -- that is the udev rules problem on Linux.
            name = usb.util.get_string(d, d.iProduct)
            print(f"{OK}   product 0x{d.idProduct:04x}: {name}")
        except Exception as exc:
            print(f"{NO}   product 0x{d.idProduct:04x}: cannot read: {exc}")
            print("       Device is visible but not accessible => PERMISSIONS.")
            print("       Linux: you need udev rules for the Crazyradio.")
            print("       Do NOT just run this with sudo; fix the rules instead,")
            print("       or the same failure returns for every other tool.")
            return False
    return True


def layer_3_drivers():
    print("\n3. Driver init")
    try:
        import cflib.crtp
        cflib.crtp.init_drivers()
        print(f"{OK} drivers initialised")
        return True
    except Exception as exc:
        print(f"{NO} {exc}")
        return False


def layer_4_scan():
    print("\n4. Scan for Crazyflies")
    import cflib.crtp
    try:
        found = cflib.crtp.scan_interfaces()
    except Exception as exc:
        print(f"{NO} scan raised: {exc}")
        return []

    if not found:
        print(f"{NO} no Crazyflies found")
        print("       Dongle works but nothing answered. Check in order:")
        print("        - Crazyflie powered on? (LEDs lit)")
        print("        - Battery charged? A flat battery browns out the radio.")
        print("        - Non-default address/channel? Check in the CF client.")
        print("        - Too far, or a USB3 port desensitising the dongle:")
        print("          try a USB2 port or a short extension cable.")
        return []

    print(f"{OK} {len(found)} found:")
    uris = []
    for uri, comment in found:
        print(f"{OK}   {uri}  {comment}")
        uris.append(uri)
    return uris


def layer_5_connect(uri: str):
    print(f"\n5. Connect to {uri}")
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    try:
        scf = SyncCrazyflie(uri, cf=Crazyflie(rw_cache="./cache"))
        scf.open_link()
        print(f"{OK} link open")
        return scf
    except Exception as exc:
        print(f"{NO} {type(exc).__name__}: {exc}")
        print("       A scan that succeeds but a connect that fails usually")
        print("       means another process already holds the radio -- close")
        print("       the Crazyflie client if it is running.")
        return None


def layer_6_params(scf):
    print("\n6. Firmware, battery and decks")
    cf = scf.cf

    for name, label in [("firmware.revision0", "firmware rev"),
                        ("deck.bcFlow2", "Flow deck v2"),
                        ("deck.bcMultiranger", "Multi-ranger"),
                        ("deck.bcLighthouse4", "Lighthouse"),
                        ("deck.bcDWM1000", "Loco (UWB)")]:
        try:
            value = cf.param.get_value(name, timeout=2.0)
            if name.startswith("deck."):
                mark = OK if int(value) else "  [ -- ]"
                print(f"{mark} {label}: {'present' if int(value) else 'absent'}")
            else:
                print(f"{OK} {label}: {value}")
        except Exception as exc:
            print(f"{HM} {label}: could not read ({exc})")

    try:
        from cflib.crazyflie.log import LogConfig
        holder = {}
        lg = LogConfig(name="vbat", period_in_ms=100)
        lg.add_variable("pm.vbat", "float")
        lg.data_received_cb.add_callback(
            lambda _t, d, _c: holder.update(v=d["pm.vbat"]))
        cf.log.add_config(lg)
        lg.start()
        time.sleep(0.6)
        lg.stop()
        v = holder.get("v")
        if v is not None:
            note = "  <-- LOW, charge before flying" if v < 3.7 else ""
            print(f"{OK} battery: {v:.2f} V{note}")
    except Exception as exc:
        print(f"{HM} battery: could not read ({exc})")


def rank_uri(uri: str) -> int:
    """Lower sorts first. A scan often returns several interfaces and the
    first one is not necessarily usable: channel 0 at 250K frequently answers
    a scan but cannot hold a link. Prefer the Crazyflie's normal 2M radio
    link, then wired USB, and leave 250K until last."""
    if uri.startswith("radio://") and "2M" in uri:
        return 0
    if uri.startswith("usb://"):
        return 1
    if "250K" in uri:
        return 3
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--uri", default=None,
                    help="skip the scan and try this URI directly")
    ap.add_argument("--all", action="store_true",
                    help="keep testing after the first URI that connects")
    args = ap.parse_args(argv)

    print("=" * 62)
    print(" Crazyflie connection diagnostic")
    print("=" * 62)

    if not layer_1_import():
        return 1
    layer_2_usb()
    if not layer_3_drivers():
        return 1

    if args.uri:
        candidates = [args.uri]
    else:
        candidates = sorted(layer_4_scan(), key=rank_uri)
    if not candidates:
        print("\nStopped: nothing to connect to.")
        return 1

    if len(candidates) > 1:
        print(f"\n   trying in order: {', '.join(candidates)}")

    working = []
    for uri in candidates:
        scf = layer_5_connect(uri)
        if scf is None:
            continue
        working.append(uri)
        try:
            layer_6_params(scf)
        finally:
            scf.close_link()
            print("   link closed.")
        if not args.all:
            break

    if not working:
        print("\nNo URI held a link.")
        print("  'Too many packets lost' on every one points at the radio")
        print("  environment rather than the code: try a USB2 port or a short")
        print("  extension cable (USB3 ports desensitise the dongle), move")
        print("  closer, and charge the battery.")
        print("  If usb://0 was listed, the wired link bypasses all of that.")
        return 1

    print("\nWorking URI(s): " + ", ".join(working))
    flyable = [u for u in working if u.startswith("radio://")]
    if flyable:
        print("\nFor flight:")
        print(f"    python3 reactive_nav.py --fly --uri {flyable[0]}")
    else:
        print("\nOnly a wired link worked. That is fine for checking decks and")
        print("params, but you cannot fly on a tether -- fix the radio first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
