MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] --revise has no phase guard against post-planning execution
**Section:** Decision `mill-plan-revise-reentry` (#786) **Issue:** the flag's only precondition is `approved: true`; `approved` is confirmed to stay `true` throughout mill-go's entire run (Prepare through Handoff) and is never reset to `false` by mill-go, so `--revise` would also fire and force-flip `phase: planning` on a task that is `implementing`, `holistic-reviewing`, or even `done` — silently stranding already-committed/approved batches. **Fix:** add an explicit phase precondition (e.g. restrict `--revise` to `phase: planned` only, or an equally explicit "not yet claimed by mill-go" check) and state the forbidden window.

### [GAP] Observability-note mechanism/placement is self-contradictory
**Section:** Decision `implementer-status-line-omission` (#781) **Issue:** the Decision text says append the note "to the `## Timeline`-adjacent commit that step 7 (or the nearest subsequent `_status.append_phase`/commit point ... at line ~630) already makes" — i.e. piggyback on an existing downstream call — but the very next sentence calls this "new machinery ... not an addition alongside a pre-existing status-append call." These describe two different implementations (a standalone new commit inside step 4(b) vs. amending whichever commit happens to run next), and the cited example (line ~630, `approved-{batch_name}`) only fires when per-batch code review is disabled — a different call runs next when review is enabled. **Fix:** pick one concrete mechanism (e.g. a single new `_status.append_phase`/commit call added directly inside step 4(b)'s success sub-case) and state it as the sole call site.

### [GAP] Heartbeat-nudge Scope entry names the wrong file
**Section:** Scope "In:" bullet for #787 vs. Decision `heartbeat-nudge-for-long-verify` **Issue:** the Scope bullet is labeled `mill-go/SKILL.md:` for the "brief-side heartbeat nudge," but the Decision, its Rationale, and Testing all specify the edit lands in `implementer-brief.md` (a separate template file rendered by `millpy-implement.py`, confirmed distinct from `mill-go/SKILL.md`). **Fix:** correct the Scope bullet's file label to `implementer-brief.md` so a plan writer doesn't edit the wrong file.

## Verdict

GAPS_FOUND
Three GAPs: missing --revise phase guard, self-contradictory observability-note placement, and a Scope/Decision file-target mismatch for #787.
MILL_REVIEW_END
