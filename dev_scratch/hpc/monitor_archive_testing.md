# Monitoring/archive capability acceptance test

Status: offline tests pass; live acceptance is waiting for the user's Gate-B
promotion. The experiment remains paused while these capabilities are tested.
See [installation and commands](helper_src/INSTALL_MONITOR_ARCHIVE.md).

## Baseline before promotion

- Installed local bundle: `0.15.0-cancel-tree`; `hpc-job logs` and
  `hpc-result archive` are correctly absent from this older installation.
- Automation checkout: clean on `codex-hpc`, commit
  `e6e6c8116eb810e0565f2302e397f5fb71c1fb86`, no active run or update lock.
- Existing test run: `hstep-l2-long-pilot-001`, controller 118074, twelve
  children. The installed old status helper reports all thirteen completed.
- Existing local reference: `../step_resp/data/l2_hstep_pilot2/input/`, 49
  compact files totaling 23,958,898 bytes. The reference manifest records
  original HPC paths and source/local SHA256 hashes.
- Rule changes, paper files, and unrelated step-response analysis changes
  are excluded from the helper promotion commit.

## Offline checks

The 114 HPC tests cover chunk boundaries, explicit failures/unknown records,
bounded output and timeouts, independent log-page cursors, a 241-file archive,
safe extraction, checksum failures, cache reuse, and preservation of modified
files. Shell promotion scripts pass syntax checks; all fifteen runtime/policy
source hashes match the promotion manifest.

## Protected live tests after both promotions pass

1. Check installed local and remote identities against the pinned hashes;
   confirm the new CLI commands exist and no run is active.
2. Query the completed pilot: require one controller and twelve children,
   each still completed and bound to the original simulation commit.
   Its thirteen IDs fit one accounting chunk. Over-25-ID chunking is tested
   synthetically; do not claim a live multi-chunk test from this small run.
3. Retrieve log pages at offsets 0, 5, and 10. Require 5/5/2 children,
   next offsets 5/10/null, unique coverage, bounded streams, and no scheduler
   queries in log retrieval. Repeat a page and verify that unchanged stream
   identities continue from the preceding end offsets. A nonempty repeat is
   valid if an earlier response reported a backlog; it must not repeat the
   consumed prefix.
4. Run `hpc-result archive hstep-l2-long-pilot-001 --unpack`. Require one
   downloaded archive, 49 compact source members plus its embedded manifest,
   successful bundle/member checksums, and the fixed local cache destination.
5. Compare every unpacked compact file with the existing local reference by
   SHA256 and size. Map archived `jobs/index.jsonl` to reference
   `jobs_index.jsonl`. Record actual compressed bytes and elapsed command time.
6. Repeat archive/unpack: require `cache-hit`, the same metadata and checksums,
   and no repeated binary download or remote source repacking. Keep both the
   reference data and the new cache intact.

All live calls must use protected installed helpers, not candidate scripts.
No new simulation jobs or changed scientific parameters are needed. Record
any failures and fix/re-promote the candidate before resuming the experiment.
