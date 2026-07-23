#!/bin/bash
# Shared logic for the TraceCompass "External Analyses" wrapper scripts
# (lami_<analysis>.sh in this folder). Not called directly.
#
# Owns everything TC-specific and machine-specific so the per-analysis
# wrappers are two lines:
#   - PATH setup: GUI apps get a minimal PATH; python3 and babeltrace2 must
#     resolve. Common homebrew locations are added automatically; anything
#     else goes in tc-local.conf (see below).
#   - Experiment-name resolution: running a TC external analysis on an
#     EXPERIMENT passes the experiment's NAME as the LAST argument (TC's
#     argument order: progress flag, --begin/--end, extra params, trace path
#     last). Resolved here to the member trace folders by mapping the
#     experiment's shadow tree under <project>/Experiments/<name>/ back to the
#     real CTF traces under <project>/Traces/ (see the Python block below).
#   - exec of the generic LAMI adapter (lami_adapter.py) with the analysis
#     module name supplied by the calling wrapper.
#
# Kept bash-3.2 compatible (macOS default bash: no mapfile etc.).

# ================= CONFIG: the three user-customizable paths ==============
# Leave empty for auto-detection/defaults, or set them here directly.
# PREFERRED: set them in tc-local.conf next to this file instead (gitignored
# plain shell, same three variable names) — that survives git updates and
# keeps machine paths out of the repo. tc-local.conf wins over these lines.
PYTHON3="${PYTHON3:-}"                  # python3 executable
                                        #   (empty: first python3 on PATH)
BABELTRACE2_DIR="${BABELTRACE2_DIR:-}"  # dir containing babeltrace2
                                        #   (empty: homebrew locations probed)
TC_WORKSPACE="${TC_WORKSPACE:-}"        # Eclipse workspace (TC title bar)
                                        #   (empty: ~/eclipse-workspace)
# (the ${VAR:-} form also lets environment variables supply values;
#  precedence: tc-local.conf > these lines/environment > built-in default)
# ==========================================================================

TC_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[ -f "$TC_HERE/tc-local.conf" ] && . "$TC_HERE/tc-local.conf"

# PATH: probe common tool locations; BABELTRACE2_DIR (if set) wins by going last.
for _d in /opt/homebrew/bin /usr/local/bin "$HOME/homebrew/bin" "${BABELTRACE2_DIR:-}"; do
  [ -n "$_d" ] && [ -d "$_d" ] && PATH="$_d:$PATH"
done
export PATH

PYTHON3="${PYTHON3:-$(command -v python3)}"
TC_WORKSPACE="${TC_WORKSPACE:-$HOME/eclipse-workspace}"
TC_ADAPTER="$TC_HERE/lami_adapter.py"

# run_lami_analysis <analysis_module> [args from TC...]
run_lami_analysis() {
  local analysis="$1"; shift
  local args=("$@")
  local n=${#args[@]}
  if [ "$n" -gt 0 ]; then
    local last="${args[$((n-1))]}"
    case "$last" in
      --*) : ;;   # handshake invocations (--mi-version/--metadata): pass through
      *)
        if [ ! -d "$last" ]; then
          # Not a path -> assume TC experiment name; resolve member locations.
          local resolved=()
          local line
          while IFS= read -r line; do
            [ -n "$line" ] && resolved+=("$line")
          done < <(EXP_NAME="$last" TC_WS="$TC_WORKSPACE" "$PYTHON3" - <<'PY'
import os, glob
# Resolve a TraceCompass EXPERIMENT name to its member CTF trace dirs.
# TMF stores an experiment's membership as a SHADOW directory tree under
# <project>/Experiments/<name>/ that reproduces, relative to that folder, the
# path of each member trace under <project>/Traces/ (the leaf is a 0-byte
# marker whose name is the trace, e.g. .../64-bit). So we map every node of
# the shadow tree back to <project>/Traces/<relpath> and keep the ones that
# are real CTF traces (contain a `metadata` file). Robust to how TMF renders
# the leaf (0-byte file, dir, or link); needs no `.project` parsing (that file
# only records lazily-created .bookmarks, NOT experiment membership).
name = os.environ["EXP_NAME"]
ws = os.path.expanduser(os.environ["TC_WS"])
found = set()
for proj in glob.glob(os.path.join(ws, "*")):
    exp = os.path.join(proj, "Experiments", name)
    traces = os.path.join(proj, "Traces")
    if not os.path.isdir(exp) or not os.path.isdir(traces):
        continue
    for root, subdirs, files in os.walk(exp):
        for entry in files + subdirs:
            rel = os.path.relpath(os.path.join(root, entry), exp)
            real = os.path.join(traces, rel)
            if os.path.isfile(os.path.join(real, "metadata")):
                found.add(real)
for d in sorted(found):
    print(d)
PY
)
          if [ "${#resolved[@]}" -gt 0 ]; then
            args=("${args[@]:0:$((n-1))}" "${resolved[@]}")
          fi   # unresolved: pass through; the adapter warns and skips it
        fi
        ;;
    esac
  fi
  exec "$PYTHON3" "$TC_ADAPTER" "$analysis" --lami "${args[@]}"
}
