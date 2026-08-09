MILL_REVIEW_BEGIN
# Review: _verify_baseline.py transient worktrees can be orphaned when the task worktree is force-removed mid-computation — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-09
```

## Findings

### [BLOCKING] Card 2 references `_verify_baseline._checkout_parent_branch` without listing its file in Context
**Location:** Batch 01, Card 2, Requirements step 3
**Issue:** Requirements text says the nested-worktree test step "mirror[s] `_verify_baseline._checkout_parent_branch`'s real detached-HEAD behavior," naming a specific function from `plugins/mill/scripts/_verify_baseline.py`, but that file is not listed in Card 2's `Context:` (only `_worktree.py`) or `Edits:` (`test-worktree.py`).
**Note:** Verified against source — `_checkout_parent_branch` actually runs `git worktree add <tmp_path> <parent_sha>` (no `-b`, no explicit `--detach`, plus `-c core.longpaths=true`), which is only loosely analogous to the card's literal `git worktree add --detach <nested_path> HEAD`; the implementer cannot check this "mirrors real behavior" claim without cold-start exploration of the unlisted file.
**Fix:** Add `plugins/mill/scripts/_verify_baseline.py` to Card 2's `Context:` list, or drop the "mirrors real behavior" justification and rely solely on the already-spelled-out literal git commands.

## Verdict

REQUEST_CHANGES
Card 2 names a function from a file absent from its Context list, per the Context-completeness rule.
MILL_REVIEW_END
