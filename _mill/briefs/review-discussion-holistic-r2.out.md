MILL_REVIEW_BEGIN
# Review: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

## Findings

### [BLOCKING:design] parse_verdict failures never reach the CLI's `except ReviewError` block
**Section:** Decisions > "error_kind bucketing" / Scope > In: (`millpy-review-plan.py` reclassification).
**Issue:** The Decision rejects "an earlier hypothesis that `finalize_scope` internally catches parse failures and returns an ERROR-shaped dict with cost metadata" as incorrect, and concludes `parse_verdict`'s `ReviewError` propagates uncaught to `millpy-review-plan.py:307-309`. Direct read of `_review_plan.py::finalize()` (lines 706-732, called at `millpy-review-plan.py:286`) shows it has its own `try/except ReviewError` around the call to `_review_common.finalize_scope`, and on catch builds and *returns* (does not raise) an ERROR-shaped dict with `apply_cost_metadata` already applied — i.e. exactly the rejected hypothesis, just one function down (`_review_plan.finalize`, not `_review_common.finalize_scope`). That returned dict flows into `result_dict` and is printed via `print(json.dumps(result_dict)); return 0` at line 305-306 — it never reaches `print_error_envelope` or the line-307 `except ReviewError` block at all. Identical pattern confirmed in `_review_discussion.py::finalize()` (lines 193-227) and `_review_code.py::finalize()` (lines 574-607).
**Fix:** Retarget the reviewer-kind `error_kind` addition to each CLI-wrapper `finalize()`'s own `except ReviewError` branch (the dict/`ReviewResult` it constructs), not to `print_error_envelope` or the outer CLI-level `except ReviewError`; re-verify whether that outer block is ever reachable for a genuine reviewer-output cause at all.

### [BLOCKING:design] Retry-semantics decision doesn't cover mixed-`error_kind` multi-scope envelopes
**Section:** Decisions > "Retry semantics keyed on error_kind"; Technical context (mill-plan/SKILL.md Step 4.5).
**Issue:** `error_kind` is defined per-`reviews[]`-entry, and `mill-plan/SKILL.md` Step 4.5's existing trigger condition is "non-empty `reviews[]` array AND *at least one* entry's verdict is ERROR" (line 451) — a materially different, weaker condition than `mill-start`/`mill-go-base`'s "top-level verdict ERROR (or every entry ERROR)" (lines 288, 780). For per-batch plan review, one batch could fail with `error_kind: "usage"` while another succeeds or fails with `"reviewer"`. The Decision states retry logic keys on "the envelope's `error_kind`" as if singular, with no rule for aggregating across a mixed `reviews[]` list.
**Fix:** Add a decision for how the four consumer sites aggregate `error_kind` across multiple `reviews[]` entries (e.g. "any usage entry halts immediately regardless of other entries' kind"), and reconcile mill-plan's any-vs-all trigger asymmetry with the other three sites.

### [BLOCKING:consistency] "round: 0 fix" decision contradicts itself on which sites thread `args.round`
**Section:** Decisions > "round: 0 fix".
**Issue:** First sentence: "Every call site in `millpy-review-plan.py` passes `args.round` when available — which is every site, since `args = parser.parse_args(...)` runs before any error branch." Next sentence: "Prepare-stage call sites keep `round=0` (or omit the param) since no round has been assigned yet." These conflict — either every site (including config/registry/slug/prepare, lines 180/187/193/260/263, which run for any `--stage`) passes the raw `args.round` (commonly `None`, since `--round` is typically supplied only at finalize), or prepare-stage sites hardcode 0. As written a plan writer cannot tell whether early failures should now emit `"round": null` (breaking the "preserving today's behavior" claim) or `"round": 0`.
**Fix:** State explicitly whether `args.round` is coalesced (`args.round or 0`) at every site, or whether pre-stage-branch vs. prepare-stage vs. finalize-stage sites are handled differently, and pick one uniformly.

### [BLOCKING:scope] `review-output.schema.md` update is described but absent from Scope > In:
**Section:** Scope > In: vs. Technical context.
**Issue:** Technical context states the demotion-note addition makes `## Verdict` a three-line section, "so this schema doc needs a one-line update describing when the note appears" — confirmed accurate against `review-output.schema.md:122-130`, which currently documents `## Verdict` as "exactly two lines." This deliverable is never listed under Scope > In:, only mentioned in passing under Technical context, so a plan writer working strictly from the In: bullet list would miss it.
**Fix:** Add a Scope > In: bullet for the `review-output.schema.md` `## Verdict` contract update.

## Verdict

REQUEST_CHANGES
Core error_kind fix targets a code path parse-verdict failures never reach; also unresolved multi-scope/round/schema gaps.
MILL_REVIEW_END
