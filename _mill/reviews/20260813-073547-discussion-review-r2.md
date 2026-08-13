MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: entry, phase-gate, finalize, and re-entry path gaps

```yaml
duration_s: 274.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-13
```

## Findings

### [BLOCKING:design] Resumed round N already exceeds max_review_rounds
**Section:** Decisions > "Max-rounds block: add a `blocked` re-entry row (#832)"
**Issue:** `blocked_reason` starts with `"max-rounds exhausted"` only after `round == max_review_rounds` (confirmed: step 6 fires only when the round counter exhausted). `discover_round` returns `max(found)+1`, so `N` on re-entry equals `max_review_rounds + 1` in the typical case. The decision says "fall through into the Plan Review loop with a fresh round budget starting at round `N`" but never states whether `max_review_rounds` itself is bumped/reset — as written, the loop's existing `round >= max_review_rounds` checks (4a/4b/4c/6, all reading the same session-config value) are already satisfied on the very first resumed iteration, reproducing the exact dead end #832 reports (or silently forcing an implicit-approve on round 1 of the "fresh" budget instead of a real review round).
**Fix:** State explicitly how the resumed budget is computed, e.g. mirror mill-start's `--auto` extension pattern (`--max-rounds <max_review_rounds + 1>` scoped to this invocation only) or define a per-resume local cap (`local_max = N + max_review_rounds - 1`) so `round < local_max` is true for at least one genuine review round before the cap can fire again.

### [NIT:consistency] Line-number citations for #827 checks conflict across sections
**Section:** Decisions > "Step 1.5 fix table... (#827)" rationale vs. Technical context
**Issue:** The Decision's rationale cites `:1071, :2242, :2305, :2173/:2237` as the 4 checks' emission sites; Technical Context cites `~1071 (depends-on-batch-mismatch), ~2237 (verify-full-suite), ~2306 (verify-malformed-cwd), ~2369 (verify-mixed-cwd)` for the same 4 checks. Verified against `_plan_validate.py`: actual sites are `~1068/1140`, `~2234/2273`, `~2303/2345`, `~2366/2452` — Technical Context's numbers track these; the Decision's `2173` does not correspond to any of the four checks' code.
**Fix:** Drop or correct the stray `2173` citation in the Decision rationale so both sections cite the same (approximately correct) line numbers.

## Verdict

REQUEST_CHANGES
The #832 re-entry round-budget interaction with `max_review_rounds` is unresolved and risks reproducing the bug being fixed.
MILL_REVIEW_END
