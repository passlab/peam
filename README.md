# Performance and Execution Analysis and Monitoring (PEAM)

### Python script
This repo comes with a few Python scripts which can dump program statistics into CSV format for analysis.

#### Per-thread per-region

On a trace that had 32 threads:

    python3 python/per_thread_per_region.py /tmp/ompt-jacobi/ 32 > per-region.csv

To run event processing in parallel, use the `-j <NUM_PROCESSES>` flag:

    python3 python/per_thread_per_region.py -j 8 /tmp/ompt-jacobi/ 32 > per-region.csv

#### Whole-program per-thread

On a trace that had 32 threads:

    python3 python/per_thread.py /tmp/ompt-jacobi/ 32 > per-thread.csv

To run event processing in parallel, use the `-j <NUM_PROCESSES>` flag:

    python3 python/per_thread.py -j 8 /tmp/ompt-jacobi/ 32 > per-region.csv

### Eclipse Trace Compass and Data-Driven Analysis
Eclipse Trace Compass can be used to view, analyze and visualize the PInsight traces. See below the screen shot for LULESH tracing and visualization with Tracecompass.
The visualization was created in Trace Compass using [Data driven analysis](
 http://archive.eclipse.org/tracecompass/doc/stable/org.eclipse.tracecompass.doc.user/Data-driven-analysis.html#Data_driven_analysis). To generate visualizations like this yourself, look at the `tracecompass/` folder in this repository.

 ![Lulesh tracing and visualization with Tracecompass](docs/OMPT_LTTng_TraceCompass.png). 

-------------------------------------

### Analyses considered

 1. Overhead analysis.
 1. Load balancing analysis.
 1. Offline analysis for configuring power usage and frequency (perhaps binary-based?).

### For enabling callstack based tracing and flamegraph
 1. https://archive.eclipse.org/tracecompass/doc/stable/org.eclipse.tracecompass.doc.user/LTTng-UST-Analyses.html
