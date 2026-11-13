"""Planned-route JSON and command-line export behavior; no hardware access."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from algorithms.grid_demo import main
from algorithms.grid_export import save_plan
from algorithms.grid_navigation import Grid


class GridExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(prefix="astrophage-export-test-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.map_path = self.directory / "map.json"
        self.destination = self.directory / "plan.json"

    def run_cli(self, data, start=(0, 0), goal=(2, 0), extra=(), process=False):
        self.map_path.write_text(json.dumps(data), encoding="utf-8")
        arguments = [str(self.map_path), "--start", *map(str, start), "--goal", *map(str, goal),
                     "--export", str(self.destination), *extra]
        if process:
            result = subprocess.run(
                [sys.executable, "-B", "-m", "algorithms.grid_demo", *arguments],
                cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, timeout=10,
            )
            return result.returncode, result.stdout, result.stderr
        output, errors = StringIO(), StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            try:
                code = main(arguments)
            except SystemExit as exc:
                code = exc.code
        return code, output.getvalue(), errors.getvalue()

    def read_plan(self):
        self.assertTrue(self.destination.is_file(), "CLI must write the requested JSON file")
        return json.loads(self.destination.read_text(encoding="utf-8"))

    def test_real_cli_exports_detour_as_planned_grid_data(self):
        code, output, errors = self.run_cli(
            {"width": 3, "height": 2, "blocked": [[1, 0]]}, process=True
        )
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertIn("Plan exported:", output)
        plan = self.read_plan()
        self.assertEqual(plan["schema_version"], 1)
        self.assertEqual(plan["data_kind"], "planned_route")
        self.assertEqual(plan["status"], "route_found")
        self.assertEqual(plan["route"], [[0, 0], [0, 1], [1, 1], [2, 1], [2, 0]])
        self.assertEqual(plan["steps"], 4)
        self.assertEqual((plan["start"], plan["goal"]), ([0, 0], [2, 0]))
        self.assertEqual(plan["map"], {"width": 3, "height": 2, "blocked": [[1, 0]]})
        self.assertEqual(plan["planning_blocked"], [[1, 0]])
        self.assertEqual(plan["movement"], {"directions": 4, "step_cost": 1, "heuristic": "manhattan"})
        self.assertEqual(plan["coordinates"]["units"], "cells")
        self.assertEqual(plan["coordinates"]["order"], "x,y")
        self.assertIsNone(plan["coordinates"]["cell_size_m"])
        self.assertIsNone(plan["coordinates"]["origin_m"])
        self.assertFalse(plan["clearance"]["enabled"])

    def test_no_route_is_distinct_from_a_zero_step_route(self):
        code, output, errors = self.run_cli(
            {"width": 3, "height": 2, "blocked": [[1, 0], [1, 1]]}
        )
        self.assertEqual(code, 1)
        self.assertEqual(errors, "")
        self.assertIn("Plan exported:", output)
        plan = self.read_plan()
        self.assertEqual(plan["status"], "unreachable")
        self.assertIsNone(plan["route"])
        self.assertIsNone(plan["steps"])
        self.destination = self.directory / "zero-step.json"
        code, _, _ = self.run_cli({"width": 1, "height": 1}, goal=(0, 0))
        self.assertEqual(code, 0)
        plan = self.read_plan()
        self.assertEqual((plan["status"], plan["route"], plan["steps"]), ("route_found", [[0, 0]], 0))

    def test_clearance_configuration_and_planning_map_are_preserved(self):
        code, _, errors = self.run_cli(
            {"width": 7, "height": 5}, (1, 2), (5, 2),
            ["--cell-size-m", "0.25", "--footprint-radius-m", "0.1", "--margin-m", "0.05"],
        )
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        plan = self.read_plan()
        self.assertEqual(plan["map"]["blocked"], [])
        self.assertIn([0, 0], plan["planning_blocked"])
        self.assertNotIn([1, 2], plan["planning_blocked"])
        self.assertEqual(plan["coordinates"]["cell_size_m"], 0.25)
        self.assertEqual(plan["coordinates"]["origin_m"], [0.0, 0.0])
        self.assertEqual(plan["clearance"], {"enabled": True, "footprint_radius_m": 0.1, "margin_m": 0.05})
        self.assertEqual(plan["steps"], 4)

    def test_export_works_without_importing_matplotlib(self):
        original_import = __import__

        def without_matplotlib(name, *args, **kwargs):
            if name == "matplotlib" or name.startswith("matplotlib."):
                raise ImportError("optional plotting library unavailable")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=without_matplotlib):
            code, _, errors = self.run_cli({"width": 3, "height": 2})
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertEqual(self.read_plan()["steps"], 2)

    def test_existing_destination_and_input_map_are_never_overwritten(self):
        self.destination.write_text("existing work", encoding="utf-8")
        code, _, errors = self.run_cli({"width": 3, "height": 2})
        self.assertEqual(code, 2)
        self.assertIn("error:", errors)
        self.assertEqual(self.destination.read_text(encoding="utf-8"), "existing work")
        self.destination = self.map_path
        data = {"width": 3, "height": 2}
        code, _, errors = self.run_cli(data)
        self.assertEqual(code, 2)
        self.assertIn("input map", errors)
        self.assertEqual(json.loads(self.map_path.read_text(encoding="utf-8")), data)

    def test_plot_and_export_destinations_must_differ_before_writing(self):
        code, _, errors = self.run_cli(
            {"width": 3, "height": 2}, extra=["--plot", str(self.destination)]
        )
        self.assertEqual(code, 2)
        self.assertIn("must differ", errors)
        self.assertFalse(self.destination.exists())

    def test_missing_parent_directory_reports_an_output_error(self):
        self.destination = self.directory / "missing" / "plan.json"
        code, _, errors = self.run_cli({"width": 3, "height": 2})
        self.assertEqual(code, 2)
        self.assertIn("error:", errors)
        self.assertNotIn("Traceback", errors)
        self.assertFalse(self.destination.exists())

    def test_nonfinite_values_are_rejected_before_creating_a_file(self):
        grid = Grid(1, 1)
        with self.assertRaises(ValueError):
            save_plan(self.destination, grid, grid, (0, 0), (0, 0), [(0, 0)], cell_size_m=math.nan)
        self.assertFalse(self.destination.exists())

    def test_same_plan_produces_deterministic_json(self):
        grid = Grid(4, 3, blocked={(2, 1), (1, 1)})
        route = [(0, 0), (1, 0), (2, 0), (3, 0)]
        other = self.directory / "second.json"
        save_plan(self.destination, grid, grid, (0, 0), (3, 0), route)
        save_plan(other, grid, grid, (0, 0), (3, 0), route)
        self.assertTrue(self.destination.exists())
        self.assertTrue(other.exists())
        self.assertEqual(self.destination.read_bytes(), other.read_bytes())
        self.assertEqual(self.read_plan()["map"]["blocked"], [[1, 1], [2, 1]])

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional Matplotlib not installed")
    def test_plot_and_export_can_be_requested_together(self):
        picture = self.directory / "plan.png"
        code, output, errors = self.run_cli(
            {"width": 3, "height": 2}, extra=["--plot", str(picture)], process=True
        )
        self.assertEqual(code, 0)
        self.assertEqual(errors, "")
        self.assertIn("Plot saved:", output)
        self.assertIn("Plan exported:", output)
        self.assertTrue(picture.read_bytes().startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(self.read_plan()["steps"], 2)


if __name__ == "__main__":
    unittest.main()
