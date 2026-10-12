# L2 simulation resource ceiling

This promotion raises the protected per-job ceiling from 2 to 30 cores and
from 16 to 128 GB RAM. Node, wall-time, child-count, concurrency, partition,
and all other limits remain unchanged.

Run the reviewed scripts from the exact commit reported by Codex:

```bash
L2_RESOURCES_COMMIT='<full 40-character commit>'
sudo bash dev_scratch/hpc/helper_src/promotion/promote_l2_resources_local.sh \
    "$L2_RESOURCES_COMMIT"
ssh lethe bash -s -- "$L2_RESOURCES_COMMIT" \
    < dev_scratch/hpc/helper_src/promotion/promote_l2_resources_lethe.sh
```

Both reports must end in `L2_RESOURCES_RESULT=PASS`.
