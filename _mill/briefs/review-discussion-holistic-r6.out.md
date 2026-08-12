MILL_REVIEW_BEGIN
# Review: _plan_validate: context-completeness fires on forbidding/explanatory file mentions

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] "touch" needs -es, not -s, for third-person inflection
**Section:** Decisions > Prohibition-detection redesign, inflected-forms paragraph.
**Issue:** The 7 verbs left to "plain regular suffixes with no adjustment" (`touch, edit, add, link, read, alter, mention`) include `touch`, which ends in a sibilant (`ch`) and per standard English orthography takes third-person `-es` (`touches`), not `-s` (`touchs`, not a real word). This is the same naive-suffix-concatenation bug class rounds 3-4 already fixed for silent-e and y->i, left unaddressed for the sibilant case.
**Fix:** Add a third rule ("sibilant -es") alongside the stated silent-e and y->i rules, scoped to `touch`, and correct its inflected-form set to `touch|touches|touched|touching`. A real sentence like "This step never touches `bar.py`" would otherwise fail to match, reproducing the exact false-positive class this task exists to fix.

## Verdict

REQUEST_CHANGES
The "regular suffix" verb-form derivation misses the sibilant -es rule for "touch", regressing the class of bug rounds 3-4 fixed.
MILL_REVIEW_END
