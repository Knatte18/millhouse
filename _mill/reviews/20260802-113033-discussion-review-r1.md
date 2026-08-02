MILL_REVIEW_BEGIN
# Review: pipeline.autonomous_mode warns as unknown config key on every mill invocation

```yaml
verdict: APPROVE
reviewer_model: sonnet
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [NOTE] "inline comment" claim slightly overstates deprecated_keys styling
**Section:** Decisions > No documentation changes
**Issue:** Rationale says "the deprecated_keys entry's own inline comment is sufficient self-documentation," but `_config.py` line 121 has one block comment above the whole `deprecated_keys` set, not a per-entry inline comment; verified in source, no per-key comment exists today.
**Fix:** No action needed for plan feasibility; optionally reword to "the set's existing block comment" for precision.

## Verdict

APPROVE
Technical context claims verified accurate against source; decisions, scope, and testing are complete and unambiguous.
MILL_REVIEW_END
