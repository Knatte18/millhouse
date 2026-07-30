MILL_REVIEW_BEGIN
# Review: mill-plan: Requirements find/replace fences lose byte-exactness under list-nested indentation — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; exact point version not independently verifiable)
reviewed_file: plan/
date: 2026-07-30
```

## Findings

### [BLOCKING] Card 3 test-insertion anchor points to the wrong file location
**Location:** Batch 01, Card 3, Requirements bullet 1
**Issue:** The card says to insert the nine new test *function definitions* "immediately after `test_check_context_completeness_dirty_line_range_suffix_missing` ... and before the `# skip_checks filtering (Card 7 / #188)` comment (around line 4972-4973)." Verified against `test-plan-validate.py`: that function's body ends at line ~2046, but the `# skip_checks filtering (Card 7 / #188)` comment occurs exactly once in the file, at line 4973 — inside `main()`'s `tests = [...]` list literal, ~2900 lines away. Following the anchor literally would place `def test_...():` statements mid-list-literal, breaking the module.
**Fix:** Split into two distinct, correctly-anchored instructions: function defs go immediately after line ~2046 (end of `test_check_context_completeness_dirty_line_range_suffix_missing`'s body); only the `tests = [...]` *name entries* belong near line 4972-4973 (as the card's second sentence already correctly states).

### [BLOCKING] Error `message` format disagrees between Card 1 (impl) and Card 2 (docs)
**Location:** Batch 01, Card 1 item 4 vs. Card 2 requirement 1
**Issue:** Card 1's authoritative message spec is `f"card {card_num}'s Requirements: fence {fence_idx} matches '{matched_token}' after stripping {n} leading spaces per line (found N={n})"` — it carries only a numeric `fence_idx`, never a text snippet of the fence body. Card 2's SKILL.md fix-table row text instructs: "Locate the card's `Requirements:` fence identified by the error payload's `message` (its first line/snippet and the reported strip amount `N`)" — claiming a content snippet is present when it isn't. This is precisely the kind of cross-card drift the batch's own single-session rationale ("the fix-table row's prose must exactly describe the check's mechanical-fix semantics") is designed to prevent, and it originates from a similar internal inconsistency already present in `_mill/discussion.md`'s Technical-context prose vs. its own worked example.
**Fix:** Make Card 2's fix-table prose (and Card 3 test 6's "or by asserting the message's content snippet matches..." alternative phrasing) reference `fence_idx` only, matching Card 1's actual message shape — or, if a content snippet is actually desired, add it to Card 1's message format first.

### [NIT] "Three new module-level pieces" imprecisely describes 4 functions + 1 nested regex
**Location:** Batch 01, Card 1, Requirements opening sentence
**Issue:** The card opens "Add three new module-level pieces... All three regexes/constants below are written fresh for this check," then enumerates four items (three helper functions plus the check function itself), two of which define regexes locally inside a function body (not module-level), with only the fence regex in item 4 being truly module-level.
**Fix:** Reword to avoid the "three"/"module-level" count mismatch, or simply drop the summary sentence since each numbered item is unambiguous on its own.

## Verdict

REQUEST_CHANGES
Two BLOCKING cross-reference/location errors in Card 3's test-insertion anchor and Card 1/2's message-format drift.
MILL_REVIEW_END
