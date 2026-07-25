MILL_REVIEW_BEGIN
# Review: mill-go CLI dispatch robustness, wiki-RPC stalls, and briefs_dir path-resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnet
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] resolve_active_hub reintroduces the daemon round-trip cluster 2 removes
**Section:** Decision "briefs_dir call sites routed through resolve_active_hub"
**Issue:** `_paths.resolve_active_hub` (`_paths.py:422-452`) calls `resolve_active_worktree`, which unconditionally calls `_marker.slug_from_branch(git_root, wiki_path, cfg)` (`_paths.py:399`) to check in-place mode — even though the caller already passed `slug` in. `slug_from_branch` hits the wiki daemon via `_list_tasks_brief_with_retry`/`wiki.list_tasks_brief` (`_marker.py:51,81`), the same `_dispatch()` retry path (worst case ~134s) cluster 2 is fixing. Worse, `resolve_active_worktree`'s try/except only catches `(MarkerError, SystemExit)` (`_paths.py:400`), not `WikiBusyError`/`WikiStartupError`, so a busy/cold daemon can crash `briefs_dir` resolution uncaught. This fires on every `--stage prepare` call in the hot per-batch dispatch path, and even when a caller passes `--slug` explicitly to avoid branch-based detection.
**Fix:** Either scope the fix to a resolver that trusts the caller's already-known `slug`/`git_root` without re-deriving via `slug_from_branch` (e.g. skip the in-place check when the caller can assert it's not in-place, or add a variant of `resolve_active_worktree` that takes `is_inplace` as a param), or explicitly acknowledge and accept the reintroduced daemon dependency and add `WikiBusyError`/`WikiStartupError` handling at each of the 8 call sites.

### [GAP] _review_plan.py's run() independently re-derives task_title outside prepare()
**Section:** Decision "On-disk-first slug/title resolution" — API-shape clarification
**Issue:** The API-shape clarification note scopes the title-threading fix to `prepare()`'s callers in `_review_code.py`/`_review_plan.py`/`_review_discussion.py`. But `_review_code.py`'s `run()` (line 644) and `_review_discussion.py`'s `run()` (docstring: "1. prepare() to render prompt") both call `prepare()` internally, so threading title through `prepare()` covers them. `_review_plan.py`'s `run()` (line 609) does **not** call `prepare()` — it duplicates plan-loading logic and calls `load_task_title(project_root, wiki_root, cfg, slug)` directly at line 692, a second call after `main()`'s `find_active_slug` (millpy-review-plan.py:131). `--stage full` is the CLI default (millpy-review-plan.py:77), so subprocess/psmux-mode plan review pays the un-merged double round-trip the fix is meant to eliminate.
**Fix:** Either thread the title into `_review_plan.py`'s `run()` too (from `main()`'s merged slug+title resolution), or explicitly note this call site as intentionally out of scope with rationale.

### [GAP] Ambiguity: does briefs_dir fix rebind project_root globally or locally
**Section:** Decision "briefs_dir call sites routed through resolve_active_hub"
**Issue:** In all 6 files, `project_root`/`hub_dir` is bound once via `resolve_hub_path()` (or `Path.cwd()`) and reused for far more than `briefs_dir` — e.g. `require_status_path(project_root, cfg)`, `plan_base`, git subprocess `cwd=`, and the `PROJECT_ROOT` template token (confirmed in `millpy-implement.py:229,266,318,583,618,640` and equivalents in the other 5 files). The Decision says "the fix touches the binding, not just the briefs_dir assignment line" but doesn't state whether `project_root` itself gets rebound (cascading to all these other uses) or a second, briefs_dir-only variable is introduced. Testing only asserts `briefs_dir` lands correctly, not whether status_path/plan_base/template-token behavior is preserved or intentionally changed.
**Fix:** State explicitly whether the fix rebinds `project_root`/`hub_dir` at its point of definition (affecting every downstream use in the file) or adds a parallel binding scoped to `briefs_dir` only, and extend the testing plan to cover whichever is chosen.

## Verdict

GAPS_FOUND
Three source-grounded gaps: a reintroduced daemon dependency, an unaddressed run()-only call site, and a binding-scope ambiguity.
MILL_REVIEW_END
