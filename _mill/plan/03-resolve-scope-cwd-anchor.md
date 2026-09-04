# Batch: resolve-scope-cwd-anchor

```yaml
task: "mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs"
batch: "resolve-scope-cwd-anchor"
number: 3
cards: 1
verify: PYTHONPATH= "$MILL_PYTHON" plugins/codeguide/unit_tests/test-resolve-scope.py
depends-on: []
```

## Batch Scope

Fixes #943: `codeguide-update`'s `resolve_scope.py` mis-resolves explicit file-path arguments in a nested-hub-root layout (hub root nested below git toplevel). This is the task's one genuine Python code change (the other four bugs are SKILL.md/doc procedure fixes), and its one TDD candidate per `_mill/discussion.md`'s Testing section. Independent root batch — no file overlap with batch 1 or batch 2. `verify:` runs the extended unit test file directly (no `uv run --project` wrapper: `plugins/codeguide` has no `pyproject.toml`, confirmed by direct invocation during plan research — `PYTHONPATH= "$MILL_PYTHON" plugins/codeguide/unit_tests/test-resolve-scope.py` runs the file's existing 18 scenarios standalone).

## Cards

### Card 7: resolve_scope.py — anchor _explicit_scope to invocation cwd, not toplevel (TDD)

- **Context:** none
- **Edits:**
  - `plugins/codeguide/scripts/resolve_scope.py`
  - `plugins/codeguide/unit_tests/test-resolve-scope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** TDD — write the failing test first, confirm it fails, then fix. (1) Append a new scenario to `test-resolve-scope.py` after the existing Scenario 18, following the file's own numbering and assertion style (a `with tempfile.TemporaryDirectory()` block using the file's existing `_make_repo`/`_commit` helpers): construct a tmp git repo, create a nested subdirectory below the repo root (simulating a hub root nested below git toplevel), write a file at a relative path inside that subdirectory, and assert `enumerate_scope(["<relative-filename>"], cwd=<nested-subdir>)` returns the path anchored to the nested `cwd` (i.e. equal to `<nested-subdir> / "<relative-filename>"`), not anchored to the repo toplevel. Run the test file and confirm the new scenario fails against the current code. (2) Fix `_explicit_scope` (function `_explicit_scope` in `resolve_scope.py`, lines 199-208) — it currently anchors every token via `toplevel / token` (line 200) regardless of invocation cwd. Change its signature to also accept `cwd_path` (the value `enumerate_scope` already computes at its own top, `resolve_scope.py:235`, but today only forwards to `_get_toplevel`), and build each relative token as `cwd_path / token` instead of `toplevel / token` (a token that is itself absolute is unaffected: `pathlib.Path.__truediv__` ignores the left operand whenever the right operand is absolute). Update `enumerate_scope`'s one call site (`return _explicit_scope(toplevel, args)`) to also pass `cwd_path`. Do NOT change `_no_arg_scope`, `_time_scope`, or `_head_rev_scope` — those three derive every path from `git diff`/`git log` output, which git itself always reports relative to the true toplevel, so anchoring those to `toplevel` remains correct and must not be touched. (3) Run the test file again and confirm the new scenario passes, and confirm every pre-existing scenario (including Scenario 10 and Scenario 18, the two existing explicit-path cases — both call `enumerate_scope` with `cwd=tmp` where `tmp` already equals `toplevel`, so they are unaffected by this change) still passes.
- **Commit:** `fix(codeguide): anchor resolve_scope.py explicit paths to invocation cwd, not git toplevel (#943)`

## Batch Tests

`verify: PYTHONPATH= "$MILL_PYTHON" plugins/codeguide/unit_tests/test-resolve-scope.py` — covers the new nested-cwd explicit-path scenario (Card 7) plus all 18 pre-existing scenarios (confirming the three git-diff-derived routes, and the two pre-existing explicit-path scenarios, are unaffected by the `_explicit_scope` change).
