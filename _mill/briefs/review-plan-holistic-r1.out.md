MILL_REVIEW_BEGIN
# Review: Misc infra/wiki/PR/self-hosting reliability bugs — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: plan/
date: 2026-09-21
```

## Findings

### [BLOCKING:design] Card 3's `error` field can't be split from the existing combined branch
**Location:** Batch 2, Card 3 (`_pr_state.py`). **Issue:** `resolve_pr_state` currently has ONE combined branch, `if result.returncode != 0 or not result.stdout.strip(): return dict(_none_result)` (line 79) — the two conditions are OR'd into a single `if`, not two separate branches. Card 3's Requirements describe "the `result.returncode != 0` branch" as though it already exists standalone and instruct populating `error` there while leaving the "empty stdout" case untouched, but as written this requires the implementer to first split the combined conditional — a restructuring the Requirements never states. **Fix:** explicitly instruct splitting line 79 into two separate `if` statements (non-zero returncode with `error` set; empty-stdout-with-rc==0 with `error: None`) before describing which branch gets the new key.

### [BLOCKING:scope] Card 11 Context omits `_status.py` despite naming its functions
**Location:** Batch 4, Card 11 (`millpy-implement.py`). **Issue:** Requirements explicitly call `_status.get_baseline_parent_sha(status_path)` and `_status.set_baseline_parent_sha(status_path, ...)` (both added by Card 8), but Card 11's `Context:` lists only `_parent_branch.py`, `_subprocess_util.py`, `_implementer_common.py` — `_status.py` is absent. None of the Context-completeness exemptions (same-line prohibition, citation/escape marker, quoted material, git-ignored, out-of-repo, trailing-slash, forward-reference-to-later-Creates) apply; Card 8 is an earlier card in the same batch, not a later card's `Creates:` target. **Fix:** add `plugins/mill/scripts/_status.py` to Card 11's `Context:`.

### [BLOCKING:design] Card 12's "speculative early launch" text describes a mechanism that no longer exists post-Card-11
**Location:** Batch 4, Card 12 (`mill-go-base/SKILL.md`, "0.5 Baseline pre-flight" / entry-gate-wait speculative launch, lines ~579-612 of the current file). **Issue:** the current "First check" paragraph explicitly does a "SECOND, ordinary (no `--module-wide-only`) `--stage baseline` invocation for the per-batch substage only" after consuming the early-launch log — but Card 11 removes the per-batch substage from `--stage baseline` entirely, so that second call has nothing left to do. Card 12's Requirements only say to update wording to "one JSON line" and remove mentions of the flag/second line — they never instruct removing this now-purposeless "second call" step itself, which is a structural deletion, not a terminology substitution. **Fix:** explicitly instruct deleting the "then proceed to run a SECOND... invocation" clause (and its `"exit"`/`"running"` branch text built around it), since the speculative early launch alone now IS the complete baseline computation.

### [BLOCKING:consistency] Card 5's halt message duplicates guidance already covered by Card 3's structural gap
**Location:** Batch 2, Card 5 (`mill-merge/SKILL.md`). **Issue:** Card 5's correctness is downstream of Card 3's `error` field actually distinguishing a `gh` failure from a genuine empty result (see the first finding above). If Card 3 ships with `error` incorrectly populated for the empty-stdout "no PR" case too, Card 5's new halt branch will fire on ordinary no-PR outcomes, turning a routine `pr-pending`-phase halt into a bogus "investigate gh auth" halt for every task with no PR yet. **Fix:** resolve Card 3's finding first; no independent Card 5 text change is otherwise needed — flagged here only because the coupling isn't called out in Card 5's own Requirements.

### [NIT:consistency] Card 1's test guidance mocks a function the fix removes from the call path
**Location:** Batch 1, Card 1 Batch Tests (`test-wiki-health-check.py`). **Issue:** the test description says to patch `wiki._client.wait_for_socket_reachable` "forced True immediately, so the loop reaches the health-probe check on its very first iteration" — but Card 1's own Requirements replace (not chain after) the `wait_for_socket_reachable` call with the health probe, so after the fix `_ensure_daemon`'s post-spawn loop never calls `wait_for_socket_reachable` at all. The patch is harmless (an unused mock) but the stated rationale ("so the loop reaches...") is inaccurate and could mislead an implementer into keeping a dead call just to satisfy it. **Fix:** drop the `wait_for_socket_reachable` patch from the test description, or note it as vestigial/no-op.

### [NIT:consistency] `derive_duration_s`'s module placement diverges from `_mill/discussion.md`'s stated Decision without noted rationale
**Location:** Batch 5, Card 13 (`_agent_dispatch.py`). **Issue:** `_mill/discussion.md`'s `review-duration-derived-not-trusted` Decision explicitly says "add a small shared helper in `_review_common.py`, e.g. `derive_duration_s(...)`", but Card 13 places it in `_agent_dispatch.py` instead (co-located with `prepare_ts_path_for`/`output_path_for`). This is arguably a better home (all three suffix-mapping helpers together) but silently overrides an explicit discussion Decision with no rationale recorded in the plan. **Fix:** add a one-line note in Card 13 (or the batch's Shared-Decisions-adjacent scope text) stating the deliberate relocation and why.

## Verdict

REQUEST_CHANGES
Two BLOCKING gaps in Cards 3/11/12 risk incorrect `error` semantics and a broken doc rewrite; fix before re-review.
MILL_REVIEW_END
