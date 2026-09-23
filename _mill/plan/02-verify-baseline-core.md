# Batch: verify-baseline-core

```yaml
task: 'compute_baseline: use the task worktree''s own pre-edit state, not a parent-branch checkout'
batch: verify-baseline-core
number: 2
cards: 7
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-verify-baseline.py test-worktree.py && PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-verify-baseline.py
depends-on: []
```

## Batch Scope

This batch rewrites `_verify_baseline.py`'s core algorithm to drop the transient-worktree checkout entirely, per Decision `remove-all-three-checkouts`/`algorithm-simplification`/`module-wide-verdict-source` in `_mill/discussion.md`: `compute_baseline` becomes a two-run, no-checkout function that returns `tuple[str, list[str]]` (verdict plus signatures), and `compute_batch_baselines` drops its checkout-path framing in favor of a plain `cwd` parameter. This is the external interface every later batch consumes: batch 3 (`millpy-implement.py`) and batch 5 (`millpy-merge-in-subagent.py`) both call the new `compute_baseline` signature, and batch 3 also calls `compute_batch_baselines` with the renamed `cwd` parameter. `compute_batch_baseline_on_demand` (the lazy per-batch path, deleted here) has its only caller deleted in batch 4, not this batch — batch 4 depends on batch 3, not this one, so it does not need a direct dependency edge to this batch beyond the shared file each already touches independently.

## Cards

### Card 3: Rewrite the module docstring for the no-checkout design

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Rewrite the module-level docstring in full. Drop the "checks out the parent branch's current tip into a fresh, throwaway worktree... reuses the task worktree's already-installed gitignored dependency state via filesystem junctions" framing entirely. State instead that this module runs `module_wide_verify_cmd` (and, via `compute_batch_baselines`, each batch's own `verify:` command) directly against an already-resolved cwd inside the task worktree itself — never a checkout — because at `--stage baseline` time (before batch 1's implementer is ever dispatched) the task worktree's source content already equals the merge-base content, per Decision `capture-site` in `_mill/discussion.md`.
  Rewrite the "Return contract" paragraph: `compute_baseline` now returns `tuple[str, list[str]]` — the existing `"clean"` / `"pre-existing-failures"` verdict, plus the deduplicated, order-preserving union of the raw failure-signature lines extracted from every run actually performed.
  Rewrite the "Public API" listing at the bottom of the docstring to: `compute_baseline(cwd, module_wide_verify_cmd, *, timeout_seconds=None) -> tuple[str, list[str]]`; `compute_batch_baselines(commands, cwd, *, pair_cache=None, timeout_seconds=None) -> dict[str, list[str]]`; delete the `compute_batch_baseline_on_demand` entry entirely.
  Delete the "confirmed by two consecutive transient-worktree failures AND a matching failure in the task worktree itself" clause (the control-check corroboration no longer exists — two consecutive failures at `cwd` alone is now sufficient) and the closing paragraph's "raises on any INFRASTRUCTURE failure (parent-branch rev-parse failure, git worktree add failure, junction creation failure)" — replace with: raises only `subprocess.TimeoutExpired`, which the caller treats as "computation failed, leave the baseline unset," identically to before.
- **Commit:** `docs(_verify_baseline): rewrite module docstring for no-checkout design`

### Card 4: Delete the checkout and dependency-junction helpers

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `_checkout_parent_branch`, `_link_dependency_dirs`, and the module-level `_DEPENDENCY_DIR_CANDIDATES` tuple constant from `_verify_baseline.py` entirely, including their docstrings and the `import _junction` line (now unused in this file — confirm no other function in this file still references `_junction` before removing the import; if one does, keep the import and only remove the now-dead call sites).
  In `test-worktree.py`, fix the stale comment "mirroring `_verify_baseline._checkout_parent_branch`'s real detached-HEAD baseline-checkout behavior" (in the block registering a nested worktree under the task worktree's `.scratch/` dir) — reword it to describe the detached-HEAD nested-worktree pattern being mirrored without citing a symbol this card deletes (e.g. "mirroring a detached-HEAD nested-worktree pattern", with no `_verify_baseline` reference). This is a comment-only fix; no test behavior changes.
- **Commit:** `refactor(_verify_baseline): delete checkout and dependency-junction-reuse helpers`

### Card 5: Rewrite compute_baseline to run in-worktree

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `compute_baseline`'s signature to `compute_baseline(cwd: Path, module_wide_verify_cmd: str, *, timeout_seconds: float | None = None) -> tuple[str, list[str]]`. Delete the `project_root`, `git_root`, `parent_branch`, and `cwd_override_relative` parameters entirely — there is no checkout to resolve a parent branch or a hub-relative re-anchoring fragment for; `cwd` is the caller's already-resolved absolute working directory (the caller resolves it the same way `_run_verify_gate` resolves its own effective cwd: an explicit override if present, else `git_root`).
  The function body becomes a single delegation: `return _run_module_wide_verify_algorithm(module_wide_verify_cmd, cwd, timeout_seconds)` — no checkout, no `try`/`finally` teardown, no dependency-junction call.
  Rewrite the docstring to match: drop the numbered "Implementation, in order" steps describing checkout/junction/teardown (steps 1-5 in the current docstring); describe only the run-then-retry algorithm now owned by `_run_module_wide_verify_algorithm`. Update `Args:` to list only `cwd`, `module_wide_verify_cmd`, `timeout_seconds`. Update `Returns:` to describe the `tuple[str, list[str]]`. Update `Raises:` to `subprocess.TimeoutExpired` only (drop `RuntimeError`, `OSError`, `ValueError` — those were checkout/junction failure modes that no longer exist).
- **Commit:** `refactor(_verify_baseline): compute_baseline runs against an already-resolved cwd, no checkout`

### Card 6: Rewrite _run_module_wide_verify_algorithm to drop the 3rd control run

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Change `_run_module_wide_verify_algorithm`'s signature to `_run_module_wide_verify_algorithm(module_wide_verify_cmd: str, cwd: Path, timeout_seconds: float | None = None) -> tuple[str, list[str]]` — drop the `effective_tmp_path`/`project_root` parameters (both runs now happen at the same `cwd`; there is no separate task-worktree control-run cwd).
  Delete the third "control check" run entirely: remove the `rc, _output = _run_verify_in(module_wide_verify_cmd, project_root, timeout_seconds)` block and the `print(... "path/environment-induced" ...)` stderr warning that followed it, per Decision `algorithm-simplification`.
  The algorithm becomes: run once at `cwd` via `_run_verify_in`; exit 0 -> return `("clean", <signatures from this run>)`; non-zero -> re-run once more at the same `cwd` (the existing flakiness-guard retry, unchanged); exit 0 -> return `("clean", <union of both runs' signatures>)`; second non-zero -> return `("pre-existing-failures", <union of both runs' signatures>)`.
  Extract each run's signatures via `_extract_failure_signatures(output)` (the same helper `_signatures_for_pair` already uses in this file) and accumulate them into the returned list using the identical dedup-by-membership-then-append pattern `_signatures_for_pair` already uses (`seen: set[str]` plus an ordered `signatures: list[str]`, appending only lines not already in `seen`).
  Update the docstring's numbered steps, `Args:` (drop `project_root`), and `Returns:` (the new tuple) to match.
- **Commit:** `refactor(_verify_baseline): drop 3rd control run, return signatures alongside verdict`

### Card 7: Delete the on-demand batch path, rename checkout_path to cwd

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `compute_batch_baseline_on_demand` in full (docstring and body). Its only caller — the on-demand-compute prelude inside `_implementer_common._run_verify_gates` — is deleted in batch 4 (`implementer-gate-cleanup`); this card removing the function first does not break batch 3 or batch 4's own diffs, since neither of this batch's own edits calls it.
  In `compute_batch_baselines`: rename the `checkout_path: Path` parameter to `cwd: Path` throughout the function body, including the `effective_cwd = cwd_override if cwd_override is not None else checkout_path` line (becomes `... else cwd`). Delete the `project_root: Path` parameter and its `del project_root  # unused today; kept for signature parity/forward compat.` line entirely — with `compute_batch_baseline_on_demand` gone, there is no longer a symmetric-signature checkout wrapper to keep parity with.
  Rewrite the docstring: drop the "Unlike `compute_baseline`, this function performs NO checkout and NO teardown of its own -- `checkout_path` must already be a live, fully linked transient worktree" framing and every "ALREADY-CHECKED-OUT" contract phrase, describing `cwd` instead as simply the default working directory used when a given command's `cwd_override` is `None`. Delete the `project_root: Unused by this function's own logic today...` `Args:` entry entirely. In the `pair_cache` `Args:` entry, replace "Only ever share a cache across calls against the SAME checkout: the key carries no checkout identity" with "Only ever share a cache across calls whose commands resolve to the SAME `cwd`: the key carries no cwd identity beyond what is already part of it."
- **Commit:** `refactor(_verify_baseline): delete on-demand batch path, rename checkout_path to cwd`

### Card 8: Rewrite the unit test for the no-checkout algorithm

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete `_run_compute_baseline_capturing_worktree_add` and both of its callers in `main()` (the case asserting `-c core.longpaths=true` appears in `git worktree add` argv, and the case asserting the transient worktree basename matches `verify-baseline-<12 hex chars>`) — there is no `git worktree add` call left for either assertion to observe.
  Add a table-driven replacement asserting `compute_baseline`'s new 2-run algorithm against its `tuple[str, list[str]]` return, using a call-counting fake for `_run_verify_in`: `(0,)` (first run exits 0) -> `("clean", ...)` after exactly one run; `(1, 0)` (first run fails, retry passes) -> `("clean", ...)` after exactly two runs; `(1, 1)` (both fail) -> `("pre-existing-failures", ...)` after exactly two runs, never three. Assert the *run count* explicitly (not just the returned verdict) — deleting the third control run is a behavioral change a bare outcome assertion would not catch. Separately assert the signature half: the returned list equals the deduplicated, order-preserving union of `_extract_failure_signatures(output)` across every run actually performed in each case.
  Add a regression guard asserting `compute_baseline` performs no git operation of any kind: patch `_verify_baseline._subprocess_util.run` with a fake that raises `AssertionError` if called with any argv containing `"git"`, call `compute_baseline` with a fake `cwd` and a benign command, and confirm it still returns successfully with `_subprocess_util.run` never invoked at all — this is the regression guard against the checkout mechanism creeping back in.
  Delete `_case_n_on_demand_checks_out_pinned_sha_and_tears_down` in full (exercises the deleted `compute_batch_baseline_on_demand`, including its own `_checkout_parent_branch`/`_junction.create`/`_worktree.remove_safe` mocking).
  In `_case_e_mixed_cwd_dependency_linking`, delete the inline `_link_dependency_dirs` calls and the accompanying `_fake_junction_create`/`linked_calls` machinery (the deleted function); keep the rest of the case's `compute_batch_baselines` mixed-cwd-dedup assertions intact.
  Update every remaining `compute_batch_baselines(commands, checkout_path, project_root, ...)` call site (cases b through m) to drop the third positional `project_root` argument and rename the second positional argument's local variable from `checkout_path` to `cwd` for clarity, matching the renamed parameter.
  Remove `_link_dependency_dirs` and `compute_batch_baseline_on_demand` from the `from _verify_baseline import (...)` block at the top of the file.
- **Commit:** `test(_verify_baseline): rewrite unit test for no-checkout compute_baseline algorithm`

### Card 9: Rework the integration test for the no-checkout algorithm

- **Context:**
  - `plugins/mill/scripts/_verify_baseline.py`
- **Edits:**
  - `plugins/mill/integration_tests/test-verify-baseline.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Delete every `.scratch/verify-baseline-*` snapshot assertion (the `_scratch_snapshot` helper and its six before/after call sites across cases 1-6) and the `_new_worktree` fixture helper that creates a second real worktree for `compute_baseline` to check out from — `compute_baseline` no longer checks out anything, so there is nothing under `.scratch/` for either to observe.
  Rebuild the cases against the new `compute_baseline(cwd, module_wide_verify_cmd, *, timeout_seconds=None)` signature, calling it directly with `cwd` set to the real task-worktree fixture `_setup_hub` already builds (no second worktree needed): a "clean baseline" case; a "confirmed pre-existing failure" case reproducing across the 2-run flakiness-guard algorithm (not the deleted 3-run corroboration); a "flaky-then-passes" case. Drop the "path-sensitive deterministic failure" case and the "dependency-junction reuse" case in their current shape — the `cwd_override_relative`/re-anchoring concept the first exercised and the junction-linking the second exercised no longer exist at this layer once `compute_baseline` takes `cwd` directly; replace the "cleanup on exception" case (there is no transient worktree teardown left to test) with a `subprocess.TimeoutExpired`-propagation case, mirroring Card 8's unit-level coverage of the same behavior.
  Add the same "no git subprocess call" regression guard Card 8 adds, at this integration level, against real subprocess history rather than a mock — the end-to-end guard against the checkout mechanism creeping back in.
- **Commit:** `test(_verify_baseline): rework integration test for no-checkout compute_baseline`

## Batch Tests

`verify:` runs the unit test (`test-verify-baseline.py`), the one-line comment fix's neighboring file (`test-worktree.py`, unaffected in behavior but re-run for safety since this batch edits it), and the real-git integration test (`integration_tests/test-verify-baseline.py`) via a `&&`-chained invocation — the three files this batch's cards edit outside `_verify_baseline.py` itself, and together the direct and end-to-end consumers of every function this batch changes.
