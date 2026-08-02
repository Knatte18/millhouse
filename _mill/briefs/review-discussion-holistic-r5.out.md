MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (self-assessed; cannot fully verify against reviewer_model tag above)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] #758 fix leaves an identical conditional hedge live in holistic review
**Section:** Decision `758-mandatory-reason-annotation` / Scope / Technical context
**Issue:** `mill-go/SKILL.md`'s `## Holistic code review` section (verified ~line 853) contains the exact same conditional hedge — "edit the plan file(s) if the failure traces to an ambiguous or incorrect card" — in its own `verify`/`logic` self-resolve branch, but the Decision, Scope, and Technical Context all cite only the per-batch `### Stuck escalation` branch (~line 596); the holistic occurrence is never mentioned.
**Fix:** Either extend the #758 decision/scope to cover both occurrences (per-batch and holistic), or explicitly state in a Decision/Note why the holistic branch is deliberately excluded from this fix.

### [NOTE] Pre-existing `wiki_root`/`wiki_path` naming mismatch preserved unchanged by #759
**Section:** Decision `759-missing-import`
**Issue:** The self-validate call being edited (verified `mill-plan/SKILL.md` ~line 193) passes `wiki_root=wiki_root`, but mill-plan's Entry step only ever binds a `wiki_path` variable (line 18) — no `wiki_root` is bound anywhere in the file; the Decision explicitly preserves this paragraph's prose "unchanged" and doesn't flag or address the mismatch.
**Fix:** Note in the plan (or as an out-of-scope acknowledgment) that the self-run call should read `wiki_root=wiki_path` for consistency, or confirm this is intentionally left alone as a pre-existing, orthogonal issue.

## Verdict

GAPS_FOUND
One GAP: #758's fix scope misses an identical conditional bug in the holistic-review self-resolve branch.
MILL_REVIEW_END
