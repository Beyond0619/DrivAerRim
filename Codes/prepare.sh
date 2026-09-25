#!/usr/bin/env bash
# =============================================================================
# Prepare Rim1 .. RimN batch cases: copy from template, then copy rim NAS from
# Rims_nas into each case CAD folder.
#
# Template CAD may omit rims_clean_sm_open_.nas; this script copies it
# from the external Rims_nas source.
#
# Usage:
#   ./prepare_rim_cases.sh [options]
#
# Options (env vars or edit defaults in script):
#   TEMPLATE_DIR   Template directory, public placeholder: -
#   RIMS_NAS_DIR   NAS source directory, public placeholder: -
#   OUTPUT_PARENT  Parent dir for Rim1..RimN, public placeholder: -
#   START          First index (default 1). Use with N or END.
#   N              Number of cases (default 500). Ignored if END is set.
#   END            Last index (e.g. END=10 with START=4 -> Rim004..Rim010). Overrides N.
#   INDICES        Exact list (space-separated), e.g. "4 7 9" -> only Rim004 Rim007 Rim009. Overrides START/N/END.
#   NAS_LAYOUT     flat | subdir | subdir_range
#     flat:         Rims_nas/rims_clean_sm_open_001.nas .. _500.nas
#     subdir:       Rims_nas/001/rims_clean_sm_open_.nas
#     subdir_range: Rims_nas/001-050/001/ ... (range subdirs, see RIMS_NAS_RANGE_SIZE)
#   RIMS_NAS_RANGE_SIZE  For subdir_range only: size per range (50) -> 001-050, 051-100, ...
#   RIM_PAD        Zero-pad width for folder and NAS index, default 3 (Rim001..Rim500; 001-050/001 etc.)
#
# Each case CAD receives rims_clean_sm_open_.nas (copied from Rims_nas).
# Also updates:
#   - run_tetralith.sh      : #SBATCH -J R<index>
#   - post_tetralith_gpu.sh : #SBATCH -J Ru<zero-padded-index>_Post (if file exists)
#
# Command examples:
#   N=3 ./prepare_rim_cases.sh
#   START=4 END=10 ./prepare_rim_cases.sh
#   START=4 N=7 ./prepare_rim_cases.sh
#   INDICES="4 7 9" ./prepare_rim_cases.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ========== Edit defaults here so you need not set env vars in the terminal ==========
# Terminal export overrides these defaults
TEMPLATE_DIR="${TEMPLATE_DIR:--}"
RIMS_NAS_DIR="${RIMS_NAS_DIR:--}"
OUTPUT_PARENT="${OUTPUT_PARENT:--}"
START="${START:-}"
N="${N:-}"
END="${END:-}"
INDICES="${INDICES:-}"
NAS_LAYOUT="${NAS_LAYOUT:-subdir_range}"
# Backward compatibility: previous versions used NAS_LAYOUT=cad_group
[[ "$NAS_LAYOUT" = "cad_group" ]] && NAS_LAYOUT="subdir_range"
RIM_PAD="${RIM_PAD:-3}"
RIMS_NAS_RANGE_SIZE="${RIMS_NAS_RANGE_SIZE:-50}"
# =================================================================

# Rim NAS filename written into each case CAD (copied from Rims_nas; template may omit it)
RIM_NAS_NAME="rims_clean_sm_open_.nas"

usage() {
  echo "Usage: $0 [options]"
  echo "  Env: TEMPLATE_DIR RIMS_NAS_DIR OUTPUT_PARENT START N END INDICES NAS_LAYOUT"
  echo "  See script header for command examples (number, range, INDICES)."
  exit 0
}

[[ "${1:-}" = "-h" || "${1:-}" = "--help" ]] && usage

if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "ERROR: Template not found: $TEMPLATE_DIR"
  exit 1
fi

if [[ ! -d "$RIMS_NAS_DIR" ]]; then
  echo "ERROR: Rims NAS dir not found: $RIMS_NAS_DIR"
  exit 1
fi

mkdir -p "$OUTPUT_PARENT"

# Index list: INDICES if set, else START..END or START..START+N-1
if [[ -n "$INDICES" ]]; then
  SEQ_INDICES=$INDICES
elif [[ -n "$END" ]]; then
  SEQ_INDICES=$(seq "$START" "$END")
else
  SEQ_INDICES=$(seq "$START" $((START + N - 1)))
fi

rim_name() { if [[ "${RIM_PAD:-0}" -gt 0 ]]; then printf "Rim%0${RIM_PAD}d" "$1"; else echo "Rim$1"; fi; }
# Zero-padded index (same as RIM_PAD) for Rims_nas file/subdir names (001 style)
pad_num() { if [[ "${RIM_PAD:-0}" -gt 0 ]]; then printf "%0${RIM_PAD}d" "$1"; else echo "$1"; fi; }

for i in $SEQ_INDICES; do
  rname=$(rim_name "$i")
  pnum=$(pad_num "$i")
  dest="$(readlink -f "${OUTPUT_PARENT}/${rname}")"
  echo "---- ${rname} ----"

  if [[ -d "$dest" ]]; then
    echo "  ${rname} exists, only updating scripts and CAD rim NAS."
  else
    echo "  Copying template to ${rname}..."
    cp -a "$TEMPLATE_DIR" "$dest"
  fi

  # Update SLURM job name in run_tetralith.sh (R301, R302, ...)
  job_script="${dest}/run_tetralith.sh"
  if [[ -f "$job_script" ]]; then
    job_name="R${i}"
    echo "  Setting job name in run_tetralith.sh to ${job_name}"
    tmp_job="${job_script}.tmp.$$"
    sed -E "s/^#SBATCH -J .*/#SBATCH -J ${job_name}/" "$job_script" > "$tmp_job"
    mv "$tmp_job" "$job_script"
  fi

  # post_tetralith_gpu.sh is already in template; only update job name if present
  post_job_script="${dest}/post_tetralith_gpu.sh"
  if [[ -f "$post_job_script" ]]; then
    post_job_name="R${pnum}_Post"
    echo "  Setting post job name in post_tetralith_gpu.sh to ${post_job_name}"
    tmp_post="${post_job_script}.tmp.$$"
    sed -E "s/^#SBATCH -J .*/#SBATCH -J ${post_job_name}/" "$post_job_script" > "$tmp_post"
    mv "$tmp_post" "$post_job_script"
  fi

  cad_dir="${dest}/CAD"
  mkdir -p "$cad_dir"

  if [[ "$NAS_LAYOUT" = "subdir_range" && -n "${RIMS_NAS_RANGE_SIZE}" && "${RIMS_NAS_RANGE_SIZE}" -gt 0 ]]; then
    # e.g. RANGE_SIZE=50: 301-350 -> .../301-350/301/ ...
    range_start=$(( ((i - 1) / RIMS_NAS_RANGE_SIZE) * RIMS_NAS_RANGE_SIZE + 1 ))
    range_end=$(( range_start + RIMS_NAS_RANGE_SIZE - 1 ))
    range_dir="$(pad_num "$range_start")-$(pad_num "$range_end")"
    src_nas="${RIMS_NAS_DIR}/${range_dir}/${pnum}/${RIM_NAS_NAME}"
  elif [[ "$NAS_LAYOUT" = "subdir" ]]; then
    src_nas="${RIMS_NAS_DIR}/${pnum}/${RIM_NAS_NAME}"
  else
    src_nas="${RIMS_NAS_DIR}/rims_clean_sm_open_${pnum}.nas"
  fi

  # File-name compatibility fallback (same directory, pnum-suffixed rim NAS)
  if [[ ! -f "$src_nas" ]]; then
    src_dir="$(dirname "$src_nas")"
    src_nas="${src_dir}/rims_clean_sm_open_${pnum}.nas"
  fi

  if [[ ! -f "$src_nas" ]]; then
    echo "  WARNING: Source NAS not found: $src_nas (skip copy)"
    continue
  fi

  # Remove any existing rim NAS in target CAD (e.g. _i.nas or _.nas)
  for f in "${cad_dir}"/rims_clean_sm_open_*.nas; do
    [[ -e "$f" ]] && rm -f "$f"
  done

  cp -f "$src_nas" "${cad_dir}/${RIM_NAS_NAME}"
  echo "  -> ${cad_dir}/${RIM_NAS_NAME}"
done

first_i=$(echo $SEQ_INDICES | awk '{print $1}')
last_i=$(echo $SEQ_INDICES | awk '{print $NF}')
echo "Done. Prepared $(rim_name "$first_i") .. $(rim_name "$last_i") ($(echo $SEQ_INDICES | wc -w) case(s)) under ${OUTPUT_PARENT}."
