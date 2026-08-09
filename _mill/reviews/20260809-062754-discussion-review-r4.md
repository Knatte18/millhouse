MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] `--reviews-subdir` plumbing omits the actual finalize-stage call site
**Section:** Decision `mill-plan-revise-reentry`, third paragraph from end ("This requires a new `--reviews-subdir <name>` flag…").
**Issue:** The decision only names `_review_plan.py`'s `reviews_dir = resolve_path(...)` sites (`prepare()` line ~369, `run()` line ~696). Verified in source: Agent-mode `--stage finalize` in `millpy-review-plan.py` computes `reviews_dir` independently at its own line 223 (`reviews_dir = resolve_path(cfg["paths"]["reviews_dir"], slug)`), then calls `_review_plan.finalize(..., reviews_dir=reviews_dir, ...)` — `finalize()` takes `reviews_dir` as a caller-supplied parameter and never re-resolves it itself. Since prepare and finalize are separate CLI invocations with no shared state, and the prepare envelope carries no `reviews_dir` field, a `--reviews-subdir` override threaded only through `_review_plan.py` would correctly namespace round *discovery* at prepare time but finalize would still write the round file to the *original* `reviews_dir` — defeating the entire point of the namespace (round-file collision / wrong-directory write).
**Fix:** Add `millpy-review-plan.py` line ~223 as a third required plumbing site (or have prepare's envelope carry the resolved `reviews_dir`/subdir so finalize doesn't independently re-resolve it).

### [GAP] Inferred-success observability call site doesn't cover the step-6.5 recovery path
**Section:** Decision `implementer-status-line-omission`, second paragraph ("Call it, and only it, directly inside step 4(b)'s Clean mid-work stop `status: success` sub-case…").
**Issue:** The new `_status.append_inferred_success_log` call is scoped only to step 4(b)'s direct Clean-mid-work-stop `status: success` branch (`mill-go/SKILL.md` line ~273). But step 6.5's own "After recovery" bullet 3 (line ~342) explicitly re-parses a fresh finalize envelope after warm-`SendMessage`/`--resume-incomplete` recovery and states "`status: success` (**or inferred success**) means the batch finished — proceed normally" — a structurally separate branch from step 4(b) that the decision's single call site does not touch. An implementer that first goes `incomplete` (no JSON, partial commits) and then completes on a resumed turn without emitting JSON would produce an `inferred: true` envelope that goes unlogged, silently undermining the stated goal (visibility into every occurrence of the protocol violation).
**Fix:** Either add a mirrored call at step 6.5's "After recovery" success branch, or state explicitly that the observability note is deliberately first-turn-only and why that's sufficient.

### [NOTE] Tree-guard checkpoint grouping miscounted in Technical context
**Section:** Technical context, "The 12 tree-guard checkpoint call sites (#783) span two sections…"
**Issue:** Described as "six pre/post pairs plus one combined-form occurrence at line 638," but the verified 12 line numbers (638, 675, 710, 775, 780, 1026, 1038, 1079, 1088, 1093, 1126, 1133) actually form five pre/post pairs plus two standalone combined-form occurrences (638 and 1026) — not six pairs plus one.
**Fix:** Correct the summary to "five pre/post pairs plus two combined-form occurrences (lines 638, 1026)"; the explicit 12-line list itself is accurate and unaffected.

## Verdict

GAPS_FOUND
Two source-grounded implementation gaps in the `--revise` and inferred-success-observability decisions block plan writing.
MILL_REVIEW_END
