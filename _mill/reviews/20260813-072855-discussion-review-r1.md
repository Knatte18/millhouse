MILL_REVIEW_BEGIN
# Review: mill-spawn, millpy-implement, _cleanliness, discussion-review: small bugs and inconsistencies

```yaml
duration_s: 237.0
verdict: REQUEST_CHANGES
reviewer_model: sonnet
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:design] #825 batch-scope mechanism may drop never-committed dirt
**Section:** Decisions > finalize-batch-scoped-dirty-check (#825)
**Issue:** The decision defines the new scope as "dirty files whose last touch is within the current batch's own commit range" (start_sha...HEAD), reusing `_is_only_start_batch_commit`/`_content_commit_count`-style mechanisms — both confirmed (`_implementer_common.py:18-35`) to be `git log`/`git rev-list` commit-diff based, not working-tree based. `_in_scope_dirty_stuck`'s whole purpose (per its docstring) is catching in-scope files still dirty (uncommitted) at finalize. A file the current batch edited but never committed at all would not appear in any start_sha...HEAD commit diff, so the described mechanism would silently stop flagging exactly the everyday "implementer forgot to commit" case the gate exists for — not just the reported false-positive (prior-batch file re-dirtied). The decision also drops `compute_terminal_dirt`'s unconditional `task_dir`-subtree inclusion without saying whether that's intentional.
**Fix:** Specify concretely how "touched since start_sha" is computed for currently-dirty, never-committed paths (e.g. union of commit-diff paths AND paths under task_dir), not just commit-range membership; confirm whether task_dir's blanket inclusion is retained.

### [NIT:scope] #818 "unknown" propagation omits markdown-driven callers
**Demoted-from:** BLOCKING
**Section:** Decisions > cleanliness-unresolvable-parent-diff (#818); Technical context
**Issue:** The decision names `_in_scope_dirty_stuck` (`_implementer_common.py`) and "mill-go's terminal cleanliness gate" as the two callers needing to escalate on "unknown," but the actual terminal-gate caller is markdown pseudocode in `plugins/mill/skills/mill-go-base/handoff.md` ("Terminal cleanliness gate": `in_scope_dirt = _cleanliness.compute_terminal_dirt(...)`, then "If it is STILL non-empty ... halt" / "If the list is empty, proceed" — binary, no unknown branch) and `SKILL.md`'s step 2b (`revert_out_of_scope_drift` → `if in_scope_dirt is non-empty` / `if in_scope_dirt is empty`, same binary shape). Neither file is cited in Technical context, Scope, or Testing. `None` is falsy exactly like `[]`, so an unspecified "unknown" encoding risks silently collapsing into "clean" at the real production call site — the opposite of #818's stated intent.
**Fix:** Add `plugins/mill/skills/mill-go-base/handoff.md` and `SKILL.md` (step 2b) to the affected-artifact list; specify the concrete "unknown" encoding for `revert_out_of_scope_drift`'s 2-tuple return and require both markdown gates be updated with an explicit third branch.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps: #825's scoping mechanism may miss uncommitted dirt; #818's propagation omits markdown-driven callers.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 1._
MILL_REVIEW_END
