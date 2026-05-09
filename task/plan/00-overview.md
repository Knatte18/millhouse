# Plan: 36 (A) — Bug-fix batch 3

```yaml
task: 36 (A) — Bug-fix batch 3
slug: mill-misc-fixes-3
approved: false
started: '20260509-101719'
parent: main
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: cleanliness-helper
    file: 01-cleanliness-helper.md
    depends-on: []
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 2
    name: cleanliness-wireup
    file: 02-cleanliness-wireup.md
    depends-on: [1]
    verify: python plugins/mill/unit_tests/run-all.py
  - number: 3
    name: git-pr-task-contract
    file: 03-git-pr-task-contract.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: helper-module-style

- **Decision:** New helper `plugins/mill/scripts/_cleanliness.py` follows the existing flat-helper pattern: lowercase-leading-underscore filename, no `if __name__ == "__main__":` smoke-block, public functions documented with module-level docstrings (style matches `_status.py`). Git invocations go through `_subprocess_util.run` (matches `_wiki.py`'s pattern), not raw `subprocess.run`.
- **Rationale:** `_subprocess_util.run` enforces UTF-8 I/O, emits the `[subprocess] spawn argv=...` breadcrumb every other helper does, and propagates timeouts uniformly. The `if __name__ == "__main__":` ban keeps helpers as production-only code per CLAUDE.md.
- **Applies to:** all batches

### Decision: unit-test-style

- **Decision:** Unit tests follow the simple `def main() -> int:` pattern from `plugins/mill/unit_tests/test-active.py`, returning 0 on success and 1 on failure. Subprocess calls in `_cleanliness` are mocked via `unittest.mock.patch("_subprocess_util.run", ...)` returning a `MagicMock` with `returncode=0` and a `stdout` string. Real `tempfile.TemporaryDirectory()` is used for snapshot-file I/O; no real git is invoked.
- **Rationale:** Matches CLAUDE.md's testing-conventions rule ("In-memory / `tempfile` fixtures; no real git, no real LLM"). The `def main` pattern keeps the test runnable directly via `python plugins/mill/unit_tests/test-cleanliness.py` and through `run-all.py`.
- **Applies to:** all batches

### Decision: snapshot-path-shape

- **Decision:** Pre-batch snapshot lives at `task/.cleanliness-snapshot-<batch_name>.txt` (worktree-relative, dot-prefixed file, plain-text body). The path is computed as `project_root / "task" / f".cleanliness-snapshot-{batch_name}.txt"` in `millpy-implement.py` and as `<worktree>/task/.cleanliness-snapshot-<batch_name>.txt` in `mill-go` SKILL.md prose. Batch name is the `name:` value from the plan-overview Batch Index, which is also the `<batch_name>` used in `_status.set_batch_field` calls.
- **Rationale:** The literal `"task"` segment matches every existing reference in `millpy-implement.py` (lines 92, 136, 221) — adding a config knob for `task_dir` is out of scope for this fix. Dot-prefix keeps the file out of casual editor file-trees; per-batch scope matches `start_sha`'s scope.
- **Applies to:** cleanliness-helper, cleanliness-wireup

### Decision: conventional-commit-prefixes

- **Decision:** Commit prefixes follow existing patterns: `feat(<scope>):` for new helper/feature code, `docs(<scope>):` for SKILL.md edits and prose changes, `test:` for new unit-test files. Scope is the directory or module short name (`scripts`, `mill-go`, `git-pr`, `implement`).
- **Rationale:** Matches the recent commit history on `main` (`fix(update-plugins):`, `chore: post-mill-setup state`).
- **Applies to:** all batches

### Decision: helper-signature-inline-doc

- **Decision:** Wherever a SKILL.md names a helper function (e.g. `_cleanliness.compute_new_dirt(...)`), an inline `signature:` line is added immediately after the call snippet, in the same `signature: <module>.<func>(...) -> <ret>` form mill-go's existing sections use (see `mill-go` SKILL.md's "2b. Cleanliness gate" at line 93 for the pattern to match).
- **Rationale:** mill-go's `Principles` section ("Don't Read or Grep helper internals" rule, project anti-pattern #1 in `mill:workflow`) requires every helper-naming SKILL.md section to include the signature inline so the implementer never reads helper source. New helper additions inherit this rule.
- **Applies to:** cleanliness-wireup

## All Files Touched

- `plugins/mill/scripts/_cleanliness.py`
- `plugins/mill/scripts/millpy-implement.py`
- `plugins/mill/skills/git-pr/SKILL.md`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/unit_tests/test-cleanliness.py`
