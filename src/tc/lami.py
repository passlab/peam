#!/usr/bin/env python3
# Shared LAMI 1.0 support for the PInsight analysis scripts — the TraceCompass
# "External Analyses" protocol, validated against TC 2026-06 on 2026-07-20
# (see doc/visualization_analysis_redesign.md WS9).
#
# Protocol (LamiAnalysis.canExecute() / execute() in TC source):
#   1. `<cmd> --mi-version`                    -> print "1.0" (REQUIRED; TC
#      marks the analysis unsupported/struck-through without it)
#   2. `<cmd> --metadata`                      -> table-schema JSON
#   3. `<cmd> --test-compatibility <trace>`    -> exit 0 if compatible
#   4. `<cmd> [--output-progress] [--begin ns --end ns] [extra args] <trace>`
#      -> results JSON. Every result object MUST carry "time-range" (TC
#      errors with 'JSONObject["time-range"] not found' otherwise).
#
# TC quirks handled here:
#   - TC treats the configured command as ONE executable (no shell splitting):
#     use a single-word wrapper script that pins interpreter/paths/PATH
#     (GUI apps get a minimal PATH: babeltrace2 & python must be resolvable).
#   - --begin/--end arrive as absolute epoch ns; babeltrace2's default text
#     output (what pinsight_reader parses) is LOCAL time-of-day, so bounds
#     are converted (ranges spanning local midnight unsupported).
#   - Extra arguments typed in TC's run dialog arrive before the trace path;
#     we treat every non-flag argument as another trace dir, so pasting the
#     other nodes' trace dirs there yields a merged multi-node analysis.
import json, os, sys, time

# The analysis scripts live one level up; make them importable from here.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pinsight_reader import expand_dirs

def duration(seconds):
    return {"class": "duration", "value": int(seconds * 1e9)}

def duration_ns(ns):
    return {"class": "duration", "value": int(ns)}

def ratio(v):
    return {"class": "ratio", "value": round(v, 4)}

def size_bytes(n):
    return {"class": "size", "value": int(n)}

def metadata(title, description, tables):
    """tables: {class_id: (table_title, [(col_title, col_class), ...])}"""
    return {
        "mi-version": {"major": 1, "minor": 0},
        "version": {"major": 0, "minor": 2, "patch": 0},
        "title": title,
        "description": description,
        "table-classes": {
            cid: {"title": ttitle,
                  "column-descriptions": [{"title": t, "class": c}
                                          for t, c in cols]}
            for cid, (ttitle, cols) in tables.items()
        },
    }

def epoch_ns_to_local_tod_ns(epoch_ns):
    lt = time.localtime(epoch_ns // 1_000_000_000)
    frac = epoch_ns % 1_000_000_000
    return ((lt.tm_hour*3600 + lt.tm_min*60 + lt.tm_sec) * 1_000_000_000) + frac

def results(tables_rows, span, begin_epoch_ns=None, end_epoch_ns=None):
    """tables_rows: [(class_id, [row, ...]), ...]; span: (t0_ns, t1_ns)."""
    if begin_epoch_ns is not None and end_epoch_ns is not None:
        tr = {"class": "time-range", "begin": begin_epoch_ns, "end": end_epoch_ns}
    else:
        tr = {"class": "time-range", "begin": span[0], "end": span[1]}
    return {"results": [{"time-range": tr, "class": cid, "data": rows}
                        for cid, rows in tables_rows]}

def run(argv, meta, analyze_lami, main_text, usage):
    """Standard CLI for a LAMI-capable analysis script.
    meta: the metadata() dict.
    analyze_lami(dirs, begin_tod_ns, end_tod_ns) -> (tables_rows, span)
    main_text(dirs) -> None  (original human-readable mode)
    """
    lami = False; begin = None; end = None; test_compat = False; dirs = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--lami": lami = True
        elif a == "--mi-version":
            print("1.0"); return 0
        elif a == "--metadata":
            print(json.dumps(meta)); return 0
        elif a == "--test-compatibility": test_compat = True
        elif a == "--begin": i += 1; begin = int(argv[i])
        elif a == "--end":   i += 1; end = int(argv[i])
        elif a == "--output-progress": pass   # progress not implemented
        elif a.startswith("--"): pass         # tolerate unknown TC flags
        else: dirs.append(a)
        i += 1
    dirs = expand_dirs(dirs)
    if test_compat:
        import os
        return 0 if dirs and all(os.path.isdir(d) for d in dirs) else 1
    if not dirs:
        print(usage); return 1
    if lami:
        b = epoch_ns_to_local_tod_ns(begin) if begin is not None else None
        e = epoch_ns_to_local_tod_ns(end)   if end   is not None else None
        tables_rows, span = analyze_lami(dirs, b, e)
        print(json.dumps(results(tables_rows, span, begin, end)))
    else:
        main_text(dirs)
    return 0
