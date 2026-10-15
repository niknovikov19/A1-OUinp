# Temporary status-query limits

Promoted on 2026-10-14. The user reported PASS at
`/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion/hpc-status-limits-promotion.XcoupK.txt`.
Installed SHA256 was verified as
`28f59366c6c05c86c1fb7fbdc3be143293c27fde67c624ced54f66bf20deee7c`;
whole-tree status and finalization passed for the pending pilot.

The child-limit promotion permitted twelve children, but the independent
scheduler-status policy still permits eleven IDs per query. A connected
twelve-child batch needs thirteen IDs including its controller; this prevents
`hpc-job status` and `hpc-job finalize` from inspecting the entire job tree.

The large-batch refactor is postponed. This Gate-B promotion changes only two
values in `/ddn/niknovikov19/hpc_codex/config/A1_OUinp-status.json`, shared by
Lethe and grid:

- `scheduler.max_job_ids`: 100, including the controller.
- `scheduler.query_timeout_sec`: 30 seconds per scheduler command.

It accepts the previous eleven-ID policy, the superseded thirteen-ID pilot
policy, or the already-promoted policy. Exact complete-file hashes are
enforced. It does not alter helpers, the checkout, child/concurrency limits,
job resources, or active-run records. The protected configuration directory is
restored to mode 0555 and the installed file has mode 0444.

The raw scheduler output cap remains 128 KiB per stream and the job-helper
JSON cap remains 1 MiB. Submission remains twelve children with concurrency
five. Polling about once per minute is a monitoring convention, not a policy
field. Thousand-job support is deferred as described in the
[refactor plan](../../status_scaling_refactor_plan.md).

An active run is allowed because this changes only read-only query limits.
The script is self-contained and binds to the current HPC checkout commit;
there is no fetch or checkout update while the pilot remains active.

Run from the local repository:

```bash
ssh lethe bash -s -- 2431fe2a4faea65df7164748398c60baba3d6a26 \
  < dev_scratch/hpc/helper_src/promotion/promote_status_limits_lethe.sh
```

Return `HPC_STATUS_LIMIT_RESULT` and `HPC_STATUS_LIMIT_REPORT`. A local
promotion is unnecessary: these settings live only in the shared remote
policy. The script replaces the earlier thirteen-ID promotion; do not run
that superseded script.

The command's commit is the current HPC checkout commit, not a new promotion
source commit. The script transforms the hash-verified installed policy
directly and does not require new source files on HPC. After promotion passes,
verify the installed policy hash and use `hpc-job status` / `hpc-job finalize`
for the pending pilot. Those job helpers have outer deadlines allowing the
two scheduler commands; the older `hpc-status` wrapper has a 60-second outer
deadline and should not be used for this recovery.
