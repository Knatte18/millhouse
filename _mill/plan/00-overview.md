# Plan: millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows

```yaml
task: "millpy-implement.py --stage baseline: WinError 3 snapshotting a transient/generated file on Windows"
slug: "mill-baseline-snapshot-windows-path-gap"
approved: false
started: "2026-07-29T13:43:56Z"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: toctou-guard-hardening
    file: 01-toctou-guard-hardening.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-safe-rmtree.py test-junction.py
```

## Shared Decisions

### Decision: `FileNotFoundError` is the only exception class caught by the new guards

- **Decision:** Both new guards (in `_safe_rmtree._walk_strip_reparse_points` and in `_junction.strip_all_in_worktree`'s `_walk`) catch `FileNotFoundError` only — never a broader `OSError` or `Exception`. No `sys.platform` gating; the guards apply unconditionally on Windows and POSIX.
- **Rationale:** `FileNotFoundError` is what Python raises for both WinError 2 (file not found) and WinError 3 (path not found), and for POSIX `ENOENT`. It is narrow enough that permission errors, disk errors, and malformed reparse points still propagate and fail loudly. `_safe_rmtree.py`'s module docstring already commits to symmetric cross-platform strip behaviour, so gating either guard to Windows-only would contradict that stated intent.
- **Applies to:** all batches (this task has exactly one batch, but the rule is stated here per convention, not batch-locally, since it governs the design uniformly across both edited files).

### Decision: skip-and-log, never silent

- **Decision:** Every new `except FileNotFoundError:` branch introduced by this task prints an ASCII-only, module-prefixed message to `sys.stderr` before continuing/returning — `[safe-rmtree] skip vanished entry: {path}` in `_safe_rmtree.py`; `[junction] WARNING: vanished entry scanning {dir_path}; skipping` in `_junction.py`. No new branch is silent.
- **Rationale:** The GitHub issue (#738) this task fixes explicitly asks for skip-and-log rather than hard-fail. A silent skip would make the race invisible again — just non-fatal instead of fatal, which is a net loss of debugging signal versus today's loud crash. `[junction]`'s new message must NOT reuse the existing `permission denied` wording from the sibling `except PermissionError:` branch — that would misreport a vanished-path race as a permission failure.
- **Applies to:** all batches.

## All Files Touched

- `plugins/mill/scripts/_junction.py`
- `plugins/mill/scripts/_safe_rmtree.py`
- `plugins/mill/unit_tests/test-junction.py`
- `plugins/mill/unit_tests/test-safe-rmtree.py`
