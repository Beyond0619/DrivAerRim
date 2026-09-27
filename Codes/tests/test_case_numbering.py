"""Small local checks for the published case and source-NAS naming scheme."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CODES_DIR = Path(__file__).resolve().parents[1]


class CaseNumberingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.template = self.root / "template"
        (self.template / "CAD").mkdir(parents=True)
        (self.template / "run.sh").write_text("#SBATCH -J old\n", encoding="utf-8")
        (self.template / "post.sh").write_text("#SBATCH -J old\n", encoding="utf-8")
        self.nas_root = self.root / "rim_nas"
        source = self.nas_root / "001-050" / "001" / "rims_clean_sm_open_.nas"
        source.parent.mkdir(parents=True)
        source.write_text("test NAS geometry\n", encoding="utf-8")
        self.cases = self.root / "cases"
        self.environment = os.environ.copy()
        for name in ("RIM_PAD", "NAS_PAD", "DRY_RUN", "STRICT"):
            self.environment.pop(name, None)

    def run_script(self, script: str, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CODES_DIR / script), *arguments],
            env=self.environment,
            capture_output=True,
            text=True,
            check=True,
        )

    def prepare(self, *extra: str) -> None:
        self.run_script(
            "prepare.py",
            "--template-dir", str(self.template),
            "--rims-nas-dir", str(self.nas_root),
            "--output-parent", str(self.cases),
            "--indices", "1",
            "--strict",
            *extra,
        )

    def test_defaults_create_four_digit_case_from_three_digit_nas(self) -> None:
        self.prepare()
        case = self.cases / "Rim0001"
        self.assertEqual(
            (case / "CAD" / "rims_clean_sm_open_.nas").read_text(encoding="utf-8"),
            "test NAS geometry\n",
        )
        self.assertIn("#SBATCH -J R1", (case / "run.sh").read_text(encoding="utf-8"))
        self.assertIn(
            "#SBATCH -J R0001_Post", (case / "post.sh").read_text(encoding="utf-8")
        )
        self.assertFalse((self.cases / "Rim001").exists())

        result = self.run_script(
            "batch_run.py",
            "--rim-parent", str(self.cases),
            "--indices", "1",
            "--batch-system", "slurm",
            "--dry-run",
        )
        self.assertIn("Rim0001: ready", result.stdout)

    def test_explicit_three_digit_case_name_remains_available(self) -> None:
        self.prepare("--rim-pad", "3")
        self.assertTrue((self.cases / "Rim001" / "CAD" / "rims_clean_sm_open_.nas").is_file())

    def test_source_nas_padding_can_change_independently(self) -> None:
        source = self.nas_root / "0001-0050" / "0001" / "rims_clean_sm_open_.nas"
        source.parent.mkdir(parents=True)
        source.write_text("four-digit NAS geometry\n", encoding="utf-8")

        self.prepare("--nas-pad", "4")
        self.assertEqual(
            (self.cases / "Rim0001" / "CAD" / "rims_clean_sm_open_.nas").read_text(
                encoding="utf-8"
            ),
            "four-digit NAS geometry\n",
        )


if __name__ == "__main__":
    unittest.main()
