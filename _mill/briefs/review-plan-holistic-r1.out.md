MILL_REVIEW_BEGIN
# Review: Auto-approve on review-round cap — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-18
```

## Findings

### [NIT:consistency] New key missing from mill-go-base Entry step 2 key inventory
**Location:** batch 3 (Card 6) / batch 4 (Card 8) **Issue:** `mill-go-base/SKILL.md` Entry step 2's "Read these keys:" list (lines 54-66) enumerates every `roles.code-review.batch.*`/`roles.code-review.holistic.*` key the file reads, including the sibling `rounds`/`min_rounds` keys, but neither batch adds a corresponding bullet for the new `auto_approve_on_cap` key even though it's read (per Card 6/8) at named use sites later in the same file. **Fix:** Add one bullet each to the Entry step 2 list, e.g. `roles.code-review.batch.auto_approve_on_cap` / `roles.code-review.holistic.auto_approve_on_cap` — treat these as inventory-list-only additions (no named local at Entry itself), consistent with the Shared Decision's "no separate Entry-step variable binding for mill-go-base."

## Verdict

APPROVE
Source-verified against all four batch files, both config YAMLs, `_config.py`, and both target SKILL.md files; only one NIT found.
MILL_REVIEW_END
