"""Fly to each target with A*, hover 3 seconds, move on, then return home.

All positions are in meters, measured from where the drone takes off (0, 0).
Place the drone facing +x; +y is to its RIGHT. (The Crazyflie itself uses
+y = left, so y is flipped only when sending commands to it.) Needs the Flow deck.

Use the values below, or override them from the terminal:
    uv run python -m algorithms.astrophage_collection_script --target 1.0 0.5 --target 0.0 1.0
        --obstacle 0.4 0.2 0.6 0.8
Add --dry-run to print the route without flying.
"""

import argparse
import heapq
import time

TARGETS = [(1.0, 1.0)]
# Each obstacle is (x_min, y_min, x_max, y_max).
OBSTACLES = [(0.49, 0.49, 0.51, 0.51), (0.99, 0.0, 1.03, 0.5)]
AREA = (0, 2, 0, 2)  # (x_min, x_max, y_min, y_max)
CELL = 0.1
CLEARANCE = 0.15
HEIGHT = 0.3
SPEED = 0.3
HOVER_S = 3.0
URI = "radio://0/80/2M/E7E7E7E7E7"


def to_cell(x, y):
    return round((x - AREA[0]) / CELL), round((y - AREA[2]) / CELL)


def to_meters(cell):
    return AREA[0] + cell[0] * CELL, AREA[2] + cell[1] * CELL


def is_blocked(cell, obstacles):
    x, y = to_meters(cell)
    for x_min, y_min, x_max, y_max in obstacles:
        dx = max(x_min - x, 0, x - x_max)
        dy = max(y_min - y, 0, y - y_max)
        if (dx * dx + dy * dy) ** 0.5 < CLEARANCE:
            return True
    return False


def astar(start, goal, obstacles):
    """Shortest up/down/left/right path between cells, or None."""
    width, height = to_cell(AREA[1], AREA[3])
    frontier = [(0, start)]
    came_from = {start: None}
    cost = {start: 0}
    while frontier:
        _, cell = heapq.heappop(frontier)
        if cell == goal:
            path = []
            while cell is not None:
                path.append(cell)
                cell = came_from[cell]
            return path[::-1]
        x, y = cell
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nxt[0] <= width and 0 <= nxt[1] <= height):
                continue
            if is_blocked(nxt, obstacles):
                continue
            new_cost = cost[cell] + 1
            if new_cost < cost.get(nxt, float("inf")):
                cost[nxt] = new_cost
                came_from[nxt] = cell
                manhattan = abs(goal[0] - nxt[0]) + abs(goal[1] - nxt[1])
                heapq.heappush(frontier, (new_cost + manhattan, nxt))
    return None


def corners(path):
    """Keep only the cells where the path turns, plus the last one."""
    kept = []
    for i in range(1, len(path)):
        last = i == len(path) - 1
        if last or (path[i][0] - path[i - 1][0], path[i][1] - path[i - 1][1]) != (
            path[i + 1][0] - path[i][0],
            path[i + 1][1] - path[i][1],
        ):
            kept.append(to_meters(path[i]))
    return kept


def plan(targets, obstacles):
    """Return a list of legs; each leg is the waypoints to one stop."""
    legs = []
    here = to_cell(0.0, 0.0)
    for stop in list(targets) + [(0.0, 0.0)]:
        goal = to_cell(*stop)
        if is_blocked(goal, obstacles):
            raise SystemExit(f"Target {stop} is inside or too close to an obstacle.")
        path = astar(here, goal, obstacles)
        if path is None:
            raise SystemExit(f"No path to {stop}.")
        legs.append((stop, corners(path)))
        here = goal
    return legs


def fly(legs):
    import cflib.crtp
    from cflib.crazyflie import Crazyflie
    from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
    from cflib.positioning.position_hl_commander import PositionHlCommander
    from cflib.utils.reset_estimator import reset_estimator

    cflib.crtp.init_drivers()
    print(f"Connecting to {URI} ...")
    with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
        print("Connected.")
        if not int(scf.cf.param.get_value("deck.bcFlow2")):
            raise SystemExit(
                "Flow deck not detected. Reseat it and power-cycle the drone."
            )
        print("Finding position: keep the drone still on the floor...")
        reset_estimator(scf)  # makes the current spot (0, 0); waits until it settles
        scf.cf.platform.send_arming_request(True)
        time.sleep(1.0)
        # Takes off on entering the block and lands on leaving it.
        with PositionHlCommander(
            scf,
            default_height=HEIGHT,
            default_velocity=SPEED,
            controller=PositionHlCommander.CONTROLLER_PID,
        ) as pc:
            for i, (stop, waypoints) in enumerate(legs):
                for x, y in waypoints:
                    pc.go_to(x, -y)  # our +y is right; Crazyflie's +y is left
                if i < len(legs) - 1:
                    print(f"Hovering at {stop} for {HOVER_S:g} s")
                    time.sleep(HOVER_S)
            print("Home, landing")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--target", type=float, nargs=2, action="append", metavar=("X", "Y")
    )
    parser.add_argument(
        "--obstacle",
        type=float,
        nargs=4,
        action="append",
        metavar=("X_MIN", "Y_MIN", "X_MAX", "Y_MAX"),
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="print the route, do not fly"
    )
    args = parser.parse_args()

    targets = [tuple(t) for t in args.target] if args.target else TARGETS
    obstacles = [tuple(o) for o in args.obstacle] if args.obstacle else OBSTACLES
    legs = plan(targets, obstacles)

    for stop, waypoints in legs:
        route = " -> ".join(f"({x:.2f}, {y:.2f})" for x, y in waypoints)
        print(f"To {stop}: {route}")
    if not args.dry_run:
        fly(legs)


if __name__ == "__main__":
    main()
