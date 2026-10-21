# GAOT-3D dataset splits

These files define the fixed data splits used for the GAOT-3D surrogate-model
experiments. Each header-free text file contains one front-left wheel sample ID
per line in the form `Wheel_FL_XXXX`, where `XXXX` maps to the corresponding
`RimXXXX` case in DrivAerRim.

The validation and test lists are shared by all six experiments:

| File | IDs |
| --- | ---: |
| `validation_ids.txt` | 92 |
| `test_ids.txt` | 92 |

Each experiment subdirectory contains its corresponding `train_ids.txt`:

| Case | Subdirectory | Training IDs | Fraction of training pool |
| --- | --- | ---: | ---: |
| 1 | `case_01_train_720` | 720 | 100% |
| 2 | `case_02_train_576` | 576 | 80% |
| 3 | `case_03_train_288` | 288 | 40% |
| 4 | `case_04_train_144` | 144 | 20% |
| 5 | `case_05_train_072` | 72 | 10% |
| 6 | `case_06_train_036` | 36 | 5% |

The training sets are nested, so every smaller training set is a subset of the
next larger set. IDs in each file are sorted numerically. The 720-case training
set, validation set and test set are mutually exclusive and together partition
all 904 cases.
