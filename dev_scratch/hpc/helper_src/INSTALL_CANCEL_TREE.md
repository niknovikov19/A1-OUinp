# Protected controller-and-child cancellation

This promotion makes `hpc-job cancel RUN_ID` cancel the recorded BatchTools
children together with the controller. The caller still cannot provide Slurm
IDs or scheduler options. It also lets terminal runs with inconsistent child
output declarations finalize as failed so their checkout lock can be released.

The remote promotion supports an active run: it fetches the reviewed commit
without changing the checkout, verifies the existing helper identities, and
installs only the two job helpers and shared lifecycle module.

```bash
CANCEL_TREE_COMMIT='<full 40-character commit>'
sudo bash dev_scratch/hpc/helper_src/promotion/promote_cancel_tree_local.sh \
    "$CANCEL_TREE_COMMIT"
bash dev_scratch/hpc/helper_src/promotion/promote_cancel_tree_lethe.sh \
    "$CANCEL_TREE_COMMIT"
```

After both reports end in `CANCEL_TREE_RESULT=PASS`, run the normal protected
finalize/release operations for the terminal active run.
