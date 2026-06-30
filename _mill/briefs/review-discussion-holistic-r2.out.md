I have verified the key claims. Producing the review.

MILL_REVIEW_BEGIN
# Review: Split mill-ghissues-to-tasks into source adapter + source-agnostic analysis

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-06-30
```

## Findings

### [GAP] embed_body missing from adapter decisions + tests
**Section:** Decisions — `_gh_issues.to_contract()` / `_sandbox_report.py`; Testing
**Issue:** `embed_body` is introduced as a required contract field (Decision 3, r1 follow-up), but Decision 4 lists `to_contract()` setting only `ref_prefix/detail_hint/source` and Decision 5 lists `read()` setting only `ref_prefix=""`/`detail_hint=None`; the Testing section likewise asserts neither `embed_body=false` (ghissues) nor `embed_body=true` (sandbox-report). A plan writer following Decisions 4/5 verbatim would omit it.
**Fix:** State that `to_contract()` sets `embed_body=false` and `_sandbox_report.read()` sets `embed_body=true`, and add an assertion for each in the two test sections.

### [GAP] Empty `items`: Decision 5 contradicts Testing
**Section:** Decisions — `_sandbox_report.py` validates strictly; Testing
**Issue:** Decision 5 says `read()` "requires `items` to be a non-[empty?] list" (text garbled as "non-... list"), but the Testing section says "missing/empty `items` is accepted (empty list, not an error)". These are directly opposed — the reader either rejects or accepts an empty `items`.
**Fix:** Pick one: `read()` accepts an empty `items` list (the "nothing to do" path is the entry skill's job) and fix Decision 5's wording to require only that `items` be a list with every present entry well-formed.

### [GAP] embed_body not applied to fold-in bodies (sandbox detail loss)
**Section:** Q&A (fold-in support) / Decision 3 rationale
**Issue:** Q&A says the shared skill handles fold-ins "identically for both sources" (append `- Sources: <ref> — <title>`), but `embed_body`'s whole rationale is that sandbox-report detail is lost once the local JSON is deleted. A folded-in sandbox item would then permanently lose its `body` — the exact failure `embed_body` exists to prevent.
**Fix:** State whether `embed_body` also governs the fold-in append (embed the item `body` under the fold-in Sources bullet when `embed_body=true`), or explicitly accept the loss for fold-ins.

### [NOTE] detail_hint `{ref}` ambiguous for grouped multi-source tasks
**Section:** Decision — triage-report contract carries ref-display fields
**Issue:** `detail_hint` is a single-`{ref}` template, but a grouped new task has multiple source refs; the discussion does not say whether the hint line is emitted once per task (which ref?) or once per Sources bullet.
**Fix:** Specify per-source vs per-task emission for `detail_hint` and, if per-task, which ref fills `{ref}`.

### [NOTE] "all-skipped" detection split across entry/shared skill
**Section:** Decision — `mill-report-to-tasks` entry check; Testing
**Issue:** "nothing to do" is called the entry skill's job, but "every item ends up skipped" is only knowable after the shared skill performs grouping/skip routing, which the entry skill cannot pre-detect.
**Fix:** Clarify that the entry skill handles only the empty-`items` short-circuit, while all-skipped "nothing to do" is reported by the shared skill (no proposal/no wiki writes).

## Verdict

GAPS_FOUND
embed_body wiring, empty-items contract, and fold-in detail handling are underspecified or contradictory.
MILL_REVIEW_END