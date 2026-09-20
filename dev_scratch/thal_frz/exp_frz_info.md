# Freezing summary

Scope: first cfg file from each immediate experiment folder, excluding folder names containing `a1`, `L2`, or `ctx` (22 folders included). The JSON field is `conns_frozen` (plural).

`X → Y` means every `[pre, post]` pair in `X × Y`. Population groups are treated as sets; source-list order is omitted.

## Population groups

- `C = [TC, HTC, TI, IRE]`
- `M = [TCM, TIM, IREM]`
- `A = C + M = [TC, HTC, TI, IRE, TCM, TIM, IREM]`
- `E = [TC, HTC, TCM]`
- `I = [TI, TIM]`
- `RE = [IRE, IREM]`
- `CE = [IT2, IT3, ITP4, ITS4, IT5A, IT5B, IT6, CT5A, CT5B, CT6, PT5B]`

## Experiments

Names omit the common `exp_` prefix and parameter suffix beginning with `_nseed_`.

| Experiment | `pops_active` | `conns_frozen` | Count |
|---|---|---|---:|
| `core_full` | `C` | `[]` | 0 |
| `irem_core_0` | `A` | `IREM → C` | 4 |
| `irem_ire_0` | `A` | `IREM → IRE` | 1 |
| `irem_tc_0` | `A` | `IREM → [TC, HTC]` | 2 |
| `irem_ti_0` | `A` | `IREM → TI` | 1 |
| `matx_core_0` | `A` | `M → C` | 12 |
| `matx_full` | `M` | `[]` | 0 |
| `matx_ti_0` | `A` | `M → TI` | 3 |
| `thal_all_fade` | `A` | `[]` | 0 |
| `thal_ee_0_ire_tc_0` | `A` | `(CE + E) → (CE + E)`; `RE → E` | 202 |
| `thal_ee_0` | `A` | `(CE + E) → (CE + E)` | 196 |
| `thal_ee_1` | `A` | `[]` | 0 |
| `thal_ire_tc_0` | `A` | `RE → E` | 6 |
| `thal_pe_0` | `A` | `A → E` | 21 |
| `thal_pti_0` | `A` | `A → I` | 14 |
| `thal_tc_ti_0` | `A` | `E → I` | 6 |
| `thal_tc_ti_fade` | `A` | `[]` | 0 |
| `thal_ti_tc_0` | `A` | `I → E` | 6 |
| `thal_ti_tc_fade` | `A` | `[]` | 0 |
| `thal_unconn` (`nseed=15`) | `A` | `"all"` | all |
| `thal_unconn` (`nseed=5`) | `A` | `"all"` | all |
| `tim_core_0` | `A` | `TIM → C` | 4 |
