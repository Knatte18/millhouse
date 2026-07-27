MILL_REVIEW_BEGIN
# Review: Agent-dispatch boundary gaps: source-read guidance, fork directive-echo, and raw FileNotFoundError on missing agent-output — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: plan/
date: 2026-07-27
```

## Findings

### [NIT] `.exists()` guard misses the directory-at-path case
**Location:** Batch 2 / Card 3
**Issue:** The new guard checks `agent_output_path.exists()`, which is also True when a directory occupies that path; the subsequent `read_text()` would then still raise an unhandled `IsADirectoryError` — the same class of raw-exception bug this card sets out to fix.
**Fix:** Use `agent_output_path.is_file()` (or `not .exists() or not .is_file()`) instead of bare `.exists()`.

### [NIT] Escaped backticks/`$` garble Card 1's anchor-quote code span
**Location:** Batch 1 / Card 1
**Issue:** The Requirements text renders the anchor bullet as a single code span containing literal backslashes before `$` and before an internal backtick (`**\${CLAUDE_PLUGIN_ROOT}\`` ...), which markdown does not un-escape inside a code span, breaking the span early.
**Fix:** Drop the stray backslashes (or fence with double backticks for the nested literal backtick); harmless in practice since the unambiguous full-sentence quote later in the same paragraph already pins the exact insertion point — verified unique (single match) in `CLAUDE.md`.

## Verdict

APPROVE
Both batches are well-grounded against source, internally consistent, and correctly scoped; only two cosmetic/edge-case NITs, no BLOCKING findings.
MILL_REVIEW_END
