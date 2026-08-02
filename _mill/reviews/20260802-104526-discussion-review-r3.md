MILL_REVIEW_BEGIN
# Review: Self-discovered mill-go/mill-plan skill-doc and behavior gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5 (Sonnet, "high" reasoning-effort variant per brief label)
reviewed_file: _mill/discussion.md
date: 2026-08-02
```

## Findings

### [GAP] Harness-contracts doc pointer list omits mill-plan's own duplicate copy
**Section:** Decision `755-harness-contracts-doc` / Scope "In:"
**Issue:** `mill-plan/SKILL.md`'s own "Entry-gate wait for upstream mill-start" section (lines ~79-91) already carries a near-verbatim inline copy of the Monitor two-notification-shape prose that `mill-go/SKILL.md`'s equivalent "Entry-gate wait for upstream mill-plan" section (lines ~130-181) also carries — neither location is in scope's pointer list, which names only `cli/SKILL.md` and mill-go's "## Agent-mode dispatch" section.
**Fix:** Add the new doc's pointer (or at least evaluate the omission explicitly) at both Entry-gate-wait sections too, since they're independent, load-bearing duplicates of exactly the contract content the new doc consolidates — verified by reading both files' Monitor-wait prose side by side.

### [GAP] 759 fix format is self-contradictory ("import line" vs. "signature: convention")
**Section:** Decision `759-missing-import`
**Issue:** The file's actual "other helper calls" convention (verified: lines 19, 20, 22, 195) is a `signature: module.func(args) -> ret` documentation line — none of which is an import statement. The decision asks for both "an explicit `from _review_common import _load_root_from_overview` line" AND that it match "the file's existing convention... with `signature:` lines" — these are two different documented styles in the file (bare `signature:` lines vs. the fenced-Python-snippet style used for `quote_scalar` at line 149-150), and the decision doesn't say which one applies to an import statement specifically.
**Fix:** Pick one form explicitly (e.g. "add it as a fenced Python snippet like the `quote_scalar` example, not a `signature:` line") so the plan writer isn't guessing between two live conventions in the same file.

## Verdict

GAPS_FOUND
Two GAPs: harness-doc pointer scope misses mill-plan's own duplicate Monitor prose; 759's fix-format instruction is internally inconsistent.
MILL_REVIEW_END
