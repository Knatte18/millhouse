MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet) — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-08-11
```

## Findings

### [BLOCKING:design] Card 7's description-recovery instruction uses an unanchored `HEAD~N`
**Location:** batch 02-thin-variants, card 7 **Issue:** The instruction to recover mill-go's pre-move `description:` "verbatim" cites `git show HEAD~N:plugins/mill/skills/mill-go/SKILL.md` with no way to compute N, and offers only "or from the pre-move frontmatter" as a fallback, which is not reachable from this card's Context (`mill-go-base/SKILL.md` already carries card 1's rewritten description, not the original). No test asserts the recovered text, so a wrong `N` (or wrong recall) silently corrupts the operator-facing skill description with nothing to catch it. **Fix:** Cite the concrete pre-move commit already established elsewhere in the plan (`6442a688`) or the actual rename commit via `git log --follow`, not a relative `HEAD~N` offset.

## Findings (non-blocking)

### [NIT:consistency] Card 6 misattributes its function-shape convention to the wrong file
**Location:** batch 02-thin-variants, card 6 **Issue:** Card 6 says the new test follows "the house shape used by `test-guards.py`: ... one function per check returning a list of failure strings," but `test-guards.py`'s check functions actually return `int` (0/1) and print PASS/FAIL directly inline — the "list of failure strings" pattern is `test-skill-helper-drift.py`'s shape, which isn't in this card's `Context:`. **Fix:** Cite `test-skill-helper-drift.py` (or both) as the shape reference instead of `test-guards.py` alone; the concrete spec given is otherwise unambiguous so this is cosmetic.

## Verdict

REQUEST_CHANGES
One BLOCKING finding (card 7's unanchored git reference); all other claims, counts, and cross-references verified accurate against source.
MILL_REVIEW_END
