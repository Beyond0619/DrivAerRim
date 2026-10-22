"""Preprocess Wheel VTP surfaces into a pressure-only or WSS-only PyG dataset.

Examples
--------
Pressure:
    python process_wheel_vtp_separate.py --input-dir "I:/data/raw" --output-root "I:/data/wheel_pressure" --target pressure

WSS:
    python process_wheel_vtp_separate.py --input-dir "I:/data/raw" --output-root "I:/data/wheel_wss" --target wss
"""

import argparse
import os
from pathlib import Path

import numpy as np
import pyvista as pv
import torch
from torch_geometric.data import Data
from tqdm import tqdm


def _as_point_array(mesh: pv.DataSet, key: str, file_path: Path) -> np.ndarray:
    """Get an array as point data; convert cell data to point data when necessary."""
    if key not in mesh.point_data and key in mesh.cell_data:
        mesh = mesh.cell_data_to_point_data()

    if key not in mesh.point_data:
        raise KeyError(
            f"Array '{key}' was not found in point or cell data in {file_path}."
        )
    return np.asarray(mesh.point_data[key])


def _as_scalar(mesh: pv.DataSet, key: str, file_path: Path) -> np.ndarray:
    arr = _as_point_array(mesh, key, file_path)
    if arr.ndim == 1:
        arr = arr[:, None]
    expected = (mesh.n_points, 1)
    if arr.shape != expected:
        raise ValueError(
            f"Expected scalar array '{key}' with shape {expected}, "
            f"got {arr.shape} in {file_path}."
        )
    return arr


def _save_data(data: Data, output_path: Path) -> None:
    """Atomically save one PyG Data object."""
    tmp_path = output_path.with_suffix(".pt.tmp")
    torch.save(data, tmp_path)
    os.replace(tmp_path, output_path)


def process_vtp_data(
    input_dir,
    output_root,
    target: str = "pressure",
    pressure_key: str = "MeanPressure",
    wss_i_key: str = "MeanWSSi",
    wss_j_key: str = "MeanWSSj",
    wss_k_key: str = "MeanWSSk",
    overwrite: bool = False,
) -> None:
    input_dir = Path(input_dir)
    output_root = Path(output_root)
    target = target.lower()

    if target not in {"pressure", "wss"}:
        raise ValueError("target must be either 'pressure' or 'wss'.")

    if not input_dir.is_dir():
        raise FileNotFoundError(f"VTP input directory does not exist: {input_dir}")

    vtp_files = sorted(
        (p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".vtp"),
        key=lambda p: p.name.casefold(),
    )
    if not vtp_files:
        raise FileNotFoundError(f"No .vtp files found in {input_dir}")

    stems = [p.stem.casefold() for p in vtp_files]
    if len(stems) != len(set(stems)):
        raise ValueError("VTP filenames collide when compared case-insensitively.")

    processed_dir = output_root / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    order_path = output_root / "order_processed.txt"

    output_files = [processed_dir / f"{p.stem}.pt" for p in vtp_files]
    existing = [p for p in output_files if p.exists()]
    if (existing or order_path.exists()) and not overwrite:
        raise FileExistsError(
            f"Output already exists under {output_root}; use --overwrite to replace it."
        )

    sample_names = []
    channel_count = 1 if target == "pressure" else 3
    total = torch.zeros(channel_count, dtype=torch.float64)
    total_squared = torch.zeros(channel_count, dtype=torch.float64)
    value_count = 0

    for file_path in tqdm(vtp_files, desc=f"Processing {target} VTP files"):
        mesh = pv.read(file_path)
        if mesh.n_points == 0:
            raise ValueError(f"VTP file has no points: {file_path}")

        # Read only the requested target fields.
        if target == "pressure":
            targets = _as_scalar(mesh, pressure_key, file_path)
        else:
            wss_i = _as_scalar(mesh, wss_i_key, file_path)
            wss_j = _as_scalar(mesh, wss_j_key, file_path)
            wss_k = _as_scalar(mesh, wss_k_key, file_path)
            targets = np.concatenate((wss_i, wss_j, wss_k), axis=1)

        mesh = mesh.compute_normals(
            cell_normals=False,
            point_normals=True,
            auto_orient_normals=True,
        )
        coords = np.asarray(mesh.points)
        normals = np.asarray(mesh.point_data["Normals"])
        feat = np.concatenate((coords, normals), axis=1)

        for name, arr in (
            ("coordinates", coords),
            ("normals", normals),
            (target, targets),
        ):
            if not np.isfinite(arr).all():
                raise ValueError(f"Non-finite values in {name} in {file_path}")

        data = Data(
            pos=torch.as_tensor(coords, dtype=torch.float32),
            x=torch.as_tensor(targets, dtype=torch.float32),
            c=torch.as_tensor(normals, dtype=torch.float32),
            feat=torch.as_tensor(feat, dtype=torch.float32),
        )
        data.filename = file_path.stem

        _save_data(data, processed_dir / f"{file_path.stem}.pt")

        values = data.x.to(dtype=torch.float64)
        total += values.sum(dim=0)
        total_squared += values.square().sum(dim=0)
        value_count += values.shape[0]
        sample_names.append(file_path.stem)

    if value_count < 2:
        raise ValueError("At least two point values are required to calculate statistics.")

    tmp_order = order_path.with_suffix(".txt.tmp")
    tmp_order.write_text(
        "".join(f"{name}\n" for name in sample_names),
        encoding="utf-8",
    )
    os.replace(tmp_order, order_path)

    mean = total / value_count
    variance = (
        total_squared - total.square() / value_count
    ) / (value_count - 1)
    std = variance.clamp_min(0).sqrt()

    print("\n" + "=" * 70)
    print(f"Target: {target}")
    print(f"Processed {len(sample_names)} samples into: {processed_dir}")
    if target == "pressure":
        print(f"x channel: {pressure_key} (shape [N, 1])")
    else:
        print(f"x channels: {wss_i_key}, {wss_j_key}, {wss_k_key} (shape [N, 3])")
    print(f"Global mean: {mean.tolist()}")
    print(f"Global std:  {std.tolist()}")
    print(f"Order file: {order_path}")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, required=True,
                        help="Directory containing source VTP files")
    parser.add_argument("--output-root", type=Path, required=True,
                        help="Output root; creates processed/ and order_processed.txt")
    parser.add_argument("--target", choices=("pressure", "wss"), required=True,
                        help="Choose exactly one target to preprocess")
    parser.add_argument("--pressure-key", default="MeanPressure",
                        help="Pressure array name")
    parser.add_argument("--wss-i-key", default="MeanWSSi",
                        help="WSS i-component array name")
    parser.add_argument("--wss-j-key", default="MeanWSSj",
                        help="WSS j-component array name")
    parser.add_argument("--wss-k-key", default="MeanWSSk",
                        help="WSS k-component array name")
    parser.add_argument("--overwrite", action="store_true",
                        help="Replace existing output files")
    args = parser.parse_args()

    process_vtp_data(
        input_dir=args.input_dir,
        output_root=args.output_root,
        target=args.target,
        pressure_key=args.pressure_key,
        wss_i_key=args.wss_i_key,
        wss_j_key=args.wss_j_key,
        wss_k_key=args.wss_k_key,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
