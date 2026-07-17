# PInsight trace-analysis scripts (Python)

Structured analysis toolkit for PInsight CTF traces. Started 2026-07-17; the
`old/` subfolder is a legacy toolkit from an early PInsight version — kept for
reference, not maintained, do not build on it.

## Layout

- top level — **app-agnostic** scripts: they consume only PInsight's tracepoint
  schemas (pmpi / roctracer / energy / enter_exit domains) and make no
  assumptions about which application produced the trace.
- `amg2023/` — AMG2023-specific scripts (e.g. parsers of AMG's own stdout).
  Add one subfolder per application for anything app-specific.

## Shared infrastructure

- `pinsight_reader.py` — common reader: runs `babeltrace2` over one or more
  trace directories (pass all of a multi-node run's per-node dirs; they are
  merged time-ordered), yields parsed events, and provides begin/end duration
  matching. All analysis scripts below build on it. Requires `babeltrace2` on
  `PATH`.

## Analysis scripts (app-agnostic)

All take one or more trace dirs: `python3 <script>.py <trace_dir> [...]`.

- `load_imbalance.py` — per-rank wall/wait/work breakdown across all ranks of
  a run; identifies which ranks wait (and the likely straggler they wait for).
- `mpi_latency.py` — MPI call-duration distributions (mean/p50/p95/p99/max)
  per call type, split same-node vs cross-node and by message size. Note:
  durations are host time in-call (skew-free), not cross-rank one-way latency.
- `gpu_datamovement.py` — host<->device copy analysis: direction/bytes/host
  time from hipMemcpy host events; actual GPU copy time and bandwidth from
  activity records.
- `halo_exchange.py` — point-to-point (halo) vs collective cost split,
  neighbor topology (who talks to whom, same-node vs cross-node), and the
  message-size profile (latency-bound vs bandwidth-bound diagnosis).
- `mpi_gpu_energy_report.py` — the combined per-rank report (MPI/GPU/energy +
  figures + kernel hotspots); reads a `babeltrace2` stream on stdin:
  `babeltrace2 <trace> | python3 mpi_gpu_energy_report.py --tag run1`.
  Per-rank GPU-exec attribution requires an unambiguous one-GPU-per-rank
  mapping and degrades gracefully (with a note) otherwise.
- `parse_energy.py` — minimal per-device energy/power from the energy domain
  only: `python3 parse_energy.py <trace_dir> [...]` (one line per dir).

## App-specific

- `amg2023/parse_overhead.py` — trace-vs-notrace overhead comparison from
  AMG2023's own stdout timing lines (not from trace data); tied to AMG's
  output format by nature.

## Conventions for new scripts

- App-agnostic scripts at top level, app-specific ones under `<app>/`.
- Build on `pinsight_reader.py` rather than re-parsing babeltrace2 text.
- Multi-node runs: accept N trace dirs, learn rank->host from the events.
- Energy gpu_uj is node-wide (same values on every rank of a node) — dedupe
  by hostname, never sum across a node's ranks.
