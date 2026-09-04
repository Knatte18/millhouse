MILL_REVIEW_BEGIN
# Review: mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] Card 3 cites codeguide_commit.py behavior outside its Context
**Location:** Batch 1 (`01-mill-merge-in-parent-and-baseline.md`), Card 3 — mill-merge-in Step 5.5.
**Issue:** Card 3's Requirements assert Step 5's codeguide docs are "already `git add`-staged by `codeguide_commit.py --mode inline` back in Step 5" as the load-bearing justification for the new staged-only commit gate. This script/flag (verified present in `plugins/codeguide/scripts/codeguide_commit.py`; inline mode does stage-without-committing) is never mentioned in `mill-merge-in/SKILL.md` itself — Step 5 there only says "invoke the `codeguide-update` skill", with no mention of `codeguide_commit.py` or its `--mode inline` staging behavior — yet Card 3's `Context:` is `none` and `Edits:` is only `mill-merge-in/SKILL.md`.
**Fix:** Add `plugins/codeguide/scripts/codeguide_commit.py` (or `plugins/codeguide/skills/codeguide-update/SKILL.md`) to Card 3's `Context:` so the implementer can verify this claim without cold-start exploration.

## Verdict

REQUEST_CHANGES
Card 3 (batch 1) makes a load-bearing external-script claim outside its declared Context.
MILL_REVIEW_END
