import argparse
import logging
import os

from main import FileParser, run_arg


def setup_logging(level: str = "INFO"):
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s: %(message)s",
    )


def set_cfg_value(obj, key, value):
    """Support both OmegaConf DictConfig and dict-like objects."""
    try:
        setattr(obj, key, value)
    except Exception:
        obj[key] = value


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Test a GAOT-3D checkpoint on exactly one specified "
            "preprocessed .pt file."
        )
    )
    parser.add_argument(
        "--config", "-c", required=True,
        help="Path to config file (.toml/.json/.yaml)",
    )
    parser.add_argument(
        "--ckpt", required=True,
        help="Path to checkpoint (.pt)",
    )
    parser.add_argument(
        "--input", "-i", nargs="+", required=True,
        help=(
            "One or more input .pt files. Example: "
            "--input Rim237.pt Rim238.pt Rim239.pt"
        ),
    )
    parser.add_argument(
        "--output_dir", "-o", default="results/single_test",
        help=(
            "Directory for outputs. Each input generates "
            "<input_name>.png and <input_name>.npz. "
            "Default: results/single_test"
        ),
    )
    parser.add_argument(
        "--visible_devices", nargs="*", type=int, default=None,
        help="Optional CUDA visible devices",
    )
    parser.add_argument(
        "--log", default=None,
        help="Optional log file",
    )
    args = parser.parse_args()

    if args.visible_devices is not None:
        os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(
            map(str, args.visible_devices)
        )

    setup_logging()

    ckpt_file = os.path.abspath(os.path.expanduser(args.ckpt))
    if not os.path.isfile(ckpt_file):
        raise FileNotFoundError(f"Checkpoint does not exist: {ckpt_file}")

    input_files = []
    for input_file in args.input:
        input_file = os.path.abspath(os.path.expanduser(input_file))
        if not os.path.isfile(input_file):
            raise FileNotFoundError(f"Input file does not exist: {input_file}")
        input_files.append(input_file)

    output_dir = os.path.abspath(os.path.expanduser(args.output_dir))
    os.makedirs(output_dir, exist_ok=True)

    logging.info("=" * 70)
    logging.info("GAOT-3D MULTI-FILE TEST")
    logging.info("=" * 70)
    logging.info("Config     : %s", args.config)
    logging.info("Checkpoint : %s", ckpt_file)
    logging.info("Input files: %d", len(input_files))
    logging.info("Output dir : %s", output_dir)
    logging.info("=" * 70)

    for sample_idx, input_file in enumerate(input_files, start=1):
        sample_name = os.path.splitext(os.path.basename(input_file))[0]
        result_path = os.path.join(output_dir, f"{sample_name}.png")

        logging.info("")
        logging.info("=" * 70)
        logging.info("Testing sample %d/%d: %s", sample_idx, len(input_files), sample_name)
        logging.info("Input  : %s", input_file)
        logging.info("Output : %s", result_path)
        logging.info("=" * 70)

        # Reload config for every sample to avoid settings leaking between files.
        cfg = FileParser(args.config).parse_args()
        set_cfg_value(cfg.setup, "train", False)
        set_cfg_value(cfg.setup, "test", True)
        set_cfg_value(cfg.setup, "resume_from_ckpt", ckpt_file)
        set_cfg_value(cfg.dataset, "input_file", input_file)
        set_cfg_value(cfg.dataset, "update_pt_files_with_edges", False)
        set_cfg_value(cfg.path, "result_path", result_path)

        if args.log is not None:
            log_path = os.path.abspath(os.path.expanduser(args.log))
            if len(input_files) > 1:
                log_base, log_ext = os.path.splitext(log_path)
                log_path = f"{log_base}_{sample_name}{log_ext or '.log'}"
            log_dir = os.path.dirname(log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            set_cfg_value(cfg.path, "log_path", log_path)

        run_arg(cfg)
        logging.info("Finished %s -> %s and %s", sample_name, result_path, os.path.splitext(result_path)[0] + ".npz")

    logging.info("")
    logging.info("=" * 70)
    logging.info("All %d samples have been tested successfully.", len(input_files))
    logging.info("Results saved in: %s", output_dir)
    logging.info("=" * 70)


if __name__ == "__main__":
    main()
