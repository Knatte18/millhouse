MILL_REVIEW_BEGIN
# Review: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-4.5 (unconfirmed self-assessment)
reviewed_file: /home/knatte/Code/millhouse/wts/mill-plan-skill-doc-gaps/_mill/discussion.md
date: 2026-07-29
```

## Verdict Summary

All source-grounded claims verified against current file contents:

- `mill-plan/SKILL.md` line 116 (Phase: Plan commit), line 242 (4d commit bullet), lines 167 and 176 (both Step 1.5 validator-fix branches) — all four confirmed to lack "push" in their literal instruction text, exactly as claimed.
- Line 126 (plan-review-skip branch) confirmed to already say "push" but omit `-C <worktree>` on `git commit` while carrying it on `git add`, matching the claimed asymmetry.
- Lines 205/207/233/260 (4a/4b/4c/Handoff) confirmed to already carry explicit push wording; 4a's literal command confirmed to already carry `-C <worktree>` on both verbs.
- Lines 246-254 max-rounds-escape prompt confirmed to use lettered `A)/B)/C)` format with a trailing `Recommended: {A/B/C}` line and a lettered follow-up sentence, matching the non-conformant-format claim.
- `mill-go/SKILL.md` Entry Step 0 (lines 14-18) confirmed as the only existing step, with numbered step 1 immediately following (no existing Step 0.5) — insertion point for Step 0b confirmed clean.
- `mill-go/SKILL.md` stuck-escalation prompts confirmed line-by-line: `infrastructure` (line 490) and `transient` commits_made>0 (lines 494-496) already show literal `1)/2)` templates with `(Recommended)` on option 1; the "Otherwise" (line 500), `incomplete` (line 502), and `verify`/`logic` (line 504) branches confirmed prose-only with no literal template; holistic-rounds-exhausted (lines 769-774) confirmed literal `1)/2)/3)` template with no `(Recommended)` anywhere — matches the claim this is still conformant (no recommendation exists).
- `0.5`/`0.55` headings confirmed to live inside `## Agent-mode dispatch`'s per-batch dispatch loop (lines 222, 248), not `## Entry`; Entry's own `4.5.` (line 38) confirmed as the genuine decimal-sub-step precedent — the `mill-conversation-load-placement` Decision's collision-avoidance rationale for choosing `Step 0b` over `Step 0.5` is factually correct.
- `conversation/SKILL.md` (the `mill:conversation` skill) confirmed to state the numbered `1) Label — description` format, `(Recommended)` on option 1's label, and the verbatim "applies retroactively... convert them" clause quoted in the Decisions section.
- `mill-start/SKILL.md` Step 0 (line 45) confirmed as the reference pattern with matching wording/rationale style.
- No `CONSTRAINTS.md` at hub root confirmed; no SKILL.md linter script found in `plugins/mill/scripts/`, consistent with the Constraints section's claims.

No undecided items, no unresolved ambiguity, all three Decisions carry rationale and rejected alternatives, scope is precisely enumerated (including exact wording/placement per instance), and testing is appropriately scoped to manual read-back for a docs-only change. No new findings from this round's independent re-verification.
MILL_REVIEW_END
