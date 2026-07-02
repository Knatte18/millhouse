I have verified the discussion's source claims thoroughly. All the precise line references (`_run_verify_gates`, the `nits_only` guard at 894-898, mill-go step 4 lines 125/129/156/158/161, the fixer-template sentences, the millpy-fix.py token maps, and the `_junction.strip_all_in_worktree` vestigial-`junctions_cfg` docstring) are accurate. One core mechanism, however, rests on a config convention that does not exist.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Baseline dependency-dir source does not exist
**Section:** Decisions -> baseline-aware module-wide verify gate (also Scope line 53)
**Issue:** The baseline computation must junction "the task worktree's known dependency directories ... whichever the project's own venv-check/dependency convention already names -- mirror the existing per-project `verify:`/venv-check pattern in `mill-config.yaml`," but `mill-config.yaml` (hub and template) has no `verify:` field and no venv/dependency-dir convention at all (verify comes from the plan overview frontmatter via `overview_frontmatter.get("verify")`, and the only junction keys are `.wiki`/`.portals`); grep for venv/node_modules/vendor across all yaml returns nothing, so a plan writer has no defined source enumerating which directories to junction, yet is told not to invent one.
**Fix:** Name the concrete source of the dependency-directory list -- either specify a fixed set (`.venv`/`node_modules`/`vendor`) the baseline stage probes-if-present, or add an explicit `dependency_dirs:` (or venv-check) key to `mill-config.yaml`'s schema as part of this task's scope.

### [NOTE] Spurious baseline failure fails unsafe (disables #541 gate)
**Section:** Decisions -> baseline-aware gate; Rejected (d)
**Issue:** The fail-safe reasoning only covers computation *exceptions* (fall back to strict). A clean non-zero verify exit in the transient worktree -- e.g. a relocated venv whose internal absolute paths point at the task worktree, a path-sensitive test, or the flaky-registry case rejection (d) itself acknowledges -- caches `"pre-existing-failures"` and silently skips the module-wide gate for the whole task, the exact opposite of "fully preserve #541 in the common case." A false `"clean"` costs one over-strict gate (safe); a false `"pre-existing-failures"` removes the regression gate (unsafe) -- this asymmetry is unaddressed.
**Fix:** State how a spurious transient-worktree failure is guarded (e.g. treat a *first-ever*/unexpected baseline red as inconclusive -> run strict, or require corroboration) rather than defaulting straight to gate-disable.

## Verdict

GAPS_FOUND
Baseline junction mechanism cites a mill-config convention that does not exist; resolve the dependency-dir source before planning.
MILL_REVIEW_END