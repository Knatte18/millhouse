MILL_REVIEW_BEGIN
# Review: plan validator and wiki-guard hook false positives

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/tooling-false-positives/_mill/discussion.md
date: 2026-09-26
```

## Findings

### [NIT:consistency] Framework set lists duplicate names in prose
**Section:** Decisions / framework-types-never-resolve **Issue:** The list names `Object`, `Array`, `Math` twice; the text acknowledges dedup is required for the frozenset literal. **Fix:** None required; the plan writer must list each once.

### [NIT:design] Tokenizer placeholder and step order are only loosely specified
**Section:** wiki-guard-detection-algorithm **Issue:** Steps 1-5 plus the trailing command-substitution paragraph describe extraction ordering (heredoc strip, then substitution extraction, then tokenize) out of numeric order. **Fix:** Plan should implement in that order; tests already cover the affected cases.

## Verdict

APPROVE
No blocking gaps; tooling claims (`PYTHONPATH=`, `uv run --project plugins/mill`, Phase 4.8 helpers, existing symbols) match CLAUDE.md and source.
MILL_REVIEW_END
