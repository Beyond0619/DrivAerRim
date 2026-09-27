import argparse
import importlib.util
import os
from pathlib import Path
import sys

VENV_PYTHON = Path(os.environ.get("PLOT_PYTHON", "-"))
VENV_DIR = VENV_PYTHON.parent.parent
NEEDED_MODULES = ("pandas", "matplotlib", "seaborn")
if (
    any(importlib.util.find_spec(name) is None for name in NEEDED_MODULES)
    and VENV_PYTHON.is_file()
    and Path(sys.prefix).resolve() != VENV_DIR.resolve()
):
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd
import seaborn as sns


"""
Quick switches (edit here if you want):

- Choose which CSV file to use by default

If you pass --input / --output-dir on CLI, they override these.
"""

# Default input locations. Set FORCES_DIR or pass --input.
FORCES_DIR = Path(os.environ.get("FORCES_DIR", "-"))
DEFAULT_INPUT_DIRS = [
    FORCES_DIR / "Data",
    FORCES_DIR,
]
DEFAULT_INPUT_PATTERN = "all_means_*.csv"

# Default output directory
DEFAULT_OUTPUT_DIR = FORCES_DIR / "Figures"

# Default figure export settings. Edit these if you want JPG/PNG or 300/600 dpi.
IMAGE_FORMAT = "jpg"
DEFAULT_DPI = 300

BASELINE_CASE_ID = 0

TARGET_COLUMNS = [
    "MeanCd",
    "MeanCl",
    "MeanClf",
    "MeanClr",
]

EXTRA_COLUMNS = [
    "MeanCd_FL",
    "MeanCd_RL",
    "MeanCd_vent_FL",
    "MeanCd_vent_RL",
    "MeanCd_wh_FL",
    "MeanCd_ws_FL",
    "MeanCd_wh_RL",
    "MeanCd_ws_RL",
]

# Column names used by Force_Coefficients_Combined.csv.  The plotting code
# keeps its original internal names so both the legacy all_means_*.csv files
# and the combined export remain supported.
COMBINED_COLUMN_ALIASES = {
    "Rim": "case",
    "Cd": "MeanCd",
    "Cl": "MeanCl",
    "Clf": "MeanClf",
    "Clr": "MeanClr",
    "Cd_FL": "MeanCd_FL",
    "Cd_RL": "MeanCd_RL",
    "Cd_vent_FL": "MeanCd_vent_FL",
    "Cd_vent_RL": "MeanCd_vent_RL",
    "Cd_wh_FL": "MeanCd_wh_FL",
    "Cd_wh_RL": "MeanCd_wh_RL",
    "Cd_ws_FL": "MeanCd_ws_FL",
    "Cd_ws_RL": "MeanCd_ws_RL",
}

CD_PAIR_COLUMNS = ["Cd", "Wheel", "WheelHouse", "Vent"]

DIST_COLOR = "#2a9d8f"
SCATTER_COLOR = "#1f77b4"
SCATTER_EDGE_COLOR = "white"
SCATTER_ALPHA = 0.82
SCATTER_LINEWIDTH = 0.2
CR_SCATTER_COLOR = "#d62728"
CR_SCATTER_ALPHA = 0.82
LINE_COLOR = "#e63946"

# Publication-oriented typography.  The pair plots need a moderate increase
# because they contain many panels, while the component-ratio comparison is
# commonly reduced to a two-column-paper width and therefore uses a larger
# dedicated scale below.
BASE_FONT_SIZE = 14
AXIS_LABEL_FONT_SIZE = 17
TICK_LABEL_FONT_SIZE = 15
LEGEND_FONT_SIZE = 14
ANNOTATION_FONT_SIZE = 13

PAIRPLOT_LABEL_FONT_SIZE = 17
PAIRPLOT_TICK_FONT_SIZE = 15
PAIRPLOT_PANEL_HEIGHT = 2.7
PAIRPLOT_X_LABEL_PAD = 7
PAIRPLOT_Y_LABEL_PAD = 9

RATIO_LABEL_FONT_SIZE = 19
RATIO_TICK_FONT_SIZE = 15
RATIO_LEGEND_FONT_SIZE = 15
FOCUS_RATIO_LABEL_FONT_SIZE = 21
FOCUS_RATIO_TICK_FONT_SIZE = 17
FOCUS_RATIO_LEGEND_FONT_SIZE = 17

PAPER_GRID_COLOR = "#b0b0b0"
PAPER_SPINE_COLOR = "#202020"
CM_FONT_RC = {
    "font.family": "serif",
    "font.serif": ["Computer Modern Roman", "CMU Serif", "cmr10", "DejaVu Serif"],
    "font.weight": "normal",
    "font.size": BASE_FONT_SIZE,
    "mathtext.fontset": "cm",
    "axes.labelsize": AXIS_LABEL_FONT_SIZE,
    "axes.titlesize": AXIS_LABEL_FONT_SIZE,
    "axes.labelweight": "normal",
    "axes.edgecolor": PAPER_SPINE_COLOR,
    "axes.linewidth": 1.0,
    "axes.axisbelow": True,
    "axes.grid": True,
    "axes.formatter.use_mathtext": True,
    "axes.unicode_minus": False,
    "xtick.labelsize": TICK_LABEL_FONT_SIZE,
    "ytick.labelsize": TICK_LABEL_FONT_SIZE,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.size": 4.5,
    "ytick.major.size": 4.5,
    "xtick.major.width": 0.9,
    "ytick.major.width": 0.9,
    "grid.color": PAPER_GRID_COLOR,
    "grid.linewidth": 0.7,
    "grid.alpha": 0.45,
    "legend.fontsize": LEGEND_FONT_SIZE,
    "legend.frameon": True,
    "legend.fancybox": False,
    "legend.framealpha": 1.0,
    "legend.edgecolor": PAPER_SPINE_COLOR,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
}


def set_plot_theme(style: str = "whitegrid", context: str = "notebook") -> None:
    sns.set_theme(style=style, context=context, rc=CM_FONT_RC)
    plt.rcParams.update(CM_FONT_RC)


def style_axis_for_paper(ax, *, show_grid: bool = True) -> None:
    """Apply the reference figure's clean boxed-axis and light-grid style."""
    ax.set_axisbelow(True)
    if show_grid:
        ax.grid(
            visible=True,
            which="major",
            color=PAPER_GRID_COLOR,
            linewidth=0.7,
            alpha=0.45,
        )
    else:
        ax.grid(visible=False, which="major")
    ax.grid(visible=False, which="minor")
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(PAPER_SPINE_COLOR)
        spine.set_linewidth(1.0)
    ax.tick_params(
        axis="both",
        which="major",
        direction="out",
        length=4.5,
        width=0.9,
        colors=PAPER_SPINE_COLOR,
    )


def style_pairplot_axes(pair, columns: list[str]) -> None:
    """Keep labels legible when a pair plot is reduced for publication."""
    for i, y_col in enumerate(columns):
        for j, x_col in enumerate(columns):
            ax = pair.axes[i, j]
            if ax is None:
                continue
            ax.set_xlabel(
                display_label(x_col),
                fontsize=PAIRPLOT_LABEL_FONT_SIZE,
                labelpad=PAIRPLOT_X_LABEL_PAD,
            )
            ax.set_ylabel(
                display_label(y_col),
                fontsize=PAIRPLOT_LABEL_FONT_SIZE,
                labelpad=PAIRPLOT_Y_LABEL_PAD,
            )
            ax.tick_params(axis="both", labelsize=PAIRPLOT_TICK_FONT_SIZE)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=4))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=4))

    # Different numeric widths (for example positive C_D versus negative C_L)
    # otherwise shift the vertical labels by different amounts.
    pair.figure.align_ylabels(
        [pair.axes[i, 0] for i in range(len(columns)) if pair.axes[i, 0] is not None]
    )


def style_ratio_comparison_axes(axes, *, emphasized: bool = False) -> None:
    """Use a stronger type scale for dense two-panel ratio comparisons."""
    if emphasized:
        label_size = FOCUS_RATIO_LABEL_FONT_SIZE
        tick_size = FOCUS_RATIO_TICK_FONT_SIZE
        legend_size = FOCUS_RATIO_LEGEND_FONT_SIZE
    else:
        label_size = RATIO_LABEL_FONT_SIZE
        tick_size = RATIO_TICK_FONT_SIZE
        legend_size = RATIO_LEGEND_FONT_SIZE

    for ax in axes:
        ax.xaxis.label.set_size(label_size)
        ax.yaxis.label.set_size(label_size)
        ax.tick_params(axis="both", labelsize=tick_size)

    legend = axes[0].get_legend()
    if legend is not None:
        plt.setp(legend.get_texts(), fontsize=legend_size)
        legend.set_title(None)
        legend.get_frame().set_edgecolor(PAPER_SPINE_COLOR)
        legend.get_frame().set_linewidth(1.0)
        legend.get_frame().set_alpha(1.0)


def figure_filename(filename: str) -> str:
    return f"{Path(filename).stem}.{IMAGE_FORMAT.lstrip('.')}"


def figure_path(output_dir: Path, filename: str) -> Path:
    return output_dir / figure_filename(filename)


def save_figure(
    fig,
    output_dir: Path,
    filename: str,
    dpi: int,
    *,
    show_grid: bool = True,
    **kwargs,
) -> None:
    for ax in fig.get_axes():
        style_axis_for_paper(ax, show_grid=show_grid)

    save_kwargs = {
        "dpi": dpi,
        "facecolor": "white",
        "bbox_inches": "tight",
        "pad_inches": 0.06,
    }
    save_kwargs.update(kwargs)
    fig.savefig(figure_path(output_dir, filename), **save_kwargs)


LABELS = {
    "Cd": r"$C_D$",
    "MeanCd": r"$C_D$",
    "Cl": r"$C_L$",
    "MeanCl": r"$C_L$",
    "Clf": r"$C_{LF}$",
    "MeanClf": r"$C_{LF}$",
    "Clr": r"$C_{LR}$",
    "MeanClr": r"$C_{LR}$",
    "DeltaCd": r"$\Delta C_D$",
    "DeltaCd_x1000": r"$\Delta C_D\times 1000$",
    "WheelFront": r"$C_{D,\mathrm{FW}}$",
    "WheelRear": r"$C_{D,\mathrm{RW}}$",
    "Wheel": r"$C_{D,\mathrm{W}}$",
    "WheelHouse": r"$C_{D,\mathrm{WH}}$",
    "WheelSupport": r"$C_{D,\mathrm{WS}}$",
    "Vent": r"$C_{D,\mathrm{V}}$",
    "WheelTotal": r"$C_{D,\mathrm{W,total}}$",
}


def display_label(column_name: str) -> str:
    return LABELS.get(column_name, column_name)


def short_label(column_name: str) -> str:
    return display_label(column_name)


def rims_label(df: pd.DataFrame) -> str:
    return f"{len(df)} rims"


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df_plot = df.copy()
    df_plot["Cd"] = df_plot["MeanCd"]
    df_plot["WheelFront"] = 2.0 * df_plot["MeanCd_FL"]
    df_plot["WheelRear"] = 2.0 * df_plot["MeanCd_RL"]
    df_plot["Wheel"] = df_plot["WheelFront"] + df_plot["WheelRear"]
    df_plot["WheelHouse"] = 2.0 * (df_plot["MeanCd_wh_FL"] + df_plot["MeanCd_wh_RL"])
    df_plot["WheelSupport"] = 2.0 * (df_plot["MeanCd_ws_FL"] + df_plot["MeanCd_ws_RL"])
    df_plot["Vent"] = 2.0 * (df_plot["MeanCd_vent_FL"] + df_plot["MeanCd_vent_RL"])
    df_plot["WheelTotal"] = df_plot["Wheel"] + df_plot["WheelHouse"] + df_plot["WheelSupport"]
    return df_plot


def numeric_scalar(value, label: str) -> float:
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        raise ValueError(f"{label} is not numeric for closed rim baseline.")
    return float(number)


def closed_rim_baseline_row(df: pd.DataFrame) -> pd.Series:
    if "case" not in df.columns:
        raise ValueError("Closed rim baseline requires a 'case' column with case 0.")

    case_values = pd.to_numeric(df["case"], errors="coerce")
    baseline = df.loc[case_values == BASELINE_CASE_ID]
    if baseline.empty:
        raise ValueError(
            "Closed rim baseline case 0 is missing from the selected data. "
            "Use an input CSV that includes case 0."
        )
    return baseline.iloc[0]


def has_closed_rim_baseline(df: pd.DataFrame) -> bool:
    if "case" not in df.columns:
        return False
    case_values = pd.to_numeric(df["case"], errors="coerce")
    return bool((case_values == BASELINE_CASE_ID).any())


def closed_rim_case_values(df: pd.DataFrame) -> pd.Series | None:
    return df["case"] if "case" in df.columns else None


def add_delta_cd_x1000(df: pd.DataFrame) -> pd.DataFrame:
    df_out = df.copy()
    baseline = closed_rim_baseline_row(df_out)
    baseline_cd = numeric_scalar(baseline["MeanCd"], "MeanCd")
    baseline_wh = numeric_scalar(baseline["WheelHouse"], "WheelHouse")

    df_out["DeltaCd"] = df_out["MeanCd"] - baseline_cd
    df_out["DeltaCd_x1000"] = (1000.0 * df_out["DeltaCd"]).round(1)
    df_out["DeltaWheelHouse"] = df_out["WheelHouse"] - baseline_wh
    df_out["DeltaWheelHouse_x1000"] = (1000.0 * df_out["DeltaWheelHouse"]).round(1)
    return df_out


def add_regression_and_corr(ax, x_values, y_values) -> None:
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("Regression data contains non-finite values.")
    if len(x) < 2:
        return

    coef = np.polyfit(x, y, 1)
    x_line = np.linspace(x.min(), x.max(), 200)
    y_line = coef[0] * x_line + coef[1]
    ax.plot(
        x_line,
        y_line,
        color=LINE_COLOR,
        linewidth=2.0,
        linestyle="--",
        label="Linear fit",
    )

    corr = float(np.corrcoef(x, y)[0, 1])
    r2 = corr ** 2
    ax.text(
        0.03,
        0.95,
        f"$r$ = {corr:.3f}\n$R^2$ = {r2:.3f}",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=ANNOTATION_FONT_SIZE,
        bbox={
            "boxstyle": "square,pad=0.25",
            "fc": "white",
            "ec": PAPER_SPINE_COLOR,
            "lw": 0.8,
            "alpha": 0.92,
        },
    )
    ax.legend(loc="lower right", frameon=True, fontsize=LEGEND_FONT_SIZE)


def plot_plain_scatter(
    ax,
    x_values,
    y_values,
    s: float = 28,
    alpha: float = SCATTER_ALPHA,
    case_values=None,
) -> None:
    x = np.asarray(x_values, dtype=float)
    y = np.asarray(y_values, dtype=float)
    if not (np.isfinite(x).all() and np.isfinite(y).all()):
        raise ValueError("Scatter data contains non-finite values.")
    if case_values is not None:
        case_array = pd.to_numeric(pd.Series(case_values), errors="coerce").to_numpy(dtype=float)
        if len(case_array) != len(x):
            case_array = None
    else:
        case_array = None

    if len(x) == 0:
        return

    cr_mask = np.zeros(len(x), dtype=bool)
    if case_array is not None:
        cr_mask = case_array == BASELINE_CASE_ID
    normal_mask = ~cr_mask

    ax.scatter(
        x[normal_mask],
        y[normal_mask],
        s=s,
        color=SCATTER_COLOR,
        alpha=alpha,
        edgecolors=SCATTER_EDGE_COLOR,
        linewidths=SCATTER_LINEWIDTH,
    )
    if np.any(cr_mask):
        ax.scatter(
            x[cr_mask],
            y[cr_mask],
            s=s * 1.25,
            color=CR_SCATTER_COLOR,
            alpha=CR_SCATTER_ALPHA,
            edgecolors=SCATTER_EDGE_COLOR,
            linewidths=SCATTER_LINEWIDTH,
            zorder=5,
        )


def add_pairplot_plain_scatter(pair, df: pd.DataFrame, cols: list[str], s: float = 18) -> None:
    cases = closed_rim_case_values(df)
    for i, y_col in enumerate(cols):
        for j, x_col in enumerate(cols):
            if i == j:
                continue
            plot_plain_scatter(
                pair.axes[i, j],
                df[x_col],
                df[y_col],
                s=s,
                alpha=SCATTER_ALPHA,
                case_values=cases,
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot aerodynamic analysis figures for rims dataset."
    )
    parser.add_argument(
        "--input",
        type=str,
        default="",
        help=(
            "Input CSV file path. Supports legacy all_means_*.csv and "
            "Force_Coefficients_Combined.csv formats."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Directory to save output images.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=DEFAULT_DPI,
        help="Image DPI for saved figures.",
    )
    return parser.parse_args()


def resolve_default_input_csv() -> Path:
    """Find the newest all_means_*.csv file in the default locations."""

    if FORCES_DIR == Path("-"):
        raise FileNotFoundError(
            "No default input directory is configured. Pass --input or set FORCES_DIR."
        )

    for input_dir in DEFAULT_INPUT_DIRS:
        matches = sorted(
            input_dir.glob(DEFAULT_INPUT_PATTERN),
            key=lambda p: (p.stat().st_mtime, p.name),
            reverse=True,
        )
        if matches:
            return matches[0]

    searched = ", ".join(str(p / DEFAULT_INPUT_PATTERN) for p in DEFAULT_INPUT_DIRS)
    raise FileNotFoundError(f"No input CSV found. Searched: {searched}")


def validate_columns(df: pd.DataFrame) -> None:
    required = TARGET_COLUMNS + EXTRA_COLUMNS
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in CSV: {missing}")


def normalize_input_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Map combined-export columns to the plotting script's legacy schema."""
    rename_map = {
        source: target
        for source, target in COMBINED_COLUMN_ALIASES.items()
        if source in df.columns and target not in df.columns
    }
    if not rename_map:
        return df

    normalized = df.rename(columns=rename_map)
    print(
        "Detected Force_Coefficients_Combined.csv format; mapped columns: "
        + ", ".join(f"{source}->{target}" for source, target in rename_map.items())
    )
    return normalized


def coerce_numeric_columns(df_raw: pd.DataFrame) -> pd.DataFrame:
    df = df_raw.copy()
    invalid_columns = []
    for col in TARGET_COLUMNS + EXTRA_COLUMNS:
        numeric_values = pd.to_numeric(df[col], errors="coerce")
        invalid = ~np.isfinite(numeric_values.to_numpy(dtype=float))
        if invalid.any():
            row_labels = ", ".join(str(label) for label in df.index[invalid][:5])
            invalid_columns.append(
                f"{col}: {int(invalid.sum())} invalid row(s), first indices {row_labels}"
            )
        df[col] = numeric_values

    if invalid_columns:
        details = "; ".join(invalid_columns)
        raise ValueError(f"Required numeric data contains non-finite values: {details}")

    zero_cd = df["MeanCd"] == 0
    if zero_cd.any():
        row_labels = ", ".join(str(label) for label in df.index[zero_cd][:5])
        raise ValueError(
            "MeanCd is zero, so component-to-Cd ratios are undefined; "
            f"first affected indices: {row_labels}"
        )
    return df


def export_cd_extremes_and_delta(
    df_raw: pd.DataFrame, output_dir: Path, dpi: int
) -> pd.DataFrame | None:
    df_raw = df_raw.copy()
    df_raw["MeanCd"] = pd.to_numeric(df_raw["MeanCd"], errors="coerce")
    if df_raw["MeanCd"].isna().all():
        raise ValueError("MeanCd column is all NaN after conversion.")

    # Four-wheel total drag (left+right) from FL/RL contributions
    df_raw["WheelFront"] = 2.0 * pd.to_numeric(df_raw["MeanCd_FL"], errors="coerce")
    df_raw["WheelRear"] = 2.0 * pd.to_numeric(df_raw["MeanCd_RL"], errors="coerce")
    df_raw["Wheel"] = df_raw["WheelFront"] + df_raw["WheelRear"]
    df_raw["WheelHouse"] = 2.0 * (
        pd.to_numeric(df_raw["MeanCd_wh_FL"], errors="coerce")
        + pd.to_numeric(df_raw["MeanCd_wh_RL"], errors="coerce")
    )

    idx_min = df_raw["MeanCd"].idxmin()
    idx_max = df_raw["MeanCd"].idxmax()
    row_min = df_raw.loc[[idx_min]]
    row_max = df_raw.loc[[idx_max]]

    row_min.to_csv(output_dir / "sample_min_MeanCd.csv", index=False)
    row_max.to_csv(output_dir / "sample_max_MeanCd.csv", index=False)

    cols = ["Wheel"]
    if "case" in df_raw.columns:
        cols = ["case"] + cols
    df_raw[cols].to_csv(output_dir / "all_samples_Wheel_total_drag.csv", index=False)

    if not has_closed_rim_baseline(df_raw):
        print(
            "Warning: closed-rim baseline case 0 is missing; "
            "skip DeltaCd figures and CSV files."
        )
        return None

    df_delta = df_raw.copy()
    baseline = closed_rim_baseline_row(df_delta)
    row_baseline = df_delta.loc[[baseline.name]]
    row_baseline.to_csv(output_dir / "sample_closed_rim_baseline.csv", index=False)

    baseline_cd = numeric_scalar(baseline["MeanCd"], "MeanCd")
    baseline_wh = numeric_scalar(baseline["WheelHouse"], "WheelHouse")
    df_delta["DeltaCd"] = df_delta["MeanCd"] - baseline_cd
    df_delta["DeltaCd_x1000"] = (1000.0 * df_delta["DeltaCd"]).round(1)
    df_delta["DeltaWheelHouse"] = df_delta["WheelHouse"] - baseline_wh
    df_delta["DeltaWheelHouse_x1000"] = (1000.0 * df_delta["DeltaWheelHouse"]).round(1)
    df_delta.to_csv(output_dir / "all_samples_with_DeltaCd.csv", index=False)

    if "case" in df_delta.columns:

        def _fmt_wheelhouse_delta_x1000(v: float) -> float | int:
            x = round(float(v), 1)
            return int(x) if abs(x - int(x)) < 1e-9 else x

        df_meta_wh = pd.DataFrame(
            {
                "stl_filename": [
                    f"spoke_{int(c):03d}" for c in df_delta["case"].astype(int)
                ],
                "DeltaCd_x1000": [
                    _fmt_wheelhouse_delta_x1000(v)
                    for v in df_delta["DeltaWheelHouse_x1000"]
                ],
            }
        )
        df_meta_wh.to_csv(output_dir / "metadata_wheelhouse.csv", index=False)

    set_plot_theme(style="whitegrid", context="notebook")
    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df_delta,
        x="DeltaCd_x1000",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(r"$\Delta C_D\times 1000 = 1000(C_D - C_{D,CR})$")
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "DeltaCd_x1000_distribution.png", dpi)
    plt.close(fig)

    x_col = "case" if "case" in df_delta.columns else None
    if x_col is None:
        df_delta = df_delta.reset_index().rename(columns={"index": "sample_id"})
        x_col = "sample_id"

    fig, ax = plt.subplots(figsize=(11.5, 5.2))
    plot_plain_scatter(
        ax,
        df_delta[x_col],
        df_delta["DeltaCd_x1000"],
        s=18,
        alpha=SCATTER_ALPHA,
        case_values=closed_rim_case_values(df_delta),
    )
    ax.set_xlabel(x_col)
    ax.set_ylabel(display_label("DeltaCd_x1000"))
    fig.tight_layout()
    save_figure(fig, output_dir, "DeltaCd_x1000_by_sample.png", dpi)
    plt.close(fig)
    return df_delta


def plot_single_feature_distributions(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    for col in TARGET_COLUMNS:
        label = short_label(col)
        fig, ax = plt.subplots(figsize=(7.5, 5.5))
        sns.histplot(
            data=df,
            x=col,
            bins=28,
            stat="density",
            kde=True,
            color=DIST_COLOR,
            edgecolor="white",
            linewidth=0.5,
            alpha=0.9,
            ax=ax,
        )
        ax.set_xlabel(label)
        ax.set_ylabel("Density")
        fig.tight_layout()
        save_figure(fig, output_dir, f"{col}_distribution.png", dpi)
        plt.close(fig)


def plot_additional_cd_distributions(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    extra_dist_cols = ["WheelFront", "WheelRear", "Wheel", "WheelHouse", "WheelSupport", "Vent", "WheelTotal"]

    for col in extra_dist_cols:
        fig, ax = plt.subplots(figsize=(7.5, 5.5))
        sns.histplot(
            data=df,
            x=col,
            bins=28,
            stat="density",
            kde=True,
            color=DIST_COLOR,
            edgecolor="white",
            linewidth=0.5,
            alpha=0.9,
            ax=ax,
        )
        ax.set_xlabel(display_label(col))
        ax.set_ylabel("Density")
        fig.tight_layout()
        save_figure(fig, output_dir, f"{col}_distribution.png", dpi)
        plt.close(fig)


def plot_pair_relationships(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    pair = sns.pairplot(
        df[TARGET_COLUMNS],
        corner=False,
        diag_kind="hist",
        height=PAIRPLOT_PANEL_HEIGHT,
        plot_kws={
            "s": 0,
            "alpha": 0.0,
            "linewidth": 0,
        },
        diag_kws={
            "bins": 28,
            "color": SCATTER_COLOR,
            "edgecolor": "white",
            "alpha": 0.85,
        },
    )
    add_pairplot_plain_scatter(pair, df, TARGET_COLUMNS, s=18)
    style_pairplot_axes(pair, TARGET_COLUMNS)
    save_figure(
        pair.figure,
        output_dir,
        "pairplot_aero_coeffs.png",
        dpi,
        show_grid=False,
        bbox_inches="tight",
    )
    plt.close(pair.figure)


def plot_cd_pair_relationships(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    pair = sns.pairplot(
        df[CD_PAIR_COLUMNS],
        corner=False,
        diag_kind="hist",
        height=PAIRPLOT_PANEL_HEIGHT,
        plot_kws={
            "s": 0,
            "alpha": 0.0,
            "linewidth": 0,
        },
        diag_kws={
            "bins": 28,
            "color": SCATTER_COLOR,
            "edgecolor": "white",
            "alpha": 0.85,
        },
    )
    add_pairplot_plain_scatter(pair, df, CD_PAIR_COLUMNS, s=18)
    style_pairplot_axes(pair, CD_PAIR_COLUMNS)
    save_figure(
        pair.figure,
        output_dir,
        "pairplot_cd_components.png",
        dpi,
        show_grid=False,
        bbox_inches="tight",
    )
    plt.close(pair.figure)


def plot_cd_front_rear_relationships(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    fig, axes = plt.subplots(1, 3, figsize=(19, 5.2))

    plot_plain_scatter(axes[0], df["Cd"], df["WheelFront"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[0], df["Cd"], df["WheelFront"])
    axes[0].set_xlabel(display_label("Cd"))
    axes[0].set_ylabel(display_label("WheelFront"))

    plot_plain_scatter(axes[1], df["Cd"], df["WheelRear"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[1], df["Cd"], df["WheelRear"])
    axes[1].set_xlabel(display_label("Cd"))
    axes[1].set_ylabel(display_label("WheelRear"))

    plot_plain_scatter(axes[2], df["WheelFront"], df["WheelRear"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[2], df["WheelFront"], df["WheelRear"])
    axes[2].set_xlabel(display_label("WheelFront"))
    axes[2].set_ylabel(display_label("WheelRear"))

    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_WheelFront_WheelRear.png", dpi)
    plt.close(fig)


def plot_cd_wheel_suspension_relationships(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2), sharex=True)

    plot_plain_scatter(axes[0], df["Cd"], df["WheelHouse"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[0], df["Cd"], df["WheelHouse"])
    axes[0].set_xlabel(display_label("Cd"))
    axes[0].set_ylabel(display_label("WheelHouse"))

    plot_plain_scatter(axes[1], df["Cd"], df["WheelSupport"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[1], df["Cd"], df["WheelSupport"])
    axes[1].set_xlabel(display_label("Cd"))
    axes[1].set_ylabel(display_label("WheelSupport"))

    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_WheelHouse_WheelSupport.png", dpi)
    plt.close(fig)


def plot_cd_vent_relationships(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))

    plot_plain_scatter(axes[0], df["Vent"], df["Wheel"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[0], df["Vent"], df["Wheel"])
    axes[0].set_xlabel(display_label("Vent"))
    axes[0].set_ylabel(display_label("Wheel"))

    plot_plain_scatter(axes[1], df["Cd"], df["Vent"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[1], df["Cd"], df["Vent"])
    axes[1].set_xlabel(display_label("Cd"))
    axes[1].set_ylabel(display_label("Vent"))

    fig.tight_layout()
    save_figure(fig, output_dir, "Vent_vs_Wheel_and_Cd.png", dpi)
    plt.close(fig)


def plot_total_vent_distribution_and_relationship(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df,
        x="Vent",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(display_label("Vent"))
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vent_total_distribution.png", dpi)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    plot_plain_scatter(ax, df["Cd"], df["Vent"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(ax, df["Cd"], df["Vent"])
    ax.set_xlabel(display_label("Cd"))
    ax.set_ylabel(display_label("Vent"))
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_Cd_vent_total.png", dpi)
    plt.close(fig)


def plot_vent_ratio_distribution_and_relationship(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["Cd_vent_ratio_pct"] = 100.0 * df_plot["Vent"] / df_plot["Cd"]

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df_plot,
        x="Cd_vent_ratio_pct",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(r"$C_{D,\mathrm{V}}/C_D$ (%)")
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vent_ratio_distribution.png", dpi)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    plot_plain_scatter(ax, df_plot["Cd"], df_plot["Cd_vent_ratio_pct"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df_plot))
    add_regression_and_corr(ax, df_plot["Cd"], df_plot["Cd_vent_ratio_pct"])
    ax.set_xlabel(display_label("Cd"))
    ax.set_ylabel(r"$C_{D,\mathrm{V}}/C_D$ (%)")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_Cd_vent_ratio.png", dpi)
    plt.close(fig)


def plot_wheel_ratio_distribution_and_relationship(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["Cd_wheel_ratio_pct"] = 100.0 * df_plot["Wheel"] / df_plot["Cd"]

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df_plot,
        x="Cd_wheel_ratio_pct",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(r"$C_{D,\mathrm{W}}/C_D$ (%)")
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_wheel_ratio_distribution.png", dpi)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    plot_plain_scatter(ax, df_plot["Cd"], df_plot["Cd_wheel_ratio_pct"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df_plot))
    add_regression_and_corr(ax, df_plot["Cd"], df_plot["Cd_wheel_ratio_pct"])
    ax.set_xlabel(display_label("Cd"))
    ax.set_ylabel(r"$C_{D,\mathrm{W}}/C_D$ (%)")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_Cd_wheel_ratio.png", dpi)
    plt.close(fig)


def plot_wheel_suspension_ratio_distribution_and_relationship(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["Cd_wh_ws_ratio_pct"] = 100.0 * (
        df_plot["WheelHouse"] + df_plot["WheelSupport"]
    ) / df_plot["Cd"]

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df_plot,
        x="Cd_wh_ws_ratio_pct",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(r"$(C_{D,\mathrm{WH}}+C_{D,\mathrm{WS}})/C_D$ (%)")
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_wh_ws_ratio_distribution.png", dpi)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    plot_plain_scatter(ax, df_plot["Cd"], df_plot["Cd_wh_ws_ratio_pct"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df_plot))
    add_regression_and_corr(ax, df_plot["Cd"], df_plot["Cd_wh_ws_ratio_pct"])
    ax.set_xlabel(display_label("Cd"))
    ax.set_ylabel(r"$(C_{D,\mathrm{WH}}+C_{D,\mathrm{WS}})/C_D$ (%)")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_Cd_wh_ws_ratio.png", dpi)
    plt.close(fig)


def plot_ws_ratio_distribution_and_relationship(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["Cd_ws_ratio_pct"] = 100.0 * df_plot["WheelSupport"] / df_plot["Cd"]

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df_plot,
        x="Cd_ws_ratio_pct",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(r"$C_{D,\mathrm{WS}}/C_D$ (%)")
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_ws_ratio_distribution.png", dpi)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    plot_plain_scatter(ax, df_plot["Cd"], df_plot["Cd_ws_ratio_pct"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df_plot))
    add_regression_and_corr(ax, df_plot["Cd"], df_plot["Cd_ws_ratio_pct"])
    ax.set_xlabel(display_label("Cd"))
    ax.set_ylabel(r"$C_{D,\mathrm{WS}}/C_D$ (%)")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_Cd_ws_ratio.png", dpi)
    plt.close(fig)


def plot_wh_ratio_distribution_and_relationship(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["Cd_wh_ratio_pct"] = 100.0 * df_plot["WheelHouse"] / df_plot["Cd"]

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df_plot,
        x="Cd_wh_ratio_pct",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(r"$C_{D,\mathrm{WH}}/C_D$ (%)")
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_wh_ratio_distribution.png", dpi)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    plot_plain_scatter(ax, df_plot["Cd"], df_plot["Cd_wh_ratio_pct"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df_plot))
    add_regression_and_corr(ax, df_plot["Cd"], df_plot["Cd_wh_ratio_pct"])
    ax.set_xlabel(display_label("Cd"))
    ax.set_ylabel(r"$C_{D,\mathrm{WH}}/C_D$ (%)")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_Cd_wh_ratio.png", dpi)
    plt.close(fig)


def plot_fl_rl_wh_ws_ratio_distribution_and_relationship(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["Cd_fl_rl_wh_ws_ratio_pct"] = 100.0 * df_plot["WheelTotal"] / df_plot["Cd"]

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    sns.histplot(
        data=df_plot,
        x="Cd_fl_rl_wh_ws_ratio_pct",
        bins=28,
        stat="density",
        kde=True,
        color=DIST_COLOR,
        edgecolor="white",
        linewidth=0.5,
        alpha=0.9,
        ax=ax,
    )
    ax.set_xlabel(r"$C_{D,\mathrm{W,total}}/C_D$ (%)")
    ax.set_ylabel("Density")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_fl_rl_wh_ws_ratio_distribution.png", dpi)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.8, 5.5))
    plot_plain_scatter(ax, df_plot["Cd"], df_plot["Cd_fl_rl_wh_ws_ratio_pct"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df_plot))
    add_regression_and_corr(ax, df_plot["Cd"], df_plot["Cd_fl_rl_wh_ws_ratio_pct"])
    ax.set_xlabel(display_label("Cd"))
    ax.set_ylabel(r"$C_{D,\mathrm{W,total}}/C_D$ (%)")
    fig.tight_layout()
    save_figure(fig, output_dir, "Cd_vs_Cd_fl_rl_wh_ws_ratio.png", dpi)
    plt.close(fig)


def plot_wheel_key_ratio_comparison(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["WheelTotal_ratio_pct"] = 100.0 * df_plot["WheelTotal"] / df_plot["Cd"]
    df_plot["Wheel_ratio_pct"] = 100.0 * df_plot["Wheel"] / df_plot["Cd"]
    df_plot["WheelHouse_ratio_pct"] = 100.0 * df_plot["WheelHouse"] / df_plot["Cd"]
    df_plot["WheelSupport_ratio_pct"] = 100.0 * df_plot["WheelSupport"] / df_plot["Cd"]

    ratio_long = df_plot[
        [
            "WheelTotal_ratio_pct",
            "Wheel_ratio_pct",
            "WheelHouse_ratio_pct",
            "WheelSupport_ratio_pct",
        ]
    ].melt(var_name="Component", value_name="RatioPct")
    ratio_long["Component"] = ratio_long["Component"].map(
        {
            "WheelTotal_ratio_pct": display_label("WheelTotal"),
            "Wheel_ratio_pct": display_label("Wheel"),
            "WheelHouse_ratio_pct": display_label("WheelHouse"),
            "WheelSupport_ratio_pct": display_label("WheelSupport"),
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(15.2, 6.2))

    sns.histplot(
        data=ratio_long,
        x="RatioPct",
        hue="Component",
        bins=28,
        kde=True,
        element="step",
        stat="density",
        common_norm=False,
        palette=["#1d3557", "#2a9d8f", "#e76f51", "#7b2cbf"],
        alpha=0.35,
        ax=axes[0],
    )
    axes[0].set_xlabel(r"Ratio to $C_D$ (%)")
    axes[0].set_ylabel("Density")

    sns.boxplot(
        data=ratio_long,
        x="Component",
        y="RatioPct",
        hue="Component",
        palette=["#1d3557", "#2a9d8f", "#e76f51", "#7b2cbf"],
        width=0.55,
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_xlabel("")
    axes[1].set_ylabel(r"Ratio to $C_D$ (%)")

    style_ratio_comparison_axes(axes, emphasized=True)
    fig.tight_layout()
    save_figure(
        fig,
        output_dir,
        "WheelTotal_Wheel_WheelHouse_WheelSupport_ratio_comparison.png",
        dpi,
    )
    plt.close(fig)


def plot_wheel_key_ratio_comparison_with_vent(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["WheelTotal_ratio_pct"] = 100.0 * df_plot["WheelTotal"] / df_plot["Cd"]
    df_plot["Wheel_ratio_pct"] = 100.0 * df_plot["Wheel"] / df_plot["Cd"]
    df_plot["WheelHouse_ratio_pct"] = 100.0 * df_plot["WheelHouse"] / df_plot["Cd"]
    df_plot["WheelSupport_ratio_pct"] = 100.0 * df_plot["WheelSupport"] / df_plot["Cd"]
    df_plot["Vent_ratio_pct"] = 100.0 * df_plot["Vent"] / df_plot["Cd"]

    ratio_long = df_plot[
        [
            "WheelTotal_ratio_pct",
            "Wheel_ratio_pct",
            "WheelHouse_ratio_pct",
            "WheelSupport_ratio_pct",
            "Vent_ratio_pct",
        ]
    ].melt(var_name="Component", value_name="RatioPct")
    ratio_long["Component"] = ratio_long["Component"].map(
        {
            "WheelTotal_ratio_pct": display_label("WheelTotal"),
            "Wheel_ratio_pct": display_label("Wheel"),
            "WheelHouse_ratio_pct": display_label("WheelHouse"),
            "WheelSupport_ratio_pct": display_label("WheelSupport"),
            "Vent_ratio_pct": display_label("Vent"),
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(15, 5.8))

    sns.histplot(
        data=ratio_long,
        x="RatioPct",
        hue="Component",
        bins=28,
        kde=True,
        element="step",
        stat="density",
        common_norm=False,
        palette=["#1d3557", "#2a9d8f", "#e76f51", "#7b2cbf", "#f4a261"],
        alpha=0.35,
        ax=axes[0],
    )
    axes[0].set_xlabel(r"Ratio to $C_D$ (%)")
    axes[0].set_ylabel("Density")

    sns.boxplot(
        data=ratio_long,
        x="Component",
        y="RatioPct",
        hue="Component",
        palette=["#1d3557", "#2a9d8f", "#e76f51", "#7b2cbf", "#f4a261"],
        width=0.55,
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_xlabel("")
    axes[1].set_ylabel(r"Ratio to $C_D$ (%)")

    style_ratio_comparison_axes(axes)
    fig.tight_layout()
    save_figure(
        fig,
        output_dir,
        "WheelTotal_Wheel_WheelHouse_WheelSupport_Vent_ratio_comparison.png",
        dpi,
    )
    plt.close(fig)


def plot_wheel_key_ratio_comparison_with_vent_no_support(
    df: pd.DataFrame, output_dir: Path, dpi: int
) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    df_plot = df.copy()
    df_plot["WheelTotal_ratio_pct"] = 100.0 * df_plot["WheelTotal"] / df_plot["Cd"]
    df_plot["Wheel_ratio_pct"] = 100.0 * df_plot["Wheel"] / df_plot["Cd"]
    df_plot["WheelHouse_ratio_pct"] = 100.0 * df_plot["WheelHouse"] / df_plot["Cd"]
    df_plot["Vent_ratio_pct"] = 100.0 * df_plot["Vent"] / df_plot["Cd"]

    ratio_long = df_plot[
        [
            "WheelTotal_ratio_pct",
            "Wheel_ratio_pct",
            "WheelHouse_ratio_pct",
            "Vent_ratio_pct",
        ]
    ].melt(var_name="Component", value_name="RatioPct")
    ratio_long["Component"] = ratio_long["Component"].map(
        {
            "WheelTotal_ratio_pct": display_label("WheelTotal"),
            "Wheel_ratio_pct": display_label("Wheel"),
            "WheelHouse_ratio_pct": display_label("WheelHouse"),
            "Vent_ratio_pct": display_label("Vent"),
        }
    )

    fig, axes = plt.subplots(1, 2, figsize=(15.2, 6.2))

    sns.histplot(
        data=ratio_long,
        x="RatioPct",
        hue="Component",
        bins=28,
        kde=True,
        element="step",
        stat="density",
        common_norm=False,
        palette=["#1d3557", "#2a9d8f", "#e76f51", "#f4a261"],
        alpha=0.35,
        ax=axes[0],
    )
    axes[0].set_xlabel(r"Ratio to $C_D$ (%)")
    axes[0].set_ylabel("Density")

    sns.boxplot(
        data=ratio_long,
        x="Component",
        y="RatioPct",
        hue="Component",
        palette=["#1d3557", "#2a9d8f", "#e76f51", "#f4a261"],
        width=0.55,
        dodge=False,
        legend=False,
        ax=axes[1],
    )
    axes[1].set_xlabel("")
    axes[1].set_ylabel(r"Ratio to $C_D$ (%)")

    style_ratio_comparison_axes(axes, emphasized=True)
    fig.tight_layout(w_pad=3.0)
    save_figure(
        fig,
        output_dir,
        "WheelTotal_Wheel_WheelHouse_Vent_ratio_comparison.png",
        dpi,
    )
    plt.close(fig)


def plot_cl_correlation_relationships(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    fig, axes = plt.subplots(1, 3, figsize=(19, 5.2))

    plot_plain_scatter(axes[0], df["MeanCl"], df["MeanClf"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[0], df["MeanCl"], df["MeanClf"])
    axes[0].set_xlabel(display_label("Cl"))
    axes[0].set_ylabel(display_label("Clf"))

    plot_plain_scatter(axes[1], df["MeanCl"], df["MeanClr"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[1], df["MeanCl"], df["MeanClr"])
    axes[1].set_xlabel(display_label("Cl"))
    axes[1].set_ylabel(display_label("Clr"))

    plot_plain_scatter(axes[2], df["MeanClf"], df["MeanClr"], s=28, alpha=SCATTER_ALPHA, case_values=closed_rim_case_values(df))
    add_regression_and_corr(axes[2], df["MeanClf"], df["MeanClr"])
    axes[2].set_xlabel(display_label("Clf"))
    axes[2].set_ylabel(display_label("Clr"))

    fig.tight_layout()
    save_figure(fig, output_dir, "Cl_Clf_Clr_correlations.png", dpi)
    plt.close(fig)


def plot_delta_cd_cl_pairplot(df: pd.DataFrame, output_dir: Path, dpi: int) -> None:
    set_plot_theme(style="whitegrid", context="notebook")

    cols = ["DeltaCd_x1000", "MeanCl", "MeanClf", "MeanClr"]
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns for DeltaCd/Cl pairplot: {missing}")

    pair = sns.pairplot(
        df[cols],
        corner=False,
        diag_kind="hist",
        height=PAIRPLOT_PANEL_HEIGHT,
        plot_kws={
            "s": 0,
            "alpha": 0.0,
            "linewidth": 0,
        },
        diag_kws={
            "bins": 28,
            "color": SCATTER_COLOR,
            "edgecolor": "white",
            "alpha": 0.85,
        },
    )
    add_pairplot_plain_scatter(pair, df, cols, s=18)
    style_pairplot_axes(pair, cols)

    save_figure(
        pair.figure,
        output_dir,
        "pairplot_DeltaCd_x1000_Cl_Clf_Clr.png",
        dpi,
        show_grid=False,
        bbox_inches="tight",
    )
    plt.close(pair.figure)


def main() -> None:
    args = parse_args()
    if args.input:
        input_path = Path(args.input).expanduser()
    else:
        input_path = resolve_default_input_csv()
    script_dir = Path(__file__).resolve().parent

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser()
    elif FORCES_DIR == Path("-"):
        output_dir = input_path.parent / "Figures"
    else:
        output_dir = DEFAULT_OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        fallback = script_dir / input_path.name
        if fallback.exists():
            input_path = fallback
        else:
            raise FileNotFoundError(
                f"Input CSV not found: {input_path} (also tried {fallback})"
            )

    df_raw = normalize_input_columns(pd.read_csv(input_path))
    validate_columns(df_raw)
    df_raw = coerce_numeric_columns(df_raw)
    if df_raw.empty:
        raise ValueError("The selected input data contains no rows.")

    df = add_derived_columns(df_raw)

    df_delta = export_cd_extremes_and_delta(df, output_dir, args.dpi)
    delta_outputs_generated = df_delta is not None
    if df_delta is not None:
        df = df_delta

    plot_single_feature_distributions(df, output_dir, args.dpi)
    plot_additional_cd_distributions(df, output_dir, args.dpi)
    plot_pair_relationships(df, output_dir, args.dpi)
    plot_cd_pair_relationships(df, output_dir, args.dpi)
    plot_cd_front_rear_relationships(df, output_dir, args.dpi)
    plot_cd_wheel_suspension_relationships(df, output_dir, args.dpi)
    plot_cd_vent_relationships(df, output_dir, args.dpi)
    plot_total_vent_distribution_and_relationship(df, output_dir, args.dpi)
    plot_vent_ratio_distribution_and_relationship(df, output_dir, args.dpi)
    plot_wheel_ratio_distribution_and_relationship(df, output_dir, args.dpi)
    plot_wheel_suspension_ratio_distribution_and_relationship(df, output_dir, args.dpi)
    plot_ws_ratio_distribution_and_relationship(df, output_dir, args.dpi)
    plot_wh_ratio_distribution_and_relationship(df, output_dir, args.dpi)
    plot_fl_rl_wh_ws_ratio_distribution_and_relationship(df, output_dir, args.dpi)
    plot_wheel_key_ratio_comparison(df, output_dir, args.dpi)
    plot_wheel_key_ratio_comparison_with_vent(df, output_dir, args.dpi)
    plot_wheel_key_ratio_comparison_with_vent_no_support(df, output_dir, args.dpi)
    plot_cl_correlation_relationships(df, output_dir, args.dpi)
    if delta_outputs_generated:
        plot_delta_cd_cl_pairplot(df, output_dir, args.dpi)

    print("Finished plotting.")
    print(f"Input CSV: {input_path.resolve()}")
    print(f"Output directory: {output_dir.resolve()}")
    print("Generated files:")
    figure_files = [
        *(f"{col}_distribution.png" for col in TARGET_COLUMNS),
        "WheelFront_distribution.png",
        "WheelRear_distribution.png",
        "Wheel_distribution.png",
        "WheelHouse_distribution.png",
        "WheelSupport_distribution.png",
        "Vent_distribution.png",
        "WheelTotal_distribution.png",
        "pairplot_aero_coeffs.png",
        "pairplot_cd_components.png",
        "Cd_vs_WheelFront_WheelRear.png",
        "Cd_vs_WheelHouse_WheelSupport.png",
        "Vent_vs_Wheel_and_Cd.png",
        "Cd_vent_total_distribution.png",
        "Cd_vs_Cd_vent_total.png",
        "Cd_vent_ratio_distribution.png",
        "Cd_vs_Cd_vent_ratio.png",
        "Cd_wheel_ratio_distribution.png",
        "Cd_vs_Cd_wheel_ratio.png",
        "Cd_wh_ws_ratio_distribution.png",
        "Cd_vs_Cd_wh_ws_ratio.png",
        "Cd_ws_ratio_distribution.png",
        "Cd_vs_Cd_ws_ratio.png",
        "Cd_wh_ratio_distribution.png",
        "Cd_vs_Cd_wh_ratio.png",
        "Cd_fl_rl_wh_ws_ratio_distribution.png",
        "Cd_vs_Cd_fl_rl_wh_ws_ratio.png",
        "WheelTotal_Wheel_WheelHouse_WheelSupport_ratio_comparison.png",
        "WheelTotal_Wheel_WheelHouse_WheelSupport_Vent_ratio_comparison.png",
        "WheelTotal_Wheel_WheelHouse_Vent_ratio_comparison.png",
        "Cl_Clf_Clr_correlations.png",
    ]
    if delta_outputs_generated:
        figure_files.extend(
            [
                "pairplot_DeltaCd_x1000_Cl_Clf_Clr.png",
                "DeltaCd_x1000_distribution.png",
                "DeltaCd_x1000_by_sample.png",
            ]
        )
    for filename in figure_files:
        print(f"- {figure_filename(filename)}")
    print("- sample_min_MeanCd.csv")
    print("- sample_max_MeanCd.csv")
    if delta_outputs_generated:
        print("- sample_closed_rim_baseline.csv")
    if delta_outputs_generated:
        print("- all_samples_with_DeltaCd.csv")
    if delta_outputs_generated:
        print("- metadata_wheelhouse.csv")
    print("- all_samples_Wheel_total_drag.csv")


if __name__ == "__main__":
    main()
