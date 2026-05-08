# Batch: script-fixes

```yaml
task: 32 (A) — Bug-fix batch 2
batch: script-fixes
number: 1
cards: 5
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Five independent script-level bug fixes that share no code surface beyond their unit-test files. Grouped into one batch because each fix is small (a handful of lines) and a single Sonnet implementer session can complete them sequentially without context-window pressure. Fixes addressed: GitHub issues #193 (with TDD test-first), #200, #191, #192. The `_plan_validate` Deletes-counting fix lands first as TDD (Card 1 writes the failing test; Card 2 implements the fix). The remaining cards each touch one source file and at most one test file, with no cross-card dependencies. The batch's `verify` runs the full unit-test suite after the last card lands.

## Cards

### Card 1: Add Deletes case to test-plan-validate.py for all-files-touched-mismatch

- **Context:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-plan-validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `test-plan-validate.py` with a new test function `test_all_files_touched_deletes_counted` that constructs a fixture where (a) the overview's `## All Files Touched` section lists `foo.md`, (b) one batch card has `- **Deletes:** \`foo.md\`` and no `Edits:` / `Creates:` for it, (c) all other validator checks pass. Assertion: after calling `_plan_validate.run(plan_dir, project_root)`, no error dict with `check == "all-files-touched-mismatch"` is returned for `foo.md`. Use the existing `_make_overview` and `_make_batch_file` helpers in the file (extend `_make_batch_file` with a `deletes:` parameter if the helper does not already accept one — keep the same shape as `creates:` / `edits:`). Register the new test in `run_all_tests` (or whatever test-runner driver the file uses, mirroring the existing test registration pattern). The test MUST fail against the unmodified `_plan_validate.py` (no Deletes union) — this is TDD; Card 2 makes it pass.
- **Commit:** `test(plan-validate): cover Deletes case for all-files-touched-mismatch`

### Card 2: Count Deletes in _check_all_files_touched_mismatch and update message strings

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_plan_validate.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_check_all_files_touched_mismatch` (lines 651–707), augment the `cards_set` construction (lines 678–682) so that for each `batch_path in batch_files`, `cards_set` is unioned with `_parse_deletes_only(batch_path)` in addition to the existing `_parse_edits_only(batch_path)` and `compute_creates_union(...)`. Then update both finding-message strings: line 692 currently reads `"but not in any card's Edits: or Creates:"` — change to `"but not in any card's Edits:, Creates:, or Deletes:"`. Line 703 currently reads `"in card Edits:/Creates: but missing"` — change to `"in card Edits:/Creates:/Deletes: but missing"`. After the change, Card 1's test must pass.
- **Commit:** `fix(plan-validate): count Deletes: in all-files-touched union`

### Card 3: Prefix task/ on four paths in millpy-implement-holistic.py and update its test fixture

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement-holistic.py`
  - `plugins/mill/unit_tests/test-millpy-implement-holistic.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-implement-holistic.py`, change four path constructions to prefix `task/`: line 77 `status_path = project_root / "status.md"` → `project_root / "task" / "status.md"`; line 91 `overview_path = project_root / "plan" / "00-overview.md"` → `project_root / "task" / "plan" / "00-overview.md"`; line 103 `str(project_root / "plan" / b["file"]) for b in batches` → `str(project_root / "task" / "plan" / b["file"]) for b in batches`; line 123 `["git", "add", "status.md", review_file_arg]` → `["git", "add", "task/status.md", review_file_arg]`. Update the corresponding error-message strings on lines 88 and 93 so they reference the `task/`-prefixed paths (the f-string already interpolates `status_path` / `overview_path` so the message updates automatically; just verify after edit). Then update `test-millpy-implement-holistic.py:_make_fixture` (lines 35–99) so the fixture writes `tmp_path / "task" / "plan" / "00-overview.md"`, `tmp_path / "task" / "plan" / "01-test-batch.md"`, and `tmp_path / "task" / "status.md"` (instead of the current unprefixed locations). Adjust the `expected_batch_path` assertion in `test_6_batch_files_and_session_ids_injected` (around line 239) to use the same `task/plan/` prefix. Run the unit-test suite after the change to confirm all six tests pass.
- **Commit:** `fix(holistic-implement): prefix task/ on status, plan, and git-add paths`

### Card 4: Push initial status commit with --set-upstream in _spawn_core.write_initial_status

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_spawn_core.py`
  - `plugins/mill/unit_tests/test-spawn-core.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_spawn_core.write_initial_status` (lines 682–743 of `_spawn_core.py`), after the existing `git commit` call (lines 736–742) and its returncode check, add a third `_subprocess_util.run` call: `result = _subprocess_util.run(["git", "-C", str(worktree_path), "push", "--set-upstream", "origin", branch])` followed by the same `if result.returncode != 0: raise RuntimeError(f"git push --set-upstream origin {branch} failed: {result.stderr.strip()!r}")` shape used by the existing add/commit blocks. Place the push immediately before the `return status_abs` line. Then in `test-spawn-core.py`, modify `_make_git_repo` (around line 138) so it ALSO sets up a tempdir-bare remote and configures `origin` — extend the helper using the existing `_make_wiki` bare-remote pattern (`test-spawn-core.py:81-135`): (a) create a `<tmp>/repo-bare/` directory, (b) `git -C <bare> init --bare`, (c) `git -C <repo> remote add origin <bare>`. Keep the helper's existing return value (the working repo path). The `test_write_initial_status` test (around line 372) will then pass because the push succeeds. Add a third test `test_write_initial_status_push_failure_raises_runtime_error` that uses a working repo with NO origin remote and asserts `RuntimeError` with `"git push --set-upstream origin"` in the message. Register the new test in the `tests = [...]` list near the bottom of the file. Verify all three spawn-status tests pass after the change.
- **Commit:** `fix(spawn): push initial status commit with --set-upstream`

### Card 5: Emit [builder-lock] acquired log line on stderr from millpy-builder-lock acquire

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-builder-lock.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-builder-lock.py`, after the successful `_builder_lock.acquire(mill_dir, args.slug)` call inside the `acquire` subcommand body (lines 35–41), emit one log line on stderr: `print(f"[builder-lock] acquired by {args.slug!r}", file=sys.stderr)`. The line MUST go to stderr (matching `_wiki._acquire`'s pattern at `_wiki.py:185`); stdout stays reserved for the parseable `read` subcommand output. Add the import `import sys` at the top of `millpy-builder-lock.py` if not already present (current file imports `argparse`, `sys` already). Format the log line exactly as `[builder-lock] acquired by '<slug>'` (with single quotes from `!r`, mirroring `_wiki._acquire`'s `[wiki] _acquire: acquired by 'slug'` pattern). Do NOT modify `_builder_lock.acquire` itself — the helper stays I/O-free.
- **Commit:** `feat(builder-lock): emit acquired log line on stderr`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` — covers `test-plan-validate.py` (Cards 1+2), `test-millpy-implement-holistic.py` (Card 3), and `test-spawn-core.py` (Card 4). Card 5 has no automated test (the log-line change is verified post-merge by inspecting mill-go logs); the existing `test-builder-lock.py` tests the helper, not the CLI, and is unaffected.
