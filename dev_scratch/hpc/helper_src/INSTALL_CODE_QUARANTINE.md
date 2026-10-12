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

## Lethe promotion when the automation checkout is dirty

The old updater cannot move a dirty checkout to the new commit. Stage only
the two reviewed remote artifacts from the local commit directly on lethe;
do not stash or modify the automation checkout. The staging directory is
outside the repository. Run these commands locally as your ordinary user:

```bash
CQ_COMMIT='<same full 40-character commit>'
CQ_REPO=/home/nnovikov/repo/A1-OUinp
CQ_SRC="$CQ_REPO/dev_scratch/hpc/helper_src"
CQ_STAGE="/ddn/niknovikov19/hpc_codex/staging/code-quarantine/$CQ_COMMIT"
ssh lethe "mkdir -p '$CQ_STAGE' && chmod 0700 '$CQ_STAGE'"
scp "$CQ_SRC/remote_lethe/hpc-lethe-code" "lethe:$CQ_STAGE/hpc-lethe-code"
scp "$CQ_SRC/config_examples/remote-hpc-code.json.example" "lethe:$CQ_STAGE/remote-hpc-code.json.example"
scp "$CQ_SRC/promotion/promote_code_quarantine_lethe.sh" "lethe:$CQ_STAGE/promote_code_quarantine_lethe.sh"
```

The commit and paths above are literal deployment inputs, not inputs accepted
by the protected helper. Review the staged configuration and script, then run
this on lethe as `niknovikov19` (no sudo):

```bash
CQ_COMMIT='<same full 40-character commit>'
CQ_STAGE="/ddn/niknovikov19/hpc_codex/staging/code-quarantine/$CQ_COMMIT"
bash "$CQ_STAGE/promote_code_quarantine_lethe.sh" "$CQ_COMMIT"
```

The script verifies hard-coded source hashes, installs the helper and config,
creates `state/A1_OUinp/code-quarantine` with mode `0700`, and restores the
protected `helpers/lethe` and `config` directories to mode `0555`. It prints
`CQ_REMOTE_RESULT` and a report path beneath
`state/A1_OUinp/reports/promotion`. The installed remote config contains no
credentials or repository URL. Do not manually edit the promoted config to
choose a different generated-output root.

If the automation checkout is clean and already at this commit, the staging
copy is still acceptable; the source hashes, not checkout location, determine
what gets installed.

## Protected test and recovery

After both reports say `PASS`, inspect status and the actual dirty paths.
Use the optional flag only if **every** change is an eligible untracked
`exp_results` file and the target commit ignores every such path:

```bash
/opt/a1-hpc/bin/hpc-code-status --json
/opt/a1-hpc/bin/hpc-code-update --json --quarantine-generated "$CQ_COMMIT"
/opt/a1-hpc/bin/hpc-code-status --json
```

For a clean checkout, use the ordinary command without the flag. If the
updater reports `quarantine-needs-review`, do not rerun it or remove
`active.json`. Read the reported `manifest.json`, inspect the retained files
under the same operation's `items/`, and decide explicitly how to reconcile
them with the new commit. The mode never silently discards a file.
