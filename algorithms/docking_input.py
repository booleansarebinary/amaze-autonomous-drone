"""Prompt for a turn and distance, then run the Crazyflie docking flight."""

from docking import dock


if __name__ == "__main__":
    angle = float(input("Turn angle in degrees (left +, right -): "))
    distance = float(input("Forward distance in meters: "))
    dock(angle, distance)
