# Five-job concurrency ceiling

This promotion raises only the protected concurrent-job ceiling from four to
five. Child-count, per-job cores and memory, node count, wall time, and allowed
partitions remain unchanged.

Run the reviewed scripts from the exact commit reported by Codex:

```bash
HPC5_COMMIT='<full 40-character commit>'
sudo bash dev_scratch/hpc/helper_src/promotion/promote_concurrency_5_local.sh \
    "$HPC5_COMMIT"
ssh lethe bash -s -- "$HPC5_COMMIT" \
    < dev_scratch/hpc/helper_src/promotion/promote_concurrency_5_lethe.sh
```

Both reports must end in `HPC_CONCURRENCY_RESULT=PASS`.
