# Code-update quarantine promotion

This is an optional recovery mode for `hpc-code-update`, not a general Git
stash. Codex prepares and tests the candidate; the user reviews and promotes
the scripts into the protected locations. Do not run candidate helpers from
`helper_src` against the real checkout before promotion.

The ordinary update still requires a clean checkout. With
`--quarantine-generated`, the lethe helper accepts only bounded, untracked,
single-link regular files below `exp_results/<experiment>/...`. It rejects
tracked edits, files outside that root, symlinks, and more than 128 files.
Before touching those files, it fetches the fixed branch and verifies the
requested exact fast-forward commit. It records each file in a private
quarantine directory, moves it aside, fast-forwards, then restores it only if
the new commit ignores that path. A conflict leaves the file and an active
recovery marker in protected state; all further updates stop for manual
review. No `git stash`, reset, force update, or arbitrary path argument is
used. This mode does not make a missing `.gitignore` rule safe: add the exact
rule to the target commit first.

## Update the clean automation checkout

The checkout was confirmed clean before this promotion. After pushing the
final commit, use the already installed A2 updater to move it to that exact
commit. Run locally as your ordinary user:

```bash
CQ_COMMIT='<full 40-character commit>'
/opt/a1-hpc/bin/hpc-code-status --json
/opt/a1-hpc/bin/hpc-code-update --json "$CQ_COMMIT"
/opt/a1-hpc/bin/hpc-code-status --json
```

The final status must report `clean: true`, `active_run: false`, and the exact
commit. Stop if any check fails; do not use the new quarantine flag to
bootstrap its own promotion.

## Local promotion

After reviewing the commit and the local promotion script, run on the local
machine under sudo. Replace the placeholder with the exact full commit that
contains this implementation:

```bash
CQ_COMMIT='<full 40-character commit>'
CQ_REPO=/home/nnovikov/repo/A1-OUinp
sudo bash "$CQ_REPO/dev_scratch/hpc/helper_src/promotion/promote_code_quarantine_local.sh" "$CQ_COMMIT"
```

The script prints `CQ_LOCAL_RESULT` and a report path under `/tmp`. It
verifies source hashes, installs `hpc-code-update`, `hpc_common.py`, and the
remote code-configuration schema, then restores the protected directories to
mode `0555`. It does not change local audit-state permissions.

## Lethe promotion

After the A2 update succeeds, log in to lethe and run the script from the
updated automation checkout as `niknovikov19` (no sudo):

```bash
CQ_COMMIT='<same full 40-character commit>'
CQ_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
bash "$CQ_REPO/dev_scratch/hpc/helper_src/promotion/promote_code_quarantine_lethe.sh" "$CQ_COMMIT"
```

The script requires the exact commit, branch, and clean checkout. It verifies
hard-coded source hashes, installs the helper and config, creates
`state/A1_OUinp/code-quarantine` with mode `0700`, and restores the protected
`helpers/lethe` and `config` directories to mode `0555`. It prints
`CQ_REMOTE_RESULT` and a report path beneath
`state/A1_OUinp/reports/promotion`. The installed remote config contains no
credentials or repository URL. Do not manually edit the promoted config to
choose a different generated-output root.

If the checkout becomes dirty before the A2 update, stop and inspect the
changes. That would require a separate bootstrap procedure; these promotion
scripts deliberately do not stash or discard them.

## Protected test and recovery

After both reports say `PASS`, inspect status. The current commit is already
installed, so a quarantine update to that same commit would be a no-op and
would not test the new mode. For a later commit, use the optional flag only
if **every** checkout change is an eligible untracked `exp_results` file and
the later target commit ignores every such path:

```bash
NEXT_COMMIT='<later full 40-character commit>'
/opt/a1-hpc/bin/hpc-code-status --json
/opt/a1-hpc/bin/hpc-code-update --json --quarantine-generated "$NEXT_COMMIT"
/opt/a1-hpc/bin/hpc-code-status --json
```

For a clean checkout, use the ordinary command without the flag. If the
updater reports `quarantine-needs-review`, do not rerun it or remove
`active.json`. Read the reported `manifest.json`, inspect the retained files
under the same operation's `items/`, and decide explicitly how to reconcile
them with the new commit. The mode never silently discards a file.
