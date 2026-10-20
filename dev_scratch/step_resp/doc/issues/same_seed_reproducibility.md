# Known issue: same seed does not reproduce the same activity

**Fix explicitly deferred by the user.** This page records a limitation,
not a request to change the model, edit companion repositories, or rerun data.

Nominally identical zero-input trials with the same seed produce different
raw rate traces. Treatment/control traces also differ before step onset.
This was first checked in the small preliminary connected experiment and
remains visible in the five-seed experiment's
[validation record](../../data/l2_connected_steps_5seeds_15_30pa_100s/analysis/validation.json).
Saved current waveforms, clamp counts, and spike-count arithmetic pass checks.

A likely contributor is process-dependent ordering of frozen populations in
the companion subnet builder (`list(set(...))`). Different order can change
cell IDs and therefore random streams despite equal numeric seeds. This is
an evidenced hypothesis, not a confirmed sole cause.

Consequences for existing results: same-seed subtraction is not a demonstrated
noise-cancelling comparison. The analysis retains both control-subtracted
response definitions, individual seeds, and control variation. This does not
by itself invalidate the earlier multi-seed J/Q identifications, which had no
same-seed repeat check within each batch.

The [evidence log](../archive/same_seed_reproducibility_evidence.md) contains
the original measurements, construction-order observations, and previously
proposed verification. Those verification steps remain deferred. Baseline rx,
surrogates, and current corrections remain unchanged.
