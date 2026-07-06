MILL_REVIEW_BEGIN
# Review: Fix nested-hub-layout path resolution bugs across scope violations and review CLIs

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-06
```

## Findings

### [GAP] millpy-fix.py verify read sites omitted from #604
**Section:** Scope (In) / Decision "Verify-cwd explicit field"
**Issue:** `millpy-fix.py` also reads `batch_frontmatter.get("verify")` (lines 239, 284) and joins per-batch verify strings at line 244 (`" && ".join(verify for _, verify in batch_verifies)` via `_plan_dag.iter_batch_verifies`), then routes `verify_cmd` through `finalize_from_output` -> `_run_verify_gate` with `git_root=` but no `cwd_override`; the discussion names only `millpy-implement.py` as "the actual read site." The new `{cwd, command}` mapping makes `get("verify")` return a dict — the join raises `TypeError` and a dict reaches the verify subprocess.
**Fix:** Add `millpy-fix.py` (and `_plan_dag.iter_batch_verifies`) to In-scope; route both fixer read sites through `parse_verify_field`, thread the resolved cwd as `cwd_override`, and define holistic-scope cwd semantics when batches mix `cwd` values.

### [GAP] Baseline-stage module-wide verify omitted from #604
**Section:** Decision "Verify-cwd explicit field" / Technical context
**Issue:** `_run_baseline_stage` -> `_verify_baseline.compute_baseline` executes the module-wide verify via `_run_verify_in(cmd, tmp_path)` where `tmp_path` is a fresh worktree checked out at git-root; a nested-layout hub-relative command runs at the temp git-root (MSB1009), fails twice, then the control run at `project_root` (hub) passes, so it mis-caches "clean" and wastes two runs. `compute_baseline`/`_run_verify_in` receive no resolved cwd.
**Fix:** Thread the resolved cwd into `compute_baseline`; for the temp-worktree runs the cwd must be `tmp_path / <hub-relative-prefix>` (not `hub_root`), since it is a separate checkout — state this explicitly.

### [GAP] Out-of-hub untracked files still flagged in nested layout
**Section:** Decision "compute_scope_violations rebasing"
**Issue:** `status_porcelain` reports whole-repo git-root-relative paths (verified: `repo.status()`, no pathspec). "Strip the hub prefix, then apply the `_mill/`/junction checks" leaves any untracked file outside the hub subtree (e.g. `othermodule/foo.txt`) prefix-unmatched, so it fails both checks and is flagged — reintroducing the false-positive-block class the task exists to remove, just relocated outside the hub.
**Fix:** Specify that violations are restricted to the hub subtree (drop paths not under the hub prefix) rather than only stripping the prefix; add a nested-layout test case with an out-of-hub untracked file asserting it is excluded.

## Verdict

GAPS_FOUND
Three verify/scope execution sites outside the enumerated ones break or misbehave in nested layouts.
MILL_REVIEW_END