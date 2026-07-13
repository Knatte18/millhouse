MILL_REVIEW_BEGIN
# Review: Port mill to POSIX, not just Windows — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-13
```

## Findings

### [NIT] Em dash in Card 5's new sentence, not ASCII per batch requirement
**Location:** `plugins/mill/skills/mill-wiki-push/SKILL.md:12`
**Issue:** Card 5 requires "Keep the text ASCII-only" but the reworded sentence uses a Unicode em dash ("no wrapper — run `millpy-wikipush.py` directly") instead of ` -- `.
**Fix:** Replace the em dash with ` -- ` to match the `ascii-only-output` shared decision and CLAUDE.md convention. Not caught by `test-guards.py` (SKILL.md files are outside its ASCII-arrow check scope) and the surrounding pre-existing prose in this same file already contains em dashes, so this is cosmetic, not a regression.

## Verdict

APPROVE
All 5 cards correctly implemented; venv-check fix, new guard, dead-config deletion, and doc corrections all verified against source.
MILL_REVIEW_END
