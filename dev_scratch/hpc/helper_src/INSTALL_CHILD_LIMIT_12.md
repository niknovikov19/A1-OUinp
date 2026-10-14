# Twelve-child batch ceiling

The first connected L2 h-step test has two seeds, three groups, and two
amplitudes, giving twelve simulation children. This promotion raises only
`max_child_jobs` from 10 to 12 in the local and Lethe preparation policies.
Concurrency remains five; per-child resources remain 30 cores and 128 GB.

The repository request validator also increases its bounded completion-file
limit from 32 to 64, allowing this request's 49 files (four per child plus the
job index). Lethe and grid keep protected copies of this request contract;
the remote promotion installs the reviewed `hpc_job.py` on both sites.

The scripts accept the previous or already-promoted policy hashes, bind to
the exact reviewed commit, and verify the installed policy and request
contract directly. Scientific configuration is not installed by promotion.

Run from the exact commit reported by Codex:

```bash
HPC12_COMMIT='<full 40-character commit>'
sudo bash dev_scratch/hpc/helper_src/promotion/promote_child_limit_12_local.sh \
    "$HPC12_COMMIT"
ssh lethe bash -s -- "$HPC12_COMMIT" \
    < dev_scratch/hpc/helper_src/promotion/promote_child_limit_12_lethe.sh
```

Both reports must end in `HPC_CHILD_LIMIT_RESULT=PASS`. Promotion is performed
by the user under the established Gate-B procedure; Codex can then prepare,
submit, monitor, and finalize the reviewed twelve-child test request.
