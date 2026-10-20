# Supplementary raster collection

Copy one existing raster PNG per condition in the supplementary simulation inventory,
preferably seed 1000, into `evidence/rasters/`. Use short descriptive filenames and
record the original experiment/file, seed, protocol duration, summary window, size,
and checksum. Include cortex references, thalamic correction and freeze/fade
comparisons, the historical full-A1 control matrix and its static references, and
the exact main-paper A1 example used for the other-population proposal.

The excluded “without 50% E-E decrease” proposal remains excluded. E-E surrogate
reference conditions are different manipulations and remain relevant.

Read only selected raster images from the mounted results. Do not read spike
pickles, generate new rasters, or scan experiment trees recursively. Reuse locally
cached configuration metadata. Log missing images explicitly. Saved rasters are
copied unchanged; their plotted interval may differ from the rate-summary window.
Fading-conductance traces refer to the same simulations and need no extra raster.
