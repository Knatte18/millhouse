MILL_REVIEW_BEGIN
# Review: Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-28
```

## Findings

### [BLOCKING] verify: commands only in Batch Index, not batch frontmatter
**Location:** 00-overview.md Batch Index + all 4 batch files' own frontmatter (01-04)
**Issue:** Each batch file's own top-of-file `verify:` field is `null` (confirmed in 01/02/03/04); the real `--only` commands exist only in the overview's Batch Index `batches:` entries. `_plan_dag.iter_batch_verifies` reads verify exclusively via `_read_batch_frontmatter(batch_path)` — each batch FILE's own yaml block — never the Batch Index; its docstring says so explicitly, and `mill-merge-in/SKILL.md`'s Verify step states "If `iter_batch_verifies` returns `[]` (no plan, or every batch had null verify) -> skip verify entirely." `millpy-fix.py`'s holistic prepare/finalize consumes the same iterator. With all 4 batches null at the frontmatter level, both consumers see `[]` and silently treat this task as if it were docs-only, never replaying `test-review-plan-flow.py` / `test-review-common.py` / `test-review-templates.py` / `test-plan-validate.py` at merge time or during a holistic fix pass. `plan-batch.md`'s template instructs the batch's own frontmatter to carry the real command ("Non-null verify: commands MUST start with 'PYTHONPATH= '") — this plan diverges from that with no Shared Decision explaining why.
**Fix:** Set each of the 4 batch files' own frontmatter `verify:` to the same command already declared in its Batch Index entry.

### [BLOCKING] Cards 9/10/11/13 miss _review_common.py in Context:
**Location:** Batch 2 (review-plan-counting-tests), Cards 9, 10, 11, 13
**Issue:** Requirements: name `resolve_existing_paths` (Card 9), `finalize_scope()` (Cards 10 and 13), and `parse_verdict` / `count_unrecognized_severity_findings` (Card 11) — all defined in `_review_common.py` — but each card's Context: lists only `plugins/mill/scripts/_review_plan.py` (Cards 9–11) or "none" (Card 13); `_review_common.py` is absent from Context:/Edits: in all four. Batch 1's Cards 1, 2, 4, and 6 correctly add `_review_common.py` to Context: whenever they name a symbol from it, so this is an internal inconsistency within the same plan, not a genuinely ambiguous case.
**Fix:** Add `plugins/mill/scripts/_review_common.py` to `Context:` for Cards 9, 10, 11, and 13.

### [NIT] Batch 2 scope overstates blocking_count==0 coverage
**Location:** Batch 2 (review-plan-counting-tests), "## Batch Scope"
**Issue:** The scope text says "the existing error-path tests already covering `blocking_count == 0` on those sites are left untouched," justifying why Cards 3/5's hardcoded `"nit_count": 0` additions get no new tests. But Tests 4/16/20/21 (the tests actually exercising those 6 catch sites) assert only `verdict == "ERROR"` and error-message content — none pins `blocking_count` or the value of the hardcoded literal.
**Fix:** Correct the rationale to the real justification (aggregation uses `sum(r.get("nit_count", 0) ...)`, which tolerates a missing/wrong key, so a dedicated assertion has low marginal value) or add a one-line key assertion to one of those tests.

## Verdict

REQUEST_CHANGES
verify: placement defeats mill-merge-in's replay step; four Batch 2 cards omit _review_common.py from Context.
MILL_REVIEW_END
