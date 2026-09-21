MILL_REVIEW_BEGIN
# Review: Misc infra/wiki/PR/self-hosting reliability bugs

```yaml
duration_s: 196.0
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/_mill/discussion.md
date: 2026-09-21
```

## Findings

### [BLOCKING:design] #1102 misattributes 0.55 to compute_batch_baselines
**Section:** Decision `baseline-preflight-lazy-not-eager (#1102)`, first bullet.
**Issue:** The bullet claims "0.5", "0.55 Done-gate baseline pre-flight", and "0.6" "all three currently drive `_verify_baseline.compute_batch_baselines`." Reading `mill-go-base/SKILL.md` §0.55 and `_done_gate.py` shows 0.55 calls `_done_gate.run_preflight(gate_cmd, git_root)` — a distinct mechanism (a pre-implementation regression-suite snapshot for Handoff comparison) that never touches `compute_batch_baselines`; only 0.5 and 0.6 (via `--stage baseline`) do.
**Fix:** Remove 0.55 from this decision's scope enumeration, or add an explicit statement that 0.55 is unaffected — 0.55's snapshot must stay eager (it exists specifically to run "before any batch touches the tree"), so converting it to lazy per this decision's framing would silently break its own stated purpose.

### [BLOCKING:design] #1092's occurrence counts/premise contradict the source
**Section:** Decision `skill-cross-reference-no-bare-cd-bait (#1092)`.
**Issue:** Grep of `mill-plan/SKILL.md` shows 12 occurrences of `mill-go-base/SKILL.md`, not the stated "9". Grep of `mill-start/SKILL.md` shows a mix of the repo-relative `plugins/mill/skills/mill-go-base/SKILL.md` form AND at least two bare `mill-go-base/SKILL.md` occurrences (lines ~300, ~320) — contradicting the decision's premise that mill-start "already" uniformly uses the safer repo-relative form.
**Fix:** Re-derive the occurrence counts and confirm mill-start's bare occurrences are also in scope for the `${CLAUDE_PLUGIN_ROOT}` rewrite, not just mill-plan's; state the enumeration method (exact grep command) so a plan writer can reproduce the count rather than trusting a stale/wrong figure.

### [NIT:consistency] Wrong function name for review finalize path
**Section:** Decision `review-duration-derived-not-trusted (#1097)` and `## Technical context`.
**Issue:** Both cite `_review_common.py`'s "`finalize`" function; the actual function is `finalize_scope` (no function literally named `finalize` exists in that file).
**Fix:** Correct the name to `finalize_scope` in both spots so a plan writer greps the right symbol.

## Verdict

REQUEST_CHANGES
Two BLOCKING findings rest on source-contradicted premises (#1102 §0.55 misattribution, #1092 wrong occurrence counts/mixed forms).
MILL_REVIEW_END
