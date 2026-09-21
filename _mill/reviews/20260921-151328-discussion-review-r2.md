MILL_REVIEW_BEGIN
# Review: Misc infra/wiki/PR/self-hosting reliability bugs

```yaml
duration_s: 189.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: /home/knatte/Code/millhouse/wts/mill-infra-reliability-misc-r2/_mill/discussion.md
date: 2026-09-21
```

## Findings

### [NIT:consistency] #1092 bare/qualified line breakdown is inverted
**Demoted-from:** BLOCKING
**Section:** Decision: skill-cross-reference-no-bare-cd-bait (#1092)
**Issue:** Discussion claims lines ~198,300,302,318,320,324 are "bare" and ~262,264,265,275 are "already-qualified" in `mill-start/SKILL.md`. Reading the actual file: 302, 318 are qualified (`plugins/mill/skills/mill-go-base/SKILL.md`), and 264 is bare (`` `mill-go-base/SKILL.md` `` with no prefix) — the true split is 4 bare (198, 264, 300, 320) / 6 qualified (262, 265, 275, 302, 318, 324), not 6/4 as stated.
**Fix:** Re-verify and correct the per-line classification before plan writing; the total count (10) and "both forms in scope" conclusion are unaffected, but presenting an "exact counts, reproducible via grep" claim with a wrong breakdown risks a plan writer trusting stale line numbers for the mechanical edit.

### [NIT:design] #1097 derivation site lacks a concrete function signature
**Section:** Decision: review-duration-derived-not-trusted (#1097)
**Issue:** The decision says derivation happens in "the shared finalize path in `_review_common.py` (`apply_cost_metadata` / `finalize_scope`'s `duration_s` handling)", but neither function currently receives a brief path or `briefs_dir` (`finalize_scope` takes `reviews_dir`, distinct from `write_brief`'s `briefs_dir`) — there is no parameter today from which either function could locate a sibling `.prepare_ts` file. Verified: each of the three CLIs (e.g. `millpy-review-discussion.py`) does already hold `agent_output_path` (`--agent-output`) at the finalize stage, which the `.prepare_ts` path could be derived from — so this is resolvable, just unstated.
**Fix:** Name the actual insertion point explicitly (e.g. a new shared helper in `_review_common.py` taking `agent_output_path` + caller-supplied `duration_s`, called from each of the three CLIs before `finalize_scope`) so the three call sites don't independently invent divergent wiring.

## Verdict

APPROVE
One BLOCKING: #1092's stated bare/qualified line breakdown contradicts the actual file contents.
_Note: 1 finding(s) demoted from BLOCKING to NIT by the stage's blocking-class ceiling; current blocking_count is 0._
MILL_REVIEW_END
