MILL_REVIEW_BEGIN
# Review: mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-09
```

## Findings

### [GAP] `--revise` round-namespace: the two named alternatives aren't equivalent
**Section:** Decision `mill-plan-revise-reentry`, para 3 + Technical context `discover_round` note.
**Issue:** The decision offers "`reviews/revise-N/`" or "an equivalent filename convention" as interchangeable options, but `discover_round`'s regexes (`RE_SIMPLE`/`RE_BATCH`, `_review_common.py`) are non-recursive single-directory scans with a hardcoded `discussion|code|plan` type alternation. A filename-only convention that "regexes will not match" (per Technical context) never matches on *any* later revision round either, so `discover_round` returns 1 forever instead of advancing — only the subdirectory form actually works. Additionally, `millpy-review-plan.py`/`_review_plan.py` resolve `reviews_dir` internally from `cfg["paths"]["reviews_dir"]` (verified: `resolve_path(cfg["paths"]["reviews_dir"], slug)`, no override parameter exists), so even the subdirectory form needs a new CLI/config hook — contradicting "reuses ... machinery unmodified."
**Fix:** Commit to the subdirectory approach explicitly and name the mechanism (new CLI flag vs. scoped config override) that redirects `reviews_dir` for the revision pass.

### [GAP] "non-clean terminal notification" is undefined and conflicts with the documented Agent-tool contract
**Section:** Decision `widen-step4-stall-classification`.
**Issue:** `harness-tool-contracts.md` states the Agent tool "Delivers exactly ONE combined-result `<task-notification>` when the subagent finishes, is stopped, or is interrupted — the notification payload carries the subagent's final message text" — no `<status>` tag is documented for this path (only the separate Monitor-tool contract has `<status>completed</status>`). The discussion's own Problem/Decision text repeatedly cites a literal `` `<status>failed</status>` `` notification for the stall/watchdog case, and the widened (c) criterion keys on "non-clean" without stating what signal (message-text pattern vs. an actual status field) discriminates clean success from this case.
**Fix:** Confirm whether Agent-tool notifications actually carry a `<status>` field (updating `harness-tool-contracts.md` if so) and state the concrete textual/structural signal step 4 tests to classify "non-clean."

### [GAP] #781 anchor site's "existing timeline/status-append calls" don't exist there
**Section:** Technical context, implementer-status-line-omission bullet; Testing section #781 bullet.
**Issue:** Both cite `mill-go/SKILL.md` step 4(b) (lines 258–281) as already making "timeline/status-append calls" the new observability note would sit "alongside." A full-file grep for `append_phase`/`append_recovery_log`/`timeline` in `mill-go/SKILL.md` shows zero hits inside step 4's classification block (lines 199–357) — the nearest `_status.append_phase` calls are in later, structurally separate sections (e.g. line 618, 639, 765). Step 4(b) has no commit/push machinery today either.
**Fix:** Correct the anchor-site description — either identify a real existing append-call site, or scope the fix as introducing new status/commit machinery at step 4(b), not an additive one-liner.

## Verdict

GAPS_FOUND
Three plan-writing blockers: --revise namespace mechanics, undefined "non-clean" signal, and an inaccurate #781 anchor-site claim.
MILL_REVIEW_END
