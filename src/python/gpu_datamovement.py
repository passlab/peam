#!/usr/bin/env python3
# GPU host<->device data-movement analysis from a (multi-node) PInsight trace.
#
#   usage: python3 gpu_datamovement.py <trace_dir> [<trace_dir> ...]
#
# Two independent views of copies:
#   host side  : hipMemcpy/hipMemcpyAsync begin/end -- direction (hipMemcpyKind),
#                bytes (count field), and how long the HOST was in the call
#                (for Async that is just enqueue overhead, not the copy itself)
#   device side: hipMemcpyActivity records -- actual GPU-side copy duration and
#                bytes per physical device (direction is NOT recorded on
#                activity records; only host events have hipMemcpyKind)
#
# On unified-memory devices (MI300A) explicit copies may be few/cheap; a LOW
# copy volume here on such hardware is itself a meaningful finding. Also worth
# comparing against MPI behavior: with host-staged MPI
# (MPICH_GPU_SUPPORT_ENABLED=0) GPU-resident halo data must reach host memory
# -- on discrete GPUs that appears as explicit D2H/H2D around MPI calls, on
# MI300A it shows up as page migration/coherence cost that no explicit-copy
# event captures.
import sys
from collections import defaultdict
from pinsight_reader import events, BeginEndMatcher, fmt_bytes, percentile

def main(dirs):
    m = BeginEndMatcher()
    host = defaultdict(lambda: dict(n=0, bytes=0, host_ns=0, durs=[]))  # [(call,kind)]
    per_rank = defaultdict(lambda: defaultdict(float))                  # [rank][(call,kind)] s
    act  = defaultdict(lambda: dict(n=0, bytes=0, gpu_ns=0))            # [devId]
    for ev in events(dirs):
        if ev.provider != "roctracer": continue
        if ev.name == "hipMemcpyActivity":
            d = ev.i("devId")
            a = act[d]
            a["n"] += 1
            a["bytes"] += ev.i("bytes", 0)
            a["gpu_ns"] += ev.i("end_ns",0) - ev.i("begin_ns",0)
            continue
        r = ev.i("mpirank")
        if r is None: continue
        got = m.add(ev, r)
        if not got: continue
        base, dns, b = got
        if base not in ("hipMemcpy","hipMemcpyAsync"): continue
        kind = b.s("hipMemcpyKind","?")
        if kind and kind.startswith("("):   # enum blob: ( "hipMemcpyHostToDevice" : ... )
            kind = kind.split('"')[1]
        key = (base, kind)
        h = host[key]
        h["n"] += 1; h["bytes"] += b.i("count",0); h["host_ns"] += dns
        h["durs"].append(dns/1e3)
        per_rank[r][key] += dns/1e9

    print("== host-side copy calls (direction from hipMemcpyKind; host time in call) ==")
    print(f"{'call':>16} {'direction':>24} {'n':>8} {'bytes':>10} {'host s':>8} "
          f"{'mean us':>8} {'p99 us':>8}")
    for key in sorted(host):
        h = host[key]; v = sorted(h["durs"])
        print(f"{key[0]:>16} {key[1]:>24} {h['n']:>8} {fmt_bytes(h['bytes']):>10} "
              f"{h['host_ns']/1e9:>8.3f} {sum(v)/len(v):>8.2f} {percentile(v,99):>8.2f}")

    print("\n== per-rank host time in copy calls (s) ==")
    keys = sorted({k for d in per_rank.values() for k in d})
    hdr = " ".join(f"{k[1].replace('hipMemcpy',''):>14}" for k in keys)
    print(f"{'rank':>4} {hdr}")
    for r in sorted(per_rank):
        print(f"{r:>4} " + " ".join(f"{per_rank[r].get(k,0):>14.3f}" for k in keys))

    print("\n== device-side copy activity (actual GPU copy time; direction not recorded) ==")
    print(f"{'devId':>6} {'n':>8} {'bytes':>12} {'GPU s':>8} {'avg GB/s':>9}")
    for d in sorted(act):
        a = act[d]
        bw = (a["bytes"]/1e9)/(a["gpu_ns"]/1e9) if a["gpu_ns"] else 0
        print(f"{d:>6} {a['n']:>8} {fmt_bytes(a['bytes']):>12} {a['gpu_ns']/1e9:>8.3f} {bw:>9.2f}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__ or "usage: gpu_datamovement.py <trace_dir>..."); sys.exit(1)
    main(sys.argv[1:])
