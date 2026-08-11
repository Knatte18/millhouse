MILL_REVIEW_BEGIN
# Review: mill-go2: opt-in skill scaffold cloned from mill-go (no fork yet) — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-11
```

## Findings

None.

Verified end-to-end against all three batches:

- `mill-go-base/SKILL.md` carries the full relocated machinery byte-for-byte (banner, Builder role
  paragraph, all sections through Handoff), with exactly the frontmatter/H1/description edits card 1
  specifies, plus the two override-point blocks (card 2's Entry-preceding "Variant binding and driver
  preamble" and card 3's single Agent-mode step-3 "Override point A") inserted verbatim per spec.
- All three literal families are fully parameterized in the base (`grep` for the raw
  `commit -m "mill-go: `, `_notify.notify("mill-go.`, `[mill-go]` literals returns zero matches) and
  every non-family `mill-go` occurrence (prose, `/mill-go` cross-refs, `mill-go: start batch` script
  prefix) is left untouched, matching `three-literal-families-only` and
  `script-side-prefixes-unchanged`.
- `mill-go/SKILL.md` and `mill-go2/SKILL.md` are both thin (29 lines, well under 4096 bytes), each
  with a distinct `VARIANT_LABEL`, both override sections declared `(none)`, and no machinery
  literals. mill-go2's description conveys exactly the four required points without wiring into any
  automatic path.
- `test-mill-go-variants.py`'s seven checks match card 6's spec exactly and pass against the actual
  file contents inspected.
- `test-guards.py` and `test-skill-helper-drift.py` retarget correctly to `mill-go-base`; no
  `mill-go2` entry was added to the wiki-cwd allowlist, per card 5's explicit prohibition.
- Batch 3's repoint is complete: no remaining `mill-go/SKILL.md` reference exists anywhere under
  `plugins/mill` (skills, docs, scripts, tests); `cli/SKILL.md` and `conversation/SKILL.md` both gained
  `mill-go2` in their orchestrator name lists without adding `mill-go-base`; `SKILLS.md` correctly
  lists all three rows with the mill-go row's description unchanged and the new base/mill-go2
  descriptions matching their SKILL.md frontmatter.
- No out-of-plan files, no duplicated helpers, no cross-batch contract breaks — the variant contract
  batch 1 publishes (VARIANT_LABEL / Driver preamble / Dispatch overrides) is exactly what batch 2
  consumes and batch 3's test re-run re-confirms.
- Per the brief's instruction, the prior non-blocking item on `test-mill-go-variants.py:34`
  (`MILL_GO_LITERALS`) is not re-litigated — no new diff or reproducible failure surfaced against it
  in this round.

## Verdict

APPROVE
All three batches fully realize the plan; parameterization, override points, and repoints are complete and consistent.
MILL_REVIEW_END
