MILL_REVIEW_BEGIN
# Review: mill-plan autonomy guidance and validation gaps: fork scope violations, missing anti-pause guidance, no mechanical Context/Edits completeness check

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: _mill/discussion.md
date: 2026-07-29
```

## Findings

### [GAP] Fork guardrail's git-status check has no pre-dispatch baseline
**Section:** Decisions > Fork scope guardrail placement and mechanism (#741), clause (c)
**Issue:** The decision specifies only a single post-return `git status --porcelain` check, but fork is explicitly reserved for cases needing "the parent's in-flight reasoning" — i.e. exactly when mill-plan's Phase: Plan already has uncommitted new/modified batch files on disk (that phase's only commit is at the very end, `mill-plan/SKILL.md:107`, confirmed by full read of lines 43-107). A single post-return snapshot cannot mechanically distinguish the orchestrator's own legitimate in-progress plan-writing dirt from a fork's unauthorized writes — every plan file the orchestrator itself is mid-writing would also show as untracked/modified. `_treeguard.check_and_restore` (cited in the rationale as a mirrored pattern) is not actually analogous: it only ever matches deletion status codes (" D"/"D "), which are abnormal regardless of baseline, so it needed no pre-snapshot — that shortcut does not carry over to detecting new/modified/untracked entries.
**Fix:** Specify capturing a `git status --porcelain` snapshot immediately BEFORE dispatching the fork and diffing the post-return snapshot against it; flag only entries that are new in the post-return snapshot, not the full unfiltered post-return listing.

### [GAP] `context-completeness`'s per-card Moves:-source extraction is unspecified
**Section:** Decisions > `context-completeness` validator check design (#742)
**Issue:** The decision says the check must extract per-card tokens using "the same backtick-extraction regex logic inline" but only names Context:/Edits:/Creates: explicitly (all three share `_RE_REFS_HEADER`). Deletes: trivially extends the same regex (also matched by `_RE_REFS_HEADER`), but Moves: uses a structurally different two-path grammar (`_RE_MOVES_HEADER` + `_RE_MOVE_PAIR`, confirmed at `_plan_validate.py:83-88`) with no existing per-card token-extraction helper (`_card_field_is_none` only returns a none/non-none bool, not tokens — confirmed at `_plan_validate.py:764-802`). A naive backtick-extraction over a Moves: sub-bullet line would pull both the source AND target path as two separate tokens, incorrectly letting a target-only Requirements: reference resolve — which directly breaks Testing scenario (j) ("the *target* half of a Moves: pair with no matching Context:/Edits: — finding still raised").
**Fix:** Add an explicit implementation note that per-card Moves:-source extraction must use `_RE_MOVES_HEADER`/`_RE_MOVE_PAIR` and take only the source-path capture group, mirroring `_card_field_is_none`'s Moves-specific branch rather than the generic backtick-extraction path used for the other four fields.

### [NOTE] Testing scenario (g) miscounts existing validator checks
**Section:** Testing > `_check_context_completeness` scenario (g)
**Issue:** States "zero false positives from the other 25 existing checks," but `run()`'s `errors.extend(...)` call sequence (`_plan_validate.py:2250-2298`) currently wires exactly 24 checks, not 25.
**Fix:** Correct the count to 24 (or drop the specific number and just assert no findings from other check names) so the scenario description doesn't set a wrong expectation for the test author.

## Verdict
GAPS_FOUND
Two technical gaps affect mechanism correctness (git-status baseline, Moves-source extraction); one minor count fix.
MILL_REVIEW_END
