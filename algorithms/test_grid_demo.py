"""Command-line navigation checks without sensors, radio, or a drone."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from algorithms.grid_demo import main


class GridDemoTests(unittest.TestCase):
    def run_demo(self, data, start=(0, 0), goal=(2, 0), extra=(), process=False):
        with TemporaryDirectory(prefix="astrophage-demo-test-") as directory:
            map_path = Path(directory) / "map.json"
            map_path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
            arguments = [str(map_path), "--start", *map(str, start), "--goal", *map(str, goal), *extra]
            if process:
                result = subprocess.run(
                    [sys.executable, "-B", "-m", "algorithms.grid_demo", *arguments],
                    cwd=Path(__file__).resolve().parents[1],
                    capture_output=True, text=True, timeout=10,
                )
                return result.returncode, result.stdout, result.stderr
            output, errors = StringIO(), StringIO()
            with redirect_stdout(output), redirect_stderr(errors):
                try:
                    code = main(arguments)
                except SystemExit as exc:
                    code = exc.code
            return code, output.getvalue(), errors.getvalue()

    def test_open_map_shows_planned_route_and_grid_axes(self):
        code, output, errors = self.run_demo({"width": 3, "height": 2, "blocked": []})
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertIn("Planned route (offline)", output)
        self.assertIn("Clearance: not applied", output)
        self.assertIn("x right, y up", output)
        self.assertIn("...\nS*G", output)
        self.assertIn("Steps: 2", output)

    def test_detour_displays_obstacle_and_route_in_a_real_process(self):
        code, output, errors = self.run_demo(
            {"width": 3, "height": 2, "blocked": [[1, 0]]}, process=True
        )
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertIn("***\nS#G", output)
        self.assertIn("[(0, 0), (0, 1), (1, 1), (2, 1), (2, 0)]", output)
        self.assertIn("Steps: 4", output)

    def test_unreachable_goal_has_a_distinct_exit_status(self):
        code, output, errors = self.run_demo(
            {"width": 3, "height": 2, "blocked": [[1, 0], [1, 1]]}
        )
        self.assertEqual(code, 1)
        self.assertEqual(errors, "")
        self.assertIn(".#.\nS#G", output)
        self.assertIn("No planned route exists", output)
        self.assertNotIn("Steps:", output)

    def test_start_at_goal_uses_a_shared_marker(self):
        code, output, _ = self.run_demo({"width": 1, "height": 1}, goal=(0, 0))
        self.assertEqual(code, 0)
        self.assertIn("\nB\n", output)
        self.assertIn("B=start and goal", output)
        self.assertIn("Steps: 0", output)

    def test_invalid_maps_are_reported_without_tracebacks(self):
        for data in [
            "{", [], {"height": 2}, {"width": True, "height": 2},
            {"width": 3, "height": 2, "blocked": "1,0"},
            {"width": 3, "height": 2, "blocked": [[1]]},
            {"width": 3, "height": 2, "blocked": [[[0], 0]]},
            {"width": 3, "height": 2, "blocked": [[3, 0]]},
            {"width": 3, "height": 2, "unknown": 1},
        ]:
            with self.subTest(data=data):
                code, output, errors = self.run_demo(data)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", errors)
                self.assertNotIn("Traceback", errors)

    def test_invalid_endpoints_are_distinct_from_unreachable_goals(self):
        data = {"width": 3, "height": 2, "blocked": [[1, 0]]}
        for start, goal in [((1, 0), (2, 0)), ((0, 0), (1, 0)), ((-1, 0), (2, 0))]:
            with self.subTest(start=start, goal=goal):
                code, output, errors = self.run_demo(data, start, goal)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", errors)

    def test_supplied_clearance_reuses_existing_inflation(self):
        data = {"width": 11, "height": 7,
                "blocked": [[x, y] for x in range(3, 8) for y in (2, 4)]}
        flags = ["--cell-size-m", "0.25", "--footprint-radius-m", "0.1", "--margin-m", "0.05"]
        code, output, errors = self.run_demo(data, (1, 3), (9, 3), flags)
        self.assertEqual(code, 1)
        self.assertEqual(errors, "")
        self.assertIn("radius 0.1 m + margin 0.05 m", output)
        self.assertIn("No planned route exists", output)

    def test_partial_or_invalid_clearance_configuration_is_rejected(self):
        data = {"width": 3, "height": 2}
        for flags in [
            ["--cell-size-m", "0.25"],
            ["--cell-size-m", "0.25", "--footprint-radius-m", "-1", "--margin-m", "0"],
        ]:
            with self.subTest(flags=flags):
                code, output, errors = self.run_demo(data, extra=flags)
                self.assertEqual(code, 2)
                self.assertEqual(output, "")
                self.assertIn("error:", errors)

    def test_missing_map_is_reported_without_a_traceback(self):
        with TemporaryDirectory(prefix="astrophage-demo-missing-") as directory:
            missing_path = Path(directory) / "missing.json"
            errors = StringIO()
            with redirect_stderr(errors), self.assertRaises(SystemExit) as result:
                main([str(missing_path), "--start", "0", "0", "--goal", "1", "0"])
            self.assertEqual(result.exception.code, 2)
            self.assertIn("error:", errors.getvalue())
            self.assertNotIn("Traceback", errors.getvalue())

    def test_text_mode_does_not_import_matplotlib(self):
        original_import = __import__

        def without_matplotlib(name, *args, **kwargs):
            if name == "matplotlib" or name.startswith("matplotlib."):
                raise ImportError("optional plotting library unavailable")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=without_matplotlib):
            code, output, errors = self.run_demo({"width": 3, "height": 2})
        self.assertEqual(code, 0)
        self.assertIn("Steps: 2", output)
        self.assertEqual(errors, "")

    def test_requested_plot_reports_missing_optional_dependency(self):
        original_import = __import__

        def without_matplotlib(name, *args, **kwargs):
            if name == "matplotlib" or name.startswith("matplotlib."):
                raise ImportError("optional plotting library unavailable")
            return original_import(name, *args, **kwargs)

        with TemporaryDirectory(prefix="astrophage-plot-missing-") as directory:
            destination = Path(directory) / "plot.png"
            with patch("builtins.__import__", side_effect=without_matplotlib):
                code, output, errors = self.run_demo(
                    {"width": 3, "height": 2}, extra=["--plot", str(destination)]
                )
            self.assertEqual(code, 2)
            self.assertEqual(output, "")
            self.assertIn("requirements-grid-plot.txt", errors)
            self.assertFalse(destination.exists())

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional Matplotlib not installed")
    def test_plot_option_saves_real_pngs_without_changing_route_exit_codes(self):
        from PIL import Image

        with TemporaryDirectory(prefix="astrophage-plot-cli-") as directory:
            for blocked, expected_code in [([[1, 0]], 0), ([[1, 0], [1, 1]], 1)]:
                with self.subTest(blocked=blocked):
                    destination = Path(directory) / f"route-{expected_code}.png"
                    code, output, errors = self.run_demo(
                        {"width": 3, "height": 2, "blocked": blocked},
                        extra=["--plot", str(destination)], process=True,
                    )
                    self.assertEqual(code, expected_code)
                    self.assertEqual(errors, "")
                    self.assertIn("Plot saved:", output)
                    with Image.open(destination) as picture:
                        self.assertEqual(picture.format, "PNG")
                        self.assertGreater(picture.width, 100)
                        self.assertGreater(picture.height, 100)
                        picture.verify()


if __name__ == "__main__":
    unittest.main()
