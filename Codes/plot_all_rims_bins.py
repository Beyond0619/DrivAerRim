#!/usr/bin/env python3
import argparse
import os
import csv
import colorsys
import math
import random
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
from matplotlib.legend_handler import HandlerTuple
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.ticker as mticker

os.environ.setdefault("XDG_RUNTIME_DIR", ".")

# Paths
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RAW_DATA_ROOT = Path("-")
BASELINE_NAME = "CR"
BASELINE_LABEL = "CR (Closed Rim)"
FIGURES_DIR = SCRIPT_DIR.parent / "Figures"
OUT_FIG = FIGURES_DIR / "all_rims_bins_overlay.jpg"

CM_FONT_RC = {
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman", "CMU Serif", "cmr10", "DejaVu Serif"],
    "font.size": 20,
    "font.weight": "normal",
    "axes.labelsize": 21,
    "mathtext.fontset": "cm",
    "xtick.labelsize": 20,
    "ytick.labelsize": 20,
    "legend.fontsize": 17,
    "axes.formatter.use_mathtext": True,
    "axes.unicode_minus": True,
}
plt.rcParams.update(CM_FONT_RC)

DIMENSIONLESS_UNIT = "[−]"
CR_COLOR = "#e63946"
COLOR_SEED = 20260529
RIM_LINE_WIDTH = 1.2
CR_LINE_WIDTH = 3.2
AXIS_LABEL_SIZE = 21
TICK_LABEL_SIZE = 20
LEGEND_FONT_SIZE = 17
AXIS_LABEL_PAD = 14
TICK_PAD = 8
FIG_SIZE = (20, 8.2)
TIGHT_LAYOUT_PAD = 1.8
CAR_BOX_ASPECT_PAD = 1.12
CD_YLIM = (0.0, 0.3)
CD_YTICK_STEP = 0.05
DELTA_CD_YLIM = (-0.02, 0.02)
DELTA_CD_YTICK_STEP = 0.01

# Binned columns to plot in one figure
PLOT_COLUMNS = [
    ("cd", rf"Accumulated $C_D$ {DIMENSIONLESS_UNIT}"),
    ("delta_cd", rf"Accumulated $\Delta C_D$ {DIMENSIONLESS_UNIT}"),
    ("cd_local", r"Accumulated $C_DA$ [m$^2$]"),
    ("clf_local", r"Accumulated $C_{L,f}A$ [m$^2$]"),
    ("clr_local", r"Accumulated $C_{L,r}A$ [m$^2$]"),
]
OUTPUT_NAME_MAP = {
    "cd": "Cd_Accumulated",
    "delta_cd": "DeltaCd_AlongX",
    "cd_local": "CdA_Accumulated",
    "clf_local": "ClfA_Accumulated",
    "clr_local": "ClrA_Accumulated",
}
COMBINED_CD_CSV_NAME = "Cd_Accumulated_Combined.csv"
# Edit parameters here directly (CLI args can still override).
DEFAULT_RIMS = ""  # e.g. "Rim001,Rim010"; empty means all rims
DEFAULT_METRICS = "cd,delta_cd,cd_local,clf_local,clr_local"
DEFAULT_RIM_START = 1
DEFAULT_RIM_END = 904
DEFAULT_OUTPUT = str(OUT_FIG)
SHOW_LEGEND = True


def rim_index_from_name(name: str):
    digits = "".join(ch for ch in name if ch.isdigit())
    return int(digits) if digits else None


def discover_rims(raw_data_root: Path):
    rims = []
    for rim_dir in sorted(raw_data_root.glob("Rim*")):
        if not rim_dir.is_dir():
            continue
        if rim_index_from_name(rim_dir.name) is None:
            continue
        binned = rim_dir / "NumData/Binned.csv"
        if binned.exists():
            rims.append((rim_dir.name, binned))
    return sorted(rims, key=lambda item: rim_index_from_name(item[0]))


def read_binned_csv(path: Path):
    with path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return {}

    columns = {k: [] for k in reader.fieldnames if k}
    for row in rows:
        for key in columns:
            val = row.get(key, "")
            if val is None or val == "":
                columns[key].append(float("nan"))
            else:
                columns[key].append(float(val))
    return columns


def read_combined_cd_csv(path: Path):
    """Read X,Rim0001,... wide-format accumulated-Cd data."""
    with path.open("r", newline="") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header or len(header) < 2 or header[0].strip() != "X":
            raise ValueError("Combined Cd CSV must start with X and at least one Rim column.")

        rim_names = []
        seen_indexes = set()
        for raw_name in header[1:]:
            name = raw_name.strip()
            rim_index = rim_index_from_name(name)
            if not name.lower().startswith("rim") or rim_index is None:
                raise ValueError(f"Invalid Rim column in combined Cd CSV: {raw_name!r}")
            if rim_index in seen_indexes:
                raise ValueError(f"Duplicate Rim index in combined Cd CSV: {rim_index}")
            seen_indexes.add(rim_index)
            rim_names.append(f"Rim{rim_index:04d}")

        x_values = []
        cd_columns = [[] for _ in rim_names]
        for row_number, row in enumerate(reader, start=2):
            if len(row) != len(header):
                raise ValueError(
                    f"Row {row_number} has {len(row)} columns; expected {len(header)}."
                )
            try:
                numeric_row = [float(value) for value in row]
            except ValueError as exc:
                raise ValueError(f"Row {row_number} contains a non-numeric value.") from exc
            if not all(math.isfinite(value) for value in numeric_row):
                raise ValueError(f"Row {row_number} contains a non-finite value.")

            x_values.append(numeric_row[0])
            for index, value in enumerate(numeric_row[1:]):
                cd_columns[index].append(value)

    if not x_values:
        raise ValueError("Combined Cd CSV contains no data rows.")

    return [
        (rim_name, {"X": x_values, "cd": cd_values})
        for rim_name, cd_values in zip(rim_names, cd_columns)
    ]


def read_vehicle_x_range(vehicle_dim_path: Path):
    if not vehicle_dim_path.exists():
        return None, None
    with vehicle_dim_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        first = next(reader, None)
    if not first:
        return None, None
    if "length_min_x" not in first or "length_max_x" not in first:
        return None, None
    return float(first["length_min_x"]), float(first["length_max_x"])


def read_area_front(vehicle_dim_path: Path):
    if not vehicle_dim_path.exists():
        return None
    with vehicle_dim_path.open("r", newline="") as f:
        reader = csv.DictReader(f)
        first = next(reader, None)
    if not first or "area_front" not in first:
        return None
    try:
        area = float(first["area_front"])
        return area if area > 0 else None
    except Exception:
        return None


def compute_cd_and_accumulated(data, area_front):
    xs = data.get("X", [])
    cda_vals = data.get("cd_local", [])
    if not xs or not cda_vals or len(xs) != len(cda_vals):
        return
    if area_front is None or area_front <= 0:
        return

    cds = []
    for val in cda_vals:
        if math.isfinite(val):
            cds.append(val / area_front)
        else:
            cds.append(float("nan"))
    data["cd"] = cds

    acc = []
    running = 0.0
    prev_x = xs[0]
    prev_cd = cds[0] if math.isfinite(cds[0]) else 0.0
    acc.append(0.0)

    for i in range(1, len(xs)):
        x = xs[i]
        cd = cds[i] if math.isfinite(cds[i]) else prev_cd
        dx = x - prev_x
        # Trapezoidal accumulation along x.
        running += 0.5 * (prev_cd + cd) * dx
        acc.append(running)
        prev_x = x
        prev_cd = cd

    data["cd_accumulated"] = acc


def compute_delta_cd(rim_data, baseline_name, baseline_data):
    """
    Adds data["delta_cd"] for each rim and baseline:
    delta_cd(x) = cd(x) - cd_closed_rim(x).
    """
    if not rim_data or baseline_data is None:
        return

    x_ref = baseline_data.get("X", [])
    ref_cd = baseline_data.get("cd", [])
    n = len(x_ref)
    if n == 0 or len(ref_cd) != n:
        print(f"[SKIP] {baseline_name}: inconsistent X/cd length; delta_cd not computed")
        return

    def has_same_x_grid(data):
        xs = data.get("X", [])
        cds = data.get("cd", [])
        if len(xs) != n or len(cds) != n:
            return False
        return all(abs(x - xr) <= 1e-10 for x, xr in zip(xs, x_ref))

    for rim_name, data in [(baseline_name, baseline_data)] + rim_data:
        if not has_same_x_grid(data):
            print(f"[SKIP] {rim_name}: inconsistent X/cd grid; delta_cd not computed")
            continue
        deltas = []
        for cdv, refv in zip(data["cd"], ref_cd):
            if (
                isinstance(cdv, (int, float))
                and math.isfinite(cdv)
                and isinstance(refv, (int, float))
                and math.isfinite(refv)
            ):
                deltas.append(cdv - refv)
            else:
                deltas.append(float("nan"))
        data["delta_cd"] = deltas


def find_nearest_zero_x_before_front(rim_data, vehicle_x_min, zero_tol=1e-12):
    if vehicle_x_min is None or not rim_data:
        return vehicle_x_min

    reference_x = rim_data[0][1].get("X", [])
    if not reference_x:
        return vehicle_x_min

    zero_x = None
    for i, x in enumerate(reference_x):
        if x > vehicle_x_min:
            break
        all_zero = True
        for _, data in rim_data:
            xs = data.get("X", [])
            vals = data.get("cd_accumulated", [])
            if i >= len(xs) or i >= len(vals) or abs(xs[i] - x) > 1e-10:
                all_zero = False
                break
            val = vals[i]
            if not isinstance(val, (int, float)) or not math.isfinite(val) or abs(val) > zero_tol:
                all_zero = False
                break
        if all_zero:
            zero_x = x

    return zero_x if zero_x is not None else vehicle_x_min


def last_finite(values):
    for value in reversed(values):
        if isinstance(value, (int, float)) and math.isfinite(value):
            return float(value)
    return float("nan")


def sort_rims_by_final_cd(rim_data):
    def sort_key(item):
        rim_name, data = item
        final_cd = last_finite(data.get("cd", []))
        missing = not math.isfinite(final_cd)
        idx = rim_index_from_name(rim_name)
        return missing, final_cd, idx if idx is not None else 10**9

    return sorted(rim_data, key=sort_key)


def coordinated_random_colors(total):
    rng = random.Random(COLOR_SEED)
    colors = []
    hue_bands = [
        (0.11, 0.18),  # muted gold
        (0.27, 0.42),  # green
        (0.48, 0.61),  # teal/cyan
        (0.64, 0.76),  # blue/violet
    ]
    for i in range(total):
        band_min, band_max = hue_bands[i % len(hue_bands)]
        fraction = ((i // len(hue_bands)) * 0.61803398875) % 1.0
        hue = band_min + (band_max - band_min) * fraction + rng.uniform(-0.006, 0.006)
        lightness = 0.38 + 0.16 * ((i % 9) / 8.0) + rng.uniform(-0.018, 0.018)
        saturation = 0.48 + 0.22 * ((i % 7) / 6.0) + rng.uniform(-0.025, 0.025)
        lightness = min(0.58, max(0.34, lightness))
        saturation = min(0.74, max(0.42, saturation))
        colors.append(colorsys.hls_to_rgb(hue % 1.0, lightness, saturation))
    rng.shuffle(colors)
    return colors


def tick_values(y_min, y_max, step):
    ticks = []
    tick = y_min
    while tick <= y_max + step * 0.5:
        ticks.append(round(tick, 10))
        tick += step
    return ticks


def set_fixed_y_axis(ax, y_lim, step):
    ax.set_ylim(y_lim)
    ax.set_yticks(tick_values(y_lim[0], y_lim[1], step))


def format_cd_tick(value, _pos):
    return f"{value:.2f}"


def sidepic_ratio(sidepic_path):
    img = mpimg.imread(sidepic_path)
    img_h, img_w = img.shape[:2]
    return float(img_h) / float(img_w)


def draw_background_car(ax, sidepic_path, x_min, x_max, y_lim):
    img = mpimg.imread(sidepic_path)
    img_h, img_w = img.shape[:2]
    img_ratio = float(img_h) / float(img_w)

    ax.figure.canvas.draw()
    bbox = ax.get_window_extent()
    if bbox.width <= 0 or bbox.height <= 0:
        return

    y_span = y_lim[1] - y_lim[0]
    draw_h = img_ratio * bbox.width * y_span / bbox.height
    y_center = 0.5 * (y_lim[0] + y_lim[1])
    y0 = y_center - 0.5 * draw_h
    y1 = y_center + 0.5 * draw_h

    ax.imshow(
        img,
        extent=[x_min, x_max, y0, y1],
        zorder=0,
        alpha=1.0,
        aspect="auto",
    )
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_lim)


def style_common_axes(ax, y_label):
    ax.set_xlabel("X Position (m)", fontsize=AXIS_LABEL_SIZE, labelpad=AXIS_LABEL_PAD)
    ax.set_ylabel(y_label, fontsize=AXIS_LABEL_SIZE, labelpad=AXIS_LABEL_PAD)
    ax.tick_params(axis="both", labelsize=TICK_LABEL_SIZE, pad=TICK_PAD)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.1f"))
    ax.grid(True, alpha=0.25)


def set_cd_axis(ax):
    set_fixed_y_axis(ax, CD_YLIM, CD_YTICK_STEP)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(format_cd_tick))


def set_delta_cd_axis(ax):
    set_fixed_y_axis(ax, DELTA_CD_YLIM, DELTA_CD_YTICK_STEP)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))


def apply_tight_layout(fig, legend_outside=False):
    if legend_outside:
        fig.tight_layout(rect=[0, 0, 0.84, 1.0], pad=TIGHT_LAYOUT_PAD)
    else:
        fig.tight_layout(pad=TIGHT_LAYOUT_PAD)


def rim_range_label(rim_data):
    indexes = [
        rim_index_from_name(rim_name)
        for rim_name, _ in rim_data
        if rim_index_from_name(rim_name) is not None
    ]
    if not indexes:
        return "Rims"
    return f"Rim{min(indexes):03d}-Rim{max(indexes):03d}"


def add_group_legend(ax, rim_data, rim_colors, include_cr=True):
    handles = []
    labels = []
    handler_map = {}

    if include_cr:
        handles.append(Line2D([], [], color=CR_COLOR, linewidth=CR_LINE_WIDTH))
        labels.append(BASELINE_LABEL)

    if rim_data:
        sample_count = min(4, max(1, len(rim_colors)))
        sample_indexes = [
            round(i * (len(rim_colors) - 1) / max(1, sample_count - 1))
            for i in range(sample_count)
        ]
        rim_handle = tuple(
            Line2D([], [], color=rim_colors[idx], linewidth=RIM_LINE_WIDTH + 0.6)
            for idx in sample_indexes
        )
        handles.append(rim_handle)
        labels.append(rim_range_label(rim_data))
        handler_map[tuple] = HandlerTuple(ndivide=None, pad=0.25)

    if not handles:
        return

    ax.legend(
        handles=handles,
        labels=labels,
        handler_map=handler_map,
        loc="upper left",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
        borderpad=0.35,
        handlelength=2.3,
        labelspacing=0.35,
    )


def plot_min_max_with_cr(
    rim_data,
    baseline_data,
    col_name,
    y_label,
    out_path,
    x_min,
    x_max,
    car_x_min,
    sidepic_ok,
    car_box_aspect,
    set_y_axis,
    y_lim,
    sidepic_path,
):
    if not rim_data:
        return

    min_name, min_data = rim_data[0]
    max_name, max_data = rim_data[-1]
    if col_name not in min_data or col_name not in max_data or col_name not in baseline_data:
        print(f"[SKIP] min/max plot: missing {col_name}")
        return

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=FIG_SIZE, dpi=160)
    if car_box_aspect is not None:
        ax.set_box_aspect(car_box_aspect)

    ax.plot(
        min_data["X"],
        min_data[col_name],
        color="#0072B2",
        linewidth=2.5,
        label=f"{min_name} min $C_D$",
        zorder=5,
    )
    ax.plot(
        max_data["X"],
        max_data[col_name],
        color="#009E73",
        linewidth=2.5,
        label=f"{max_name} max $C_D$",
        zorder=5,
    )
    ax.plot(
        baseline_data["X"],
        baseline_data[col_name],
        color=CR_COLOR,
        linewidth=CR_LINE_WIDTH,
        label=BASELINE_LABEL,
        zorder=20,
        path_effects=[
            pe.Stroke(linewidth=CR_LINE_WIDTH + 1.3, foreground="white", alpha=0.85),
            pe.Normal(),
        ],
    )

    if x_min is not None and x_max is not None:
        ax.set_xlim(x_min, x_max)
    set_y_axis(ax)
    style_common_axes(ax, y_label)
    ax.legend(
        loc="upper left",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
        borderpad=0.35,
        handlelength=1.8,
        labelspacing=0.35,
    )
    apply_tight_layout(fig)

    if sidepic_ok:
        draw_background_car(ax, sidepic_path, car_x_min, x_max, y_lim)
        ax.set_xlim(x_min, x_max)

    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved: {out_path}")
    save_metric_csv(
        [(min_name, min_data), (max_name, max_data), (BASELINE_LABEL, baseline_data)],
        col_name,
        out_path,
        x_min=x_min,
        x_max=x_max,
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Plot accumulated rim curves from raw Binned.csv files or a wide "
            "Cd_Accumulated_Combined.csv file."
        )
    )
    parser.add_argument(
        "--input",
        default="",
        help=(
            "Wide Cd_Accumulated_Combined.csv input. When omitted, the legacy "
            "raw Binned.csv workflow is used."
        ),
    )
    parser.add_argument(
        "--raw-data-root",
        default=os.environ.get("RAW_DATA_ROOT", str(DEFAULT_RAW_DATA_ROOT)),
        help=(
            "Root containing Rim*/ and CR/ for the legacy Binned.csv workflow "
            "(env: RAW_DATA_ROOT). The public default '-' must be replaced."
        ),
    )
    parser.add_argument(
        "--rims",
        default=DEFAULT_RIMS,
        help='Comma-separated rim list, e.g. "Rim001,Rim010". Default: all rims',
    )
    parser.add_argument(
        "--metrics",
        default=DEFAULT_METRICS,
        help='Comma-separated metrics from Binned.csv, e.g. "cd_local,clf_local"',
    )
    parser.add_argument(
        "--rim-start",
        type=int,
        default=DEFAULT_RIM_START,
        help="Start rim index, e.g. 1 means Rim001",
    )
    parser.add_argument(
        "--rim-end",
        type=int,
        default=DEFAULT_RIM_END,
        help="End rim index, inclusive, e.g. 120 means Rim120",
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help="Output image path",
    )
    return parser.parse_args()


def compute_y_limits(rim_data, col_name, x_min=None, x_max=None):
    values = []
    for _, data in rim_data:
        if col_name not in data:
            continue
        xs = data.get("X", [])
        ys = data.get(col_name, [])
        for x, y in zip(xs, ys):
            if not isinstance(y, float) or not math.isfinite(y):
                continue
            if x_min is not None and x < x_min:
                continue
            if x_max is not None and x > x_max:
                continue
            values.append(y)

    if not values:
        return None

    y_min = min(values)
    y_max = max(values)
    if y_min == y_max:
        pad = max(1e-4, abs(y_min) * 0.05)
        return y_min - pad, y_max + pad

    pad = (y_max - y_min) * 0.08
    return y_min - pad, y_max + pad


def csv_value(value):
    if isinstance(value, (int, float)) and math.isfinite(value):
        return f"{value:.12g}"
    return ""


def save_metric_csv(rim_data, col_name, out_path, x_min=None, x_max=None):
    rows = []
    headers = ["X"]
    selected = []
    for rim_name, data in rim_data:
        if col_name not in data:
            continue
        headers.append(rim_name)
        selected.append((rim_name, data))

    if not selected:
        return

    reference_x = selected[0][1].get("X", [])
    for i, x in enumerate(reference_x):
        if x_min is not None and x < x_min:
            continue
        if x_max is not None and x > x_max:
            continue
        row = [csv_value(x)]
        for _, data in selected:
            xs = data.get("X", [])
            values = data.get(col_name, [])
            if i >= len(xs) or i >= len(values) or abs(xs[i] - x) > 1e-10:
                row.append("")
            else:
                row.append(csv_value(values[i]))
        rows.append(row)

    csv_path = out_path.with_suffix(".csv")
    with csv_path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    print(f"[OK] Saved: {csv_path}")


def save_cd_accumulated_combined_csv(rim_data, out_path, x_min=None, x_max=None):
    """Save Cd data in numeric Rim order with four-digit Rim column names."""
    ordered_rims = []
    seen_indexes = set()
    for rim_name, data in sorted(
        rim_data,
        key=lambda item: rim_index_from_name(item[0]),
    ):
        rim_index = rim_index_from_name(rim_name)
        if rim_index is None or "cd" not in data:
            continue
        if rim_index in seen_indexes:
            raise ValueError(f"Duplicate Rim index in combined Cd output: {rim_index}")
        seen_indexes.add(rim_index)
        ordered_rims.append((f"Rim{rim_index:04d}", data))

    save_metric_csv(
        ordered_rims,
        "cd",
        out_path,
        x_min=x_min,
        x_max=x_max,
    )


def select_combined_rims(rim_data, args):
    selected_names = {name.strip() for name in args.rims.split(",") if name.strip()}
    if selected_names:
        selected_indexes = {
            rim_index_from_name(name)
            for name in selected_names
            if rim_index_from_name(name) is not None
        }
        rim_data = [
            (name, data)
            for name, data in rim_data
            if name in selected_names or rim_index_from_name(name) in selected_indexes
        ]
        if not rim_data:
            raise SystemExit("No matching rims found for --rims selection.")

    start = args.rim_start if args.rim_start is not None else -10**9
    end = args.rim_end if args.rim_end is not None else 10**9
    if end < start:
        raise SystemExit("--rim-end must be >= --rim-start")
    rim_data = [
        (name, data)
        for name, data in rim_data
        if start <= rim_index_from_name(name) <= end
    ]
    if not rim_data:
        raise SystemExit("No rims found in selected --rim-start/--rim-end range.")
    return rim_data


def plot_min_max_without_cr(rim_data, out_path, x_min, x_max):
    if not rim_data:
        return

    min_name, min_data = rim_data[0]
    max_name, max_data = rim_data[-1]
    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=FIG_SIZE, dpi=160)
    ax.plot(
        min_data["X"],
        min_data["cd"],
        color="#0072B2",
        linewidth=2.5,
        label=f"{min_name} min $C_D$",
    )
    ax.plot(
        max_data["X"],
        max_data["cd"],
        color="#009E73",
        linewidth=2.5,
        label=f"{max_name} max $C_D$",
    )
    ax.set_xlim(x_min, x_max)
    set_cd_axis(ax)
    style_common_axes(ax, dict(PLOT_COLUMNS)["cd"])
    ax.legend(
        loc="upper left",
        fontsize=LEGEND_FONT_SIZE,
        frameon=True,
        borderpad=0.35,
        handlelength=1.8,
        labelspacing=0.35,
    )
    apply_tight_layout(fig)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved: {out_path}")


def plot_combined_cd_input(input_path: Path, args):
    if not input_path.is_file():
        raise SystemExit(f"Combined Cd CSV not found: {input_path}")

    try:
        rim_data = read_combined_cd_csv(input_path)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Failed reading combined Cd CSV {input_path}: {exc}") from exc

    rim_data = select_combined_rims(rim_data, args)
    rim_data = sort_rims_by_final_cd(rim_data)
    rim_colors = coordinated_random_colors(len(rim_data))

    reference_x = rim_data[0][1]["X"]
    x_min = min(reference_x)
    x_max = max(reference_x)
    out_path = Path(args.output)
    if not out_path.suffix:
        out_path = out_path.with_suffix(".jpg")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(nrows=1, ncols=1, figsize=FIG_SIZE, dpi=160)
    for rank, (_, data) in enumerate(rim_data):
        ax.plot(
            data["X"],
            data["cd"],
            color=rim_colors[rank],
            linewidth=RIM_LINE_WIDTH,
            alpha=0.84,
            zorder=2,
        )
    ax.set_xlim(x_min, x_max)
    set_cd_axis(ax)
    style_common_axes(ax, dict(PLOT_COLUMNS)["cd"])
    if SHOW_LEGEND:
        add_group_legend(ax, rim_data, rim_colors, include_cr=False)
    apply_tight_layout(fig)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Saved: {out_path}")

    min_max_out = out_path.with_name(f"{out_path.stem}_Min_Max{out_path.suffix}")
    plot_min_max_without_cr(rim_data, min_max_out, x_min, x_max)
    print(f"Input CSV: {input_path.resolve()}")
    print(f"Loaded rims: {len(rim_data)}")


def main():
    args = parse_args()
    if args.input:
        plot_combined_cd_input(Path(args.input), args)
        return

    if not args.raw_data_root or args.raw_data_root == "-":
        raise SystemExit(
            "--raw-data-root is required for the legacy Binned.csv workflow; "
            "replace the public '-' placeholder."
        )
    raw_data_root = Path(args.raw_data_root).expanduser().resolve()
    if not raw_data_root.is_dir():
        raise SystemExit(f"Raw-data root not found: {raw_data_root}")
    rim001_dir = raw_data_root / "Rim001"
    baseline_dir = raw_data_root / BASELINE_NAME
    sidepic_path = rim001_dir / "Pictures/Dimensions/sidepic.png"
    vehicle_dim_path = rim001_dir / "NumData/Vehicle_dimensions.csv"

    rims = discover_rims(raw_data_root)
    if not rims:
        raise SystemExit(f"No Rim*/NumData/Binned.csv found under {raw_data_root}")
    selected_rims = {x.strip() for x in args.rims.split(",") if x.strip()}
    if selected_rims:
        rims = [(name, path) for name, path in rims if name in selected_rims]
        if not rims:
            raise SystemExit("No matching rims found for --rims selection.")
    if args.rim_start is not None or args.rim_end is not None:
        start = args.rim_start if args.rim_start is not None else -10**9
        end = args.rim_end if args.rim_end is not None else 10**9
        if end < start:
            raise SystemExit("--rim-end must be >= --rim-start")

        def rim_index(name: str):
            digits = "".join(ch for ch in name if ch.isdigit())
            return int(digits) if digits else None

        filtered = []
        for name, path in rims:
            idx = rim_index(name)
            if idx is None:
                continue
            if start <= idx <= end:
                filtered.append((name, path))
        rims = filtered
        if not rims:
            raise SystemExit("No rims found in selected --rim-start/--rim-end range.")

    baseline_binned = baseline_dir / "NumData/Binned.csv"
    if not baseline_binned.exists():
        raise SystemExit(f"No CR baseline found at {baseline_binned}")

    metric_names = [x.strip() for x in args.metrics.split(",") if x.strip()]
    if not metric_names:
        raise SystemExit("No valid metrics from --metrics.")
    label_map = dict(PLOT_COLUMNS)
    selected_columns = [(m, label_map.get(m, m)) for m in metric_names]

    default_area_front = read_area_front(vehicle_dim_path)
    rim_data = []
    for rim_name, binned_path in rims:
        try:
            data = read_binned_csv(binned_path)
        except Exception as exc:
            print(f"[SKIP] {rim_name}: failed reading {binned_path} ({exc})")
            continue
        if "X" not in data:
            print(f"[SKIP] {rim_name}: no X column in {binned_path}")
            continue
        area_front = read_area_front(binned_path.parent / "Vehicle_dimensions.csv")
        if area_front is None:
            area_front = default_area_front
        compute_cd_and_accumulated(data, area_front)
        rim_data.append((rim_name, data))

    if not rim_data:
        raise SystemExit("No valid Binned.csv files were loaded.")

    try:
        baseline_data = read_binned_csv(baseline_binned)
    except Exception as exc:
        raise SystemExit(f"Failed reading CR baseline {baseline_binned}: {exc}") from exc
    if "X" not in baseline_data:
        raise SystemExit(f"CR baseline has no X column in {baseline_binned}")
    baseline_area_front = read_area_front(baseline_binned.parent / "Vehicle_dimensions.csv")
    if baseline_area_front is None:
        baseline_area_front = default_area_front
    compute_cd_and_accumulated(baseline_data, baseline_area_front)

    compute_delta_cd(rim_data, BASELINE_NAME, baseline_data)
    rim_data = sort_rims_by_final_cd(rim_data)
    rim_colors = coordinated_random_colors(len(rim_data))
    all_plot_data = rim_data + [(BASELINE_LABEL, baseline_data)]

    x_min, x_max = read_vehicle_x_range(vehicle_dim_path)
    plot_x_min = find_nearest_zero_x_before_front(
        rim_data + [(BASELINE_NAME, baseline_data)],
        x_min,
    )
    sidepic_ok = sidepic_path.exists() and x_min is not None and x_max is not None
    car_box_aspect = None
    if sidepic_ok:
        car_box_aspect = sidepic_ratio(sidepic_path) * CAR_BOX_ASPECT_PAD

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = out_path.suffix or ".jpg"

    for col_name, y_label in selected_columns:
        fig, ax = plt.subplots(nrows=1, ncols=1, figsize=FIG_SIZE, dpi=160)
        if car_box_aspect is not None:
            ax.set_box_aspect(car_box_aspect)
        plotted = 0
        for rank, (rim_name, data) in enumerate(rim_data):
            if col_name not in data:
                continue
            ax.plot(
                data["X"],
                data[col_name],
                color=rim_colors[rank],
                linewidth=RIM_LINE_WIDTH,
                label=rim_name,
                alpha=0.84,
                zorder=2,
            )
            plotted += 1
        baseline_plotted = False
        if col_name in baseline_data:
            ax.plot(
                baseline_data["X"],
                baseline_data[col_name],
                color=CR_COLOR,
                linewidth=CR_LINE_WIDTH,
                label=BASELINE_LABEL,
                alpha=1.0,
                zorder=20,
                path_effects=[
                    pe.Stroke(linewidth=CR_LINE_WIDTH + 1.3, foreground="white", alpha=0.85),
                    pe.Normal(),
                ],
            )
            baseline_plotted = True

        if plot_x_min is not None and x_max is not None:
            ax.set_xlim(plot_x_min, x_max)

        y_lim = compute_y_limits(all_plot_data, col_name, x_min=plot_x_min, x_max=x_max)
        if col_name == "cd":
            y_lim = CD_YLIM
            set_cd_axis(ax)
        elif col_name == "delta_cd":
            y_lim = DELTA_CD_YLIM
            set_delta_cd_axis(ax)
        elif y_lim is not None:
            ax.set_ylim(y_lim)

        style_common_axes(ax, y_label)
        if SHOW_LEGEND and (plotted > 0 or baseline_plotted):
            add_group_legend(ax, rim_data, rim_colors, include_cr=baseline_plotted)

        apply_tight_layout(fig)

        if sidepic_ok and y_lim is not None:
            draw_background_car(ax, sidepic_path, x_min, x_max, y_lim)
            ax.set_xlim(plot_x_min, x_max)

        metric_base = OUTPUT_NAME_MAP.get(col_name, f"{col_name}_Accumulated")
        metric_out = out_path.with_name(f"{metric_base}{suffix}")
        fig.savefig(metric_out, bbox_inches="tight")
        plt.close(fig)
        print(f"[OK] Saved: {metric_out}")
        save_metric_csv(all_plot_data, col_name, metric_out, x_min=plot_x_min, x_max=x_max)

    combined_cd_out = out_path.with_name(COMBINED_CD_CSV_NAME)
    save_cd_accumulated_combined_csv(
        rim_data,
        combined_cd_out,
        x_min=plot_x_min,
        x_max=x_max,
    )

    cd_min_max_out = out_path.with_name(f"Cd_Accumulated_CR_Min_Max{suffix}")
    plot_min_max_with_cr(
        rim_data,
        baseline_data,
        "cd",
        dict(PLOT_COLUMNS)["cd"],
        cd_min_max_out,
        plot_x_min,
        x_max,
        x_min,
        sidepic_ok,
        car_box_aspect,
        set_cd_axis,
        CD_YLIM,
        sidepic_path,
    )

    delta_cd_min_max_out = out_path.with_name(f"DeltaCd_AlongX_CR_Min_Max{suffix}")
    plot_min_max_with_cr(
        rim_data,
        baseline_data,
        "delta_cd",
        dict(PLOT_COLUMNS)["delta_cd"],
        delta_cd_min_max_out,
        plot_x_min,
        x_max,
        x_min,
        sidepic_ok,
        car_box_aspect,
        set_delta_cd_axis,
        DELTA_CD_YLIM,
        sidepic_path,
    )


if __name__ == "__main__":
    main()
