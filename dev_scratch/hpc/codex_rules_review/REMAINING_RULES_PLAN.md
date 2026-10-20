# Remaining command-rules migration plan

## Status — 2026-10-20

The A1-OUinp repository migration is complete in commit `5a43724`.
The maintained project policy is `.codex/rules/a1-ouinp.rules` at the repository
root; `a1-ouinp.rules.proposed` is the historical baseline only. Installation
status of user-wide rules and rules for other repositories was not rechecked.
The remaining suggestions below are deferred review items, not authorized work.

## Goal

Do not discard potentially useful permissions merely because they do not
belong in the A1-OUinp policy. Migrate them deliberately, one repository at a
time, while retiring stale one-off approvals.

The original line numbers below refer to `default.rules.original`.

## Planned destinations

### A1-OUinp

Lines 2-3, 13, 15-17, 20, 22-24, 26, 28-30, 37, 40-41, and the Git/HPC rules
from line 44 onward were created while working on A1-OUinp.

Disposition:

- Git and HPC-Codex capabilities were collected in `a1-ouinp.rules.proposed`;
  the maintained repository policy is now `.codex/rules/a1-ouinp.rules`.
- Exact deletion commands do not move. They were approvals for completed
  cleanups, not durable capabilities.
- If cache cleanup becomes repetitive, implement one tracked cleanup command
  with fixed repository-relative targets and give that command a project rule.
- Environment installation and large analysis execution remain task-specific
  approvals.

### pytorch_test

Line 1 executes one exact notebook through `bash -lc` with a temporary
Matplotlib directory.

Later work:

1. Open `pytorch_test` as the active trusted repository.
2. Confirm that this notebook execution is still part of the normal workflow.
3. Prefer a small fixed project script or direct executable invocation over a
   persistent `bash -lc` rule.
4. Add a project-local rule only after checking its output paths and runtime.

### cell_tuning

Lines 5-6 download one upstream model file and write it into `cell_tuning`.

Do not copy these two raw rules. `curl` can accept extra output options, and
`dd` can accept another destination argument. If the operation is still
needed, replace it with a tracked import command that fixes the URL and
destination, validates a reviewed checksum, and fails if the destination is
unexpected. Network use should remain prompted unless imports become a stable
reviewed capability.

### osc_rate_shift

Line 10 appears to create `wm_paper` output directories in `osc_rate_shift`.
Lines 31-32 remove two Matplotlib cache directories there.

These normally need no persistent rules: directory creation inside the active
workspace should stay in the sandbox, and named cache deletion should be
approved only when required. Reassess them from an `osc_rate_shift` session
rather than migrating them automatically.

### resp_predictor

Line 11 appears to run `dev_scratch/eig_opt/opt_w_new.py` from
`resp_predictor` with the shared `pytorch2` interpreter.

If this remains a regular operation, audit its inputs, outputs, network use,
and resource cost, then add one exact project-local rule. Otherwise leave it as
a one-time approval.

### User-level MATLAB wrapper

`~/.codex/rules/matlab.rules` is already separate from `default.rules`. Keep it
user-level if the same protected wrapper is intentionally available across
repositories. Correct its justification: the current decision is `allow`, but
the text says "Prompt".

## Rules to retire rather than migrate

The following are not stable capabilities:

- lines 12, 14, 18-19, 21, 25, 27, 33-36, and 38: generated Matplotlib
  temporary-directory deletion;
- lines 23-24 and 37: deletion of exact analysis artifacts after a completed
  task;
- line 42: one exact read of an OpenAI skill file;
- line 43: one diagnostic read of the Codex binary.

Retain them only in the historical snapshot.

## Generic commands requiring a fresh decision

These rules are not tied safely enough to a repository:

| Original line | Command family | Later policy |
| --- | --- | --- |
| 4 | `pip install` into `netpyne` | Prompt per dependency change; prefer reviewed environment files. |
| 7 | `git clone --depth 1` | Prompt per clone or use a repository-specific bootstrap command. |
| 8 | `python -m unittest` | Normally run inside the sandbox; fix cache/output paths if it escapes. |
| 9 | `sort` | No persistent rule should be necessary. |
| 39 | `apply_patch` | No shell-command rule should be necessary for the editing tool. |

## Implementation order

1. Preserve the completed A1-OUinp repository migration and original snapshot;
   review the maintained rule file rather than reinstalling the old proposal.
2. Correct `matlab.rules` wording without changing its effective decision.
3. Audit `pytorch_test`, `cell_tuning`, `osc_rate_shift`, and `resp_predictor`
   only when work resumes in each repository.
4. Put durable permissions under each trusted repository's `.codex/rules/`
   directory. If a repository already has a `.codex` regular file, first review
   and commit its replacement with the directory. Keep the user-level default
   empty unless a capability is truly repository-independent.
5. Test every candidate with `codex execpolicy check` before installation.
6. Review user-level rules periodically and move new one-off approvals back to
   one-time prompts instead of keeping an approval history indefinitely.

No rule for another repository should be activated solely because it existed
in the old global file.
