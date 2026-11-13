"""Plot content checks using the optional real Matplotlib backend."""

import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from algorithms.grid_navigation import Grid, GridCoordinates, astar, inflate_obstacles
from algorithms.grid_plot import route_figure, save_route_plot


@unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional Matplotlib not installed")
class GridPlotTests(unittest.TestCase):
    def test_detour_uses_cell_coordinates_and_shows_obstacle_area(self):
        grid = Grid(3, 2, blocked={(1, 0)})
        figure = route_figure(grid, grid, (0, 0), (2, 0), astar(grid, (0, 0), (2, 0)))
        self.assertIsNotNone(figure)
        self.addCleanup(figure.clear)
        axes = figure.axes[0]
        self.assertIn("Planned route (offline)", axes.get_title())
        self.assertIn("cells", axes.get_xlabel())
        self.assertIn("cells", axes.get_ylabel())
        route_line = next(line for line in axes.lines if line.get_label() == "Planned route")
        self.assertEqual(list(route_line.get_xdata()), [0, 0, 1, 2, 2])
        self.assertEqual(list(route_line.get_ydata()), [0, 1, 1, 1, 0])
        obstacle = axes.patches[0]
        self.assertEqual(obstacle.get_xy(), (0.5, -0.5))
        self.assertEqual((obstacle.get_width(), obstacle.get_height()), (1, 1))
        self.assertLess(axes.get_xlim()[0], axes.get_xlim()[1])
        self.assertLess(axes.get_ylim()[0], axes.get_ylim()[1])

    def test_clearance_exclusions_are_distinct_from_original_obstacles(self):
        original = Grid(7, 5, blocked={(3, 2)})
        planning = inflate_obstacles(GridCoordinates(original, 0.25), 0.1, 0.05)
        figure = route_figure(original, planning, (1, 1), (5, 3), None)
        self.assertIsNotNone(figure)
        self.addCleanup(figure.clear)
        axes = figure.axes[0]
        labels = [text.get_text() for text in axes.get_legend().get_texts()]
        self.assertIn("Obstacle", labels)
        self.assertIn("Clearance exclusion", labels)
        self.assertEqual(len(axes.patches), len(planning.blocked))
        obstacle = next(patch for patch in axes.patches if patch.get_label() == "Obstacle")
        excluded = next(patch for patch in axes.patches if patch.get_label() == "Clearance exclusion")
        self.assertNotEqual(obstacle.get_facecolor(), excluded.get_facecolor())

    def test_unreachable_map_keeps_endpoints_without_a_route_line(self):
        grid = Grid(3, 2, blocked={(1, 0), (1, 1)})
        figure = route_figure(grid, grid, (0, 0), (2, 0), None)
        self.assertIsNotNone(figure)
        self.addCleanup(figure.clear)
        axes = figure.axes[0]
        self.assertIn("No route", axes.get_title())
        self.assertFalse(any(line.get_label() == "Planned route" for line in axes.lines))
        markers = {item.get_label(): item.get_offsets().tolist() for item in axes.collections}
        self.assertEqual(markers["Start"], [[0, 0]])
        self.assertEqual(markers["Goal"], [[2, 0]])

    def test_plot_does_not_overwrite_an_existing_file(self):
        grid = Grid(2, 2)
        with TemporaryDirectory(prefix="astrophage-plot-existing-") as directory:
            destination = Path(directory) / "existing.png"
            destination.write_bytes(b"existing work")
            with self.assertRaises(FileExistsError):
                save_route_plot(destination, grid, grid, (0, 0), (1, 1), [(0, 0), (1, 0), (1, 1)])
            self.assertEqual(destination.read_bytes(), b"existing work")


if __name__ == "__main__":
    unittest.main()
