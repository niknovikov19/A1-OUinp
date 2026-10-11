# B2 child-aware observation promotion

Run 005 recorded simulation jobs `117836` and `117837`, but the installed
`hpc-job status` and `hpc-job log` commands exposed only the BatchTools main
job. BatchTools continued to display both failed simulations as running and
kept its main allocation alive until explicit cancellation.

This narrow promotion adds read-only child observation. It does not submit or
cancel jobs and does not change scheduler policy:

- `hpc-job status RUN_ID` queries the recorded main ID and all recorded child
  IDs together through `hpc-grid-status`;
- `hpc-job log RUN_ID --child CHILD_KEY` reads bounded incremental stdout and
  stderr only from paths already validated in `jobs/index.jsonl`;
- controller and per-child log cursors remain separate in protected local
  state.

After Codex reports the exact commit, run locally under `sudo`:

```bash
sudo bash \
  dev_scratch/hpc/helper_src/promotion/promote_b2_observe_local.sh \
  '<full 40-character commit>'
```

Update the automation checkout to the same commit with the approved A2 helper.
Then run on lethe without `sudo`:

```bash
bash \
  dev_scratch/hpc/helper_src/promotion/promote_b2_observe_lethe.sh \
  '<same full 40-character commit>'
```

Both reports must end in `B2_OBSERVE_RESULT=PASS`. Codex can then inspect the
preserved run 005 child states and logs through the promoted commands. A later
mutation-focused change will add a protected cancellation operation; it is not
bundled into this read-only correction.
