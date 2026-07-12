I have now thoroughly cross-checked all cards across all 5 batches against the actual source. Rendering the final verdict.

MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration -- holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-07-12
```

Cross-checked all 5 batches end-to-end against source: `_agent_dispatch.output_path_for`/`write_brief` (footer, unconditional `.out.md` truncation, default-off byte-identity) in `_agent_dispatch.py`; the four-cell `build_tool_rule` matrix in `_review_common.py` (non-agent cells byte-identical, agent cells carve out exactly one `Write`, defaults preserved for all 7 pre-existing positional callsites); `agent_mode` threading through `_review_discussion.prepare`, `_review_code.prepare`, and both `_review_plan.prepare` calls (batch-scope + holistic) while `_review_one_batch` and `run()`'s own `build_tool_rule` calls in `_review_plan.py` correctly stay non-agent; all three `millpy-review-*.py` CLIs correctly add `output_path` to the prepare envelope, pass `agent_mode=True`/`output_contract=True` only in `--stage prepare`, replace the `html.unescape` read with a missing-file guard, and preserve the plan-validator carve-out (no `output_path` on the `{"errors":...}` envelope). The five templates and `mill-reviewer.md` match cards 14-16 exactly (tool prohibitions and sole-output sentence deleted, `Write` granted with the briefs-scoped guardrail prose, discussion.md's false tool-use-mode claim removed, `mill-implementer.md` untouched). `mill-go/SKILL.md`'s reviewer-skipped capture, envelope-sourced `output_path`, no-ack-predicate note, and "Why not fork?" section (correct `roles.*.model` vs. reviewer-registry citations, verified against `mill-config.yaml`) all match card 19; `mill-start`/`mill-plan` SKILL.md rationale rewrites match cards 20-21. Test coverage is thorough and mocking discipline is followed precisely as specified (real `_agent_dispatch`/`_review_common` where the assertion requires it, `--slug` passed to avoid real git) in `test-agent-dispatch.py`, `test-review-common.py`, `test-agents-defs.py`, `test-review-templates.py`, `test-review-finalize.py`, `test-review-prepare-envelope.py`, and `test-review-output-contract.py`. No out-of-plan files found; no cross-batch contract violations; no utility duplication.

## Verdict

APPROVE
All 5 batches implement the plan precisely; cross-batch contracts, defaults, and test coverage all verified consistent.
MILL_REVIEW_END
