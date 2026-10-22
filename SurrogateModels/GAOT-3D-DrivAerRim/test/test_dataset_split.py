import unittest
import tempfile
from pathlib import Path

import numpy as np

from src.data.split import make_split_indices, read_case_id_splits


class MakeSplitIndicesTest(unittest.TestCase):
    def test_seed42_split_has_expected_sizes_and_disjoint_sets(self):
        splits = make_split_indices(
            total_samples=904,
            train_size=720,
            val_size=92,
            test_size=92,
            seed=42,
        )

        self.assertEqual(len(splits["train"]), 720)
        self.assertEqual(len(splits["val"]), 92)
        self.assertEqual(len(splits["test"]), 92)
        self.assertEqual(
            len(set(splits["train"]).union(splits["val"]).union(splits["test"])),
            904,
        )
        self.assertEqual(set(splits["train"]).isdisjoint(splits["val"]), True)
        self.assertEqual(set(splits["train"]).isdisjoint(splits["test"]), True)
        self.assertEqual(set(splits["val"]).isdisjoint(splits["test"]), True)

    def test_training_sample_size_is_a_prefix_of_the_same_split(self):
        full_split = make_split_indices(
            total_samples=904,
            train_size=720,
            val_size=92,
            test_size=92,
            seed=42,
        )
        baseline = full_split["train"]

        for sample_count in (720, 576, 288, 144, 72):
            with self.subTest(sample_count=sample_count):
                splits = make_split_indices(
                    total_samples=904,
                    train_size=720,
                    val_size=92,
                    test_size=92,
                    seed=42,
                    train_sample_size=sample_count,
                )
                self.assertTrue(np.array_equal(splits["train"], baseline[:sample_count]))
                self.assertEqual(len(splits["val"]), 92)
                self.assertEqual(len(splits["test"]), 92)

    def test_seed_produces_reproducible_indices(self):
        first = make_split_indices(904, 720, 92, 92, seed=42)
        second = make_split_indices(904, 720, 92, 92, seed=42)

        self.assertTrue(np.array_equal(first["train"], second["train"]))
        self.assertTrue(np.array_equal(first["val"], second["val"]))
        self.assertTrue(np.array_equal(first["test"], second["test"]))

    def test_case_id_split_files_map_to_dataset_order(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "case_custom").mkdir()
            (root / "case_custom" / "train_ids.txt").write_text(
                "Wheel_02\nWheel_01\n", encoding="utf-8"
            )
            (root / "validation_ids.txt").write_text("Wheel_03\n", encoding="utf-8")
            (root / "test_ids.txt").write_text("Wheel_04\n", encoding="utf-8")

            splits = read_case_id_splits(
                str(root),
                "case_custom",
                ["Wheel_01", "Wheel_02", "Wheel_03.pt", "Wheel_04"],
            )

        self.assertEqual(splits["train"], ["Wheel_02", "Wheel_01"])
        self.assertEqual(splits["val"], ["Wheel_03.pt"])
        self.assertEqual(splits["test"], ["Wheel_04"])

    def test_case_id_split_files_reject_overlapping_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "case_custom").mkdir()
            (root / "case_custom" / "train_ids.txt").write_text(
                "Wheel_01\n", encoding="utf-8"
            )
            (root / "validation_ids.txt").write_text("Wheel_01\n", encoding="utf-8")
            (root / "test_ids.txt").write_text("Wheel_03\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "overlap"):
                read_case_id_splits(
                    str(root),
                    "case_custom",
                    ["Wheel_01", "Wheel_02", "Wheel_03"],
                )


if __name__ == "__main__":
    unittest.main()
