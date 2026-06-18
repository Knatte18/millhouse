The test-merge.py uses worktrees layout `<container>/worktrees/<slug>` (hub-form default), but `resolve_active_hub` (the helper the discussion mandates for mill-merge) expects `container_path / "wts" / slug` (per `_paths.py:397`). The existing integration test uses `worktrees/` not `wts/`. This is a feasibility note: the new nested-hub scenario test must build the `wts/`-form layout for `resolve_active_hub` to find the worktree, OR the test exercises the squash sequence directly without calling `resolve_active_hub`. The discussion's test plan (testing section, line 211-217) describes the git-level squash sequence directly and does not depend on `resolve_active_hub`, so this is workable — but worth noting the layout mismatch so the implementer doesn't assume the existing fixture's `worktrees/` path works with the hub resolver.

I have enough to render the review. Let me compile findings. The discussion is well-structured with clear decisions, rationale, rejected alternatives, scope in/out, constraints, and testing. The main genuine gap is the drift-guard `_client`/subpackage matching. Let me also note the "register in run-all.py" inaccuracy and the test-layout note.

MILL_REVIEW_BEGIN
# Review: Fix nested-hub path resolution and SKILL.md vs shipped-API mismatches

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-18
```

## Findings

### [GAP] Drift-guard mis-flags wiki subpackage helpers (_client.*)
**Section:** Decisions › drift-guard scope; Testing › Drift-guard unit test
**Issue:** The test resolves `_<module>.<fn>(` against "functions defined in `plugins/mill/scripts/*.py`" (non-recursive), but `_client` lives only at `scripts/wiki/_client.py`; ~8 SKILL files reference `_client.list_tasks_brief/get_task/set_phase/upsert_task/health_check`, none of which would resolve, producing false-positive failures that the "small allowlist" cannot absorb without defeating the guard.
**Fix:** State that the scan recurses into `scripts/` subpackages (e.g. `wiki/`) so subpackage-qualified helpers resolve, rather than relying on the allowlist for a heavily-used shipped module.

### [NOTE] "Register in run-all.py" is a no-op
**Section:** Scope › drift-guard; Technical context; Testing
**Issue:** The discussion says to register the new test in `run-all.py`, but `run-all.py` auto-discovers every `test-*.py` by glob — there is no registration step (only the `SKIP` frozenset, which a passing test should stay out of).
**Fix:** Drop the "register" instruction or reword to "ensure the filename matches `test-*.py` so auto-discovery picks it up".

### [NOTE] Nested-hub test fixture layout vs resolve_active_hub
**Section:** Testing › nested-hub squash safety
**Issue:** Existing `test-merge.py` builds `<container>/worktrees/<slug>`, but `resolve_active_hub` expects `container/"wts"/slug` (`_paths.py:397`); the new scenario should drive the git squash sequence directly (as the test plan already does) and not assume the existing fixture path works with the hub resolver.
**Fix:** Note that the nested-hub scenario exercises the squash/restore-from-HEAD sequence at the git level and need not route through `resolve_active_hub` unless the fixture is rebuilt in `wts/`-form.

## Verdict

GAPS_FOUND
One feasibility gap in the drift-guard matching rule must be resolved before planning.
MILL_REVIEW_END