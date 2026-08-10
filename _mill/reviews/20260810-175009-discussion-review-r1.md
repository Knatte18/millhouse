MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan SKILL.md: undocumented mutation sequences, precondition bugs, and non-portable cross-references

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5
reviewed_file: _mill/discussion.md
date: 2026-08-10
```

## Findings

### [BLOCKING:design] 810's precedent claim misdescribes lines 1187/1190/1195
**Section:** Decisions > 810-mutation-sequence (Rationale). **Issue:** Rationale claims 1187/1190/1195 "already spell out" a full mutation sequence (notify + lock release) before halting, but source shows those lines only do `append_phase`+commit then `"and go to *Blocked*"` — notify/lock-release/message live solely in the shared `### Blocked` section (853-862), reached by indirection, never inlined. `mill-merge/SKILL.md:81` and `mill-start/SKILL.md:315` (also cited elsewhere as `set_blocked` precedent) likewise do `set_blocked`+commit+halt with **no** notify/lock-release at all. **Fix:** Correct the rationale to state accurately what the cited lines do, and explicitly decide (not silently choose) whether 3.5/3.6 should reuse the `"invoke cleanup, go to *Blocked*"` idiom instead of inlining a shape that exists nowhere else in the file — noting that indirection loses the `reviews[].error` detail the custom BLOCKED messages need, which may justify inlining but should be argued, not asserted as already-precedented.

### [NIT:consistency] Post-fix, holistic halts have 3 different mutation shapes in one section
**Demoted-from:** BLOCKING
**Section:** Decisions > 810-mutation-sequence + 809-set_blocked-swap (Scope "Out" rejects broadening step 7). **Issue:** After this task, `## Holistic code review` will contain three distinct halt-mutation shapes: 3.5/3.6 (inline `set_blocked`+commit+notify+lock-release, newly added), 1187/1190/1195 (redirect via `"go to *Blocked*"`), and step 7 (still no notify, no lock-release at all — confirmed at lines 1200-1205, unchanged by the #809 minimal fix). The discussion never surfaces this resulting three-way inconsistency as a tradeoff of the scope-boundary decision. **Fix:** Add a sentence acknowledging step 7 keeps the builder lock held on halt as a known, deliberately-deferred residual gap (not an oversight), so a plan writer/reviewer doesn't mistake it for an accidental omission.

### [NIT:consistency] mill-start "throughout" precedent is partly wrong
**Section:** Decisions > 806-portable-cross-refs (Rationale). **Issue:** Cites mill-start/SKILL.md lines 177, 239, 249, 274, 288, 290, 317 as established bare-form (`mill-go/SKILL.md`) precedent. Verified: 249 and 288 actually use the full non-portable `plugins/mill/skills/mill-go/SKILL.md` form (the exact bug being fixed elsewhere), and 317 has no path-form reference at all ("mirrors mill-go's Step 4.5"). The core precedent at mill-plan/SKILL.md:381 (verified accurate) already fully supports the decision. **Fix:** Trim the citation list to lines that actually use bare form (177, 239, 274, 290), or drop the mill-start "throughout" claim and rely on the solid in-file line-381 precedent alone.

## Verdict

REQUEST_CHANGES
One BLOCKING precedent-misdescription affecting the 3.5/3.6 mutation-sequence design must be resolved.
MILL_REVIEW_END
