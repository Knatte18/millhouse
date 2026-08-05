MILL_REVIEW_BEGIN
# Review: markdown skill: use semantic line breaks instead of one unbroken line per paragraph

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-05
```

## Findings

### [GAP] Blockquote rationale's "all short one-liners" claim is factually wrong
**Section:** Scope > In (bullet 1, blockquote paragraph) and Decisions (blockquote justification restated in round 3)
**Issue:** The claim "this repo's existing blockquotes (checked) are all short one-liners today" is false — `plugins/mill/skills/mill-finalize/SKILL.md` lines 135-139 is a genuine multi-line blockquote (a blank `>` separator line plus two `>`-prefixed list items), spanning 5 lines, not a one-liner.
**Fix:** Correct the empirical claim (e.g. "most existing blockquotes are short one-liners; one multi-line exception exists in mill-finalize/SKILL.md and is out of scope per the forward-only decision") so the stated project-style rationale for exempting blockquotes doesn't rest on an inaccurate survey of the repo.

## Verdict
GAPS_FOUND
Blockquote-exception rationale cites a repo-wide claim that a checked file (mill-finalize/SKILL.md) contradicts.
MILL_REVIEW_END
