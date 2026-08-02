MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (environment-reported model ID: claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] `self-resolved-verify-logic` phase is routing-ambiguous
**Section:** Decision `757-phase-gate-widening`
**Issue:** `self-resolved-verify-logic` is appended with the identical literal string at both mill-go/SKILL.md:596 (per-batch) and :853 (holistic), but the Decision routes the two occurrences to different destinations (`## Resume` vs `## Holistic code review`). The widened Entry-gate match only has `phase` to key on and documents no secondary signal to tell the two apart — this also contradicts the same Decision's Rejected-alternative claim that "phase already discriminates it."
**Fix:** Specify the disambiguator explicitly, e.g. check `## Batches` for any non-terminal (`running`/`reviewing`/`fixing`) entry: present → per-batch occurrence → `## Resume`; none (all `approved`) → holistic occurrence → `## Holistic code review`.

### [GAP] Holistic multi-batch annotation target has no mapping mechanism
**Section:** Decision `758-mandatory-reason-annotation`
**Issue:** For the holistic branch, the fix requires annotating "each named batch file" a finding spans, but a holistic stuck reason (or a holistic code-review finding, per `review-code-holistic.md`'s `Location: path/to/file.py:N`) cites a source-file path, not a batch name — no mechanism is specified for mapping a cited path back to its owning batch file(s) via the Batch Index's `Edits:`/`Creates:` lists, nor a fallback for a whole-plan reason (e.g. an `untracked files outside scope` violation spanning several batches) that names no single file at all.
**Fix:** Name the lookup mechanism (e.g. cross-reference each cited path against every batch's `Edits:`/`Creates:`) and state the fallback for reasons that name no specific file.

### [NOTE] #757 testing plan covers the predicate, not the new routing table
**Section:** `## Testing` (#757) / Decision `757-phase-gate-widening`
**Issue:** The named test extension only exercises `matches_wait_trigger`'s new patterns (a pre-existing, already-tested pure function); it says nothing about verifying the three-way routing logic itself (Resume vs Execute-loop-continue vs Holistic-code-review, plus the last-batch edge case) — the actual novel, unstestable-by-Python risk surface `#757` introduces.
**Fix:** Either explicitly defer routing-table correctness to plan/code review (as `#758`'s Testing entry already does for its own prose-only change) or state why no such note is needed here.

## Verdict
GAPS_FOUND
Two routing/mapping mechanisms referenced by Decisions 757 and 758 are unspecified and must be resolved before planning.
MILL_REVIEW_END
