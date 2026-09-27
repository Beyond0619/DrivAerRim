#!/usr/bin/env bash
#SBATCH -J jobname
#SBATCH -N 1 -n 1 -c 32
#SBATCH --gpus-per-task=1
#SBATCH --exclusive
#SBATCH -A -
#SBATCH -t 04:00:00
#SBATCH --mail-type=ALL
#SBATCH --mail-user=-

# =============================================================================
# Post-processing job for Tetralith GPU nodes (Tesla T4, 1 GPU/node).
# Submit AFTER the main run.sh has produced *_Finished.sim.
#   sbatch post.sh
# Or chain from the main job:
#   sbatch --dependency=afterok:${RUN_JOBID} post.sh
#
# Rationale: STAR-CCM+ picture export is single-threaded and entirely GPU-bound
# (remote rasterizer). On Tetralith CPU nodes it falls back to mesa software
# rendering, which makes 11520x6480 mesh pics take ~20 min instead of <1 min.
# On a GPU node we use EGL (like VCC does) or VirtualGL native GL to get the
# real GPU involved.
# =============================================================================

set -euo pipefail

CASE_DIR="${SLURM_SUBMIT_DIR:-$(pwd)}"
cd "$CASE_DIR"

mkdir -p log

# STAR-CCM+ and license (same settings as run.sh).
STARCCM_MODULE="${STARCCM_MODULE:-star-ccm+/2506-mixed-precision}"
module load "${STARCCM_MODULE}"
export LM_PROJECT="${LM_PROJECT:--}"
export LM_LICENSE_FILE="${LM_LICENSE_FILE:--}"
if [[ "${LM_PROJECT}" == "-" || "${LM_LICENSE_FILE}" == "-" ]]; then
  echo "WARNING: Replace the public LM_PROJECT/LM_LICENSE_FILE placeholders or export valid values before submission."
fi

# ImageMagick for outline + mesh pic size reduction (identify/convert).
if ! command -v convert >/dev/null 2>&1; then
  module load ImageMagick 2>/dev/null || module load imagemagick 2>/dev/null || true
fi
if ! command -v convert >/dev/null 2>&1; then
  echo "WARNING: ImageMagick (convert/identify) not in PATH. Outline and mesh pics compression will fail."
fi

# Tetralith has no 'vccsingularity' wrapper; use the shim that strips
# "exec IMG.sif" and runs the command on the host shell.
export PATH="${CASE_DIR}/repo/STARCFD/bin/tetralith_shims:${PATH}"

# Python runtime used by Post.java (geometrical_properties / cdAx_clAx, etc.) on Tetralith.
# Mirror the priority logic in run.sh so Post subprocess Python calls see the same env.
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

# Preflight check for python modules required by Post scripts. Post is actually
# the stage that invokes geometrical_properties.py / cdAx_clAx etc., so this
# matters MORE here than in the main run job.
if ! "${STARCFD_PYTHON}" - <<'PY' >/dev/null 2>&1
import numpy, pandas, matplotlib
PY
then
  echo "WARNING: Python deps missing in ${STARCFD_PYTHON} (need numpy, pandas, matplotlib)."
  echo "         Post scripts may fail and files like NumData/Uncertainty.csv may be missing."
  echo "         Replace STARCFD_PY_ENV=- or set STARCFD_PYTHON=python3 with those packages installed."
fi

# Classpath: repo dist/ + third-party JARs in repo/STARCFD/lib/ (same as run.sh).
STARCFD_REPO="${CASE_DIR}/repo/STARCFD"
RUNCLASSpath="${STARCFD_REPO}/dist"
if [[ ! -d "${STARCFD_REPO}/dist" ]]; then
  echo "WARNING: ${STARCFD_REPO}/dist not found. Build the STARCFD project so that classes are in dist/."
  RUNCLASSpath="${STARCFD_REPO}/build/classes:${RUNCLASSpath}"
fi
if [[ -d "${STARCFD_REPO}/lib" ]]; then
  for j in "${STARCFD_REPO}"/lib/*.jar; do
    [[ -f "$j" ]] && RUNCLASSpath="${RUNCLASSpath}:${j}"
  done
fi
if [[ ! -d "${STARCFD_REPO}/lib" ]] || ! compgen -G "${STARCFD_REPO}/lib/*.jar" >/dev/null; then
  echo "ERROR: Missing STARCFD macro dependency JARs in ${STARCFD_REPO}/lib/"
  echo "Required minimum: toml4j-0.7.2.jar, json-20211205.jar"
  echo "See repo/STARCFD/lib/README.txt for full jar list and how to copy from VCC."
  exit 1
fi

# Find the simulation to post-process.
fin_sim=$(find . -maxdepth 1 -name '*_Finished.sim' -print -quit)
if [[ -z "$fin_sim" ]]; then
  echo "ERROR: No *_Finished.sim found in $(pwd). Run the main job first."
  exit 1
fi

# GPU sanity check.
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "-- nvidia-smi on $(hostname) --"
  nvidia-smi || true
else
  echo "WARNING: nvidia-smi not found on $(hostname). Is this a GPU node?"
fi

echo "========== POST-GPU (using $fin_sim) =========="

# MPI rank count for Post. Post uses CPU for sim load, repartition, field
# functions and CSV/python export; only rendering is single-threaded on rank 0
# and sent to the GPU. Using too few ranks (e.g. -np 1) causes OOM on large
# cases because a single rank has to hold the entire 80M-cell mesh after
# repartitioning (2850|1 or 1024|1 is memory-fatal => SIGKILL/137).
#
# Priority for rank count:
#   1) STARCFD_POST_NP environment override
#   2) 8 (safe default: leaves RAM for ad-hoc renderer subprocess so
#      ScalarDisplayer-heavy iso/surface pics do not OOM at 82M cells.
#      -np 32 was observed to OOM the 96GB node at iso 3; 8 ranks still
#      keep sim load / repartition fast and leave ~30GB headroom.)
# Override with STARCFD_POST_NP=<N> if your case is small or the node is
# fat (>128GB).
POST_NP="${STARCFD_POST_NP:-8}"
echo "Post MPI ranks: ${POST_NP} (intra-node, 1 GPU shared by rank 0)"

# Graphics backend selection. Priority:
#   STARCFD_POST_GRAPHICS=adhoc   -> -rr <hostname> -agraphics egl   (default, VCC-style)
#   STARCFD_POST_GRAPHICS=server  -> -rr server -rgraphics egl       (hits STAR 2506 bug on ScalarDisplayer)
#   STARCFD_POST_GRAPHICS=vgl     -> vglrun + -graphics native       (matches ThinLinc GUI alias)
#   STARCFD_POST_GRAPHICS=auto    -> try adhoc, fallback vgl
#
# Empirical result: STAR-CCM+ 2506 server-mode EGL crashes the moment a
# ScalarDisplayer is rasterised (SceneManager.getVerbose -> "Property key
# (Verbose) does not exist" -> broken pipe). VCC batch Post does NOT use
# server mode; it uses ad-hoc EGL ("-rr <host> -agraphics egl") which spawns
# the renderer as a separate starrenderer process over ssh. We do the same
# here, pointing -rr at $(hostname) so the renderer is spawned on the same
# allocated GPU node.
POST_GRAPHICS="${STARCFD_POST_GRAPHICS:-adhoc}"

run_starccm_adhoc() {
  # Ad-hoc EGL renderer, VCC-style, on the local GPU node. STAR-CCM+ spawns
  # a 'starrenderer -mode single' child process via ssh $(hostname) which
  # renders with EGL on the Tesla T4. This is the path VCC has verified and
  # it avoids the server-mode SceneManager.getVerbose() regression in 2506.
  local render_host
  render_host="$(hostname)"
  echo "Ad-hoc remote renderer on ${render_host} (EGL)"
  starccm+ -collab -power \
    -rr "${render_host}" -agraphics egl \
    -batch "${STARCFD_REPO}/src/aero/Post.java" \
    -classpath "${RUNCLASSpath}" \
    -np "${POST_NP}" \
    "$fin_sim"
}

run_starccm_server() {
  # Server-mode EGL: simpler (no ssh, no separate process) but triggers a
  # STAR-CCM+ 2506 bug as soon as a ScalarDisplayer is printed. Kept only
  # for debugging/comparison.
  starccm+ -collab -power \
    -rr server -rgraphics egl \
    -batch "${STARCFD_REPO}/src/aero/Post.java" \
    -classpath "${RUNCLASSpath}" \
    -np "${POST_NP}" \
    "$fin_sim"
}

run_starccm_vgl() {
  # Matches the interactive alias used on Tetralith ThinLinc:
  #   Starccm+='vglrun starccm+ -clientldpreload libdlfaker.so:libvglfaker.so -graphics native'
  vglrun starccm+ -clientldpreload libdlfaker.so:libvglfaker.so -graphics native \
    -collab -power \
    -batch "${STARCFD_REPO}/src/aero/Post.java" \
    -classpath "${RUNCLASSpath}" \
    -np "${POST_NP}" \
    "$fin_sim"
}

case "$POST_GRAPHICS" in
  adhoc|egl)
    run_starccm_adhoc > log/post.log 2>&1
    ;;
  server)
    run_starccm_server > log/post.log 2>&1
    ;;
  vgl)
    run_starccm_vgl > log/post.log 2>&1
    ;;
  auto)
    if ! run_starccm_adhoc > log/post.log 2>&1; then
      echo "Ad-hoc EGL path failed, retrying with vglrun + -graphics native" | tee -a log/post.log
      run_starccm_vgl >> log/post.log 2>&1
    fi
    ;;
  *)
    echo "Unknown STARCFD_POST_GRAPHICS='$POST_GRAPHICS' (expected: adhoc|server|vgl|auto)" >&2
    exit 2
    ;;
esac

echo "Post done. Log: log/post.log"
