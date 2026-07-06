# Batch: implementer-verify-cwd

```yaml
task: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs
batch: implementer-verify-cwd
number: 4
cards: 6
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py
depends-on: [1, 3]
```

## Batch Scope

Fixes #604 for the implementer path: threads a `cwd_override` (per-batch/module-wide verify subprocess) and `cwd_override_relative` (baseline temp-worktree verify subprocess) through `_implementer_common.py`'s verify-gate chain and `_verify_baseline.py`'s `compute_baseline`, then wires both into `millpy-implement.py`'s three `verify` frontmatter read sites via `parse_verify_field` (batch 3). `cwd_override` always takes precedence over the existing `git_root`/`project_root` fallback when set, and is `None` whenever `parse_verify_field` returns a `None` cwd (plain-string `verify:`, today's format) — this is what keeps the #554-pinned flat-layout test green with zero behavior change. Depends on batch 1 in addition to batch 3: both batches edit `plugins/mill/scripts/_implementer_common.py` (batch 1 at the `compute_scope_violations` call sites, this batch at the verify-gate chain) and are otherwise parallel-eligible, so the DAG serializes them to avoid two builders editing the same file concurrently.

## Cards

### Card 13: Add cwd_override to the _implementer_common.py verify-gate chain

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `_run_verify_gate` gains a `cwd_override: Path | None = None` keyword-only parameter (in addition to its existing `git_root` kwarg). Change `effective_cwd = git_root if git_root is not None else project_root` to first check `cwd_override`: `effective_cwd = cwd_override if cwd_override is not None else (git_root if git_root is not None else project_root)`. `_run_verify_gates` gains `cwd_override: Path | None = None` and `module_wide_cwd_override: Path | None = None` keyword-only parameters, threading `cwd_override` into its batch-level `_run_verify_gate(project_root, verify_cmd, git_root=git_root)` call and `module_wide_cwd_override` into its module-wide `_run_verify_gate(project_root, module_wide_verify_cmd, git_root=git_root)` call. `finalize_from_output` and `_forward_output` each gain the same two new keyword-only parameters, threading them into their internal `_run_verify_gates(...)` call. Update each function's docstring `Args:` section to describe the new parameters and their precedence over `git_root`/`project_root`.
- **Commit:** `feat(implementer-common): thread cwd_override through the verify-gate chain (#604)`

### Card 14: Add cwd_override_relative to _verify_baseline.compute_baseline

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `compute_baseline` gains a `cwd_override_relative: Path | None = None` keyword-only parameter. `compute_baseline` runs the module-wide verify inside a temporary git worktree at `tmp_path` (a fresh checkout equivalent to `git_root`, not `hub_root`) — a resolved `cwd: hub` must therefore run at `tmp_path / cwd_override_relative`, never at the real worktree's `hub_root`. Change both `_run_verify_in(module_wide_verify_cmd, tmp_path)` calls to `_run_verify_in(module_wide_verify_cmd, tmp_path / cwd_override_relative if cwd_override_relative is not None else tmp_path)`. Update the docstring to state that this parameter is a hub-relative *path fragment* (not an absolute cwd) precisely because it must be re-anchored to the temp checkout, not the real worktree.
- **Commit:** `feat(verify-baseline): thread cwd_override_relative into the temp-worktree verify run (#604)`

### Card 15: Thread parse_verify_field through millpy-implement.py per-batch verify reads

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** At both per-batch `verify_cmd = batch_frontmatter.get("verify")` read sites (the finalize-stage and full-stage branches), replace the bare `.get("verify")` read with `verify_cmd, cwd_override = _plan_dag.parse_verify_field(batch_frontmatter, project_root, git_root)`. Thread `cwd_override` onward as the new `cwd_override=` keyword argument to the enclosing `finalize_from_output(...)` / `_forward_output(...)` call (added in Card 13). Let a `ValueError` from `parse_verify_field` (malformed `verify:` mapping) propagate uncaught — a malformed plan file is an authoring bug that must surface immediately, not be silently coerced to a fallback.
- **Commit:** `feat(millpy-implement): resolve per-batch verify cwd via parse_verify_field (#604)`

### Card 16: Thread parse_verify_field through module-wide verify and the baseline stage

- **Context:**
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace `module_wide_verify_cmd = overview_frontmatter.get("verify") or None` with `module_wide_verify_cmd, module_wide_cwd_override = _plan_dag.parse_verify_field(overview_frontmatter, project_root, git_root)`. Thread `module_wide_cwd_override` onward as the new `module_wide_cwd_override=` keyword argument to both the finalize-stage and full-stage `finalize_from_output(...)` / `_forward_output(...)` calls (added in Card 13), alongside the existing `module_wide_verify_cmd=` argument. In `_run_baseline_stage`, before calling `_verify_baseline.compute_baseline(...)`, derive `cwd_override_relative` from `module_wide_cwd_override`: when `module_wide_cwd_override == project_root`, `cwd_override_relative = project_root.relative_to(git_root)` (empty/`.` in flat layout, where `project_root == git_root`); when `module_wide_cwd_override is None` (plain-string `verify:` or absent), `cwd_override_relative = None`. Note `module_wide_cwd_override` can never resolve to a value other than `project_root`, `git_root`, or `None` per `parse_verify_field`'s contract, so no `git_root`-resolved branch needs a relative-prefix conversion (a `git_root`-resolved cwd already matches `compute_baseline`'s existing `tmp_path` default). Pass `cwd_override_relative=cwd_override_relative` to `compute_baseline`.
- **Commit:** `feat(millpy-implement): resolve module-wide verify cwd and thread it into the baseline stage (#604)`

### Card 17: Add cwd_override precedence test to test-implementer-common.py

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new test case asserting `_run_verify_gate`'s `cwd_override` (when passed a synthetic Path) takes precedence over both `git_root` and `project_root` as the verify subprocess's cwd. Leave the existing "Test A: git_root kwarg selects cwd for the verify subprocess (#554)" case entirely unchanged — it must continue to pass with `cwd_override` absent (defaulting to `None`), asserting `git_root` still wins over `project_root` in that case exactly as before.
- **Commit:** `test(implementer-common): cover cwd_override precedence without regressing #554 (#604)`

### Card 18: Add nested-layout cases to test-millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a nested-layout case for the per-batch verify path (Card 15) asserting a `verify: {cwd: hub, command: ...}` batch frontmatter resolves `cwd_override` to the nested `project_root` and threads it through to the verify subprocess's cwd. Add a nested-layout case for the module-wide verify path (Card 16) asserting the same for overview-level `verify:`. Add a nested-layout case asserting the baseline stage's `compute_baseline` call receives the correct `cwd_override_relative` (the hub-relative prefix) when the module-wide verify resolves to `cwd: hub`, and `None` when it resolves to `cwd: git_root` or is a plain string.
- **Commit:** `test(millpy-implement): cover nested-layout verify cwd resolution (#604)`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py` covers both affected test files: the verify-gate chain's cwd_override precedence (Card 17, including the unmodified #554 case) and millpy-implement.py's three read sites plus the baseline stage (Card 18).
