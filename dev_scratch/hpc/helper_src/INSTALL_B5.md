# B5 selective result-access promotion

B5 adds read-only inventory and retrieval for exact artifacts from completed
runs. It does not add a remote filesystem mount, arbitrary path access, or a
recursive result scan.

The first `inventory RUN_ID` call reads only protected lifecycle records and
the output paths declared in the validated child index. It stores the compact
inventory under protected state. Later inventory calls load that record rather
than scanning scientific results again.

## Promotion

After Codex reports the exact commit, run locally under `sudo`:

```bash
sudo bash \
  dev_scratch/hpc/helper_src/promotion/promote_b5_result_local.sh \
  '<full 40-character commit>'
```

Update the automation checkout to the same commit with `hpc-code-update`.
Then run on lethe without `sudo`:

```bash
bash \
  dev_scratch/hpc/helper_src/promotion/promote_b5_result_lethe.sh \
  '<same full 40-character commit>'
```

Both reports must end in `B5_RESULT=PASS`. The lethe report is stored beneath
`state/A1_OUinp/reports/promotion/`; the local report is stored in `/tmp`.

## Protected tests

List the B3 inventory:

```bash
/opt/a1-hpc/bin/hpc-result --json inventory b3-tiny-batch-003
```

Retrieve one exact result JSON:

```bash
/opt/a1-hpc/bin/hpc-result --json get \
  b3-tiny-batch-003 b3_tiny_batch_00003 result-json
```

Repeat the same command. The first successful call must report `downloaded`;
the second must report `cache-hit`. The cached file is beneath:

```text
/home/nnovikov/repo/A1-OUinp/exp_results_local/hpc_codex/b3-tiny-batch-003/
```

Negative tests use only public selectors and must reject before transfer:

```bash
/opt/a1-hpc/bin/hpc-result inventory '../bad'
/opt/a1-hpc/bin/hpc-result get b3-tiny-batch-003 '*' result-json
/opt/a1-hpc/bin/hpc-result get b3-tiny-batch-003 unknown result-json
/opt/a1-hpc/bin/hpc-result get b3-tiny-batch-003 b3_tiny_batch_00003 raster
```

The prototype transfer cap is 256 KiB. Larger known artifacts remain visible
in the inventory but cannot be retrieved by this operation.
