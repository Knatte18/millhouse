# Review: 19 (A) — mill-go + scripts infra fixes — 01-lock-cli-and-mill-go-skill

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: 01-lock-cli-and-mill-go-skill
date: 2026-05-06
```

## Findings

### [NIT] Card 2 says "four changes" but specifies five
**Step:** Card 2 Requirements preamble
**Issue:** "Make four changes to `mill-go SKILL.md`:" is immediately followed by five numbered items (1–3 lock replacements, 4 pause note, 5 cleanliness gate). A strict read of "four" could prompt the implementer to skip one.
**Fix:** Change "Make four changes" to "Make five changes".

### [NIT] Plan instructs removing a signature line that doesn't exist in Blocked
**Step:** Card 2, requirement 2 (Lock release, Blocked step)
**Issue:** "Remove the `signature: _builder_lock.release(...)` line" — the current `### Blocked` section has no `signature:` line under the release call, only Handoff step 4 does. The instruction is a harmless no-op but adds noise.
**Fix:** Remove the "Remove the `signature:` line" clause from requirement 2; keep it only in requirement 3 (Handoff).

## Verdict

APPROVE — two documentation-only NITs; no implementation risk.