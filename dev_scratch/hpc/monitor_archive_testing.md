# Monitoring/archive capability acceptance test

Status: initial protected installation and core live checks passed. One
compatibility correction, found during acceptance, is fixed and awaiting remote
re-promotion. The experiment has not resumed while this gate remains open.
See [installation and commands](helper_src/INSTALL_MONITOR_ARCHIVE.md).

## Initial promotion and live results

Reviewed revision: `fe323427f6e0e6bf956e48e03c9dbfc5ac7fddeb`.
The user reported both promotions successful:

- Local: `/tmp/monitor-archive-local-promotion.W4WBug.txt`.
- Lethe: `/ddn/niknovikov19/hpc_codex/state/A1_OUinp/reports/promotion/monitor-archive-remote-promotion.9ohzdm.txt`.

Protected installed commands were tested against `hstep-l2-long-pilot-001`:

| Check | Result |
| --- | --- |
| Local installed bundle | `0.16.0-chunked-monitoring-archive`; installed source hashes match the reviewed initial manifest |
| Controller and children | All 13 completed; original simulation commit `ba7022adb012d4b0b3c67fa2c1ba1c51bdd8b3d2` retained |
| Log pages | Offsets 0/5/10 return 5/5/2 children, with next offsets 5/10/null and unique coverage |
| Log stream bounds | All returned streams within 8192 bytes and 40 lines |
| Repeated log page | All ten stream identities unchanged; each new start offset equals its preceding end offset |
| Archive and unpack | Downloaded successfully, 49 compact files plus embedded manifest |
| Reference comparison | All 49 file sizes, SHA256 hashes, and HPC source paths match the existing local handoff |
| Repeated archive/unpack | `cache-hit`, identical metadata and checksum; no second binary transfer or source repacking |
| Protected status parser self-test | 17 cases passed; grid helper hash matches the initial promoted source |

Source bytes: **23,958,898**. Compressed archive: **1,694,850 bytes**
(1.69 MB), about 14.1× smaller. First archive creation, transfer, checksum
verification, and unpacking took **11.09 s**, measured between the protected
local audit intent/completion timestamps. Original scientific data and the
previous local reference were preserved.

The archive is stored remotely at:

```text
/ddn/niknovikov19/hpc_codex/state/A1_OUinp/result-archives/hstep-l2-long-pilot-001.tar.gz
```

The verified local cache and extracted files are under:

```text
/home/nnovikov/repo/A1-OUinp/exp_results_local/hpc_codex/hstep-l2-long-pilot-001/
```

Archive SHA256:
`8ddf3f3df91d6f136bce2dd725ecce8db56dc0dfafcc8719844bb425735cab4d`.

## Compatibility correction found during acceptance

The legacy `hpc-status` path's Lethe validator still accepted only zero or one
`sacct` call in a grid reply. Grid-side chunking and the main `hpc-job status`
path worked, but the legacy path would reject successful multi-chunk replies.
The 13-job live pilot alone cannot expose this because it fits one 25-ID chunk.

A new integration regression passes actual fixture-generated grid replies
through the Lethe validator for 26 and 61 completed IDs. It reproduced the
failure before the fix. The validator now accepts nonnegative integer counts
up to `ceil(requested_IDs / accounting_chunk_size)` and rejects booleans,
negative values, and excessive counts. Only `hpc-lethe-status` runtime code
changes in this correction; local runtime files and the other installed
remote helpers are unchanged.

Its pinned SHA256 is
`2262c2d143e6a86bd76dbe1d55cf35857354257e78f9c89b5812a649fde73c50`.
All **115 HPC tests** pass with the correction, including the new multi-hop
chunk-count regression. Promotion hashes and whitespace checks also pass.
The promotion manifest accepts both the original predecessor and the initial
promoted hash. Reuse the remote Gate-B script with the corrective commit;
no repeat local promotion is necessary. After remote PASS, repeat the protected
status self-test and a completed-pilot status check before closing acceptance.

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
