# GAOT-3D case ID lists

Enter one case ID per line, using the case names from the dataset order file
(for example, `Wheel_FL_0006`). Keep the files header-free. Blank lines are
ignored.

The two files in this directory are shared by all training cases:

| File | Expected IDs |
| --- | ---: |
| `validation_ids.txt` | 92 |
| `test_ids.txt` | 92 |

Each subfolder contains a `train_ids.txt` for one training case:

| Case | Subfolder | Expected training IDs | Fraction of training pool |
| --- | --- | ---: | ---: |
| 1 | `case_01_train_720` | 720 | 100% |
| 2 | `case_02_train_576` | 576 | 80% |
| 3 | `case_03_train_288` | 288 | 40% |
| 4 | `case_04_train_144` | 144 | 20% |
| 5 | `case_05_train_072` | 72 | 10% |
| 6 | `case_06_train_036` | 36 | 5% |

Each training list is used exactly as written; its order and membership are
preserved. Training, validation and test IDs must not overlap.

To use a case in a config file, set `dataset.split_dir` to this directory (or
another split directory) and `dataset.split_name` to the selected subfolder,
for example:

```json
{
  "dataset": {
    "split_dir": "splits",
    "split_name": "case_02_train_576"
  }
}
```

Relative `split_dir` paths are resolved from the project root. If both options
are omitted, training keeps using the configured deterministic size-based
split. When ID-based splits are enabled, the ID lists determine the split
sizes, and `train_sample_size` is ignored.
