# Repair the output-list mismatch and recover the locked pilot

Status: local and lethe installation passed for commit `ad2805c`. Live recovery,
result inventory, repeated finalization/release, and checkout unlock passed on
October 20, 2026. No simulations were rerun.

## What changes?

The required files are the union of the request's `completion_files` and the
simulation outputs in the validated `jobs/index.jsonl`. The lethe helper checks
those exact paths on disk. Additional files are allowed; it does not scan the
result directory. The combined list retains the existing 256-file limit.

New batch final records save this list as `completion_files_required`. The
functions that write and validate them use the same completion rule. Old records
remain readable. An old failed batch may remain failed and still be released;
the validator must not infer success merely because its missing reason was not
stored. Single-job records keep their current format.

For the specific old list-mismatch pattern, `hpc-job finalize` preserves the
original final record and a replacement in two recovery files:

- Protected state: `finals/<run-id>.output-recovery.json`.
- Run directory: `hpc_jobs/runs/<run-id>/final-output-recovery.json`.

The helper rechecks the jobs and named files before creating the replacement.
If an output is missing, the replacement remains failed. It can resume after
an interruption between replacement of the two final copies. The original
request and scientific files are unchanged.

Finalization and release now require the main and every recorded simulation
job to have ended. A running job or unknown accounting state blocks them.
This patch retains the existing main-state/file-existence completion policy;
it does not add scientific file-format validation or a complete upfront plan.
Result inventories and compact archives can include verified simulation files
that the request did not repeat. Compact archives retain their existing directory
profile and omit rasters/raw data that do not match that profile.

## Install the reviewed code

These steps document the completed installation. The run is now released;
the installer deliberately requires the former active-run state, so do not rerun
this recovery-specific installation after release.

The [promotion rule](README.md#promotion-rule) requires the user to install
protected copies. Codex must not execute candidate helpers as replacements or
patch installed copies. These are manual installation steps, not commands that
Codex has already run.

The installer accepts only the pinned old or new hashes, checks every source
before writing, restores old code on an ordinary installation error, and restores
read-only directory permissions. A process or machine crash during installation
still requires inspection/repeating installation before using the helpers.

### On the local computer

Set the full commit hash reported by Codex, then run:

```bash
RECOVERY_COMMIT='ad2805cf57e81e868ef85f41949ed975f89e2e5c'
sudo /usr/bin/python3 \
  /home/nnovikov/repo/A1-OUinp/dev_scratch/hpc/helper_src/promotion/promote_completion_recovery.py \
  local "$RECOVERY_COMMIT"
```

This changes only installed `hpc_job_lifecycle.py` and `hpc_archive.py`.

### On lethe, as `niknovikov19`, without sudo

The active lock prevents checkout updates. Fetch the commit and export the
installer from Git without checking it out:

```bash
RECOVERY_COMMIT='ad2805cf57e81e868ef85f41949ed975f89e2e5c'
RECOVERY_REPO=/ddn/niknovikov19/repo/A1_OUinp_codex
RECOVERY_SCRIPT=$(mktemp /tmp/promote-completion-recovery.XXXXXX.py)

git -C "$RECOVERY_REPO" fetch --no-tags origin codex-hpc
git -C "$RECOVERY_REPO" show \
  "$RECOVERY_COMMIT:dev_scratch/hpc/helper_src/promotion/promote_completion_recovery.py" \
  > "$RECOVERY_SCRIPT"
/ddn/niknovikov19/miniconda3/bin/python3 \
  "$RECOVERY_SCRIPT" lethe "$RECOVERY_COMMIT"
rm -f "$RECOVERY_SCRIPT"
```

The installer checks that the checkout remains at `a1d5bb2`, that the active run
is `thal-irem-fade-pilot-20261020b`, and that main 118799 and children 118800–118803
all completed with exit code `0:0`. It holds the existing update/job locks while
installing. It changes these files only:

- Lethe helpers: `hpc-lethe-job`, `hpc_job_lifecycle.py`, `hpc_job_control.py`,
  and `hpc_archive.py`.
- Grid helpers: `hpc_job_lifecycle.py` and `hpc_job_control.py`.

Both installations must print `COMPLETION_RECOVERY_INSTALL=PASS` with the
appropriate site. The output includes installed hashes. Return both outputs
to Codex before proceeding.

## Live acceptance results

After both installations, Codex used the installed commands:

1. `hpc-job --json finalize thal-irem-fade-pilot-20261020b` returned `recovered`,
   `complete`, four simulation IDs, and nine verified files.
2. Repeating finalization returned `existing` with the same complete result.
3. `hpc-result --json inventory thal-irem-fade-pilot-20261020b` listed all eight
   simulation outputs: four result JSONs and four rasters.
4. `hpc-job --json release thal-irem-fade-pilot-20261020b` returned `released`;
   repeating it returned `existing` with the same release timestamp.
5. `hpc-code-status --json` confirmed `active_run: false`, no update lock, and a
   clean checkout at the original simulation commit `a1d5bb2`.

The original failure was preserved by the recovery operation. No scientific
payloads were downloaded and the checkout was not updated. Full command responses
are saved in [live_acceptance.json](../list_mismatch_recovery/live_acceptance.json).
