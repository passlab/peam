#!/usr/bin/env python3
# Shared reader for PInsight CTF traces (via babeltrace2 text output).
# Used by the analysis scripts in this folder. App-agnostic.
#
# Feed it one or more trace directories (e.g. the per-node output dirs of a
# multi-node run); babeltrace2 merges them into one time-ordered stream.
#
#   from pinsight_reader import events
#   for ev in events(["/path/node1", "/path/node2"]):
#       ev.t_ns, ev.host, ev.provider, ev.name, ev.fields (dict of str->str)
import re, subprocess, sys
from dataclasses import dataclass

_ts_re  = re.compile(r'^\[(\d\d):(\d\d):(\d\d)\.(\d{9})\]')
_ev_re  = re.compile(r'(\S+?)_pinsight_lttng_ust:(\w+):')
_host_re= re.compile(r'hostname = "([^"]*)"')
# generic "key = value" fields; values may be numbers, hex, quoted strings, or
# enum-like ( "label" : container = N ) blobs -- keep the raw string, callers
# int()/strip as needed.
_fld_re = re.compile(r'(\w+) = (0x[0-9A-Fa-f]+|-?\d+|"[^"]*"|\( "[^"]*" : container = \d+ \))')

@dataclass
class Event:
    t_ns: int
    host: str
    provider: str   # pmpi | roctracer | ompt | energy | pinsight_enter_exit
    name: str       # e.g. MPI_Isend_begin, hipKernelActivity
    fields: dict    # raw string values keyed by field name

    def i(self, key, default=None):
        v = self.fields.get(key)
        if v is None: return default
        try: return int(v, 0)
        except ValueError: return default

    def s(self, key, default=None):
        v = self.fields.get(key)
        return v.strip('"') if v is not None else default

def _to_ns(h, mi, s, f):
    return ((int(h)*3600+int(mi)*60+int(s))*1_000_000_000)+int(f)

def events(trace_dirs, babeltrace="babeltrace2"):
    """Yield Event for every PInsight event across the given trace dirs,
    time-ordered (babeltrace2 merges multiple inputs by timestamp)."""
    proc = subprocess.Popen([babeltrace] + list(trace_dirs),
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, bufsize=1<<20)
    for line in proc.stdout:
        tm = _ts_re.match(line)
        if not tm: continue
        em = _ev_re.search(line)
        if not em: continue
        hm = _host_re.search(line)
        yield Event(t_ns=_to_ns(*tm.groups()),
                    host=hm.group(1) if hm else "",
                    provider=em.group(1), name=em.group(2),
                    fields=dict(_fld_re.findall(line)))
    proc.wait()

class BeginEndMatcher:
    """Pair *_begin/*_end events per (rank) into durations.
    add() returns (base_name, duration_ns, begin_event) on each completed pair."""
    def __init__(self):
        self.open = {}
    def add(self, ev, rank):
        if ev.name.endswith("_begin"):
            self.open[(rank, ev.name[:-6])] = ev
            return None
        if ev.name.endswith("_end"):
            base = ev.name[:-4]
            b = self.open.pop((rank, base), None)
            if b is not None:
                return base, ev.t_ns - b.t_ns, b
        return None

def fmt_bytes(n):
    for unit in ("B","KB","MB","GB","TB"):
        if n < 1024 or unit == "TB": return f"{n:.1f} {unit}" if unit!="B" else f"{n} B"
        n /= 1024

def percentile(sorted_vals, p):
    if not sorted_vals: return 0
    k = (len(sorted_vals)-1) * p / 100
    lo = int(k)
    hi = min(lo+1, len(sorted_vals)-1)
    return sorted_vals[lo] + (sorted_vals[hi]-sorted_vals[lo]) * (k-lo)
