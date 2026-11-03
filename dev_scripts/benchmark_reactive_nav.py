"""Reproducible, hardware-free navigation benchmark.

Run from the repository root:
  .venv/bin/python dev_scripts/benchmark_reactive_nav.py
Optionally compare a saved pre-change reactive_nav.py with --baseline PATH.
"""
import argparse
import importlib.util
import json
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from algorithms import reactive_nav as nav


def layouts(trials, seed):
    rng = nav.np.random.default_rng(seed)
    for _ in range(trials):
        world = nav.SimWorld([0, 0], [5, 4])
        for _ in range(int(rng.integers(1, 5))):
            cx, cy = rng.uniform(1, 4), rng.uniform(.5, 3.5)
            wx, wy = rng.uniform(.2, .6), rng.uniform(.3, 1.8)
            world.rects.append(nav.Rect([cx-wx/2, cy-wy/2], [cx+wx/2, cy+wy/2]))
        start = nav.np.array([.5, rng.uniform(.6, 3.4)])
        goal = nav.np.array([4.5, rng.uniform(.6, 3.4)])
        yield world, start, goal


def summary(log):
    return {key: log[key] for key in ('arrived', 'collided', 'duration', 'min_clearance',
                                     'path_length', 'path_ratio')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--trials', type=int, default=150)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--seeds', type=int, nargs='+', help='independent layout seeds; overrides --seed')
    parser.add_argument('--profiles', choices=['sim', 'flight'], nargs='+', default=['sim', 'flight'])
    parser.add_argument('--dt', type=float, default=.05)
    parser.add_argument('--tau', type=float, default=.25)
    parser.add_argument('--sensor-delay', type=float, default=0)
    parser.add_argument('--random-yaw', action='store_true')
    parser.add_argument('--output', type=Path, default=Path('docs/reactive_nav/benchmark.json'))
    args = parser.parse_args()
    if args.trials < 1:
        parser.error('--trials must be positive')
    versions = []
    if args.baseline:
        spec = importlib.util.spec_from_file_location('baseline_nav', args.baseline)
        baseline = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = baseline
        spec.loader.exec_module(baseline)
        versions.append(('before', baseline.ReactiveController, baseline.Gains))
    versions.append(('after', nav.ReactiveController, nav.Gains))
    original = nav.ReactiveController
    seeds = args.seeds or [args.seed]
    results = {'metadata': {'trials_per_seed': args.trials, 'seeds': seeds, 'dt': args.dt,
                            'tau': args.tau, 'sensor_delay': args.sensor_delay,
                            'random_yaw': args.random_yaw, 'radius': .09, 'time_limit': 120,
                            'ranger': 'continuous cone',
                            'controller_sha256': hashlib.sha256(Path(nav.__file__).read_bytes()).hexdigest(),
                            'baseline_sha256': hashlib.sha256(args.baseline.read_bytes()).hexdigest() if args.baseline else None}}
    settings = dict(dt=args.dt, tau=args.tau, sensor_delay=args.sensor_delay)
    try:
        for version, controller, gains_class in versions:
            nav.ReactiveController = controller
            for profile in args.profiles:
                gains = gains_class() if profile == 'sim' else gains_class.flight()
                key = f'{version}_{profile}'
                row = {'fixed': {}, 'random': {'reached': 0, 'collided': 0, 'timeout': 0},
                       'failures': [], 'trials': []}
                results[key] = row
                for name, make in nav.SCENARIOS.items():
                    _, world, start, goal = make()
                    row['fixed'][name] = summary(nav.simulate(world, start, goal, gains, **settings))
                began = time.perf_counter()
                for seed in seeds:
                    yaw_rng = nav.np.random.default_rng(seed + 10000)
                    for trial, (world, start, goal) in enumerate(layouts(args.trials, seed)):
                        yaw = float(yaw_rng.uniform(-nav.math.pi, nav.math.pi)) if args.random_yaw else 0.0
                        log = nav.simulate(world, start, goal, gains, initial_yaw=yaw, **settings)
                        verdict = 'reached' if log['arrived'] else 'collided' if log['collided'] else 'timeout'
                        row['random'][verdict] += 1
                        row['trials'].append(dict(seed=seed, trial=trial, initial_yaw=yaw, **summary(log)))
                        if verdict != 'reached':
                            row['failures'].append({'seed': seed, 'trial': trial, 'verdict': verdict,
                                                    'clearance': log['min_clearance']})
                        if (trial + 1) % 50 == 0:
                            print(key, seed, trial + 1, row['random'], flush=True)
                row['wall_seconds'] = time.perf_counter() - began
                reached = [r for r in row['trials'] if r['arrived']]
                row['median_duration'] = float(nav.np.median([r['duration'] for r in reached])) if reached else None
                row['median_path_length'] = float(nav.np.median([r['path_length'] for r in reached])) if reached else None
    finally:
        nav.ReactiveController = original
    results['sensitivity'] = {}
    for profile in args.profiles:
        for delay, tau in [(0, .25), (.1, .5), (.2, .75)]:
            row = results['sensitivity'][f'{profile},delay={delay},tau={tau}'] = {}
            for name, make in nav.SCENARIOS.items():
                _, world, start, goal = make()
                gains = nav.Gains() if profile == 'sim' else nav.Gains.flight()
                row[name] = summary(nav.simulate(world, start, goal, gains,
                                                dt=1/15, tau=tau, sensor_delay=delay))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    print(f'Results written to {args.output}')


if __name__ == '__main__':
    main()
