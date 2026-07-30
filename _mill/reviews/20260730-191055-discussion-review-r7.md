MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet 5, Anthropic)
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [NOTE] "autonomous_mode-style toggle" precedent is mid-deprecation
**Section:** Decisions → Master on/off config switch (Rationale)
**Issue:** The switch's rationale cites `pipeline.autonomous_mode` as the established toggle convention to mirror, but `plugins/mill/scripts/_autonomous.py`'s docstring states it "Replaces the removed `pipeline.autonomous_mode` config key" with a per-hub flag file, and this repo's own hub `mill-config.yaml` already omits `autonomous_mode` from its `pipeline:` block (template still has it; four SKILL.md files still read it as config) — i.e. the cited precedent is itself a stale/in-flight migration, not a stable convention.
**Fix:** No design change needed (`entry_wait` is a static, operator-set feature toggle — a materially different shape of state than `autonomous_mode`'s per-task ephemeral escalation flag, so the flag-file rationale doesn't actually transfer). Just drop or soften the "matches the existing `autonomous_mode`-style toggle convention" framing so a future reader isn't misled into thinking `autonomous_mode` is still the model to copy.

## Verdict

APPROVE
All citations re-verified against source; no unresolved blocking gaps remain after 6 prior rounds.
MILL_REVIEW_END
