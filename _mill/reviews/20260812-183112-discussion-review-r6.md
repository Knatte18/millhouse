MILL_REVIEW_BEGIN
# Review: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale

```yaml
duration_s: 183.0
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 4.5 (self-assessed; unverified)
reviewed_file: _mill/discussion.md
date: 2026-08-12
```

Independently re-verified every source citation against current worktree code (not prior review output): `_review_cli.py::print_error_envelope` (24-45), `millpy-review-plan.py` `main()` call sites (180, 187, 193, 260, 263, 267, 308, 354, 357 — exact), `_review_plan.py::finalize` (662-746, catch 712-732 — exact), `_review_discussion.py::finalize` (153-246, catch 206-227 — exact), `_review_code.py::finalize` (519-626, catch 580-607 — exact), `_review_common.py::parse_verdict` (1569 — exact), `finalize_scope` (2465, `demoted_any` at 2540, gate at 2552 — exact), `rewrite_verdict_token` (2186, docstring confirms summary line untouched), `resolve_blocking_classes` (2614-2645, "Never raises" confirmed by every branch), `DEFAULT_BLOCKING_CLASSES` (2601), `ReviewResult` dataclass + `to_dict()` (346-372, fixed field set confirmed), and all four SKILL.md `ERROR-only-aggregate` sites (mill-start:286, mill-plan:449, mill-go-base/SKILL.md:778, holistic-review.md:112 — line numbers exact; ANY-vs-ALL trigger asymmetry claim confirmed verbatim in each file). `millpy-review-code.py`'s `--round`-required-before-try-block claim (240-242) also confirmed. No `CONSTRAINTS.md` confirmed absent repo-wide. No factual or citation error found anywhere checked.

Decisions all carry rationale + rejected alternatives, including the two self-corrections from prior rounds (error_kind bucketing site, round_n vs args.round at the dead finalize-stage outer catch), both of which now match the code exactly. Scope in/out is unambiguous; Testing section names concrete TDD-candidate tests per function plus an explicit unit-test strategy for the acknowledged-dead defensive path. No undecided items or TBDs remain.

## Verdict

APPROVE
All source citations independently re-verified exact; decisions, scope, and testing are complete and self-consistent.
MILL_REVIEW_END
