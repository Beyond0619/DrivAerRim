from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np


def make_split_indices(
    total_samples: int,
    train_size: int,
    val_size: int,
    test_size: int,
    seed: int = 42,
    train_sample_size: Optional[int] = None,
) -> Dict[str, np.ndarray]:
    """Create reproducible, non-overlapping indices for the requested splits."""
    sizes = {
        "train": train_size,
        "val": val_size,
        "test": test_size,
    }
    if total_samples < 0 or any(size < 0 for size in sizes.values()):
        raise ValueError("Sample counts must be non-negative.")
    if sum(sizes.values()) > total_samples:
        raise ValueError(
            f"Requested {sum(sizes.values())} split samples from "
            f"a dataset with {total_samples} samples."
        )
    if train_sample_size is not None and not 0 <= train_sample_size <= train_size:
        raise ValueError(
            f"train_sample_size must be between 0 and train_size ({train_size})."
        )

    indices = np.random.RandomState(seed).permutation(total_samples)
    train_end = train_size
    val_end = train_end + val_size
    test_end = val_end + test_size

    train_indices = indices[:train_end]
    if train_sample_size is not None:
        train_indices = train_indices[:train_sample_size]

    return {
        "train": train_indices,
        "val": indices[train_end:val_end],
        "test": indices[val_end:test_end],
    }


def read_case_id_splits(
    split_dir: str,
    split_name: str,
    order_entries: Sequence[str],
) -> Dict[str, List[str]]:
    """Read case IDs and map them to the corresponding entries in an order file."""
    split_root = Path(split_dir)
    split_paths = {
        "train": split_root / split_name / "train_ids.txt",
        "val": split_root / "validation_ids.txt",
        "test": split_root / "test_ids.txt",
    }

    order_by_id: Dict[str, str] = {}
    for entry in order_entries:
        cleaned_entry = entry.strip()
        if not cleaned_entry:
            continue
        case_id = Path(cleaned_entry).name
        if case_id.endswith(".pt"):
            case_id = case_id[:-3]
        if case_id in order_by_id:
            raise ValueError(f"Duplicate case ID in dataset order file: {case_id}")
        order_by_id[case_id] = cleaned_entry

    result: Dict[str, List[str]] = {}
    for split, split_path in split_paths.items():
        if not split_path.is_file():
            raise FileNotFoundError(f"Split ID file does not exist: {split_path}")
        case_ids = [
            line.strip()
            for line in split_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not case_ids:
            raise ValueError(f"Split ID file is empty: {split_path}")
        if len(case_ids) != len(set(case_ids)):
            raise ValueError(f"Duplicate case ID in split file: {split_path}")

        missing_ids = [case_id for case_id in case_ids if case_id not in order_by_id]
        if missing_ids:
            preview = ", ".join(missing_ids[:5])
            raise ValueError(
                f"{split_path} contains {len(missing_ids)} IDs missing from the "
                f"dataset order file; examples: {preview}"
            )
        result[split] = [order_by_id[case_id] for case_id in case_ids]

    split_sets = {split: set(entries) for split, entries in result.items()}
    for left, right in (("train", "val"), ("train", "test"), ("val", "test")):
        overlap = split_sets[left] & split_sets[right]
        if overlap:
            preview = ", ".join(sorted(overlap)[:5])
            raise ValueError(
                f"Case IDs overlap between {left} and {right} splits: {preview}"
            )
    return result
