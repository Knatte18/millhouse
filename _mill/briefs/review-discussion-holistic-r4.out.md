MILL_REVIEW_BEGIN
# Review: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] "Regular suffix rule" for inflected verbs is underspecified for silent-e/y-ending verbs
**Section:** Decisions > Prohibition-detection redesign > "Inflected verb forms" bullet
**Issue:** The stated rule ("base, third-person -s/-es, past -ed, gerund -ing", irregulars hand-added "where the regular suffix rule doesn't apply") only illustrates `touch` -> `touch|touches|touched|touching`, a verb needing no spelling adjustment. Naive suffix concatenation is wrong for the majority of the 20-word verb list: silent-e verbs (`change, use, reference, include, update, remove, rename, move, create, delete, cite`) need e-drop before `-ed`/`-ing` (`use`+`ing` -> `using`, not `useing`), and `modify` needs y->i before `-s`/`-ed` (`modifies`/`modified`, not `modifys`/`modifyed`). Only `write`/`wrote`/`written` is explicitly called out as irregular.
**Fix:** State explicitly that standard English silent-e-drop and y->i orthographic rules apply as part of "regular," or enumerate the affected verbs (11 of 20) alongside `write` as needing hand-derived forms, so the plan writer doesn't reproduce a `useing`/`citeing`/`modifys`-shaped false-negative gap identical in kind to the round-3 gerund gap this task already fixed once.

## Verdict

REQUEST_CHANGES
Inflected-verb-form rule omits silent-e/y-ending spelling adjustments needed for most of the verb list.
MILL_REVIEW_END
