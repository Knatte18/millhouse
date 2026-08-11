MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet) — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (model id claude-sonnet-5, per system self-report; not independently verifiable from within the session)
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:decision] Line-321 self-reference in the relocated file is never repointed
**Location:** batch 1 (card 1/4) and batch 3 (cards 9-12) **Issue:** `_mill/discussion.md`'s "Cross-references that must be repointed" explicitly lists `plugins/mill/skills/mill-go/SKILL.md` line 321 (the `--actual-model` paragraph's `` `mill-go/SKILL.md` `` mention inside "## Agent-mode dispatch" step 6) as a site "All must be checked and repointed to `mill-go-base/SKILL.md`." No card touches it: card 1 makes only 3 named surgical edits and moves everything else unchanged; card 4 explicitly excludes "section cross-references" from parameterization; batch 3's cards 9-12 never list `mill-go-base/SKILL.md` under `Edits:` (card 9's own note says the implementer "should not load" it). Verified the line exists at 321 in the pre-move file, containing the literal substring `` `mill-go/SKILL.md` ``. **Fix:** Add a card (or a fifth surgical edit to card 1) repointing this one occurrence to `mill-go-base/SKILL.md`, or add an explicit Shared Decision stating it is deliberately left unchanged with rationale.

### [NIT:consistency] "Step 0a" is placed before "Step 0"
**Location:** batch 1, card 2 **Issue:** The inserted block is named "Step 0a" but card 2 requires it to be inserted immediately BEFORE the existing "Step 0," inverting the usual lettered-suffix convention (0a normally follows 0, as "Step 0b" already does later in the same file). Functionally correct per the stated ordering rationale (VARIANT_LABEL must bind before Step 0's now-parameterized halt string fires), but the label reads oddly against the file's own "0, 0b, 0.5, 0.55, 0.6" numbering precedent. **Fix:** Consider naming it something that doesn't imply post-0 ordering (e.g. "Step -1" or an unlettered "Variant binding" step), or note the inversion explicitly in the card.

## Verdict

REQUEST_CHANGES
Discussion's explicit line-321 repoint checklist item has no implementing card anywhere in the plan.
MILL_REVIEW_END
