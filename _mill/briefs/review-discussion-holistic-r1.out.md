MILL_REVIEW_BEGIN
# Review: Surface reviewer time/tool-call cost + a review-summary command

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-11
```

## Findings

### [BLOCKING:decision] `cost_usd` sourcing for Claude never decided
**Section:** Decisions > "Tool-call counting: best-effort stream-json block count, subprocess mode only"; Technical context > `_parse_stream_json()` bullet.
**Issue:** `tool_calls` gets a full Decision (fallback block-count, prefer native `num_turns`, schema-verification deferred to implementation). `cost_usd` is named throughout Scope/Decisions as a field to carry but its Claude-mode sourcing is only mentioned once, in Technical Context, as "opportunistically" extracting `total_cost_usd` — no current code references any such field, so this is unverified and never actually decided.
**Fix:** Add a Decision for `cost_usd`'s Claude subprocess/psmux sourcing (native field vs. always-`None` vs. deferred), mirroring the `tool_calls` Decision's structure.

### [BLOCKING:design] Fast-fail retry duration silently undercounted
**Section:** Technical context > `_llm_claude.py::_invoke()`; Decision "Duration for multi-call rounds: sum across resume retries."
**Issue:** `_invoke()`'s subprocess branch (~lines 350-400) computes `dt` once, then may fast-fail-retry (non-zero exit, <2s, empty stdout, not resume) and re-run the subprocess — but `dt` is never recomputed after that retry. Once `dt` becomes the persisted `duration_s`, a round hitting this retry reports only the failed first attempt's sub-2s time, undercounting exactly the case the NEED_CONTEXT-summing Decision says to avoid — but that Decision's scope (`_reviewer_single.run()`-level resume calls) never reaches this in-`_invoke()` retry.
**Fix:** Decide whether `dt` should be recomputed/summed across the fast-fail retry, or explicitly accept the undercount, before plan-writing.

### [BLOCKING:design] Agent-mode retry/re-dispatch duration left ambiguous
**Section:** Decision "Agent-mode is in scope, with a reduced field set"; `mill-go-base/SKILL.md` "## Agent-mode dispatch" step 4(a)/(c).
**Issue:** Agent-mode `duration_s` is defined as "timestamp before `Agent()` vs. timestamp the completion `<task-notification>` arrives." Step 4(a)/(c) document that a raw-API-error triggers a fresh re-dispatch (new brief/session) and a stopped/interrupted notification can be stale, requiring an unbounded wait for a later real completion. The discussion never says whether `duration_s` should sum across such a retry (consistent with the NEED_CONTEXT-summing rationale) or measure only the final successful dispatch.
**Fix:** State explicitly whether agent-mode duration sums across a transient re-dispatch, consistent with the "true round cost" rationale already used for the NEED_CONTEXT case.

### [BLOCKING:design] Caller-enumeration claim is factually incomplete
**Section:** Technical context > `_reviewer_single.run()` bullet ("Confirmed callers ... only `_review_code.py`, `_review_discussion.py`, `_review_plan.py` (grepped repo-wide)"); Decision "Reviewer-call return contract becomes a small dataclass."
**Issue:** `plugins/mill/integration_tests/bench-reviewers.py` also calls `_reviewer_single.run()` directly, unpacks a bare `(text, _sid)` 2-tuple, and seeds `_reviewer_test_stub` with 2-tuples — a fourth caller the stated grep evidently missed (likely by excluding `integration_tests/`). The dataclass-conversion decision's "only 3 backends" framing rests on this enumeration being exhaustive; it is not.
**Fix:** Re-run the caller enumeration including `integration_tests/` before finalizing the "only 3 backends" scoping, or explicitly state the enumeration excludes integration tests and give their disposition.

## Verdict

REQUEST_CHANGES
Four undecided/false-premise gaps (cost_usd sourcing, two retry-duration ambiguities, incomplete caller enumeration) need resolving first.
MILL_REVIEW_END
