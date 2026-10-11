# B2 failed-finalization recovery

Run `b2-child-discovery-004` proved that Ray starts and returns away from
`node10`, but BatchTools rejected both child scripts before `sbatch` because
Python formatting interpreted `${LD_LIBRARY_PATH:+...}` as a template field.
Ray exited with status zero, so Slurm reported `COMPLETED` despite missing run
evidence. The original finalizer rejected that evidence mismatch and therefore
could not create the record required for release.

The recovery changes completed-job semantics: a terminal Slurm job with
missing declared evidence receives a durable `failed` final record. Scheduler
state remains `COMPLETED`; it is not rewritten. This allows explicit release
without pretending that the scientific run succeeded.

The active-run lock prevents the normal A2 checkout update. Fetching updates
only the remote-tracking Git reference and leaves the checked-out commit and
active run unchanged. After Codex reports the exact recovery commit, run on
lethe without `sudo`:

```bash
B2_FINALIZE_COMMIT='<full 40-character commit>'
B2_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B2_SCRIPT=$(mktemp /tmp/promote-b2-finalize-recovery.XXXXXX.sh)

git -C "$B2_REPO" fetch --no-tags origin codex-hpc
test "$(git -C "$B2_REPO" rev-parse refs/remotes/origin/codex-hpc)" = \
    "$B2_FINALIZE_COMMIT"
git -C "$B2_REPO" show \
    "$B2_FINALIZE_COMMIT:dev_scratch/hpc/helper_src/promotion/promote_b2_finalize_recovery_lethe.sh" \
    > "$B2_SCRIPT"
chmod 0700 "$B2_SCRIPT"
bash "$B2_SCRIPT" "$B2_FINALIZE_COMMIT"
rm -f "$B2_SCRIPT"
```

The report must end in `B2_FINALIZE_RECOVERY_RESULT=PASS`. Codex will then
finalize run 004 as failed, release it, update the checkout normally through
A2, and prepare fresh run `b2-child-discovery-005` with the corrected child
environment line.
