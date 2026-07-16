MILL_REVIEW_BEGIN
# Review: Unhandled exceptions in mill-go orchestration components should degrade gracefully — holistic

```yaml
verdict: APPROVE
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-16
```

## Findings

### [NIT] Card 4 Context is `none` but names cross-file symbols
**Location:** Batch 1 / Card 4
**Issue:** Requirements references `_config_mod.load_config` (`_config.py`), `_paths.resolve_git_root` (`_paths.py`), and the `cleanup_session` gate (`_llm_claude.py`) — none listed in Context/Edits; a literal read of the Context-completeness rule flags this.
**Fix:** Add `_llm_claude.py`, `_config.py`, `_paths.py` to Card 4 Context (as Card 3 already does). Mitigated in practice: these are mock targets with return values fully specified inline, mirroring the existing in-file Test 12 pattern (~lines 888-890), so no cold-start exploration is actually required.

### [NIT] Card 5 prose-preservation rationale is inaccurate for the holistic block
**Location:** Batch 1 / Card 5
**Issue:** Card asserts both cleanup paragraphs "describe the calls as 'idempotent and failure-swallowing'." Only the per-batch prose (SKILL.md:180) contains that phrase; the holistic paragraph (SKILL.md:531/544) does not.
**Fix:** Reword the card's justification; the instruction itself (remove `|| true`, leave prose untouched) is correct and executable regardless.

## Verdict

APPROVE
Cards accurately grounded in source; both fixes and their tests are correct and sequenced.
MILL_REVIEW_END
