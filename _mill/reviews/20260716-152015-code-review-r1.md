MILL_REVIEW_BEGIN
# Review: Agent-mode dispatch: envelope fields and session/runtime state are unreliable — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-16
```

## Findings

(none)

All six batches were verified against their cards and the shared decisions:

- Batch 1: `_agent_dispatch.resolve_dispatch_mode` defaults to `"agent"` (code + docstring + renamed/updated test); `millpy-implement.py`'s three-way prepare branch (resume-incomplete / prepare-reuse / fresh-mint) matches Card 2's spec exactly, gated correctly on `args.stage == "prepare"` and mutually exclusive with `--resume-incomplete`; `emit_prepare(..., start_sha=start_sha)` wired; push failure is a non-fatal warning while commit failure still returns 1, with tests covering both sub-cases.
- Batch 2: `emit_prepare` gained `effort: str | None = None` mirroring `start_sha`'s conditional-inclusion pattern; both `millpy-implement.py` and `millpy-fix.py` thread their already-resolved `impl_effort`/`fixer_effort` into the prepare-stage `emit_prepare` call; unit tests (case 65, `test_stage_prepare_batch_scope_includes_effort_from_fixer_spec`, `test_9_model_and_effort_from_config`) all present.
- Batch 3: `_review_code.py`, `_review_plan.py` (both batch and holistic return sites), `_review_discussion.py` all surface `"effort": <spec>.get("effort")` using the correct post-large-prompt-switch spec variable at each return site. All three CLIs conditionally add `envelope["effort"]` only when non-None, matching the `start_sha` convention. `mill-go/SKILL.md` documents the `effort` envelope field, the recorded Agent-tool `model` Builder variable, and the intentional agent-mode gap for `effort` — all as specified in Card 11.
- Batch 4: `apply_actual_model_override` and `finalize_scope`'s new `actual_model` kwarg in `_review_common.py` match the spec (identity on `None`, in-place rewrite of a well-formed line, fallback injection after the verdict-carrying `` ```yaml `` fence). All three backends' `finalize()` thread `actual_model` through to the success-path `finalize_scope` call only, leaving the `ReviewError` fallback path untouched as required.
- Batch 5: all three review CLIs gained `--actual-model`, forwarded into `finalize(...)`; `mill-go/SKILL.md` step 6 documents threading it from the step-3 recorded variable. Test coverage in `test-review-finalize.py` and `test-review-cli.py` exercises both the override and omitted-flag cases per CLI.
- Batch 6: `_claude_settings.py`'s `merge_permission_allowlist` and `MILL_SUBAGENT_TOOLS` match Card 18 exactly (order-preserving, no-dup, no-op write-skip, other top-level keys untouched); `MILL_SUBAGENT_TOOLS` is verified against the union of `mill-implementer.md`/`mill-reviewer.md` `tools:` frontmatter by a dedicated test rather than a second hardcode. `mill-setup/SKILL.md` Phase 4.8 calls the helper unconditionally after the `MILL_PYTHON` write/no-op branch, consistent with the idempotency pattern, and documents the no-restart-needed distinction.

Cross-batch contracts checked and consistent: Batch 2/3's `effort` conditional-inclusion convention matches Batch 1's `start_sha` precedent; Batch 3's SKILL.md-recorded `model` Builder variable is consumed correctly by Batch 5's step-6 edit; Batch 4→5's `actual_model` parameter threads cleanly from backend to CLI flag. No out-of-plan files, no duplicated helpers, no naming/style deviations from surrounding code observed.

## Verdict

APPROVE
All six batches match their plan cards; cross-batch contracts hold; test coverage is comprehensive.
MILL_REVIEW_END
