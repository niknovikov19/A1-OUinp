# `hpc_common.py` reference

## Purpose

`hpc_common.py` contains the local safety and bookkeeping primitives shared by
the protected HPC helper commands.

The module provides:

- fixed installation, configuration, audit-log, and request-registry locations;
- strict identifier and configuration validation;
- installed-source and configuration hashing;
- configuration redaction for display;
- bounded JSONL audit-log writes and reads;
- shared result codes and exception types.

It does not invoke SSH, Git, Slurm, subprocesses, or file-transfer programs. It is not a standalone command.

## Trust model

The repository copy is only a candidate source. Its checks become part of the safety boundary only after the user manually installs it in a protected directory such as `/opt/a1-hpc/bin/hpc_common.py`.

The module assumes:

- its installed source directory and configuration are not writable by Codex;
- `state/` exists and the helper process may append to its audit file;
- the configuration contains no credentials or private-key paths;
- later remote helpers independently enforce their own command and path restrictions.

Validation here is mainly lexical and structural. For example, an absolute path can be syntactically valid even if it does not exist. A later operation must still confirm that the path resolves inside its configured root and has the expected ownership and type.

## Installed layout

Paths are derived from the installed location of `hpc_common.py`; environment variables and caller-provided paths cannot redirect them.

For `/opt/a1-hpc/bin/hpc_common.py`, the functions resolve:

```text
get_install_root()  -> /opt/a1-hpc
get_config_path()   -> /opt/a1-hpc/config/hpc-helper.json
get_audit_path()    -> /opt/a1-hpc/state/actions.jsonl
get_request_catalog_path()
    -> /opt/a1-hpc/config/A1_OUinp-preview-requests.json
```

`Path(__file__).resolve()` is used before moving to the installation root.

## Versions and result codes

`BUNDLE_VERSION` identifies the helper implementation. `CONFIG_SCHEMA_VERSION` identifies the accepted protected-configuration format.

| Constant | Value | Meaning |
| --- | ---: | --- |
| `EXIT_SUCCESS` | 0 | The requested operation succeeded. |
| `EXIT_REJECTED` | 2 | Caller input was rejected locally. |
| `EXIT_UNKNOWN` | 3 | Remote state is unavailable or unknown; reserved for later gates. |
| `EXIT_FAILED` | 4 | A known helper or operation failure occurred. |

The module defines the constants but does not exit by itself. The command-line entry point maps exceptions and results to these codes.

## Exceptions

### `RejectedInput`

Raised when caller-controlled data or configuration structure violates an allowlist or format rule. No remote operation should occur after this exception.

Examples include a short Git hash, a job label containing `/`, an unknown configuration key, or a resource limit that is not a positive integer.

### `HelperFailure`

Raised for a known local operational problem rather than invalid caller input.

Examples include a missing protected configuration, a symlink where a regular protected file is required, unreadable JSON, or failure to append the audit log.

## Identifier validation

`validate_identifier(kind, value)` exposes four validator types through a fixed dispatch table.

| Kind | Rules |
| --- | --- |
| `run-id` | 1–80 ASCII letters, digits, `.`, `_`, or `-`; first character must be alphanumeric; `.` and `..` are rejected. |
| `git-commit` | Exactly 40 lowercase hexadecimal characters. Abbreviated and uppercase hashes are rejected. |
| `experiment-id` | One or more `/`-separated safe segments; each segment starts alphanumerically and is at most 64 characters; `.`, `..`, backslashes, empty segments, and unsafe punctuation are rejected; total length is at most 255. |
| `job-label` | 1–128 ASCII letters, digits, `.`, `_`, or `-`; first character must be alphanumeric; no path separators. |

The individual functions are `validate_run_id`, `validate_git_commit`, `validate_experiment_id`, and `validate_job_label`. Successful validation returns the original string unchanged.

`validate_request_id()` applies the same path-safe syntax as a run ID but
reports request-specific errors. Preview and submission use it before
selecting an entry from the fixed protected request registry.

These functions establish safe identifier syntax only. They do not prove that a commit exists, an experiment is present, or a job label belongs to a run.

## Configuration validation

`load_config()` reads only the fixed `config/hpc-helper.json` path. Before reading, it requires the path to be a real regular file rather than a symlink. Parsed JSON is passed to `validate_config()`.

`validate_config()` requires exactly these top-level keys:

```text
schema_version
deployment_id
ssh
git
remote_helpers
runs
scheduler
```

Unknown keys are rejected to make misspellings and unintended settings visible.

### `ssh`

Required keys:

- `lethe_host_alias` and `grid_host_alias`: safe names, not arbitrary SSH destinations or shell expressions;
- `grid_access_mode`: must be `through-lethe-helper` for the prototype;
- `connect_timeout_sec`: integer from 1 through 120.

The aliases are configuration data only in A0. This module never opens a connection.

### `git`

Required keys:

- `remote_name`: one safe Git remote name;
- `branch`: a restricted Git branch name;
- `automation_checkout`: normalized absolute POSIX path;
- `manual_checkout`: normalized absolute POSIX path.

The two checkout paths must differ. This check prevents the most direct configuration mistake but does not yet inspect either checkout.

### `remote_helpers`

`lethe_dir` and `grid_dir` must be normalized absolute POSIX paths. Later gates will use these as fixed remote-helper roots.

### `runs`

`root` must be a normalized absolute POSIX path. Later helpers will constrain run records and results beneath this root.

### `scheduler`

Required values are:

- safe `user` and optional empty `account` names;
- a non-empty, duplicate-free list of safe `allowed_partitions`;
- positive integer ceilings for child jobs, concurrent jobs, nodes, cores, memory, and wall time.

`max_concurrent_jobs` cannot exceed `max_child_jobs`.

The runtime validator is authoritative. `schemas/hpc-helper-config.schema.json` documents the same external structure, while the Python checks also enforce cross-field rules such as distinct checkout paths.

## File safety helper

`_require_regular_file()` uses `lstat()` and rejects symlinks and non-regular files. It is used for:

- the protected configuration;
- all seven installed runtime source files;
- the audit log when it already exists.

The audit file may be absent before its first append, but its parent directory must already exist and must be a real directory rather than a symlink.

## Deterministic hashing

### Installed source identity

`get_bundle_identity()` hashes the installed `hpc-code-status`,
`hpc-code-update`, `hpc-helper-info`, `hpc-probe`, `hpc-run-preview`,
`hpc-submit`, and `hpc_common.py` files. It returns:

```json
{
  "bundle_version": "0.5.0-a4",
  "bundle_sha256": "...",
  "source_sha256": {
    "hpc-code-status": "...",
    "hpc-code-update": "...",
    "hpc-helper-info": "...",
    "hpc-probe": "...",
    "hpc-run-preview": "...",
    "hpc-submit": "...",
    "hpc_common.py": "..."
  }
}
```

The bundle digest is built in the fixed `RUNTIME_SOURCE_NAMES` order. For each file it hashes the filename, a null separator, and the binary value of that file's SHA256 digest. Binding names as well as contents prevents two files from being silently exchanged.

### Configuration identity

`canonical_json()` serializes JSON with sorted keys and compact separators. `get_config_identity()` hashes that representation, so formatting and dictionary insertion order do not change the configuration digest.

## Configuration redaction

`redact_config()` recursively replaces values when their key contains one of:

```text
identity_file
password
private_key
secret
token
```

This is defense in depth for display output. Sensitive data should never be placed in the helper configuration in the first place, and the redactor should not be treated as a general secret detector.

## Audit logging

`append_audit_event()` writes one compact JSON object per line to the fixed audit path. Each event contains:

- schema version and UTC timestamp;
- helper name and helper version;
- action, status, and exit code;
- sanitized arguments;
- an optional bounded detail string.

Argument logging retains only fixed public command words from `PUBLIC_AUDIT_ARGS`. Other values are stored as `<value>`, preventing identifiers accidentally supplied in an inappropriate position from being copied verbatim into the audit log. At most 20 arguments are recorded, and details are capped at 500 characters.

Writes use append mode, a Linux file lock, one encoded JSON line, and `fsync()`. `O_CLOEXEC` and `O_NOFOLLOW` are enabled when the platform provides them. Failure to append raises `HelperFailure`; the command should then fail instead of performing an unaudited action.

The audit file is operational evidence, not a cryptographically tamper-proof ledger. In the prototype it is writable by the helper's WSL user while remaining outside the Codex filesystem sandbox.

## Bounded audit reads

`read_recent_audit_events()` reads at most 64 KiB from the end of the audit file and returns at most 20 decoded events by default. It never accepts a caller-provided path.

If reading begins in the middle of a large file, the first partial line is discarded. A missing audit file produces an empty list; invalid JSON or an I/O failure raises `HelperFailure`.

Because `hpc-helper-info audit-tail` reads before its own success event is appended, its output shows the preceding events rather than the current invocation.

## A0 call flow

```text
hpc-helper-info
    -> parse one fixed subcommand
    -> call hpc_common validation/hash/read function
    -> prepare result or classified error
    -> append mandatory audit event
    -> print result
    -> return shared exit code
```

For `info`, the internal flow is:

```text
fixed config path
    -> regular-file check
    -> JSON decode
    -> exact schema and cross-field validation
    -> canonical configuration hash
    -> display redaction
    -> source bundle identity
```

## Per-function reference

Functions beginning with `_` are internal implementation helpers. Later command scripts should normally use the public validation, loading, identity, redaction, and audit functions instead of calling internal pieces directly.

### `get_install_root()`

Derives the protected installation root from the installed location of `hpc_common.py`.

- Parameters: none.
- Returns: `Path(__file__).resolve().parent.parent`.
- Side effects: none.
- Security role: prevents callers and environment variables from selecting a different helper root.

### `get_config_path()`

Builds the only configuration path accepted by this module.

- Parameters: none.
- Returns: `<install root>/config/hpc-helper.json` as a `Path`.
- Side effects: none; it does not check or open the path.
- Security role: removes arbitrary configuration-path input from the command interface.

### `get_audit_path()`

Builds the only audit-log path accepted by this module.

- Parameters: none.
- Returns: `<install root>/state/actions.jsonl` as a `Path`.
- Side effects: none; it does not create or read the file.
- Security role: prevents callers from redirecting audit writes to another path.

### `get_request_catalog_path()`

Builds the only protected request-registry path accepted by the local helper.

- Parameters: none.
- Returns: `<install root>/config/A1_OUinp-preview-requests.json` as a `Path`.
- Side effects: none; it does not inspect or read the path.
- Security role: prevents callers from selecting a request file or directory.

### `_require_string(value, label)`

Checks the common minimum requirements for identifier strings.

- `value`: candidate value.
- `label`: human-readable field name used in an error.
- Returns: the unchanged string.
- Raises: `RejectedInput` when `value` is not a string, is empty, or contains a null byte.
- Side effects: none.

### `validate_run_id(value)`

Validates one path-safe run identifier.

- `value`: candidate run ID.
- Returns: the unchanged validated string.
- Raises: `RejectedInput` unless it is 1–80 allowed characters, starts alphanumerically, and is neither `.` nor `..`.
- Side effects: none.
- Security role: makes run IDs safe to use as one directory-name component; it does not resolve or create a directory.

### `validate_request_id(value)`

Validates one path-safe protected request identifier.

- `value`: candidate request ID.
- Returns: the unchanged validated string.
- Raises: `RejectedInput` unless it is 1–64 allowed characters, starts alphanumerically, and is neither `.` nor `..`.
- Side effects: none.
- Security role: permits selection by identifier without accepting a request-file path.

### `validate_git_commit(value)`

Validates one exact Git object identifier for deployment pinning.

- `value`: candidate commit hash.
- Returns: the unchanged validated hash.
- Raises: `RejectedInput` unless it contains exactly 40 lowercase hexadecimal characters.
- Side effects: none.
- Security role: excludes abbreviated, symbolic, uppercase, and shell-like revision expressions. It does not verify that the commit exists.

### `validate_experiment_id(value)`

Validates a repository-relative experiment identifier such as `group/experiment`.

- `value`: candidate experiment ID.
- Returns: the unchanged validated string.
- Raises: `RejectedInput` for values longer than 255 characters, backslashes, empty segments, `.` or `..` segments, unsafe characters, or segments longer than 64 characters.
- Side effects: none.
- Security role: permits hierarchical experiment names without permitting path traversal or absolute paths. A later helper must still resolve the ID beneath `exp_configs` and check existence.

### `validate_job_label(value)`

Validates one BatchTools/Slurm job label.

- `value`: candidate label.
- Returns: the unchanged validated string.
- Raises: `RejectedInput` unless the label is 1–128 safe characters, starts alphanumerically, and is neither `.` nor `..`.
- Side effects: none.
- Security role: makes a label safe as a metadata key or filename component; it does not establish membership in a run.

### `validate_identifier(kind, value)`

Dispatches public identifier validation through a fixed allowlist.

- `kind`: one of `run-id`, `git-commit`, `experiment-id`, or `job-label`.
- `value`: candidate identifier.
- Returns: the unchanged string returned by the selected validator.
- Raises: `RejectedInput` for an unsupported kind or invalid value.
- Side effects: none.
- Security role: prevents caller-selected function names or dynamic evaluation.

### `_require_mapping(value, label)`

Requires a JSON object represented as a Python dictionary.

- `value`: candidate configuration block.
- `label`: block name for errors.
- Returns: the same dictionary.
- Raises: `RejectedInput` when `value` is not a dictionary.
- Side effects: none.

### `_require_exact_keys(value, required, label)`

Requires a configuration dictionary to contain exactly an expected key set.

- `value`: dictionary being checked.
- `required`: iterable of required key names.
- `label`: block name for errors.
- Returns: `None` on success.
- Raises: `RejectedInput` listing missing keys or, after missing keys pass, unknown keys.
- Preconditions: `value` is already known to be a dictionary.
- Security role: turns misspelled, obsolete, and unreviewed settings into explicit errors.

### `_require_regular_file(fpath, label, allow_missing=False)`

Checks a fixed path using `lstat()` so a symlink is distinguishable from its target.

- `fpath`: `Path` to inspect.
- `label`: file description for errors.
- `allow_missing`: when true, absence is accepted.
- Returns: `True` for a real regular file; `False` only when the file is absent and `allow_missing=True`.
- Raises: `HelperFailure` when a required file is absent, the path is a symlink/non-regular file, or the metadata lookup fails.
- Side effects: one metadata lookup; it does not open or modify the file.
- Security role: rejects symlink redirection for protected source, configuration, and audit files.

### `_validate_safe_name(value, label, allow_empty=False)`

Validates a short shell-inert configuration name.

- `value`: candidate name.
- `label`: field name for errors.
- `allow_empty`: permits exactly an empty string, used for an optional scheduler account.
- Returns: the unchanged validated string.
- Raises: `RejectedInput` unless the value is at most 64 characters, begins alphanumerically, and otherwise contains only letters, digits, `.`, `_`, or `-`.
- Side effects: none.

### `_validate_branch(value)`

Validates the one configured Git branch name.

- `value`: candidate branch.
- Returns: the unchanged validated branch.
- Raises: `RejectedInput` for unsafe characters, leading/trailing `/`, `..`, `//`, an empty value, or a value longer than 128 characters.
- Side effects: none.
- Security role: excludes Git revision expressions and malformed path-like branch names. Later Git helpers must additionally compare it with the protected configured branch.

### `_validate_absolute_path(value, label)`

Validates a normalized absolute POSIX path string.

- `value`: candidate path.
- `label`: field name for errors.
- Returns: the original string.
- Raises: `RejectedInput` for non-strings, relative paths, null bytes, `..` components, duplicate/trailing separators normalized by `Path`, or non-POSIX textual form.
- Side effects: none; it does not access the filesystem.
- Security role: establishes safe path syntax only. It does not check existence, ownership, symlinks, or containment beneath another root.

### `_validate_positive_int(value, label, minimum=1, maximum=None)`

Validates a bounded integer setting.

- `value`: candidate integer; booleans are explicitly rejected even though `bool` subclasses `int` in Python.
- `label`: field name for errors.
- `minimum`: inclusive lower bound, default 1.
- `maximum`: optional inclusive upper bound.
- Returns: the unchanged integer.
- Raises: `RejectedInput` for a wrong type or out-of-range value.
- Side effects: none.

### `_validate_ssh_config(config)`

Validates the complete `ssh` configuration block.

- `config`: dictionary with exactly `lethe_host_alias`, `grid_host_alias`, `grid_access_mode`, and `connect_timeout_sec`.
- Returns: `None` on success.
- Raises: `RejectedInput` for structural or field errors.
- Enforces: safe aliases, timeout from 1 through 120 seconds, and `grid_access_mode == 'through-lethe-helper'`.
- Side effects: none; it never connects to either host.

### `_validate_git_config(config)`

Validates the complete `git` configuration block.

- `config`: dictionary with exactly `remote_name`, `branch`, `automation_checkout`, and `manual_checkout`.
- Returns: `None` on success.
- Raises: `RejectedInput` for structural/field errors or identical automation and manual checkout paths.
- Side effects: none; it does not inspect a repository.
- Security role: establishes one safe remote/branch and protects the manual checkout from the most direct path mix-up.

### `_validate_remote_helpers(config)`

Validates fixed remote-helper directory syntax.

- `config`: dictionary containing exactly `lethe_dir` and `grid_dir`.
- Returns: `None` on success.
- Raises: `RejectedInput` unless both values are normalized absolute paths.
- Side effects: none; it does not query lethe or grid.

### `_validate_runs_config(config)`

Validates the remote automation-run root.

- `config`: dictionary containing exactly `root`.
- Returns: `None` on success.
- Raises: `RejectedInput` unless `root` is a normalized absolute path.
- Side effects: none.

### `_validate_scheduler_config(config)`

Validates scheduler identity, partition allowlist, and resource ceilings.

- `config`: scheduler dictionary containing exactly `user`, `account`, `allowed_partitions`, and `limits`.
- Returns: `None` on success.
- Raises: `RejectedInput` for unsafe names, an empty/non-list partition set, duplicate partitions, missing/unknown limits, non-positive limit values, or concurrency greater than total child jobs.
- Side effects: none; it performs no scheduler query.
- Security role: establishes protected upper bounds that later preview and submission helpers must enforce independently of repository-authored requests.

### `validate_config(config)`

Validates the complete decoded protected configuration.

- `config`: decoded JSON value expected to be a dictionary.
- Returns: the same validated dictionary without normalization or copying.
- Raises: `RejectedInput` for missing/unknown top-level keys, an unsupported schema version, or any nested validation failure.
- Side effects: none.
- Call sequence: validates `deployment_id`, then delegates to the SSH, Git, remote-helper, run-root, and scheduler block validators.

### `load_config()`

Loads and validates the one fixed protected configuration.

- Parameters: none.
- Returns: the decoded validated dictionary.
- Raises: `HelperFailure` when the fixed path is missing, is not a real regular file, cannot be read/decoded, or contains a configuration rejected by `validate_config()`.
- Side effects: reads one fixed local JSON file.
- Security role: converts validation exceptions into an operational helper failure because the protected installed configuration, not a caller-supplied value, is defective.

### `load_preview_request(request_id)`

Loads one request from the fixed protected request registry.

- `request_id`: path-safe registry key validated by `validate_request_id()`.
- Returns: the selected request dictionary without mutating it.
- Raises: `HelperFailure` for a missing, redirected, unreadable, or structurally invalid protected registry; raises `RejectedInput` for an unknown request, a non-object selected entry, or a mismatched embedded request ID.
- Side effects: reads one fixed local JSON file.
- Security role: callers select only an ID; they cannot supply request JSON or a filesystem path. Detailed request policy is independently enforced by the protected lethe helper.

### `canonical_json(value)`

Serializes JSON-compatible data deterministically.

- `value`: JSON-serializable value.
- Returns: compact JSON text with sorted object keys and no optional whitespace.
- Raises: standard `TypeError`/`ValueError` from `json.dumps()` for unsupported values.
- Side effects: none.
- Use: configuration hashing and audit-line construction.

### `hash_bytes(value)`

Calculates SHA256 for bytes.

- `value`: bytes-like input accepted by `hashlib.sha256`.
- Returns: 64-character lowercase hexadecimal digest.
- Side effects: none.

### `hash_file(fpath)`

Calculates SHA256 for one file's complete contents.

- `fpath`: path-like file location.
- Returns: 64-character lowercase hexadecimal digest.
- Raises: normal filesystem exceptions if reading fails.
- Side effects: reads the complete file into memory.
- Preconditions: security-sensitive callers should first use `_require_regular_file()`; `hash_file()` alone follows normal path-opening behavior.

### `get_bundle_identity()`

Calculates identity information for the installed runtime source bundle.

- Parameters: none.
- Returns: dictionary containing `bundle_version`, `bundle_sha256`, and a filename-to-SHA256 `source_sha256` dictionary.
- Raises: `HelperFailure` if an expected installed source is missing, a symlink, or not a regular file; filesystem errors may also propagate while reading.
- Side effects: reads all files listed by `RUNTIME_SOURCE_NAMES` in their fixed order.
- Security role: lets the user compare the protected runtime with reviewed candidate hashes.

### `get_config_identity(config)`

Calculates a formatting-independent identity for configuration data.

- `config`: JSON-compatible configuration object, normally returned by `load_config()`.
- Returns: SHA256 of the UTF-8 encoded canonical JSON representation.
- Raises: JSON serialization errors for unsupported values.
- Side effects: none.

### `redact_config(value, key='')`

Recursively prepares configuration for display.

- `value`: dictionary, list, or scalar value.
- `key`: current dictionary key used for sensitivity matching.
- Returns: a new dictionary/list structure for containers; non-sensitive scalars are returned unchanged; a sensitive keyed value becomes `<redacted>`.
- Sensitive key fragments: `identity_file`, `password`, `private_key`, `secret`, and `token`, matched case-insensitively.
- Side effects: none; input containers are not mutated.
- Limitation: heuristic redaction does not make it acceptable to store secrets in the configuration.

### `_validate_audit_parent(dirpath)`

Checks the pre-created audit directory.

- `dirpath`: expected audit parent as a `Path`.
- Returns: `None` on success.
- Raises: `HelperFailure` if it is absent, a symlink, not a directory, or cannot be inspected.
- Side effects: one metadata lookup.
- Security role: prevents audit creation through a redirected parent path.

### `sanitize_audit_args(args)`

Bounds and redacts command arguments before persistence.

- `args`: iterable of values, normally raw command-line arguments.
- Returns: list containing at most 20 strings. Exact words from `PUBLIC_AUDIT_ARGS` are retained; every other value becomes `<value>`.
- Side effects: none.
- Security role: records command shape without copying arbitrary caller-controlled values into the audit log.

### `read_recent_audit_events(limit=20, max_bytes=65536)`

Reads a bounded tail from the fixed audit log.

- `limit`: maximum decoded events returned; default 20.
- `max_bytes`: maximum bytes read from the end; default 65,536.
- Returns: list of decoded JSON event dictionaries, oldest to newest within the selected tail; returns an empty list when the audit file is absent.
- Raises: `HelperFailure` for a symlink/non-regular audit file, read failure, or invalid JSON in a selected complete line.
- Side effects: reads only the fixed audit path.
- Boundary behavior: when reading begins after byte zero, the first line is discarded because it may be partial.

The current function is internal to the fixed CLI call and does not validate caller-supplied `limit` or `max_bytes`. Future public exposure of those parameters would require strict upper-bound validation.

### `append_audit_event(action, status, exit_code, args, details=None, helper='hpc-helper-info')`

Appends one mandatory JSONL event to the fixed audit log.

- `action`: trusted command action name supplied by the fixed entry point.
- `status`: trusted status such as `success`, `rejected`, `unknown`, or `failed`.
- `exit_code`: numeric result code.
- `args`: raw command argument sequence, passed through `sanitize_audit_args()`.
- `details`: optional diagnostic converted to text and truncated to 500 characters.
- `helper`: trusted installed-helper name; defaults to `hpc-helper-info`.
- Returns: the dictionary that was serialized.
- Raises: `HelperFailure` for an invalid/missing parent, an existing symlink/non-regular audit file, or an append/lock/fsync failure. A non-Linux platform without `fcntl` is unsupported.
- Side effects: creates the audit file with mode `0600` if absent, otherwise appends one line; acquires an exclusive advisory lock and calls `fsync()`.
- Security role: failure is intended to stop the caller so an operation is not silently unaudited.

`action`, `status`, and `exit_code` are supplied by trusted helper code and are not schema-validated inside this function. A future helper must not pass arbitrary caller text into those fields.

## Extension rules for later gates

When this module is extended:

- keep caller-selectable values behind explicit validators and allowlists;
- do not add arbitrary command, host, branch, or path parameters;
- keep protected paths derived from installed configuration rather than environment variables;
- distinguish rejected input, unavailable remote state, and known failure;
- audit before printing a successful result or performing a later state-changing action;
- bump `BUNDLE_VERSION`, recalculate reviewed source hashes, and require manual promotion of the protected copy;
- update this reference, the JSON schemas, fixtures, and installation handoff together.
