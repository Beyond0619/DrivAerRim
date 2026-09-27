#!/usr/bin/env python3
"""Prepare numbered rim case directories from a reusable template."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile


RIM_NAS_NAME = "rims_clean_sm_open_.nas"
VALID_NAS_LAYOUTS = ("flat", "subdir", "subdir_range")


def env_int(name: str, default: int | None) -> int | None:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {value!r}.") from exc


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare Rim case directories and install the matching rim NAS file."
    )
    parser.add_argument(
        "--template-dir",
        default=os.environ.get("TEMPLATE_DIR", "-"),
        help="Case-template directory (env: TEMPLATE_DIR).",
    )
    parser.add_argument(
        "--rims-nas-dir",
        default=os.environ.get("RIMS_NAS_DIR", "-"),
        help="Root directory containing rim NAS files (env: RIMS_NAS_DIR).",
    )
    parser.add_argument(
        "--output-parent",
        default=os.environ.get("OUTPUT_PARENT", "-"),
        help="Destination parent for Rim directories (env: OUTPUT_PARENT).",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=env_int("START", 1),
        help="First rim index; default: 1 (env: START).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=env_int("N", 500),
        help="Number of cases; default: 500 (env: N).",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=env_int("END", None),
        help="Inclusive last rim index; overrides --count (env: END).",
    )
    parser.add_argument(
        "--indices",
        default=os.environ.get("INDICES", ""),
        help='Exact indices separated by spaces or commas, for example "4 7 9".',
    )
    parser.add_argument(
        "--nas-layout",
        choices=VALID_NAS_LAYOUTS,
        default=os.environ.get("NAS_LAYOUT", "subdir_range").replace(
            "cad_group", "subdir_range"
        ),
        help="NAS source layout (env: NAS_LAYOUT).",
    )
    parser.add_argument(
        "--rim-pad",
        type=int,
        default=env_int("RIM_PAD", 4),
        help="Zero-padding width for Rim case directories; default: 4.",
    )
    parser.add_argument(
        "--nas-pad",
        type=int,
        default=env_int("NAS_PAD", 3),
        help="Zero-padding width for source NAS identifiers; default: 3.",
    )
    parser.add_argument(
        "--range-size",
        type=int,
        default=env_int("RIMS_NAS_RANGE_SIZE", 50),
        help="Directory range size for subdir_range; default: 50.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=env_flag("DRY_RUN"),
        help="Print planned changes without creating, deleting, or copying files.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        default=env_flag("STRICT"),
        help="Return a non-zero status when any source NAS file is missing.",
    )
    return parser.parse_args()


def parse_indices(text: str) -> list[int]:
    tokens = text.replace(",", " ").split()
    try:
        return [int(token) for token in tokens]
    except ValueError as exc:
        raise SystemExit("--indices must contain only integers.") from exc


def build_indices(args: argparse.Namespace) -> list[int]:
    if args.indices.strip():
        indices = parse_indices(args.indices)
    elif args.end is not None:
        if args.end < args.start:
            raise SystemExit("--end must be greater than or equal to --start.")
        indices = list(range(args.start, args.end + 1))
    else:
        if args.count <= 0:
            raise SystemExit("--count must be greater than zero.")
        indices = list(range(args.start, args.start + args.count))

    if not indices:
        raise SystemExit("No rim indices were selected.")
    if any(index <= 0 for index in indices):
        raise SystemExit("Rim indices must be positive integers.")
    if len(indices) != len(set(indices)):
        raise SystemExit("Duplicate rim indices are not allowed.")
    return indices


def require_public_path(value: str, label: str, *, must_exist: bool) -> Path:
    if not value or value == "-":
        raise SystemExit(f"{label} is required; replace the public '-' placeholder.")
    path = Path(value).expanduser().resolve()
    if must_exist and not path.is_dir():
        raise SystemExit(f"{label} directory not found: {path}")
    return path


def rim_name(index: int, pad: int) -> str:
    return f"Rim{index:0{pad}d}" if pad > 0 else f"Rim{index}"


def padded(index: int, pad: int) -> str:
    return f"{index:0{pad}d}" if pad > 0 else str(index)


def source_nas_path(
    root: Path,
    index: int,
    pad: int,
    layout: str,
    range_size: int,
) -> Path:
    number = padded(index, pad)
    if layout == "subdir_range":
        range_start = ((index - 1) // range_size) * range_size + 1
        range_end = range_start + range_size - 1
        range_dir = f"{padded(range_start, pad)}-{padded(range_end, pad)}"
        candidate = root / range_dir / number / RIM_NAS_NAME
    elif layout == "subdir":
        candidate = root / number / RIM_NAS_NAME
    else:
        candidate = root / f"rims_clean_sm_open_{number}.nas"

    if candidate.is_file():
        return candidate
    return candidate.parent / f"rims_clean_sm_open_{number}.nas"


def update_slurm_job_name(path: Path, job_name: str, dry_run: bool) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"^#SBATCH\s+-J\s+.*$", re.MULTILINE)
    if not pattern.search(text):
        print(f"  WARNING: no '#SBATCH -J' line in {path.name}; leave unchanged")
        return
    updated = pattern.sub(f"#SBATCH -J {job_name}", text, count=1)
    print(f"  Set {path.name} job name to {job_name}")
    if dry_run or updated == text:
        return

    mode = path.stat().st_mode
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(updated)
        temporary = Path(handle.name)
    temporary.chmod(mode)
    temporary.replace(path)


def prepare_case(
    index: int,
    args: argparse.Namespace,
    template_dir: Path,
    rims_nas_dir: Path,
    output_parent: Path,
) -> bool:
    name = rim_name(index, args.rim_pad)
    number = padded(index, args.rim_pad)
    destination = output_parent / name
    print(f"---- {name} ----")

    source = source_nas_path(
        rims_nas_dir,
        index,
        args.nas_pad,
        args.nas_layout,
        args.range_size,
    )
    if not source.is_file():
        print(f"  WARNING: source NAS not found: {source}")
        return False

    if destination.is_dir():
        print("  Case exists; update scripts and rim NAS only.")
    else:
        print(f"  Copy template: {template_dir} -> {destination}")
        if not args.dry_run:
            shutil.copytree(template_dir, destination, symlinks=True)

    for script_name in ("run.sh", "run_tetralith.sh"):
        update_slurm_job_name(destination / script_name, f"R{index}", args.dry_run)
    for script_name in ("post.sh", "post_tetralith_gpu.sh"):
        update_slurm_job_name(destination / script_name, f"R{number}_Post", args.dry_run)

    cad_dir = destination / "CAD"
    target = cad_dir / RIM_NAS_NAME
    action = "Replace" if target.is_file() else "Install"
    print(f"  {action} NAS: {source} -> {target}")
    if args.dry_run:
        return True

    cad_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return True


def main() -> int:
    args = parse_args()
    if args.rim_pad < 0:
        raise SystemExit("--rim-pad must be zero or greater.")
    if args.nas_pad < 0:
        raise SystemExit("--nas-pad must be zero or greater.")
    if args.range_size <= 0:
        raise SystemExit("--range-size must be greater than zero.")

    template_dir = require_public_path(
        args.template_dir, "TEMPLATE_DIR/--template-dir", must_exist=True
    )
    rims_nas_dir = require_public_path(
        args.rims_nas_dir, "RIMS_NAS_DIR/--rims-nas-dir", must_exist=True
    )
    output_parent = require_public_path(
        args.output_parent, "OUTPUT_PARENT/--output-parent", must_exist=False
    )
    if any(
        output_parent == source_root or output_parent.is_relative_to(source_root)
        for source_root in (template_dir, rims_nas_dir)
    ):
        raise SystemExit(
            "OUTPUT_PARENT must not be the template/NAS source or a directory inside it."
        )
    if not args.dry_run:
        output_parent.mkdir(parents=True, exist_ok=True)

    indices = build_indices(args)
    missing = 0
    for index in indices:
        if not prepare_case(
            index, args, template_dir, rims_nas_dir, output_parent
        ):
            missing += 1

    action = "Would prepare" if args.dry_run else "Prepared"
    print(
        f"Done. {action} {len(indices)} case(s) under {output_parent}; "
        f"missing NAS files: {missing}."
    )
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    sys.exit(main())
