# Codex command-rules review archive

## Current repository status — 2026-10-20

The file-to-directory migration described below was completed in commit
`5a437243c0c4c04d1a408416f03fc76c96e43488`: the empty `.codex` file was
replaced by `.codex/rules/a1-ouinp.rules`. That project file is the maintained
repository policy. It now also includes the job-preparation, lifecycle,
result-retrieval, and Git-inspection rules absent from the original proposal.

The `*.proposed` files in this directory preserve the earlier review candidates;
they are not synchronized copies of the current policy and should not replace it.
`default.rules.original` remains the unchanged 2026-10-09 user-rule snapshot.
The user-level installed configuration was not re-audited during this cleanup.

The audit and migration procedure below are historical context, not outstanding
instructions to repeat the migration. Other-repository suggestions in
`REMAINING_RULES_PLAN.md` still require a separate review when relevant.

## Scope

This directory is a review workspace only. Codex does not load rules from this
location, and no file here changes the active user configuration.

Files:

- `default.rules.original`: exact 2026-10-09 snapshot of
  `~/.codex/rules/default.rules`;
- `default.rules.proposed`: historical user-level candidate for all local Codex
  sessions using this Codex home;
- `a1-ouinp.rules.proposed`: historical project-level candidate, predating
  the additional rules now in `.codex/rules/a1-ouinp.rules`;
- `REMAINING_RULES_PLAN.md`: future disposition of omitted A1 and other-repo
  rules;
- this audit and migration note.

The original and snapshot SHA256 values were both:

```text
9279ae8a1dd297b76b00c6ac7ccf1f6313d1505ef58d79be521a83c264354718
```

The snapshot contains local usernames and absolute paths but no credential,
token, private-key path, or password.

## Audit summary

The original file has 75 rules. It is an accumulated approval history rather
than a deliberate persistent policy:

- 31 rules permanently allow individual `rm` commands;
- 21 rules concern HPC-Codex;
- 14 of those repeat `hpc-code-update` for individual commits;
- 12 rules concern Git, mostly fragmented `git add` commands;
- the remainder mixes unrelated repositories, downloads, package installation,
  test execution, temporary directories, and one-off diagnostics.

Important findings:

1. One-off deletion rules should not remain globally allowed after the task
   that created them. A prefix rule can also match extra trailing arguments.
2. `pip install`, `curl`, `git clone`, arbitrary Python tests, and shell-wrapped
   notebook execution can modify environments, access the network, or execute
   project code. They should require task-specific approval.
3. Rules for `pytorch_test`, `cell_tuning`, `osc_rate_shift`, and other projects
   do not belong in a global A1-OUinp/HPC policy. Persistent project rules should
   live in each trusted project's `.codex/rules/` layer when genuinely needed.
4. Fourteen exact-commit `hpc-code-update` rules are redundant. The protected
   helper already fixes the checkout, branch, remote, fast-forward policy, and
   full-hash validation, so one executable-level rule expresses the intended
   capability.
5. Most rules have no justification or match examples, making later review
   unnecessarily difficult.

`~/.codex/rules/matlab.rules` is already separated and structured. It was not
copied or changed. Its justification says "Prompt" while its decision is
`allow`; that wording should be corrected separately if `allow` is intended.

## Proposed user-level policy

`default.rules.proposed` contains no active rule. No command from the accumulated
history was sufficiently universal to keep as an automatic permission in every
repository.

All one-off removal, download, installation, test, and analysis commands are
omitted. Codex can still request approval when a task needs one; such approvals
should normally be for one invocation rather than persisted globally.

## Proposed A1-OUinp policy

`a1-ouinp.rules.proposed` contains capabilities specific to this repository:

- local `git add` and `git commit`;
- the existing `git push origin codex-hpc` permission;
- fixed protected HPC-Codex inspection, preview, update, submission, status,
  and incremental-log operations.

The executable-only HPC patterns intentionally allow varying arguments. This
is acceptable only because the root-owned helpers reject unsupported commands,
identifiers, paths, resource requests, and extra arguments themselves.

The fourteen commit-specific update entries are replaced by one
`hpc-code-update` entry. The helper remains responsible for requiring a full
commit, the fixed remote and branch, a clean checkout, fast-forward ancestry,
and the active-run lock.

## Historical `.codex` path conflict — resolved

At the time of the original review, this repository tracked `.codex` as a
zero-byte regular file. It was
added in commit `8f03c8a27e5a5c4c3fd2a49c216812027250722f`; the repository contains
no explanation or consumer for it.

Current Codex project layers require a directory layout:

```text
<repo>/.codex/
  rules/
    a1-ouinp.rules
```

The file and directory could not coexist. The proposal therefore required a
reviewed Git change replacing the empty file with the directory and rule file.
That replacement is complete, as recorded above.

The originally proposed migration was:

```text
delete tracked empty file: .codex
add tracked file:          .codex/rules/a1-ouinp.rules
```

Do not perform this migration merely as a filesystem copy. It should be a
normal reviewed repository change so the structural replacement and project
policy travel together in one commit. Codex will load the project layer only
after the repository is trusted and Codex is restarted.

If the empty `.codex` file must be retained for an unknown legacy reason, the
fallback is `~/.codex/rules/a1-ouinp.rules`. That fallback is user-level despite
its name: its `git add`, `git commit`, and push prefixes would apply in other
repositories too. It is therefore not the recommended final arrangement.

## Retained push behavior

The requested push permission remains exactly this prefix:

```text
git push origin codex-hpc
```

It does not match `git push origin main` or a different remote. Because Codex
rules match prefixes, it does match a command with extra trailing arguments,
including another refspec. This limitation is accepted for now; the proposal
does not add a protected push helper or GitHub-side identity restriction.

Codex should continue to issue the simple four-argument command only. Before a
push, it should verify the current branch, review the diff and commit, and
confirm that the remote update is a normal non-force push.

## Historical manual migration procedure

This checklist records the original proposal. Do not replay it over the current
project policy. The original procedure, after review, was:

1. keep an independent backup of the active user rules;
2. test both proposed files together with `codex execpolicy check`;
3. manually replace `~/.codex/rules/default.rules` with
   `default.rules.proposed`;
4. review and commit the structural replacement of the tracked empty `.codex`
   file with `.codex/rules/a1-ouinp.rules` containing the proposed A1 policy;
5. confirm that the project `.codex` layer is trusted;
6. restart Codex;
7. verify allowed A1-OUinp operations and ordinary approval for an omitted
   one-off command.

Future persistent rules should include a justification and represent a stable
capability, not one completed command.

The remaining original rules are organized for later repository-by-repository
review in `REMAINING_RULES_PLAN.md`; they have not been silently discarded or
activated elsewhere.

## Cleanup validation — 2026-10-20

The maintained project file was checked with the installed `codex execpolicy
check`, following the [official rules documentation](https://learn.chatgpt.com/docs/agent-configuration/rules).
Examples cover Git inspection, the existing branch push, and the three added
HPC helpers; pushes to another branch and `git reset --hard` do not match an
allow rule in this project file. These checks inspect decisions without
executing the example commands.

The original user-rule snapshot hash still matches the value above. Cleanup
changed historical labels and status notes, not the proposal's effective rules
or installed user configuration. The local watcher remains a discussion draft;
this commit does not implement or install it.
