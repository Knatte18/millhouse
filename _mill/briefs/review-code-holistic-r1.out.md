MILL_REVIEW_BEGIN
# Review: millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-08-12
```

## Findings

No findings.

Verified end-to-end across all 5 batches:

- **Batch 1** (`_review_cli.py::print_error_envelope`): `error_kind`/`round` kwargs added exactly as specified, defaults preserve today's behavior, docstring updated, `print_error` untouched. Card 2's test extends `test_print_error_envelope_shape` with default-lock-in and explicit-override assertions, reusing the existing "plan" envelope per the card's instruction, matching the file's print/failures-counter convention.
- **Batch 2**: every `print_error_envelope` call site in all three CLIs threads `round=` — verified via grep, 9/9 sites in `millpy-review-code.py`, all sites in `-plan.py`/`-discussion.py`. The `round_n`-vs-`args.round` distinction (plan/discussion outer catch uses resolved `round_n`; code's outer catch uses `args.round` directly since `--round` is required there) matches Cards 3–5 exactly. Tests (Cards 6–7) cover pre-launch round threading and the outer-catch dead path for all three CLIs, including the newly-added `millpy_review_code` importlib block and the `ReviewError` import fix.
- **Batch 3**: `error_kind: "reviewer"` added only to each `finalize()` wrapper's `except ReviewError` dict/`ReviewResult` entry in `_review_plan.py`, `_review_discussion.py`, `_review_code.py` — success paths and `run()`/`_review_one_batch()` correctly left untouched, matching the batch's documented scope boundary. Card 11's direct-`finalize()`-call tests in all three `*-flow.py` files assert `error_kind == "reviewer"` without going through `run()`.
- **Batch 4**: `append_demotion_note` added to `_review_common.py` immediately between `rewrite_verdict_token` and `write_review_file`, with matching heading/token/summary-line location logic and no-op-safe fallbacks. `finalize_scope` wires it in unconditionally on `demoted_any`, independent of `rewrite_verdict_token`'s narrower gate; `demoted_count` is always bound. `review-output.schema.md`'s `## Verdict` contract section updated with the optional third line, matching the exact note format. Card 15's three new tests (flip / no-flip / absent) reuse existing fixture helpers and assert the exact on-disk note text.
- **Batch 5**: all four SKILL.md/`.md` sites (`mill-start`, `mill-plan`, `mill-go-base/SKILL.md`, `mill-go-base/holistic-review.md`) gained the usage-error immediate-halt paragraph ahead of the existing ERROR-only-aggregate trigger, with the trigger's lead-in correctly narrowed to exclude `error_kind: "usage"` entries. Halt wording is distinct from each site's existing `ERROR-only round {N}` phrasing per site. The `mill-plan` halt correctly matches the verified existing `BLOCKED: review ERROR-only round {N}` wording (no "plan" token) rather than assuming symmetry. `holistic-review.md`'s usage-error halt correctly bypasses sub-step 3.6's rate-limit fallback entirely, and 3.6's own body is untouched. Cross-references (`mill-go-base/SKILL.md`'s "Post-dispatch form" paragraph) are unmodified as required.

No out-of-plan files, no cross-batch contract violations, no duplicated helpers, no naming/style deviations from surrounding code. Every file in "All Files Touched" is accounted for and no extra file appears.

## Verdict

APPROVE
All five batches faithfully realize the plan; no BLOCKING or NIT findings identified.
MILL_REVIEW_END
