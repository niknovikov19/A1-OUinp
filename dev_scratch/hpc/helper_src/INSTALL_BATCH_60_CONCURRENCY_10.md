# Sixty-child batches with concurrency ten

Status: **installed** after both user-run Gate-B promotions passed. This
changes only two limits in each of the local
helper and remote preparation policies:

| Policy limit | Before | After |
| --- | ---: | ---: |
| Maximum simulation children per batch | 12 | 60 |
| Maximum concurrent simulation children | 5 | 10 |

Per-job ceilings remain 30 ranks, 128 GB, one node, and 1440 minutes. The
ordinary 2-core/16-GB controller is separate from the simulation-child cap.
At full utilization, ten such children plus the controller request 302 cores
and 1296 GB across allocations. No jobs are submitted by the promotion.

An individual tracked request must still explicitly select its job count and
concurrency. Historical requests are unchanged; the next planned 60-trial
experiment will request concurrency ten. Sixty children then require roughly
six waves rather than twelve. Based on the completed 100-s L2 pilot, allow
roughly 35–40 minutes once resources are available, with queue delays additional.
The data volume and total simulation work are unchanged by concurrency.

## Promotion

Once this revision is committed, pushed, and the idle automation checkout is
updated to the same commit, the user runs:

```bash
sudo bash dev_scratch/hpc/helper_src/promotion/promote_batch_60_concurrency_10_local.sh FULL_COMMIT

ssh lethe bash -s -- FULL_COMMIT \
  < dev_scratch/hpc/helper_src/promotion/promote_batch_60_concurrency_10_lethe.sh
```

Both reports must end with `HPC_BATCH_LIMITS_RESULT=PASS`. The policy-only
installer pins source/predecessor hashes, accepts an idempotent repeat, checks
the exact committed revision and branch, and verifies that no other policy
values change. Lethe must be idle and clean. Installation uses atomic file
replacement and restores mode 0444 for policy files and 0555 for their parent.

After PASS, verify local limits with the protected `hpc-helper-info` command.
The next real request's protected preparation must accept its 60-child count
and concurrency ten before submission. Do not run candidate helpers in place.
The fixture tests cover acceptance at 60/10, rejection at 61 children or
concurrency eleven, unchanged per-job ceilings, and rejection of unrelated
policy changes. The installed monitoring/archive capabilities already support
the 61 total scheduler IDs and 241 completion files of the proposed experiment.

All **118 HPC tests pass**, including the new policy-boundary and transition
checks. Both shell wrappers and the Python policy installer pass syntax checks.

## Installed verification

Promoted revision: `b6fbac9b0bb6e791d5c42ed79735c12720a500fc`.
The user reported both promotions PASS:

- Local report: `/tmp/batch-60-concurrency-10-local-promotion.pVzERh.txt`.
- Remote report: `/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion/batch-60-concurrency-10-remote-promotion.olYZmC.txt`.

The protected `hpc-helper-info --json info` command independently confirms
60 children and concurrency ten, with all four per-job resource ceilings
unchanged. The installed local policy raw SHA256 is
`546fae687acbd5269f94e6d946f24e665259fbc54eab39340a20c3d3ef8ac61b`;
the normalized configuration digest reported by the helper is
`e36ed233606ada4ca4ab9e2ba61dfde836c89e36936a90903ac29820b970a035`.
The remote promotion's PASS verifies the pinned preparation-policy SHA256
`b44abec6b2ba18ed7e0e1b3a594d80a2016614fe6182dc2401cf9bddb7fedb84`
and the same 60/10 limits. The automation checkout is clean and idle.
The next experiment request must explicitly select these values and pass
protected preparation before submission; historical requests are preserved.
