# Static response-prediction project

This directory develops a predictor of recurrent population-rate responses
from static open-loop transfer measurements. The directory name is retained
for continuity; dynamic step responses are not currently in scope.

- [`processing.md`](processing.md) is the short operational recipe for running
  a new sweep, extracting rates on HPC, and fitting locally.
- [`h_r_processing.md`](h_r_processing.md) describes the current-input fitter
  and its local input/output layout.
- [`inventory.md`](inventory.md) records the existing rate-sweep datasets,
  artifacts, and provenance caveats.
- [`resp_predictor_outline.md`](resp_predictor_outline.md) summarizes the
  relevant ideas found in the read-only `resp_predictor` repository.
- [`resp_predictor_reference/`](resp_predictor_reference) contains snapshots
  of its original description Markdown and notebook.
- [`code/`](code) contains the local h-r fitter and snapshots of the relevant
  historical Python analysis files.
- `data/` is the ignored local workspace for compact HPC inputs and fitted
  results; its layout and remote provenance are documented in
  [`h_r_processing.md`](h_r_processing.md).

The existing experiment measures static operating-point gains using a slow
presynaptic triangular rate sweep. Those gains are the required open-loop
linear-response measurement; no separate dynamic-response experiment is
currently planned.
