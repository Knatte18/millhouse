MILL_REVIEW_BEGIN
# Review: Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] `--reviewer` unknown-alias path raises uncaught `ReviewerError`, not `ReviewError`
**Section:** Decisions > reviewer-flag-validation; Testing > "Unknown alias"
**Issue:** `_reviewers.resolve()` raises `_reviewers.ReviewerError` on an unknown name (`_reviewers.py:47`, raised at `:385-387`) — a class unrelated to `_review_common.ReviewError` (`_review_common.py:101`; both extend `Exception` directly, no shared base). The validation Decision covers only post-resolve spec checks (cluster type; `model_to_tier`'s `ValueError`) — it never says to catch `ReviewerError` around the initial `resolve()` call itself, and no existing helper converts one to the other. `millpy-review-discussion.py`'s `--stage prepare` and `--stage full` blocks (lines 118-152, 195-204) catch only `except ReviewError`, no catch-all — an unknown `--reviewer` alias crashes with a raw traceback there instead of the JSON `ERROR` envelope the Testing section promises ("this test confirms it propagates through the CLI layer's `print_error_envelope` correctly"). Every other `_reviewers.resolve`-adjacent call site in this codebase needs its own dedicated `except _reviewers.ReviewerError` clause (e.g. `millpy-review-discussion.py:101`, `millpy-review-plan.py:126`, `millpy-fix.py:347`) — this is a recurring, non-automatic requirement, not an incidental one. `millpy-review-plan.py` happens to have a broad `except Exception` catch-all in the same two blocks (lines 201-203, and the `else: # full` block) that would mask the crash there, but with a different message prefix ("unhandled review error: ...") than the clean `ReviewerError` text the Testing section describes reusing, and the discussion never names this catch-all as the intended mechanism.
**Fix:** Add to Technical Context: the new `reviewer_override` resolution in `_review_discussion.py`/`_review_plan.py` must wrap `_reviewers.resolve(registry, reviewer_override)` itself in `try/except _reviewers.ReviewerError`, re-raising as `_review_common.ReviewError`, for both CLIs uniformly.

### [NOTE] Schema doc's canonical example block not listed for the new field
**Section:** Technical context — review-output.schema.md
**Issue:** Only the field table (line ~44-49) is named for the `reviewer_self_id` addition; the "File format" fenced example above it (lines 9-17) is the doc's own worked example and would go stale/inconsistent with the table once the field ships.
**Fix:** State whether the top example block should also gain a `reviewer_self_id:` line, or that its omission from the terse example is intentional.

## Verdict

GAPS_FOUND
Unresolved exception-type mismatch (ReviewerError vs ReviewError) would crash the discussion CLI's unknown-alias path instead of erroring cleanly.
MILL_REVIEW_END
