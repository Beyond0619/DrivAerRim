# DrivAerRim workflow and analysis scripts

This directory contains portable plotting, case-preparation, and batch-submission
utilities for rim aerodynamics workflows. Public path and credential values are
represented by `-` and must be configured locally before use.

## Contents

- `plot_rim_aero_analysis.py`: plots force-coefficient distributions and
  relationships from `Force_Coefficients_Combined.csv` or the legacy
  `all_means_*.csv` schema.
- `plot_all_rims_bins.py`: plots accumulated drag curves from
  `Cd_Accumulated_Combined.csv`, or from legacy `Rim*/NumData/Binned.csv` data.
- `prepare.py`: creates numbered case directories from a template and installs
  the corresponding rim NAS file.
- `batch_run.py`: submits and monitors selected cases with bounded concurrency.
- `prepare.sh` and `batch_run.sh`: compatibility wrappers for the Python tools.
- `run.sh` and `post.sh`: Slurm scripts for STAR-CCM+ solve and GPU
  post-processing stages. These remain Shell scripts because Slurm directives,
  environment modules, and scheduler variables are Shell-native.

## Python setup

Python 3.10 or newer is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

The preparation and batch tools use only the Python standard library. The
packages in `requirements.txt` are required by the plotting scripts.

## Plot combined CSV exports

Force coefficients:

```bash
python3 plot_rim_aero_analysis.py \
  --input ./data/Force_Coefficients_Combined.csv \
  --output-dir ./Figures/force_coefficients
```

Accumulated drag:

```bash
python3 plot_all_rims_bins.py \
  --input ./data/Cd_Accumulated_Combined.csv \
  --output ./Figures/Cd_Accumulated.jpg
```

For the legacy `Binned.csv` workflow, provide the raw-data root explicitly:

```bash
python3 plot_all_rims_bins.py \
  --raw-data-root ./Raw_data \
  --rim-start 1 --rim-end 10 \
  --output ./Figures/all_rims_bins_overlay.jpg
```

The plotting scripts validate required numeric values and report invalid rows;
they do not silently remove data points.

## Prepare cases

Always inspect a dry run before creating or updating cases:

```bash
python3 prepare.py \
  --template-dir ./template \
  --rims-nas-dir ./rim_nas \
  --output-parent ./cases \
  --indices "1 2" \
  --nas-layout subdir_range \
  --dry-run
```

Remove `--dry-run` after checking the paths. `--strict` returns a non-zero exit
status if any requested NAS source is missing. Existing cases are not deleted;
only the fixed target `CAD/rims_clean_sm_open_.nas` and the `#SBATCH -J` lines
in `run.sh`/`post.sh` are updated. `prepare.sh` accepts the same arguments.

Supported NAS layouts are:

- `flat`: `rim_nas/rims_clean_sm_open_001.nas`
- `subdir`: `rim_nas/001/rims_clean_sm_open_.nas`
- `subdir_range`: `rim_nas/001-050/001/rims_clean_sm_open_.nas`

## Submit cases

Validate case selection and the submit command first:

```bash
python3 batch_run.py \
  --rim-parent ./cases \
  --indices "1 2" \
  --batch-system slurm \
  --submit-cmd "sbatch run.sh" \
  --check
```

Then run the same command without `--check`. Use `--dry-run` to list selected
cases without launching anything, and `--concurrent N` to limit active cases.
`batch_run.sh` is a compatibility wrapper with identical arguments. Slurm, LSF,
and direct background processes are supported through `--batch-system`.

Stopping the monitor does not cancel jobs already submitted to a scheduler.
Review the per-case `batch_Rim*.log` files and the final selected/submitted/
missing/failed summary.

## Configure STAR-CCM+ and Slurm

Before submitting `run.sh` or `post.sh`:

1. Replace the public `-` placeholders in the `#SBATCH` account and mail
   directives, or remove directives that are not required by the target cluster.
2. Export valid `LM_PROJECT` and `LM_LICENSE_FILE` values. The scripts preserve
   values supplied by the environment.
3. Set `STARCCM_MODULE` if the default module name is unavailable.
4. Review CPU, node, GPU, memory, and wall-time requests for the target mesh and
   cluster policy.
5. Provide the compiled `repo/STARCFD` classes and required dependency JARs.

The full pipeline is the default:

```bash
sbatch run.sh all
```

For recovery or staged execution, select `prep`, `surf`, `vol`, `run`, or
`post`. `STARCFD_STAGE` can be used instead of a positional stage. By default,
the main job submits `post.sh`; set `STARCFD_POST_MODE=cpu` for CPU fallback or
`STARCFD_POST_MODE=none`/`RUN_POST=0` to skip it.

## License and redistribution notes

- These scripts are covered by the repository's
  [CC BY-NC 4.0 license](../LICENSE.md), unless otherwise noted.
- Do not publish STAR-CCM+ binaries, licensed templates, restricted JARs,
  simulation files, NAS geometry, raw data, credentials, or cluster account
  details unless redistribution is explicitly permitted.
- Review example data for confidential geometry and metadata before release.
- Run the local checks below from this `Codes` directory.

```bash
python3 -m compileall -q .
bash -n prepare.sh batch_run.sh run.sh post.sh
```

Real STAR-CCM+ and scheduler execution must be verified on the target cluster;
local syntax checks cannot validate licenses, modules, queues, or allocation
requirements.
