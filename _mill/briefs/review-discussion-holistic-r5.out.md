MILL_REVIEW_BEGIN
# Review: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; cannot verify with certainty)
reviewed_file: /home/knatte/Code/millhouse/wts/review-pipeline-consistency-bugs/_mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] Load-bearing example for finalize-outer-catch reachability is false
**Section:** "error_kind bucketing" Decision; "round: 0 fix" Decision; Technical Context (millpy-review-plan.py bullet).
**Issue:** Both Decisions repeatedly justify keeping/wiring the finalize-stage outer `except ReviewError` (millpy-review-plan.py:307-309, millpy-review-discussion.py:245-247) via the example "`resolve_blocking_classes` failing on bad config." Direct read of `resolve_blocking_classes` (`_review_common.py:2614-2645`) shows its docstring states "Never raises" and its body confirms this: every missing/malformed config path falls back to `DEFAULT_BLOCKING_CLASSES[role]` rather than raising. In every `finalize()` wrapper (`_review_plan.py:704`, `_review_discussion.py:192`, `_review_code.py:573`), `resolve_blocking_classes` is the *only* statement between function entry and the internal `try/except ReviewError` wrapping `finalize_scope` — so with this example false, no other ReviewError source reaches that outer catch either. The site the "round: 0 fix" Decision most carefully hand-tuned (`round_n` vs `args.round`) is, under current code, effectively unreachable/dead.
**Fix:** Either name a call site that genuinely can raise `ReviewError` at that point, or explicitly state the outer catch is defensive-only (not exercised by any known live path) and add a Testing-section item for how the `round_n`-threading fix there gets verified without a real trigger (e.g. a direct unit test of the wiring, not an end-to-end repro).

### [NIT:consistency] Wrong end-lines cited for two finalize() functions
**Section:** Technical Context; "error_kind bucketing" Decision rationale.
**Issue:** `_review_discussion.py::finalize` is cited as "lines 153-227" but direct read shows the function runs 153-246 (227 is only the internal catch block's closing line, not the function's). `_review_code.py::finalize` is cited as "lines 519-607" but actually runs 519-626 (607 is likewise only the catch block's end). By contrast `_review_plan.py::finalize` is cited correctly as 662-746. Both wrong citations look copy-pasted from the catch-block end rather than the function end.
**Fix:** Correct to 153-246 and 519-626 respectively wherever cited.

## Verdict

REQUEST_CHANGES
One BLOCKING: a load-bearing Decision example (resolve_blocking_classes raising) is contradicted by source; a NIT line-range slip.
MILL_REVIEW_END
