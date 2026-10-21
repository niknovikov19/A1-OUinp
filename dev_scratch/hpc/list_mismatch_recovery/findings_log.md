# Findings and recovery progress

- The installed status command confirmed that main 118799 and simulations
  118800–118803 all completed with exit code `0:0` and no accounting gaps.
- The final-record builder checks whether simulation outputs were repeated in
  the request. Its validator omits that check, so it rejects the saved failure.
- Proposed immediate rule: required files are the union of request-listed files
  and outputs in validated submission records. Finalization checks those exact
  paths without scanning the result directory. Extra files do not cause failure.
- New batch final records will retain the required-file list so writing and
  validation can use the same rule. Old records remain readable. The existing
  malformed failure will be preserved before a narrowly scoped recheck.
- The helper-source README requires the user to promote protected programs.
  Candidate sources must not be executed as replacement remote helpers.

## Repair prepared and tested

- Added `get_required_completion_files()` to combine validated request and
  simulation paths, with the existing 256-file cap. The filesystem check visits
  those paths only; it does not scan directories or read scientific payloads.
- New batch final records retain `completion_files_required`. Their builder
  validates its own output using the same completion rule as later readers.
  Legacy failed batches remain failed and readable instead of becoming unreleasable.
- Added narrow recovery through the existing `finalize` operation. It archives
  the original and replacement final records in matching recovery files before
  atomically replacing either final copy. Repeating finalize resumes an interrupted
  replacement; released histories are not rewritten.
- Finalization/release check that every recorded Slurm allocation has ended.
  Missing accounting evidence remains unknown. Result inventories accept verified
  child outputs; compact archives now select from the combined required list.
- Prepared a hash-pinned manual installer for two local module files and six
  remote helper/module files. It checks this exact settled pilot, holds existing
  locks, preserves active records and checkout commit, and restores read-only
  directory permissions. The source README still requires manual promotion.
- The complete local HPC suite passed: **136 tests**, using
  `/home/nnovikov/conda_env/netpyne/bin/python -m unittest discover -s tests -p 'test_hpc*.py'`.
  System Python lacked `batchtk`; the project environment passed that test too.
- Tests cover all nine outputs, missing child files, extra files, request-subset
  inventories/archives, persisted legacy recovery, interruption between final
  writes, release idempotence, active/unknown children, symlink rejection, and
  pinned installation sources. Installation links, Python syntax, replacement
  hashes, and Git whitespace checks passed.
- Protected installation, live re-finalization, normal result inventory, and
  explicit release remain pending. No simulation was rerun or data file changed.

## Installed recovery — 2026-10-20

- The user reported successful local and lethe installation of commit
  `ad2805cf57e81e868ef85f41949ed975f89e2e5c`.
- Installed `hpc-job finalize` returned `recovered` and `run_status: complete`
  for `thal-irem-fade-pilot-20261020b`. It verified all nine required files and
  retained child IDs 118800–118803. The helper identified itself as
  `0.17.0-completion-recovery`, source SHA256
  `d86f49f25d52affe7d2f8c22df9c1b506e13f41627941a09af3eb0be4b834ff8`.
  Observation: `2026-10-21T00:39:14.107430+00:00` (October 20 locally).
- Repeating installed finalization returned `existing` with the same complete
  status and nine files. Normal installed result inventory succeeded and listed
  four result JSONs and four rasters. No scientific payloads were downloaded.
  Saved those command responses in `live_acceptance.json`.
- Installed release returned `released` at `2026-10-21T00:40:09.870608+00:00`
  (October 20 locally). Repeating release returned `existing` with the same
  timestamp. Installed checkout status then confirmed `active_run: false`,
  `update_lock_active: false`, and a clean checkout at the original `a1d5bb2`
  simulation commit. Normal updates are no longer blocked by this run.
- Live recovery and release are complete. No simulations were submitted or
  rerun, the checkout was not updated, and no scientific payloads were downloaded.
  The previously staged four pilot files remain separate from this recovery record.
