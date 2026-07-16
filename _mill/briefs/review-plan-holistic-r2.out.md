MILL_REVIEW_BEGIN
# Review: Miscellaneous small tooling and doc/template accuracy gaps — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [BLOCKING] Card 4 new tests never run — missing runner registration
**Location:** Batch 1, Card 4 (test-reviewers.py)
**Issue:** `test-reviewers.py`'s `main()` runs an EXPLICIT `tests = [...]` list (lines 968-1015), not auto-discovery; a function that is only defined but not appended to that list silently never executes, so `verify:` passes green with zero added coverage — the card's Requirements name the new `test_*` functions but never instruct adding them to the `tests` list.
**Fix:** Add a Requirements clause: append every new `tier_rank`/`fixer_weaker_than_reviewer_warning` test function to the `tests = [...]` list in `main()`.

### [NIT] Card 5 full-stage run would invoke the real LLM
**Location:** Batch 1, Card 5 (test-millpy-fix.py)
**Issue:** `setUp` does not mock `_implementer_claude.run`; a literal "run the CLI end-to-end via `self._run_main`" full-stage call (as the card instructs) reaches the real `_implementer_claude.run` dispatch, since the warning is emitted before the stage branch anyway.
**Fix:** Have the card either patch `_implementer_claude.run` (as `test_batch_happy_path` does) or dispatch `--stage prepare`, which fires the warning without an LLM call.

### [NIT] Card 2 Context omits _reviewers.py
**Location:** Batch 1, Card 2 (millpy-fix.py)
**Issue:** Requirements reference `_reviewers.fixer_weaker_than_reviewer_warning` (created in Card 1), `_reviewers.resolve`, and `_reviewers.ReviewerError`, but `_reviewers.py` is not in Card 2's `Context:`/`Edits:` (mitigated: `_reviewers` is already imported/used in the edited millpy-fix.py and the call signature is inlined).
**Fix:** List `plugins/mill/scripts/_reviewers.py` under Card 2 `Context:` for completeness.

## Verdict

REQUEST_CHANGES
Card 4's new tests are unregistered and would silently never run; two nits.
MILL_REVIEW_END
