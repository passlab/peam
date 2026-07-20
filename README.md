# PEAM — Performance and Execution Analysis and Monitoring

PEAM is the analysis and visualization companion to
[PInsight](https://github.com/passlab/pinsight). PInsight traces parallel
applications (OpenMP/OMPT, MPI/PMPI, GPU via CUDA-CUPTI and HIP-ROCTracer,
Python, and energy) into LTTng-UST/CTF traces with very low overhead; PEAM
turns those traces into performance insight — scriptable analyses, reports,
and interactive TraceCompass visualization — for single-process runs up to
multi-node MPI+GPU jobs.

## What's here

| Path | Contents |
|---|---|
| `src/` | **Python analysis toolkit** (the main entry point — see its [README](src/README.md)) |
| `src/tc/` | all TraceCompass integration: run the Python analyses from TC menus, plus the **XML data-driven analyses** (timeline/state views) |
| `experiment/`, `docs/` | exploratory prototypes and presentation material (not maintained) |

## Python analysis toolkit (`src/`)

Tool-independent command-line analyses over PInsight CTF traces. Requires
`python3` and [`babeltrace2`](https://babeltrace.org) on `PATH`.

Current analyses (multi-node aware — pass a whole run folder, or any mix of
trace/parent folders):

- **`load_imbalance.py`** — per-rank wall/wait/work breakdown; which ranks
  wait, and the likely straggler they wait for.
- **`mpi_latency.py`** — MPI call-duration distributions (mean/p50/p95/p99)
  per call type, same-node vs cross-node, and by message size.
- **`gpu_datamovement.py`** — host↔device copy cost: direction/bytes/host
  time from HIP host events, true GPU copy time and bandwidth from activity
  records.
- **`halo_exchange.py`** — point-to-point (halo) vs collective cost split,
  neighbor topology, message-size profile (latency- vs bandwidth-bound).
- **`mpi_gpu_energy_report.py`** — combined per-rank MPI/GPU/energy report
  with figures and GPU-kernel hotspots.

```bash
# whole 4-node run (a run folder expands to all per-node traces beneath it):
python3 src/load_imbalance.py /path/to/run_folder

# machine-readable output for scripts/spreadsheets:
python3 src/mpi_latency.py --json /path/to/run_folder
python3 src/halo_exchange.py --csv  /path/to/run_folder
```

Output formats: human-readable text (default), `--json`, `--csv` — all
driven by a per-script declarative table contract, so every analysis gets
all formats (and the TraceCompass integration below) automatically. Details
and conventions for adding new analyses: [`src/README.md`](src/README.md).

## TraceCompass integration

Two complementary mechanisms:

1. **XML data-driven analyses** (`src/tc/*.xml`) — import
   `pinsight_analysis.xml` via TraceCompass's *Manage XML analyses…* to get
   a unified cross-domain timeline (OpenMP threads/teams/regions, CUDA and
   HIP devices/kernels, MPI per-rank states) over any PInsight trace, batch
   or live. `pinsight_omp_pattern_analysis.xml` adds OpenMP parallel-region
   segment statistics.

2. **Run the Python analyses from the TC GUI** (`src/tc/`) — register
   the committed `tc/lami_<analysis>.sh` wrappers as TraceCompass *External
   Analyses*; results render as native report tables (and charts), honoring
   the GUI's time-range selection and working on traces or experiments.
   Setup (three machine-local paths) in
   [`src/README.md`](src/README.md).

![LULESH traced by PInsight, visualized in TraceCompass](docs/OMPT_LTTng_TraceCompass.png)

## Typical workflow

1. Trace your application with PInsight (see the
   [PInsight repo](https://github.com/passlab/pinsight); for MPI jobs, one
   LTTng session per node writing to a shared filesystem, one trace dir per
   node).
2. Skim interactively: open the trace(s)/experiment in TraceCompass with
   the XML analyses for the timeline view.
3. Quantify: run the Python analyses — from the shell for reports/automation
   (`--json`/`--csv`), or from TraceCompass's External Analyses menu for
   in-GUI tables scoped to a selected time range.
