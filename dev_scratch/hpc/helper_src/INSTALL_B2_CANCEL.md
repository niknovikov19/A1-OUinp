# B2 protected cancellation and completion fallback

Run 006 proved that both simulation jobs can complete successfully while the
BatchTools main job remains stuck because its final file signal is missing.
This promotion adds a protected `hpc-job cancel RUN_ID` operation. The caller
provides no job ID or Slurm option: the helpers bind `scancel` to the recorded
active top-level job. It also promotes the repository-owned completion fallback
for the next attempt; BatchTools itself is not modified.

## Local promotion

Run from the local repository checkout under `sudo`, using the exact commit
reported by Codex:

```bash
sudo bash dev_scratch/hpc/helper_src/promotion/promote_b2_cancel_local.sh \
    '<full 40-character commit>'
```

The report must end in `B2_CANCEL_RESULT=PASS`.

## Lethe promotion while run 006 is active

The automation checkout remains pinned to the active run, so fetch the new
remote commit without checking it out and extract the reviewed promotion
script:

```bash
B2_CANCEL_COMMIT='<same full 40-character commit>'
B2_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
B2_SCRIPT=$(mktemp /tmp/promote-b2-cancel.XXXXXX.sh)

git -C "$B2_REPO" fetch --no-tags origin codex-hpc
test "$(git -C "$B2_REPO" rev-parse refs/remotes/origin/codex-hpc)" = \
    "$B2_CANCEL_COMMIT"
git -C "$B2_REPO" show \
    "$B2_CANCEL_COMMIT:dev_scratch/hpc/helper_src/promotion/promote_b2_cancel_lethe.sh" \
    > "$B2_SCRIPT"
chmod 0700 "$B2_SCRIPT"
bash "$B2_SCRIPT" "$B2_CANCEL_COMMIT"
rm -f "$B2_SCRIPT"
```

The report must end in `B2_CANCEL_RESULT=PASS`. Codex will then cancel run 006
through the protected command, finalize it from scheduler and output evidence,
release the checkout, and prepare a fresh completion-fallback verification.
