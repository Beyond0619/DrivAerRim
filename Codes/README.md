# Workflow and analysis scripts

This directory contains the released scripts used to prepare and execute DrivAerRim cases on a high performance computing system and to analyse the resulting aerodynamic data.

## Contents

| File | Role |
|---|---|
| `prepare.sh` | Copies a common case template, creates the requested rim cases, inserts each rim NAS file into `CAD/`, and updates SLURM job names |
| `run.sh` | SLURM job template that calls the STARCFD Java macros for case preparation, surface meshing, volume meshing, solution, and postprocessing |
| `post.sh` | Separate GPU postprocessing job for STAR-CCM+ field and image export |
| `plot_all_rims_bins.py` | Plots accumulated drag curves from per-case `Binned.csv` files or the released `Cd_Accumulated_Combined.csv` file |
| `plot_rim_aero_analysis.py` | Generates distributions, pair plots, component comparisons, and derived summaries from `Force_Coefficients_Combined.csv` |

## HPC workflow

The shell scripts are templates from the original Tetralith SLURM workflow. Before use, replace the public `-` placeholders and check the resource requests for the target system.

### 1. Configure and prepare cases

`prepare.sh` reads its settings from environment variables. The required locations are:

- `TEMPLATE_DIR`: common CFD case template containing `CAD/`, `repo/`, and `resources/`;
- `RIMS_NAS_DIR`: directory containing the preprocessed rim NAS files;
- `OUTPUT_PARENT`: destination for the generated rim case directories.

Case selection is controlled by `START` with `N` or `END`, or by an explicit space-separated `INDICES` list. `NAS_LAYOUT`, `RIM_PAD`, and `RIMS_NAS_RANGE_SIZE` describe the source geometry layout.

Example:

```bash
TEMPLATE_DIR=/path/to/template \
RIMS_NAS_DIR=/path/to/rim_nas \
OUTPUT_PARENT=/path/to/cases \
START=1 END=10 RIM_PAD=4 \
bash prepare.sh
```

Run `bash prepare.sh --help` for the compact option summary.

### 2. Configure and submit CFD jobs

Update the SLURM account, email, node and task requests, STAR-CCM+ module, `LM_PROJECT`, and `LM_LICENSE_FILE` entries in `run.sh` and `post.sh`. The scripts also support these environment settings:

- `STARCFD_PYTHON` or `STARCFD_PY_ENV` for the Python runtime used by the STARCFD macros;
- `STARCFD_POST_MODE=gpu|cpu|none` to select the postprocessing route;
- `RUN_POST=0|1` to disable or enable postprocessing;
- `STARCFD_POST_NP` and `STARCFD_POST_GRAPHICS` for the separate GPU postprocessing job.

The case directory must contain the STARCFD macros, templates, dependencies, and settings referenced by `repo/STARCFD`. In the released `run.sh`, the solver stage is active and the earlier preparation and meshing calls are commented so that the script can resume an already meshed case. Uncomment the required stages when executing the full sequence.

Typical submission from a configured case directory:

```bash
sbatch run.sh
```

The GPU postprocessing job may also be submitted independently after a `*_Finished.sim` file has been created:

```bash
sbatch post.sh
```

## Aerodynamic analysis

Install the Python dependencies:

```bash
python -m pip install -r Codes/requirements.txt
```

From the repository root, analyse the released combined force coefficients with:

```bash
python Codes/plot_rim_aero_analysis.py \
  --input NumData/Force_Coefficients_Combined.csv \
  --output-dir Figures/aerodynamic_coefficients \
  --dpi 300
```

Plot accumulated drag for all 904 cases with:

```bash
python Codes/plot_all_rims_bins.py \
  --input NumData/Cd_Accumulated_Combined.csv \
  --rim-start 1 \
  --rim-end 904 \
  --output Figures/accumulated_cd.jpg
```

Both plotting scripts provide command line help through `--help`. Paths given on the command line override their public placeholder defaults.

## Reuse notes

The SLURM directives, module names, rendering options, and hardware allocations reflect the computing environment used for DrivAerRim. Adapt them to the local scheduler and software installation. Simcenter STAR-CCM+ and a valid license are required for the CFD stages. The Python analysis scripts operate directly on the released CSV summaries and do not require STAR-CCM+.
