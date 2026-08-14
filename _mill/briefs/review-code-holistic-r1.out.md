MILL_REVIEW_BEGIN
# Review: mill-plan SKILL.md: step 6 max-rounds escape bugs, self-run validator citation errors, and Step 1.5 fix-table wrong remedies — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-14
```

## Verification notes

All 7 cards in batch 01 were traced against the live `mill-plan/SKILL.md` text and match the plan's literal replacement blocks byte-for-byte at their cited locations:

- Card 1 (`--revise` pre-check widened to `phase == "blocked"`, `revise_from_blocked` bound) — SKILL.md:56-61.
- Card 2 (Entry step-4 `phase: blocked` row) — SKILL.md:69.
- Card 3 (stale "no pre-existing blocked row" cross-reference fixed) — SKILL.md:100.
- Card 4 (`revise-{N+1}` namespacing narrowed to `revise_requested and not revise_from_blocked`; `blocked_resume_round`/`--max-rounds` threading added) — SKILL.md:264-276.
- Card 5 (`_status.set_blocked` added to Step 1.5 two-pass cap) — SKILL.md:306.
- Card 6 (`_status.set_blocked` added to both Step 4.5 branches) — SKILL.md:484-485.
- Card 7 (Go `-tags` remedy rewritten to chain a new invocation instead of comma-joining) — SKILL.md:332.

Cross-checked call signatures used by the new prose against actual source: `_status.set_blocked(status_path, reason, *, timestamp)` (`_status.py:244`), `_review_common.discover_round(reviews_dir, review_type, scope) -> int` (`_review_common.py:496`), and `millpy-review-plan.py`'s pre-existing `--max-rounds`/`--reviews-subdir` flags (lines 59, 117) — all match the plan's usage exactly; no Python was touched, consistent with the "no code changes" Shared Decision.

Verified the Category A/Category B round-cap-threading design (step 6 self-terminates on resume since the convergence gate/step-6 check stays keyed on the original, unbumped `max_review_rounds`; steps 1.5/4.5/5 resume with the loop's full remaining budget) against `_mill/discussion.md`'s `revise-blocked-resume (#852)` Decision — the implemented text matches that decision's Category A/B split verbatim, including the corrections from prior discussion-review rounds.

Verified the `#853` Go `-tags` remedy against `_plan_validate.py`'s `_verify_command_has_any_tag` (ANY-membership matching, `-tags` value scanned via `_RE_VERIFY_TAGS_FLAG.finditer`) — the "chain a new invocation" remedy round-trips cleanly on re-validation as the discussion's rationale claims.

A candidate scope gap was investigated (a stale `"line 104"` self-citation at SKILL.md:400, unrelated to any of the 7 cards) but `_mill/discussion.md` explicitly maps the task title's "self-run validator citation errors" clause to issue #854 and documents it as already-fixed/out-of-scope (Decisions § `already-fixed-issues`); the line-104 drift is a separate, never-in-scope cosmetic citation, not part of #852/#853 — not a finding.

## Verdict

APPROVE
All 7 cards faithfully implemented; design matches discussion.md decisions; no code/signature mismatches found.
MILL_REVIEW_END
