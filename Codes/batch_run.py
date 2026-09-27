#!/usr/bin/env python3
"""Submit and monitor multiple numbered rim cases with bounded concurrency."""

from __future__ import annotations

import argparse
import atexit
from collections import deque
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys
import time
from typing import IO


SLURM_ACTIVE_STATES = {
    "PENDING",
    "CONFIGURING",
    "RUNNING",
    "COMPLETING",
    "SUSPENDED",
    "RESIZING",
    "STAGE_OUT",
    "REQUEUE_HOLD",
    "REQUEUED",
}
SLURM_TERMINAL_STATES = {
    "COMPLETED",
    "CANCELLED",
    "FAILED",
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "PREEMPTED",
    "BOOT_FAIL",
    "DEADLINE",
    "NODE_FAIL",
    "REVOKED",
    "SPECIAL_EXIT",
}
LSF_ACTIVE_STATES = {"PEND", "RUN", "PSUSP", "USUSP", "SSUSP", "WAIT", "PROV"}
STOP_REQUESTED = False


@dataclass
class SchedulerSlot:
    index: int
    name: str
    log_path: Path
    job_ids: set[str]


@dataclass
class BackgroundSlot:
    index: int
    name: str
    process: subprocess.Popen[str]
    log_handle: IO[str]


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise SystemExit(f"{name} must be an integer, got {value!r}.") from exc


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="Submit Rim cases with bounded background, Slurm, or LSF concurrency."
    )
    parser.add_argument(
        "--rim-parent",
        default=os.environ.get("RIM_PARENT", "-"),
        help=(
            "Parent directory containing Rim folders (env: RIM_PARENT). "
            "The public default '-' must be replaced."
        ),
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=env_int("CONCURRENT_N", 4),
        help="Maximum concurrently active cases; default: 4.",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=env_int("MAX_M", 500),
        help="Number of contiguous cases; default: 500 (env: MAX_M).",
    )
    parser.add_argument(
        "--start-at",
        type=int,
        default=env_int("START_AT", 1),
        help="First contiguous rim index; default: 1.",
    )
    parser.add_argument(
        "--indices",
        default=os.environ.get("INDICES", ""),
        help='Exact indices separated by spaces or commas, for example "1 4 9".',
    )
    parser.add_argument(
        "--rim-pad",
        type=int,
        default=env_int("RIM_PAD", 3),
        help="Zero-padding width for Rim directory names; default: 3.",
    )
    parser.add_argument(
        "--submit-cmd",
        default=os.environ.get("SUBMIT_CMD", "sbatch run.sh"),
        help="Command executed inside each Rim directory (env: SUBMIT_CMD).",
    )
    parser.add_argument(
        "--submit-env",
        default=os.environ.get("SUBMIT_ENV", ""),
        help="Optional shell file sourced before the submit command.",
    )
    parser.add_argument(
        "--batch-system",
        choices=("auto", "slurm", "lsf", "background"),
        default=os.environ.get("BATCH_SYS", "auto").lower(),
        help="Scheduler type; default: auto (env: BATCH_SYS).",
    )
    parser.add_argument(
        "--python-env",
        default=os.environ.get("STARCFD_PY_ENV", "-"),
        help="Optional STARCFD Python environment; public placeholder: -.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=float(os.environ.get("POLL_INTERVAL", "30")),
        help="Scheduler/background polling interval in seconds; default: 30.",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        default=env_flag("BATCH_DAEMON"),
        help="Detach with nohup-like logging and write a PID file.",
    )
    parser.add_argument(
        "--pid-file",
        default=os.environ.get("BATCH_PIDFILE", str(script_dir / "batch_run.pid")),
        help="Daemon PID file.",
    )
    parser.add_argument(
        "--daemon-log",
        default=os.environ.get(
            "BATCH_DAEMON_LOG", str(script_dir / "batch_run_daemon.log")
        ),
        help="Daemon stdout/stderr log.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=env_flag("DRY_RUN"),
        help="Show selected cases and commands without submitting them.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate configuration and selected case directories without submitting.",
    )
    return parser.parse_args()


def parse_indices(text: str) -> list[int]:
    tokens = text.replace(",", " ").split()
    try:
        return [int(token) for token in tokens]
    except ValueError as exc:
        raise SystemExit("--indices must contain only integers.") from exc


def selected_indices(args: argparse.Namespace) -> list[int]:
    if args.indices.strip():
        indices = parse_indices(args.indices)
    else:
        if args.max_cases <= 0:
            raise SystemExit("--max-cases must be greater than zero.")
        indices = list(range(args.start_at, args.start_at + args.max_cases))
    if not indices or any(index <= 0 for index in indices):
        raise SystemExit("Rim indices must be positive integers.")
    if len(indices) != len(set(indices)):
        raise SystemExit("Duplicate rim indices are not allowed.")
    return indices


def rim_name(index: int, pad: int) -> str:
    return f"Rim{index:0{pad}d}" if pad > 0 else f"Rim{index}"


def resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def detect_batch_system(args: argparse.Namespace) -> str:
    if args.batch_system != "auto":
        return args.batch_system
    command = args.submit_cmd.lower()
    if "sbatch" in command:
        return "slurm"
    if "bsub" in command:
        return "lsf"
    return "background"


def command_argv(args: argparse.Namespace, submit_env: Path | None) -> list[str]:
    try:
        argv = shlex.split(args.submit_cmd)
    except ValueError as exc:
        raise SystemExit(f"Invalid SUBMIT_CMD: {exc}") from exc
    if not argv:
        raise SystemExit("SUBMIT_CMD/--submit-cmd cannot be empty.")
    if submit_env is not None:
        return [
            "bash",
            "-lc",
            'source "$1" && shift && exec "$@"',
            "batch-run",
            str(submit_env),
            *argv,
        ]
    return argv


def child_environment(args: argparse.Namespace) -> dict[str, str]:
    environment = os.environ.copy()
    if args.python_env and args.python_env != "-":
        environment["STARCFD_PY_ENV"] = args.python_env
    else:
        environment.pop("STARCFD_PY_ENV", None)
    return environment


def parse_slurm_job_ids(text: str) -> set[str]:
    ids = set(re.findall(r"Submitted batch job\s+(\d+)", text))
    for line in text.splitlines():
        token = line.strip().split(";", 1)[0]
        if token.isdigit():
            ids.add(token)
    return ids


def parse_lsf_job_ids(text: str) -> set[str]:
    patterns = (
        r"Submitted jobid\s*(\d+)",
        r"Job\s*<(\d+)>",
        r"\b[Jj]ob\s+(\d+)\b",
    )
    ids: set[str] = set()
    for pattern in patterns:
        ids.update(re.findall(pattern, text))
    return ids


def parse_job_ids(batch_system: str, text: str) -> set[str]:
    return (
        parse_slurm_job_ids(text)
        if batch_system == "slurm"
        else parse_lsf_job_ids(text)
    )


def run_capture(argv: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    return completed.returncode, completed.stdout or ""


def normalize_state(value: str) -> str:
    return value.strip().upper().split("+", 1)[0].split(" ", 1)[0]


def slurm_job_active(job_id: str) -> bool:
    code, output = run_capture(["scontrol", "show", "job", "-o", job_id])
    if code == 0 and output:
        match = re.search(r"\bJobState=([^\s]+)", output)
        if match:
            state = normalize_state(match.group(1))
            if state in SLURM_ACTIVE_STATES:
                return True
            if state in SLURM_TERMINAL_STATES:
                return False

    code, output = run_capture(["squeue", "-h", "-j", job_id])
    if code == 0:
        return bool(output.strip())

    code, output = run_capture(
        ["sacct", "-n", "-j", job_id, "--format=State", "--parsable2"]
    )
    if code == 0:
        for line in output.splitlines():
            state = normalize_state(line.split("|", 1)[0])
            if state in SLURM_ACTIVE_STATES:
                return True
            if state in SLURM_TERMINAL_STATES:
                return False
    return True


def lsf_job_active(job_id: str) -> bool:
    code, output = run_capture(["bjobs", "-noheader", "-o", "stat", job_id])
    if code != 0:
        return False
    states = {normalize_state(line) for line in output.splitlines() if line.strip()}
    return bool(states & LSF_ACTIVE_STATES)


def all_jobs_done(batch_system: str, job_ids: set[str]) -> bool:
    if not job_ids:
        return False
    active = slurm_job_active if batch_system == "slurm" else lsf_job_active
    return all(not active(job_id) for job_id in sorted(job_ids))


def submit_scheduler_case(
    index: int,
    name: str,
    case_dir: Path,
    log_path: Path,
    argv: list[str],
    environment: dict[str, str],
    batch_system: str,
) -> SchedulerSlot:
    completed = subprocess.run(
        argv,
        cwd=case_dir,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    output = completed.stdout or ""
    log_path.write_text(output, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"Submission failed for {name} with exit code {completed.returncode}; "
            f"see {log_path}."
        )
    job_ids = parse_job_ids(batch_system, output)
    if not job_ids:
        raise RuntimeError(f"No scheduler job ID found for {name}; see {log_path}.")
    print(f"[batch] Submitted {name} {batch_system} job(s): {' '.join(sorted(job_ids))}")
    return SchedulerSlot(index, name, log_path, job_ids)


def submit_background_case(
    index: int,
    name: str,
    case_dir: Path,
    log_path: Path,
    argv: list[str],
    environment: dict[str, str],
) -> BackgroundSlot:
    log_handle = log_path.open("a", encoding="utf-8")
    print(f"[batch] Starting {name} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    process = subprocess.Popen(
        argv,
        cwd=case_dir,
        env=environment,
        text=True,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return BackgroundSlot(index, name, process, log_handle)


def refresh_slot_job_ids(slot: SchedulerSlot, batch_system: str) -> bool:
    if not slot.log_path.is_file():
        return False
    discovered = parse_job_ids(
        batch_system, slot.log_path.read_text(encoding="utf-8", errors="replace")
    )
    new_ids = discovered - slot.job_ids
    if not new_ids:
        return False
    slot.job_ids.update(new_ids)
    print(
        f"[batch] {slot.name}: discovered additional job(s): "
        f"{' '.join(sorted(new_ids))}"
    )
    return True


def request_stop(_signum: int, _frame: object) -> None:
    global STOP_REQUESTED
    STOP_REQUESTED = True
    print("\n[batch] Stop requested; no new cases will be submitted.", flush=True)


def run_cases(args: argparse.Namespace) -> int:
    script_dir = Path(__file__).resolve().parent
    if not args.rim_parent or args.rim_parent == "-":
        raise SystemExit(
            "RIM_PARENT/--rim-parent is required; replace the public '-' placeholder."
        )
    rim_parent = resolve_path(args.rim_parent, script_dir)
    if not rim_parent.is_dir():
        raise SystemExit(f"Rim parent directory not found: {rim_parent}")
    if args.concurrent <= 0:
        raise SystemExit("--concurrent must be greater than zero.")
    if args.rim_pad < 0:
        raise SystemExit("--rim-pad must be zero or greater.")
    if args.poll_interval <= 0:
        raise SystemExit("--poll-interval must be greater than zero.")

    submit_env = None
    if args.submit_env and args.submit_env != "-":
        submit_env = resolve_path(args.submit_env, script_dir)
        if not submit_env.is_file():
            raise SystemExit(f"SUBMIT_ENV/--submit-env not found: {submit_env}")

    indices = selected_indices(args)
    batch_system = detect_batch_system(args)
    argv = command_argv(args, submit_env)
    environment = child_environment(args)
    cases = [
        (index, rim_name(index, args.rim_pad), rim_parent / rim_name(index, args.rim_pad))
        for index in indices
    ]

    print(f"[batch] Rim parent: {rim_parent}")
    print(f"[batch] Batch system: {batch_system}")
    print(f"[batch] Concurrent cases: {args.concurrent}")
    print(f"[batch] Submit command: {shlex.join(argv)}")
    print(f"[batch] Selected cases: {len(cases)}")

    missing = [(name, path) for _, name, path in cases if not path.is_dir()]
    if missing:
        print(f"[batch] Missing case directories: {len(missing)}")
        for name, path in missing[:10]:
            print(f"  - {name}: {path}")
        if len(missing) > 10:
            print(f"  ... and {len(missing) - 10} more")

    if args.check:
        executable = argv[0]
        if submit_env is None and shutil.which(executable) is None:
            print(f"[batch] ERROR: command not found: {executable}")
            return 1
        return 1 if missing else 0

    if args.dry_run:
        for _, name, path in cases:
            state = "ready" if path.is_dir() else "missing"
            print(f"[dry-run] {name}: {state}; cwd={path}")
        return 0

    pending = deque(case for case in cases if case[2].is_dir())
    scheduler_slots: list[SchedulerSlot] = []
    background_slots: list[BackgroundSlot] = []
    submitted = 0
    failed_cases: list[str] = []

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        while (pending or scheduler_slots or background_slots) and not STOP_REQUESTED:
            active_count = len(scheduler_slots) + len(background_slots)
            while pending and active_count < args.concurrent and not STOP_REQUESTED:
                index, name, case_dir = pending.popleft()
                log_path = case_dir / f"batch_{name}.log"
                try:
                    if batch_system in {"slurm", "lsf"}:
                        scheduler_slots.append(
                            submit_scheduler_case(
                                index,
                                name,
                                case_dir,
                                log_path,
                                argv,
                                environment,
                                batch_system,
                            )
                        )
                    else:
                        background_slots.append(
                            submit_background_case(
                                index, name, case_dir, log_path, argv, environment
                            )
                        )
                except (OSError, RuntimeError) as exc:
                    failed_cases.append(name)
                    print(f"[batch] ERROR: {name}: {exc}")
                    continue
                submitted += 1
                active_count += 1

            if not scheduler_slots and not background_slots:
                continue
            time.sleep(args.poll_interval)

            for slot in scheduler_slots[:]:
                refresh_slot_job_ids(slot, batch_system)
                if all_jobs_done(batch_system, slot.job_ids):
                    print(f"[batch] {batch_system} case {slot.name} finished.")
                    scheduler_slots.remove(slot)

            for slot in background_slots[:]:
                return_code = slot.process.poll()
                if return_code is None:
                    continue
                slot.log_handle.close()
                print(
                    f"[batch] Background case {slot.name} finished "
                    f"with exit code {return_code}."
                )
                if return_code != 0:
                    failed_cases.append(slot.name)
                background_slots.remove(slot)
    finally:
        for slot in background_slots:
            if slot.process.poll() is None:
                slot.process.terminate()
            slot.log_handle.close()

    if STOP_REQUESTED:
        print(
            "[batch] Monitor stopped. Scheduler jobs already submitted were not cancelled."
        )
        return 130
    print(
        f"[batch] Summary: selected={len(cases)}, submitted={submitted}, "
        f"missing={len(missing)}, failed={len(failed_cases)}."
    )
    if failed_cases:
        print(f"[batch] Failed cases: {' '.join(failed_cases)}")
    return 1 if missing or failed_cases else 0


def daemonize(args: argparse.Namespace) -> int:
    script_dir = Path(__file__).resolve().parent
    pid_file = resolve_path(args.pid_file, script_dir)
    log_file = resolve_path(args.daemon_log, script_dir)
    if pid_file.exists():
        raise SystemExit(f"PID file already exists: {pid_file}")
    if log_file.exists():
        raise SystemExit(f"Daemon log already exists: {log_file}")

    log_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    environment = os.environ.copy()
    environment["BATCH_DAEMON_WORKER"] = "1"
    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]]
    with log_file.open("x", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            cwd=script_dir,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    print(f"[batch] Started daemon PID {process.pid}; log: {log_file}")
    print(f"[batch] Stop with: kill $(cat {pid_file})")
    return 0


def install_worker_pid_cleanup(pid_file_value: str) -> None:
    script_dir = Path(__file__).resolve().parent
    pid_file = resolve_path(pid_file_value, script_dir)
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")

    def cleanup() -> None:
        try:
            if pid_file.read_text(encoding="utf-8").strip() == str(os.getpid()):
                pid_file.unlink()
        except FileNotFoundError:
            pass

    atexit.register(cleanup)


def main() -> int:
    args = parse_args()
    worker = os.environ.get("BATCH_DAEMON_WORKER") == "1"
    if args.daemon and not worker:
        if args.dry_run or args.check:
            raise SystemExit("--daemon cannot be combined with --dry-run or --check.")
        return daemonize(args)
    if worker:
        install_worker_pid_cleanup(args.pid_file)
    return run_cases(args)


if __name__ == "__main__":
    sys.exit(main())
