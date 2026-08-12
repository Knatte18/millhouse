MILL_REVIEW_BEGIN
# Review: mill-go-base: remove subprocess/psmux dispatch branches — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-reported; matches the "Sonnet 5"/sonnethigh designation used by this harness)
reviewed_file: plan/
date: 2026-08-12
```

## Findings

### [BLOCKING:scope] Batch 5 Card 20's self-reference enumeration is a non-exhaustive example list, not a full sweep
**Location:** batch 5 (`05-renumber-and-siblings.md`), Card 20
**Issue:** `## Agent-mode dispatch` contains dozens of numbered self-references beyond the six Card 20 names "for example" (verified via grep: lines 234, 245-246, 251, 254, 256, 261-262, 265-266, 272, 280, 289, 297, 299-300, 311-312, 335, 353, 358, 375, 385-392 all cite `step 2`/`3`/`4`/`4(b)`/`4(c)`/`5`/`6`/`7`). Card 20's instruction ("apply the same mapping" to a short illustrative list) does not require enumerating every `step N` occurrence inside the section before editing, unlike Card 21's rigorous "enumerate every occurrence... classify each" method for the rest of the file. Card 21 explicitly scopes itself to text *outside* `## Agent-mode dispatch`, so any reference Card 20 misses inside the section is never caught by a later card.
**Fix:** Rewrite Card 20 to require the same enumerate-then-classify method as Card 21: grep every `step ` + number occurrence inside `## Agent-mode dispatch` (list markers, bold titles, and prose) and remap all of them, not just the six named examples.

### [NIT:design] Cards 14-16/24's frontmatter rationale for skills-index exclusion is inaccurate but harmless
**Location:** batch 4 Cards 14-16 ("must not be picked up by the `plugins/*/skills/**/SKILL.md` scan... a `name:`/`description:` block would make that ambiguous"); batch 5 Card 24 invariant 1 ("a companion file can only appear if it grew a `name:`/`description:` block")
**Issue:** `millpy-skills-index.py` scans via `skills_dir.rglob("SKILL.md")` — an exact filename match. `resume.md`/`holistic-review.md`/`handoff.md` can never be picked up regardless of frontmatter, so the stated causal mechanism (frontmatter presence -> index inclusion) is false; the "no-frontmatter" rule and Card 24's invariant-1 risk framing are both moot by filename alone.
**Fix:** Reword the rationale to cite the filename-based glob as the actual exclusion mechanism; keep the no-frontmatter instruction as defense-in-depth if desired, but drop the "would make that ambiguous" claim.

## Verdict

REQUEST_CHANGES
Card 20's non-exhaustive self-reference list risks leaving stale step numbers inside the renumbered section, uncaught by any later card.
MILL_REVIEW_END
