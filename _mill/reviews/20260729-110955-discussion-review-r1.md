MILL_REVIEW_BEGIN
# Review: Cross-machine resume, wiki-daemon health-check, and hub-in-subdirectory config resolution gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Phase 1 unconditional halt blocks the new repair phase from ever running
**Section:** Decisions > mill-resume-detection-point; Scope
**Issue:** `mill-resume/SKILL.md` Phase 1 (lines 29-33, verified) unconditionally "stop"s when `.millhouse/config.local.yaml` or `.wiki` is missing. Scope says the new phase is "inserted after Phase 1, not renumbering existing phases," implying Phase 1's own content is untouched — but if Phase 1 still halts unconditionally, no later phase (including the new repair phase) can ever execute in exactly the scenario it targets.
**Fix:** Clarify whether Phase 1's halt logic itself must change (branch on `_mill/status.md` presence before halting) or whether "insert after" was meant loosely to include modifying Phase 1's condition.

### [GAP] millpy-validate-plan.py fix leaves two more cwd-rooted call sites unaddressed
**Section:** Decisions > load-config-validate-plan-included; Technical context (load_config call sites)
**Issue:** The decision fixes only `mill_dir` (verified `Path.cwd() / ".millhouse"` at validate-plan.py:39). But `project_root = Path.cwd()` (line 38) is also passed to `find_active_slug(project_root, wiki_root, cfg)` — whose first parameter is named `hub_root` in `_review_common.py:306` — and to `_plan_validate.run(plan_dir, project_root, ...)`, whose docstring at `_plan_validate.py:1455` states `project_root` "also doubles as the hub_root." Both are the identical cwd-vs-hub-root bug class, unfixed, in a hub-in-subdirectory layout.
**Fix:** Decide whether `project_root` in validate-plan.py should also become `_paths.resolve_hub_path()` (matching the reference-correct pattern in `millpy-review-code.py:112`), or state explicitly why it's out of scope.

### [GAP] No behavior specified for relocate-target-path collision
**Section:** Decisions > mill-resume-relocate-then-scaffold; Testing
**Issue:** `git worktree move <old> <canonical>` is not addressed for the case where `<container>/wts/<slug>` already exists (stale entry, or another worktree occupying the canonical slot) — plausible precisely because the reported scenario already has a worktree living somewhere non-canonical.
**Fix:** Specify the collision behavior (halt with message vs. other) and add a corresponding Testing scenario alongside the existing dirty-worktree and decline-confirmation cases.

### [NOTE] Existing git-validity-check pattern in _sync.commit_push not surfaced
**Section:** Technical context; Decisions > wiki-health-check-scope
**Issue:** `wiki/_sync.py`'s `commit_push()` (lines ~206-225, verified) already runs `git rev-parse --git-dir` and raises `WikiPushError` with a clear "not a git repository" message — the exact validity check `_handle_health` needs — but Technical Context cites only `pull()`/`commit_push()` as reuse targets without mentioning this inline check as a factoring/reuse candidate.
**Fix:** Note the existing check at `_sync.py:206-225` as a reuse/extraction candidate so `_handle_health`'s validity logic doesn't duplicate it inconsistently.

## Verdict

GAPS_FOUND
Three GAPs: mill-resume phase-flow contradiction, incomplete validate-plan.py fix scope, unaddressed relocate collision.
MILL_REVIEW_END
