I've verified the discussion's claims against source. Key validations:
- #552: `parse_blocking_count` (line 1328) is heading-regex-only -- confirmed; `finalize_scope` (1423-1424) calls it for both severities.
- #553: `millpy-review-discussion.py:98` uses `resolve_task_path(git_root, ...)` with a deliberate counter-comment; mill-start `SKILL.md:53,56,189` anchors `_mill/` and stages `_mill/briefs/` from `resolve_hub_path()` (hub_dir) -- confirming the brief written under git_root is never staged. The hub_dir fix is correct.
- #554: `_run_verify_gate` (line 350) uses `cwd=project_root` -- confirmed.
- #561: gate insertion point (between SKILL.md 712 and 716) correctly precedes both `append_phase("done")` and the wiki flip to ready-to-merge.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-28
```

## Findings

### [NOTE] #556 global shutdown vs parallel dotnet verifies
**Section:** Decisions / #556
**Issue:** `dotnet build-server shutdown` is machine/user-global, not worktree-scoped; if two mill tasks run dotnet verifies concurrently, one task's post-verify shutdown can kill another's in-flight build server, reintroducing the exact transient lock failures #556 targets -- concurrency is not addressed.
**Fix:** State the assumption that the builder lock serializes builds across tasks (so no overlap), or scope/guard the shutdown accordingly.

### [NOTE] #561 done_gate dotnet leak not covered by #556 cleanup
**Section:** Decisions / #561 + #556
**Issue:** The #556 build-server shutdown lives in `_run_verify_gate`, but the #561 done_gate runs as an inline SKILL.md `_subprocess_util.run` command; a dotnet done_gate leaks processes whose file locks can then surface in mill-finalize's full-suite verify.
**Fix:** Note that the done_gate should also run `dotnet build-server shutdown` (or otherwise reuse the #556 cleanup) when the gate command is dotnet-based.

## Verdict

APPROVE
All five fixes are source-grounded and well-specified; the two NOTEs are non-blocking refinements.
MILL_REVIEW_END
