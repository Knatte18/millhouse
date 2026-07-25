MILL_REVIEW_BEGIN
# Review: Batch review/verify pipeline doesn't account for cross-batch state changes

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

## Findings

### [GAP] `parse_deletes` helper does not exist
**Section:** Decision 2 (rationale) + Technical context (last bullet, line 95)
**Issue:** Both claim Decision 2 can call an existing per-batch `parse_deletes` in `_review_common.py` ("same helpers used internally by `compute_deletes_union`... no new parsing surface") — but no such function exists; `compute_deletes_union` inlines its Deletes: parsing (`_review_common.py:684-696`) and only `parse_moves` (line 551) is a standalone per-batch parser. The only per-batch deletes parser, `_parse_deletes_only`, lives in a different module (`_plan_validate.py:220`).
**Fix:** Correct the premise — acknowledge Decision 2 must either extract a new per-batch `parse_deletes` helper from `compute_deletes_union`'s inline logic (a small new parsing/test surface, not pure reuse) or reuse `_plan_validate._parse_deletes_only` cross-module; state which, since "no new parsing surface" is load-bearing for choosing metadata over disk-existence.

### [NOTE] Multi-target verify: any single removed token skips whole command
**Section:** Decision 2 (a–d)
**Issue:** The suppression test is existential over tokens (a command "references a removed-later target" when *a* token matches a later removal), and the consequence is dropping the entire triple — so a verify like `go build ./tools/x ./tools/y` is fully suppressed when only `tools/x` is reverted, silently skipping the still-valid `tools/y` check. Not hit by #689/#698 but unstated.
**Fix:** State explicitly that any matching token suppresses the whole command and that this can over-suppress co-targets, or note it as an accepted limitation like the flag=value / directory-containment carve-outs.

### [NOTE] Verify-cwd vs Deletes-root coordinate space unaddressed
**Section:** Decision 2 (c–d)
**Issue:** Matching is purely lexical on raw strings, but verify tokens are relative to the command's resolved `cwd:` (hub/git_root) while `Deletes:`/`Moves:` tokens are relative to the plan `root:`. When these bases differ, a genuinely-reverted target may fail to match (verify still runs — #689 unfixed for that config). Degradation, not a false positive.
**Fix:** Note the assumption that verify path tokens and Deletes/Moves tokens are authored in the same coordinate space, or scope the mismatch out explicitly.

## Verdict

GAPS_FOUND
Decision 2 relies on a `parse_deletes` helper that does not exist; correct the premise.
MILL_REVIEW_END