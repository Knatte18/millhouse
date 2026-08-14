MILL_REVIEW_BEGIN
# Review: mill-go/millpy-implement: Windows dotnet build-server file-lock races in verify/baseline stages — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-14
```

## Findings

### [BLOCKING:scope] Requirements name symbols from files absent from Context
**Location:** Card 3, Card 5 (`_safe_rmtree.safe_rmtree`/`_safe_rmtree._blacklist_for`/`_safe_rmtree.shutil.rmtree`); Card 6 (`_parent_branch.resolve`, `_verify_baseline._checkout_parent_branch`/`_link_dependency_dirs`/`compute_batch_baselines`).
**Issue:** Each card's `Requirements:` mentions functions from `_safe_rmtree.py` / `_parent_branch.py` / `_verify_baseline.py`, but none of those files appear in `Context:` (Card 3's is `none`; Card 5/6's is `_worktree.py` only) or `Edits:`.
**Mitigating factor:** all three cards give fully verbatim code/patch targets copied from an adjacent existing block in the same Edits: file, so no live exploration is actually required — but this is a literal violation of the stated bright-line rule.
**Fix:** add `plugins/mill/scripts/_safe_rmtree.py` to Card 3/5's `Context:`, and `plugins/mill/scripts/_parent_branch.py` + `plugins/mill/scripts/_verify_baseline.py` to Card 6's `Context:`.

### [NIT:consistency] Card 2 references undefined helper-function names for mocks
**Location:** Batch 1, Card 2 (Test I1–I4).
**Issue:** `failing_result(...)`, `passing_result(...)`, `failing_result_2(...)` read as calls to pre-existing test helpers, but no such functions exist in `test-implementer-common.py` — only the local-variable convention `shutdown_result = unittest.mock.MagicMock()` (seen in `Test C`) exists.
**Fix:** clarify these are shorthand for inline `MagicMock()` construction (as the parenthetical "(3 MagicMocks in order)" already implies), not existing helpers.

## Verdict

REQUEST_CHANGES
Add the three missing Context: entries (_safe_rmtree.py, _parent_branch.py, _verify_baseline.py); otherwise the plan is exceptionally well source-grounded.
MILL_REVIEW_END
