"""Optional saved route figures; importing this module does not load Matplotlib."""

from pathlib import Path


def route_figure(original_grid, planning_grid, start, goal, route):
    """Build a figure in grid-cell coordinates without opening a GUI window."""
    try:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        from matplotlib.patches import Rectangle
    except ImportError as exc:
        raise RuntimeError(
            "Plotting needs Matplotlib. Install with: "
            "python -m pip install -r algorithms/requirements-grid-plot.txt"
        ) from exc

    figure = Figure(figsize=(7, 5))
    FigureCanvasAgg(figure)
    axes = figure.subplots()
    # Adapt the existing plot_runs rectangle/equal-axis/Agg conventions to
    # static cells. Do not import its simulator, telemetry, or flight adapter.
    for cells, color, label in (
        (original_grid.blocked, "#a63232", "Obstacle"),
        (planning_grid.blocked - original_grid.blocked, "#edbe72", "Clearance exclusion"),
    ):
        for index, (x, y) in enumerate(sorted(cells)):
            axes.add_patch(Rectangle(
                (x - 0.5, y - 0.5), 1, 1, facecolor=color, edgecolor="#555555",
                label=label if index == 0 else "_nolegend_",
            ))
    if route is not None:
        axes.plot([cell[0] for cell in route], [cell[1] for cell in route],
                  "o-", color="#2463a0", label="Planned route")
    axes.scatter(*start, marker="^", s=100, color="#16713c", label="Start", zorder=4)
    axes.scatter(*goal, marker="*", s=150, color="#772f96", label="Goal", zorder=5)
    title = "Planned route (offline)" if route is not None else "Planned route (offline): No route"
    axes.set_title(title)
    axes.set_xlabel("Grid x (cells)")
    axes.set_ylabel("Grid y (cells)")
    axes.set_xlim(-0.5, planning_grid.width - 0.5)
    axes.set_ylim(-0.5, planning_grid.height - 0.5)
    axes.set_xticks(range(planning_grid.width))
    axes.set_yticks(range(planning_grid.height))
    axes.set_aspect("equal")
    axes.grid(alpha=0.2)
    axes.legend()
    figure.tight_layout()
    return figure


def save_route_plot(path, original_grid, planning_grid, start, goal, route):
    """Save a PNG to a new file; preserve existing files and close figure data."""
    path = Path(path)
    if path.suffix.lower() != ".png":
        raise ValueError("plot output must use a .png filename")
    figure = route_figure(original_grid, planning_grid, start, goal, route)
    try:
        with path.open("xb") as output:
            figure.savefig(output, format="png", dpi=140)
    finally:
        figure.clear()
