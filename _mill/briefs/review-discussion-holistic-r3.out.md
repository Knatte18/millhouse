MILL_REVIEW_BEGIN
# Review: Non-interactive pipeline: only mill-start's interview may prompt the operator

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed)
reviewed_file: _mill/discussion.md
date: 2026-08-01
```

## Findings

### [GAP] Scope Out-list contradicts Decisions/Technical-context/Q&A on mill-merge M2
**Section:** Scope › Out; Decisions › `stays-a-genuine-halt-list`; Technical context › mill-merge/_parent_branch.py; Q&A log
**Issue:** Scope's Out list says the missing-`parent:`-row halt (M2) "stay[s] exactly as [it is]" alongside the three genuinely untouched mill-merge halts — but Decisions, Technical context, and the Q&A log all mandate an active code edit at `mill-merge/SKILL.md:45` (swap the undefined `interactive=<True unless called non-interactively>` placeholder for a hardcoded `interactive=False`, catch `ParentBranchError`, turn it into `_status.set_blocked`). Scope's In-list for mill-merge also omits this change entirely (only mentions `prompt_stale_worktree`).
**Fix:** Reconcile Scope so it explicitly lists the `_parent_branch.resolve` call-site edit as in-scope (matching Decisions/Technical-context/Q&A), and narrow the Out-list's "all four stay exactly as they are" to the three halts that truly get no code change (PR-still-open, dirty-parent-worktree, merge-lock-timeout).

### [NOTE] `test-config.py:599` fixture is unrelated to the real schema key
**Section:** Testing; Technical context (`unit_tests/_test_cfg.py:62` / `unit_tests/test-config.py:599`)
**Issue:** `test-config.py`'s `test_unknown_key_warning_emitted` uses a fully synthetic template (`_setup_plugin_template`) with no `pipeline:` section at all, so `autonomous_mode` there is just an arbitrary placeholder for "any unrecognized key" — deleting the real `pipeline.autonomous_mode` schema key has no effect on this test either way, unlike `_test_cfg.py:62` which is a genuine dead-baseline-field cleanup.
**Fix:** Clarify in Testing/Technical-context that `test-config.py:599`'s edit is optional hygiene (swap the placeholder key name to avoid reader confusion), not a required fix tied to the schema removal, to avoid a plan writer over-scoping this line.

## Verdict
GAPS_FOUND
Scope section internally contradicts three other sections on whether mill-merge's parent-branch call site changes.
MILL_REVIEW_END
