MILL_REVIEW_BEGIN
# Review: Blocking phase-wait gate for mill-plan/mill-go chaining

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (Anthropic)
reviewed_file: _mill/discussion.md
date: 2026-07-30
```

## Findings

### [GAP] `plan-review-r{N}`/`plan-fix-r{N}` recur through the whole blocking-findings loop, not just pre-Handoff
**Section:** Decisions → "Exact phase-table edit sites" (mill-plan side)
**Issue:** The Decision cites "step 4a/4b" at "lines ~239, ~244" as the source of the transient post-approve/pre-Handoff window, and claims the in-progress loop "stays `planning` the whole time" before any round's APPROVE. Verified against the actual file (`plugins/mill/skills/mill-plan/SKILL.md`): lines 239/244 are inside **step 4d** (`REQUEST_CHANGES AND blocking_count > 0`, ~line 238), not 4a (line 208) or 4b (line 210). Critically, 4d does **not** break the loop — it falls through to steps 5/6 and can repeat for many rounds — so `plan-review-r{N}`/`plan-fix-r{N}` are the phase for the entire duration of a blocking-findings review loop, not a brief window between an APPROVE-commit and Handoff.
**Fix:** Correct the citation and rationale: the widened trigger set is still the right fix (it happens to cover 4d's writes too), but the "brief, post-approve" framing is factually wrong and should describe the phase as covering the full multi-round review loop whenever findings remain BLOCKING.

### [GAP] Orchestrator reaction to `BLOCKED`/`TIMEOUT` wait outcomes is undecided
**Section:** Decisions → "Terminal-state (blocked) detection" / "Resume behavior on `READY`"
**Issue:** Only the `READY` case has a decided orchestrator action (re-run the entry-gate from scratch). The poll script's other two possible outputs — `BLOCKED: <reason>` and `TIMEOUT after ...` — are fully specified at the *script* level (grep target, exit code, message text) but nothing in the discussion states what the SKILL.md orchestrator does upon receiving each as the Monitor notification payload (e.g., halt with `blocked_reason` the same way the existing `blocked` phase-table row does; halt with a distinct give-up message on timeout, and whether re-running the skill re-arms the wait).
**Fix:** Add explicit orchestrator-side decisions for the `BLOCKED` and `TIMEOUT` notification cases, mirroring the level of detail already given for `READY`.

## Verdict

GAPS_FOUND
Two verification gaps: a mischaracterized phase-transition citation and undecided orchestrator handling of BLOCKED/TIMEOUT outcomes.
MILL_REVIEW_END
