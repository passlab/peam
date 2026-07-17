#!/usr/bin/env python3
import re, glob, statistics

LABELS = ["hypre_init", "gen_matrix", "rhs_setup", "amg_setup", "amg_solve"]

def parse(path):
    times = []
    fom = None
    with open(path) as f:
        for line in f:
            if not line.startswith("0:"):
                continue
            m = re.search(r"wall clock time = ([\d.]+) seconds", line)
            if m:
                times.append(float(m.group(1)))
            m = re.search(r"Figure of Merit.*?([\d.]+e[+-]?\d+)", line)
            if m:
                fom = float(m.group(1))
    d = dict(zip(LABELS, times))
    d["fom"] = fom
    d["total"] = d.get("amg_setup", 0) + d.get("amg_solve", 0)
    return d

def summarize(mode, skip_warmup=True):
    files = sorted(glob.glob(f"logs/{mode}_rep*.out"))
    if skip_warmup:
        files = files[1:]  # discard rep1 (cold start)
    rows = [parse(f) for f in files]
    print(f"=== {mode} (n={len(rows)}, warmup discarded) ===")
    for label in LABELS + ["total"]:
        vals = [r[label] for r in rows if r.get(label) is not None]
        if vals:
            print(f"  {label:12s}: mean={statistics.mean(vals):8.3f}  "
                  f"median={statistics.median(vals):8.3f}  "
                  f"min={min(vals):8.3f}  max={max(vals):8.3f}  vals={['%.3f'%v for v in vals]}")
    foms = [r["fom"] for r in rows if r.get("fom") is not None]
    if foms:
        print(f"  FOM         : mean={statistics.mean(foms):.4e}  median={statistics.median(foms):.4e}")
    return rows

if __name__ == "__main__":
    notrace = summarize("notrace")
    trace = summarize("trace")

    print("\n=== Overhead (median total = amg_setup + amg_solve) ===")
    nt_total = statistics.median([r["total"] for r in notrace])
    tr_total = statistics.median([r["total"] for r in trace])
    print(f"  notrace median total: {nt_total:.3f} s")
    print(f"  trace   median total: {tr_total:.3f} s")
    print(f"  overhead: {(tr_total/nt_total - 1)*100:+.1f}%")

    for label in ["amg_setup", "amg_solve"]:
        nt = statistics.median([r[label] for r in notrace if r.get(label) is not None])
        tr = statistics.median([r[label] for r in trace if r.get(label) is not None])
        print(f"  {label}: notrace={nt:.3f}s trace={tr:.3f}s overhead={(tr/nt-1)*100:+.1f}%")
