#!/usr/bin/env python3
# MPI call-latency analysis from a (multi-node) PInsight trace: duration
# distributions per MPI call type, split same-node vs cross-node, and by
# message size.
#
#   usage: python3 mpi_latency.py <trace_dir> [<trace_dir> ...]
#
# What "latency" means here (important): durations are HOST TIME INSIDE each
# MPI call on the calling rank --
#   - blocking Send/Recv: includes actual transfer/synchronization delay
#   - Isend/Irecv: just the posting overhead (transfer happens in background)
#   - Wait/Waitall: the completion wait (where deferred transfer time shows up)
# True one-way message latency (send timestamp -> matching recv completion on
# the OTHER rank) would need cross-rank send/recv matching by (src,dest,tag);
# the fields exist (dest/source/tag are traced) but clock-skew between nodes
# makes sub-microsecond cross-node claims unreliable, so this script sticks to
# per-call host durations, which are skew-free.
#
# same-node vs cross-node: dest/source is interpreted as a COMM_WORLD rank and
# mapped to a hostname learned from the trace. Caveat: calls made on
# sub-communicators (if the app uses them) would mislabel peers; counts from
# comm-world-style halo exchange dominate in practice.
import sys
from collections import defaultdict
from pinsight_reader import events, BeginEndMatcher, percentile

P2P = {"MPI_Send":"dest","MPI_Isend":"dest","MPI_Recv":"source","MPI_Irecv":"source"}
OTHER = {"MPI_Wait","MPI_Waitall","MPI_Allreduce","MPI_Barrier","MPI_Allgather"}

def size_bucket(count):
    if count is None: return "?"
    for hi,label in ((8,"<=8"),(64,"<=64"),(512,"<=512"),(4096,"<=4K"),(32768,"<=32K")):
        if count <= hi: return label
    return ">32K"

def dist_row(name, vals_us):
    v = sorted(vals_us)
    return (f"{name:>28} {len(v):>8} {sum(v)/len(v):>9.2f} {percentile(v,50):>9.2f} "
            f"{percentile(v,95):>9.2f} {percentile(v,99):>9.2f} {v[-1]:>10.2f} "
            f"{sum(v)/1e6:>9.3f}")

def main(dirs):
    m = BeginEndMatcher()
    host_of = {}                      # rank -> hostname (learned)
    by_call  = defaultdict(list)      # call -> [dur_us]
    by_local = defaultdict(list)      # (call, "same-node"/"cross-node") -> [dur_us]
    by_size  = defaultdict(list)      # (call, size_bucket) -> [dur_us]
    pending = []                      # (call, dur_us, peer_rank, count) until host map complete

    for ev in events(dirs):
        r = ev.i("mpirank")
        if r is None or ev.provider != "pmpi": continue
        if ev.host: host_of[r] = ev.host
        got = m.add(ev, r)
        if not got: continue
        base, dns, b = got
        us = dns/1e3
        if base in P2P:
            peer = b.i(P2P[base])
            cnt  = b.i("count")
            by_call[base].append(us)
            by_size[(base, size_bucket(cnt))].append(us)
            pending.append((base, us, r, peer))
        elif base in OTHER:
            by_call[base].append(us)

    for base, us, r, peer in pending:
        h1, h2 = host_of.get(r), host_of.get(peer)
        loc = "same-node" if (h1 and h2 and h1==h2) else ("cross-node" if h1 and h2 else "?")
        by_local[(base, loc)].append(us)

    hdr = (f"{'call':>28} {'n':>8} {'mean us':>9} {'p50 us':>9} {'p95 us':>9} "
           f"{'p99 us':>9} {'max us':>10} {'total s':>9}")
    print("== per call type =="); print(hdr)
    for c in sorted(by_call): print(dist_row(c, by_call[c]))

    print("\n== P2P: same-node vs cross-node =="); print(hdr)
    for k in sorted(by_local):
        print(dist_row(f"{k[0]} [{k[1]}]", by_local[k]))

    print("\n== P2P by message size (count = MPI elements, datatype not traced) ==")
    print(hdr)
    order = {"<=8":0,"<=64":1,"<=512":2,"<=4K":3,"<=32K":4,">32K":5,"?":6}
    for k in sorted(by_size, key=lambda k:(k[0],order.get(k[1],9))):
        print(dist_row(f"{k[0]} [{k[1]}]", by_size[k]))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__ or "usage: mpi_latency.py <trace_dir>..."); sys.exit(1)
    main(sys.argv[1:])
