# GAOT-3D DrivAerRim

This project preprocesses DrivAerRim VTP files into PyTorch Geometric samples, then trains and evaluates GAOT-3D models for pressure or wall shear stress (WSS) prediction.

## Quick start

The workflow is:

1. Set up Python and install dependencies.
2. Preprocess raw VTP files into `.pt` samples.
3. Select a case-ID split and set the dataset paths in a config.
4. Precompute graph edges once, then train.
5. Evaluate the checkpoint on the test split or selected samples.

## 1. Environment

Create and activate an environment. In Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install PyTorch for your system's CUDA version, then install matching PyTorch Geometric extensions and the remaining requirements:

```powershell
python -m pip install torch
python -m pip install torch-cluster torch-scatter -f 'https://data.pyg.org/whl/torch-<TORCH_TAG>+<CUDA_TAG>.html'
python -m pip install -r requirements.txt
```

Replace `<TORCH_TAG>` and `<CUDA_TAG>` with the tags for your installed PyTorch/CUDA build. Use the [PyTorch Geometric installation guide](https://pytorch-geometric.readthedocs.io/en/latest/install/installation.html) to find a compatible wheel index. The example configs enable `torch-cluster`; `torch-scatter` accelerates aggregation and has a native PyTorch fallback. The trainer also imports `wandb`, even when W&B logging is disabled.

On Linux/macOS, activate the environment with `source .venv/bin/activate` before installing packages.

## 2. Preprocess the data

Place one `.vtp` file per case in the raw-data directory. Each filename (without `.vtp`) must match the case IDs in [`splits/`](splits/).

Run the preprocessing script once for each target:

```powershell
python dataset\drivaerrim\process_wheel_vtp_separate.py `
  --input-dir "D:\data\raw_vtp" `
  --output-root "D:\data\wheel_pressure_900" `
  --target pressure

python dataset\drivaerrim\process_wheel_vtp_separate.py `
  --input-dir "D:\data\raw_vtp" `
  --output-root "D:\data\wheel_wss_900" `
  --target wss
```

The script creates `processed\<case_id>.pt` and `order_processed.txt` under each output root. Pressure defaults to the VTP array `MeanPressure`; WSS defaults to `MeanWSSi`, `MeanWSSj`, and `MeanWSSk`. Use `--pressure-key` or `--wss-*-key` if your array names differ. Existing outputs are not overwritten unless `--overwrite` is provided.

## 3. Configure data and splits

Edit the example config for the target:

- Pressure: [`wheel_pressure_900.json`](config/examples/drivaerrim/wheel_pressure_900.json)
- WSS: [`wheel_wss_900.json`](config/examples/drivaerrim/wheel_wss_900.json)

Set `dataset.base_path` to the preprocessing `--output-root`. Keep `dataset.processed_folder` set to `processed`. Select the training case list using:

```json
"split_dir": "splits",
"split_name": "case_02_train_576"
```

Each `case_*` folder supplies a training list; `validation_ids.txt` and `test_ids.txt` are shared. Available training sizes are 720, 576, 288, 144, 72, and 36. The IDs in the lists determine dataset membership; size and seed settings do not override them. The loader checks for empty lists, duplicate or missing IDs, and overlap between splits. See [`splits/README.md`](splits/README.md) for details.

Current examples select `case_02_train_576` for pressure and `case_05_train_072` for WSS. Also check `setup.device` and output paths under `path` before running.

## 4. Precompute graph edges once

For each preprocessed dataset, set `dataset.update_pt_files_with_edges` to `true` in its config and run the training command below. The trainer writes encoder/decoder graph edges into the processed `.pt` files, then continues training.

After the first run successfully generates the edges, set `dataset.update_pt_files_with_edges` back to `false`. Keep `model.args.magno.precompute_edges` set to `true` for subsequent runs. Repeat precomputation if you regenerate the `.pt` data or change graph settings such as the latent grid, radius, or neighbor strategy. Pressure and WSS have separate output directories, so precompute each one separately.

## 5. Train

From the project root:

```powershell
python main.py --config config/examples/drivaerrim/wheel_pressure_900.json
```

Use `wheel_wss_900.json` for WSS. Both example configs have `setup.train` and `setup.test` enabled, so the run trains and then evaluates the test split. Set `setup.test` to `false` to train only. Checkpoint, loss curve, plots, and metrics are saved to the paths in the config's `path` section.

## 6. Test

To test an existing checkpoint without training, set `setup.train` to `false`, `setup.test` to `true`, and set `path.ckpt_path` to the checkpoint:

```powershell
python main.py --config path/to/test_config.json
```

This evaluates the configured test split (`splits/test_ids.txt`). To test specific preprocessed samples instead:

```powershell
python test\test_single_multi.py `
  --config config/examples/drivaerrim/wheel_wss_900.json `
  --ckpt path\to\model.pt `
  --input path\to\processed\Wheel_FL_0006.pt path\to\processed\Wheel_FL_0033.pt `
  --output_dir results\single_test
```

The script evaluates each input separately and saves its outputs in the selected directory.

## Project structure

```text
GAOT-3D-DrivAerRim/
├── config/examples/drivaerrim/  Experiment configs
├── dataset/drivaerrim/          VTP preprocessing script
├── data/                        Raw and processed data
├── splits/                      Train/validation/test case-ID lists
├── src/
│   ├── data/                    Dataset loading, transforms, collation, split utilities
│   ├── model/                   GAOT-3D and model layers
│   ├── trainer/                 Training, validation, testing
│   └── utils/                   Shared utilities
├── test/                        Split tests and selected-sample test script
├── main.py                      Main training/test entry point
└── requirements.txt             Python dependencies
```

Run the split unit tests from the project root with:

```powershell
python -m unittest test.test_dataset_split
```
