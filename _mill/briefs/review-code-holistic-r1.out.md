MILL_REVIEW_BEGIN
# Review: mill-start Explore: Agent(subagent_type: fork) dispatch fails to perform assigned investigation — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-09-18
```

Single-batch, doc-only change verified against the plan's exact specified text and against the two Context source files.

- `plugins/mill/skills/mill-start/SKILL.md:205-206` — the two appended sentences match the batch card's specified text verbatim, each sentence on its own line per the repo's semantic-line-break convention, correctly placed immediately after the existing four-sentence "Fork echo caution" paragraph and before the `### Phase: Discuss` heading.
- Vocabulary substitution is correct: the appended text reads "investigation" throughout (matching mill-start's own Explore-phase terminology) rather than mill-plan's "research", while still citing `general-purpose`/`Explore` as the cold-agent choice and explicitly mirroring `plugins/mill/skills/mill-plan/SKILL.md`'s "Fork scope guardrail" paragraph (`mill-plan/SKILL.md:151-160`), which does use exactly that same `Explore`/`general-purpose` cold-agent split.
- No contradiction with `mill-go-base/SKILL.md`'s "Why not fork?" section — that section already lists mill-start's Explore phase as one of the three sanctioned fork sites, so the new fallback (abandon forking after one failed corrective retry, dispatch a cold agent) is consistent with, not contrary to, that inventory.
- Scope discipline held: the `**Fork scope guardrail.**` paragraph and the "Sub-investigation guidance" bullet list in `mill-start/SKILL.md` are untouched; only the "Fork echo caution" paragraph was extended.
- Files present match the plan's `## All Files Touched` (`mill-start/SKILL.md` only) and the batch's `Context:`/`Edits:` lists (`mill-plan/SKILL.md`, `mill-go-base/SKILL.md` as context, `mill-start/SKILL.md` edited) — no out-of-plan files.

No findings.

## Verdict

APPROVE
Doc-only append matches the plan's specified text verbatim and stays consistent with mill-plan/mill-go-base's fork guidance.
MILL_REVIEW_END
