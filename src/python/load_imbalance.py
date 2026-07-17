#!/usr/bin/env python3
# Load-imbalance analysis across ALL ranks of a (multi-node) MPI+HIP PInsight
# trace: how much of each rank's wall time is real work vs waiting on others.
#
#   usage: python3 load_imbalance.py <trace_dir> [<trace_dir> ...]
#          (pass every node's trace dir of one run; they are time-merged)
#
# Per rank: wall time, blocking-MPI ("wait") time, non-blocking-posting time,
# GPU-sync time, kernel-launch + memcpy host overheads. The imbalance signature
# is a rank with low wait and high everything-else (the straggler everyone
# waits FOR) vs ranks with high wait (the ones waiting).
import sys
from collections import defaultdict
from pinsight_reader import events, BeginEndMatcher

MPI_WAIT = {"MPI_Waitall","MPI_Wait","MPI_Allreduce","MPI_Barrier","MPI_Allgather",
            "MPI_Recv","MPI_Send"}   # blocking calls: time here = waiting/synchronizing

def main(dirs):
    m = BeginEndMatcher()
    dur   = defaultdict(lambda: defaultdict(float))  # [rank][cat] s
    first = {}; last = {}; host_of = {}
    for ev in events(dirs):
        r = ev.i("mpirank")
        if r is None: continue
        if ev.provider in ("pmpi","roctracer","pinsight_enter_exit"):
            if r not in first: first[r] = ev.t_ns
            last[r] = ev.t_ns
            if ev.host: host_of[r] = ev.host
        if ev.provider not in ("pmpi","roctracer"): continue
        got = m.add(ev, r)
        if not got: continue
        base, dns, _b = got
        d = dns/1e9
        if ev.provider == "pmpi":
            dur[r]["mpi_total"] += d
            dur[r]["mpi_wait" if base in MPI_WAIT else "mpi_post"] += d
        elif base in ("hipStreamSync","hipDeviceSync"):
            dur[r]["gpu_sync"] += d
        elif base == "hipKernelLaunch":
            dur[r]["launch"] += d
        elif base in ("hipMemcpy","hipMemcpyAsync"):
            dur[r]["memcpy"] += d

    ranks = sorted(first)
    print(f"{'rank':>4} {'host':>14} {'wall(s)':>8} {'MPIwait':>8} {'MPIpost':>8} "
          f"{'GPUsync':>8} {'launch':>7} {'memcpy':>7} {'other':>8}  wait%")
    print("-"*88)
    waits = []
    for r in ranks:
        wall = (last[r]-first[r])/1e9
        d = dur[r]
        acct = d["mpi_total"]+d["gpu_sync"]+d["launch"]+d["memcpy"]
        other = max(wall-acct, 0)
        waitpct = 100*(d["mpi_wait"]+d["gpu_sync"])/wall if wall else 0
        waits.append(d["mpi_wait"])
        print(f"{r:>4} {host_of.get(r,'?'):>14} {wall:8.2f} {d['mpi_wait']:8.3f} "
              f"{d['mpi_post']:8.3f} {d['gpu_sync']:8.3f} {d['launch']:7.3f} "
              f"{d['memcpy']:7.3f} {other:8.2f}  {waitpct:5.1f}")
    print("-"*88)
    if waits and sum(waits):
        mean = sum(waits)/len(waits)
        print(f"MPI-wait imbalance (max-min)/mean: {(max(waits)-min(waits))/mean*100:.0f}%   "
              f"min={min(waits):.2f}s max={max(waits):.2f}s")
        least = min(range(len(waits)), key=lambda i: waits[i])
        print(f"least-waiting rank (likely straggler others wait for): rank {ranks[least]} "
              f"on {host_of.get(ranks[least],'?')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__ or "usage: load_imbalance.py <trace_dir>..."); sys.exit(1)
    main(sys.argv[1:])
