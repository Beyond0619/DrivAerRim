#!/usr/bin/env bash
#SBATCH -J jobname
#SBATCH -N 32 -n 1024
#SBATCH -A -
#SBATCH -t 48:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=-

# =============================================================================
# Rim1_Tetralith_template: run Prep -> Surf -> Vol -> Run -> Post on Tetralith
# Submit from the case directory (where settings.toml and repo/ live).
# Requires: STAR-CCM+ module, repo/STARCFD built (dist/ or classpath), license.
# =============================================================================

set -euo pipefail

PIPELINE_STAGE="${1:-${STARCFD_STAGE:-all}}"
if [[ "${PIPELINE_STAGE}" == "-h" || "${PIPELINE_STAGE}" == "--help" ]]; then
  cat <<'EOF'
Usage: sbatch run.sh [all|prep|surf|vol|run|post]

The default stage is "all". STARCFD_STAGE can be used instead of a positional
argument. Configure cluster-specific SBATCH, module, and license settings
before submission.
EOF
  exit 0
fi
case "${PIPELINE_STAGE}" in
  all|prep|surf|vol|run|solver|post) ;;
  *)
    echo "Unknown stage '${PIPELINE_STAGE}' (expected: all|prep|surf|vol|run|post)" >&2
    exit 2
    ;;
esac

CASE_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$CASE_DIR"

NODEFILE=""
cleanup_nodefile() {
  if [[ -n "${NODEFILE}" ]]; then
    rm -f -- "${NODEFILE}"
  fi
}
trap cleanup_nodefile EXIT

prepare_nodefile() {
  if [[ -n "${NODEFILE}" && -f "${NODEFILE}" ]]; then
    return
  fi
  if [[ -z "${SLURM_JOB_ID:-}" || -z "${SLURM_JOB_NODELIST:-}" || -z "${SLURM_NTASKS:-}" ]]; then
    echo "ERROR: Vol/Run stages require a Slurm allocation." >&2
    exit 1
  fi
  NODEFILE="${CASE_DIR}/hostlist.${SLURM_JOB_ID}"
  if command -v hostlist &>/dev/null; then
    hostlist -e "${SLURM_JOB_NODELIST}" > "${NODEFILE}"
  else
    scontrol show hostnames "${SLURM_JOB_NODELIST}" > "${NODEFILE}"
  fi
}

mkdir -p log

# STAR-CCM+ and license (adjust for the target cluster).
STARCCM_MODULE="${STARCCM_MODULE:-star-ccm+/2506-mixed-precision}"
module load "${STARCCM_MODULE}"
export LM_PROJECT="${LM_PROJECT:--}"
export LM_LICENSE_FILE="${LM_LICENSE_FILE:--}"
if [[ "${LM_PROJECT}" == "-" || "${LM_LICENSE_FILE}" == "-" ]]; then
  echo "WARNING: Replace the public LM_PROJECT/LM_LICENSE_FILE placeholders or export valid values before submission."
fi

# ImageMagick is needed by Post/Analyze for outline + size reduction (identify/convert).
# Tetralith ships it as a module; no-op if already available.
if ! command -v convert >/dev/null 2>&1; then
  module load ImageMagick 2>/dev/null || module load imagemagick 2>/dev/null || true
fi
if ! command -v convert >/dev/null 2>&1; then
  echo "WARNING: ImageMagick (convert/identify) not in PATH. Outline and mesh pics compression will fail."
fi

# Tetralith has no 'vccsingularity' wrapper; ship a shim that strips "exec IMG.sif"
# and runs the command on the host shell. See repo/STARCFD/bin/tetralith_shims/.
export PATH="${CASE_DIR}/repo/STARCFD/bin/tetralith_shims:${PATH}"

# Python runtime used by Run.java::runPython and Post.java (geometrical_properties / cdAx_clAx, etc.) on Tetralith.
# Priority:
#   1) STARCFD_PYTHON exported by user/job script
#   2) STARCFD_PY_ENV (if set and valid)
#   3) Auto-detect venv: case dir, parent, grandparent
#   4) SHARED_STARCFD_PY_ENV, with "-" as the public placeholder
#   5) python3 fallback
if [[ -z "${STARCFD_PY_ENV:-}" ]]; then
  for _py_candidate in \
    "${CASE_DIR}/.venv_starcfd" \
    "$(dirname "${CASE_DIR}")/.venv_starcfd" \
    "$(dirname "$(dirname "${CASE_DIR}")")/.venv_starcfd" \
    "${SHARED_STARCFD_PY_ENV:--}"; do
    [[ -z "${_py_candidate}" ]] && continue
    if [[ -x "${_py_candidate}/bin/python" ]]; then
      STARCFD_PY_ENV="${_py_candidate}"
      break
    fi
  done
fi

if [[ -n "${STARCFD_PY_ENV:-}" && -f "${STARCFD_PY_ENV}/bin/activate" ]]; then
  # Activate venv in this shell so any subprocesses (python scripts) see the same environment.
  # shellcheck disable=SC1090
  source "${STARCFD_PY_ENV}/bin/activate"
  export STARCFD_PYTHON="${STARCFD_PY_ENV}/bin/python"
elif [[ -n "${STARCFD_PY_ENV:-}" ]]; then
  echo "WARNING: STARCFD_PY_ENV is set but invalid: ${STARCFD_PY_ENV}"
  echo "         Expected: ${STARCFD_PY_ENV}/bin/python"
  export STARCFD_PYTHON="${STARCFD_PYTHON:-python3}"
else
  export STARCFD_PYTHON="${STARCFD_PYTHON:-python3}"
fi
echo "Using STARCFD_PYTHON=${STARCFD_PYTHON}"

# Preflight check for python modules required by STARCFD post scripts.
if ! "${STARCFD_PYTHON}" - <<'PY' >/dev/null 2>&1
import numpy, pandas, matplotlib
PY
then
  echo "WARNING: Python deps missing in ${STARCFD_PYTHON} (need numpy, pandas, matplotlib)."
  echo "         Post scripts may fail and files like NumData/Uncertainty.csv may be missing."
  echo "         Replace STARCFD_PY_ENV=- or set STARCFD_PYTHON=python3 with those packages installed."
fi

# Classpath: repo dist/ + third-party JARs in repo/STARCFD/lib/ (no VCC paths).
# STAR-CCM+ compiles macros at runtime and needs toml4j, org.json, etc. Copy those
# JARs from VCC extra_libraries to repo/STARCFD/lib/ (see repo/STARCFD/lib/README.txt).
STARCFD_REPO="${CASE_DIR}/repo/STARCFD"
RUNCLASSpath="${STARCFD_REPO}/dist"
if [[ ! -d "${STARCFD_REPO}/dist" ]]; then
  echo "WARNING: ${STARCFD_REPO}/dist not found. Build the STARCFD project (e.g. ant or NetBeans) so that classes are in dist/."
  RUNCLASSpath="${STARCFD_REPO}/build/classes:${RUNCLASSpath}"
fi
if [[ -d "${STARCFD_REPO}/lib" ]]; then
  for j in "${STARCFD_REPO}"/lib/*.jar; do
    [[ -f "$j" ]] && RUNCLASSpath="${RUNCLASSpath}:${j}"
  done
fi
if [[ ! -d "${STARCFD_REPO}/lib" ]] || ! compgen -G "${STARCFD_REPO}/lib/*.jar" >/dev/null; then
  echo "ERROR: Missing STARCFD macro dependency JARs in ${STARCFD_REPO}/lib/"
  echo "Required minimum:"
  echo "  - toml4j-0.7.2.jar"
  echo "  - json-20211205.jar"
  echo "See repo/STARCFD/lib/README.txt for full jar list and how to copy from VCC."
  exit 1
fi
if [[ "${RUNCLASSpath}" = "${STARCFD_REPO}/dist" ]] || [[ "${RUNCLASSpath}" = "${STARCFD_REPO}/build/classes:${STARCFD_REPO}/dist" ]]; then
  echo "WARNING: No JARs in ${STARCFD_REPO}/lib/. Prep/Run will fail (missing toml4j, org.json). Copy JARs - see repo/STARCFD/lib/README.txt"
fi

# starccm+ options: same as your working Tetralith script
# -mpiflags "-bootstrap slurm" (quoted), -rsh jobsh separate; -np 1 for Prep/Surf, -np $SLURM_NTASKS for Vol/Run/Post

# Same as VCC (Remote=1): Prep starts from FilterTemplate.sim when present under repo/STARCFD/templates/aero/
run_prep() {
  echo "========== PREP =========="
  PREP_TEMPLATE="${STARCFD_REPO}/templates/aero/FilterTemplate.sim"
  if [[ -f "${PREP_TEMPLATE}" ]]; then
    PREP_SIM="${PREP_TEMPLATE}"
    echo "Using template: ${PREP_TEMPLATE}"
  else
    PREP_SIM="-new"
    echo "Using -new (no FilterTemplate.sim found)"
  fi
  starccm+ -collab -power -mpi intel -mpiflags "-bootstrap slurm" -rsh jobsh -batch "${STARCFD_REPO}/src/aero/Prep.java" \
    -classpath "${RUNCLASSpath}" \
    -np 1 \
    ${PREP_SIM} \
    > log/prep.log 2>&1
}

run_surf() {
  local prep_sim
  prep_sim=$(find . -maxdepth 1 -name '*_prep.sim' -print -quit)
  if [[ -z "$prep_sim" ]]; then
    echo "ERROR: No *_prep.sim found. Check log/prep.log."
    exit 1
  fi
  echo "========== SURF (using $prep_sim) =========="
  starccm+ -collab -power -mpi intel -mpiflags "-bootstrap slurm" -rsh jobsh -batch "${STARCFD_REPO}/src/aero/Surf.java" \
    -classpath "${RUNCLASSpath}" \
    -np 1 \
    "$prep_sim" \
    > log/surf.log 2>&1
}

run_vol() {
  local surf_sim
  surf_sim=$(find . -maxdepth 1 -name '*_surf.sim' -print -quit)
  if [[ -z "$surf_sim" ]]; then
    echo "ERROR: No *_surf.sim found. Check log/surf.log."
    exit 1
  fi
  prepare_nodefile
  echo "========== VOL (using $surf_sim) =========="
  starccm+ -collab -power -mpi intel -mpiflags "-bootstrap slurm" -rsh jobsh -batch "${STARCFD_REPO}/src/aero/Vol.java" \
    -classpath "${RUNCLASSpath}" \
    -np "$SLURM_NTASKS" -machinefile "$NODEFILE" \
    "$surf_sim" \
    > log/vol.log 2>&1
}

run_solver() {
  local vol_sim
  vol_sim=$(find . -maxdepth 1 -name '*_vol.sim' -print -quit)
  if [[ -z "$vol_sim" ]]; then
    echo "ERROR: No *_vol.sim found. Check log/vol.log."
    exit 1
  fi
  prepare_nodefile
  echo "========== RUN (using $vol_sim) =========="
  starccm+ -collab -power -mpi intel -mpiflags "-bootstrap slurm" -rsh jobsh -batch "${STARCFD_REPO}/src/aero/Run.java" \
    -classpath "${RUNCLASSpath}" \
    -np "$SLURM_NTASKS" -machinefile "$NODEFILE" \
    "$vol_sim" \
    > log/run.log 2>&1
}

run_post_cpu_fallback() {
  # Fallback: run Post inside this CPU job. Rendering goes through mesa software
  # OpenGL and will be ~20x slower than on a GPU node. Only used when the
  # separate GPU job cannot be submitted. Controlled by STARCFD_POST_MODE=cpu.
  local fin_sim
  fin_sim=$(find . -maxdepth 1 -name '*_Finished.sim' -print -quit)
  if [[ -z "$fin_sim" ]]; then
    echo "ERROR: No *_Finished.sim found. Check log/run.log."
    exit 1
  fi
  echo "========== POST [CPU fallback, SLOW] (using $fin_sim) =========="
  starccm+ -collab -power -batch "${STARCFD_REPO}/src/aero/Post.java" \
    -classpath "${RUNCLASSpath}" \
    -np 1 \
    "$fin_sim" \
    > log/post.log 2>&1
}

submit_post_gpu() {
  # Submit a separate GPU sbatch for picture export. This is the recommended
  # path on Tetralith (Tesla T4, --gpus-per-task=1) and mirrors how VCC runs
  # Post on a dedicated remote renderer (cs7-xxxx with EGL).
  local post_script="${CASE_DIR}/post.sh"
  if [[ ! -f "$post_script" ]]; then
    echo "WARNING: $post_script not found. Cannot chain GPU Post job."
    return 1
  fi
  echo "========== Submitting GPU Post job =========="
  local post_jobid
  if [[ -n "${SLURM_JOB_ID:-}" ]]; then
    post_jobid=$(sbatch --parsable --dependency=afterok:${SLURM_JOB_ID} "$post_script")
  else
    post_jobid=$(sbatch --parsable "$post_script")
  fi
  echo "GPU Post job submitted: ${post_jobid}"
}

# Simple post toggle (more intuitive than STARCFD_POST_MODE).
# - RUN_POST=1 (default): run/submit post according to STARCFD_POST_MODE (gpu|cpu|none)
# - RUN_POST=0          : skip Post entirely
RUN_POST="${RUN_POST:-1}"

# Post-processing:
#   - STARCFD_POST_MODE=gpu  (default) -> submit post.sh as a
#     separate 1-node GPU job (with --dependency=afterok on this job), much
#     faster for picture export (EGL / vglrun on Tesla T4).
#   - STARCFD_POST_MODE=cpu  -> run Post inside this CPU job via software
#     rendering. Slow but needs no GPU allocation.
#   - STARCFD_POST_MODE=none -> skip Post here (submit manually later).
run_configured_post() {
  if [[ "${RUN_POST}" == "0" ]]; then
    echo "Skipping Post (RUN_POST=0)."
    return
  fi
  case "${STARCFD_POST_MODE:-gpu}" in
    gpu)
      submit_post_gpu
      ;;
    cpu)
      run_post_cpu_fallback
      ;;
    none)
      echo "Skipping Post (STARCFD_POST_MODE=none). Submit post.sh manually when ready."
      ;;
    *)
      echo "Unknown STARCFD_POST_MODE='${STARCFD_POST_MODE}' (expected: gpu|cpu|none)" >&2
      exit 2
      ;;
  esac
}

case "${PIPELINE_STAGE}" in
  all)
    run_prep
    run_surf
    run_vol
    run_solver
    run_configured_post
    ;;
  prep) run_prep ;;
  surf) run_surf ;;
  vol) run_vol ;;
  run|solver) run_solver ;;
  post) run_configured_post ;;
esac
echo "Done. Logs in log/prep.log, log/surf.log, log/vol.log, log/run.log, log/post.log"
