# Batch: go-artifact-allowlist

```yaml
task: "Fix stale checkpoint safety, Go binary ephemeral allowlist, and bare agent-tier name trap"
batch: go-artifact-allowlist
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py
depends-on: []
```

## Batch Scope

Fixes issue #571: a compiled Go binary (`sandbox.exe`) left untracked at the repo root is flagged as a blocking scope violation at the mill-go Handoff cleanliness gate instead of being auto-cleaned like coverage artifacts. This batch extends `_cleanliness.clean_ephemeral_scope_violations` to recognize Go build artifacts and adds unit tests. No external interface is produced for other batches. Batch-local decisions: `.exe` is a **blanket** suffix rule (not gated by the package-main heuristic — see discussion `go-artifact-allowlist`); extensionless bare-name binaries are allowlisted only when corroborated by a matching `package main` source directory.

## Cards

### Card 4: Extend the ephemeral allowlist for Go build artifacts

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `clean_ephemeral_scope_violations`, extend the per-violation allowlist test. (1) Add a blanket `.exe` suffix: a violation whose basename ends in `.exe` is allowlisted (this also keeps the existing `.test.exe` case working). (2) Add a bare-name Go-binary check: for a violation whose basename contains NO `.` (no extension), allowlist it only if a new helper `_is_go_main_artifact(worktree, path)` returns True. Implement `_is_go_main_artifact(worktree: Path, path: str) -> bool` in `_cleanliness.py`: it runs `git ls-files "*.go"` via `_subprocess_util.run([...], cwd=worktree)`, and returns True iff at least one tracked `.go` file (a) lives in a directory whose basename equals the violation's basename (`Path(go_file).parent.name == basename`) and (b) declares `package main` (a line that, stripped, starts with `package main`). Read each candidate `.go` file's text with a guarded read (skip files that fail to read). To keep the common case free, only call `_is_go_main_artifact` when the basename has no `.`; do not call it for extension-bearing violations. Preserve the existing removal semantics for every allowlisted path: `os.remove`, swallow `FileNotFoundError` (still report as removed), report `OSError` as blocking. Non-allowlisted violations remain blocking. Update the function docstring to document the Go `.exe` + bare-name coverage. ASCII only.
- **Commit:** `feat(cleanliness): auto-clean Go .exe and package-main build artifacts`

### Card 5: Unit tests for Go artifact allowlisting

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanliness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add test functions to `test-cleanliness.py` following the existing CESV-style real-`git init` tmp-fixture pattern (see the existing CESV-1..5 tests). (1) An untracked `app.exe` at repo root is removed (in `removed`, not `blocking`). (2) An untracked extensionless `sandbox` at repo root WITH a tracked `tools/sandbox/main.go` containing `package main` is removed (bare-name heuristic hit). (3) An untracked extensionless `notes` file with NO matching `package main` directory is reported as blocking (heuristic must not over-match). (4) Regression: an untracked `coverage.out` is still removed and a non-allowlisted untracked `data.json` is still blocking (the existing CESV cases must keep passing). Register any new test functions in the file's run harness the same way existing tests are registered.
- **Commit:** `test(cleanliness): cover Go .exe and bare-name build-artifact allowlisting`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanliness.py` runs the single test file this batch touches. It covers the extended allowlist logic (card 4) via the new and existing CESV tests (card 5). Scope is intentionally limited to `test-cleanliness.py` because `_cleanliness.py` is consumed only by mill-go Handoff, which is exercised through integration tests, not unit tests; the allowlist logic itself is fully unit-testable here.
