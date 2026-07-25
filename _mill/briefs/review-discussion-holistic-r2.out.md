MILL_REVIEW_BEGIN
# Review: Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)

```yaml
verdict: APPROVE
reviewer_model: sonnetmax
reviewed_file: _mill/discussion.md
date: 2026-07-25
```

Verified against source: the verbatim gap text in `mill-go/SKILL.md` ("has no corresponding Agent-tool parameter to forward it to"; Agent tool call takes only `subagent_type`/`model`/`prompt`/optional `isolation`); the four already-correct envelope sites (`_review_discussion.py:123`, `_review_plan.py:453,545`, `_review_code.py:382` all return `spec.get("effort")`); the fifth, broken site (`millpy-merge-in-subagent.py:356,437` call `emit_prepare` without `effort=`, while `impl_effort` is computed at :328 and correctly forwarded to `_implementer_claude.run` at :363/:444); `emit_prepare`'s existing `effort: str | None = None` kwarg in `_implementer_common.py` (confirms the merge-in fix is a pure 2-line addition, no signature change needed); `mill-agents.yaml`'s exact effort values (opusmedium/opus/opushigh/opusmax/sonnetmedium/sonnet/sonnethigh/sonnetmax vs. haiku/g25flash/g25pro/g3flash_preview carrying none); base agent files' absence of `model:` and existing `test-agents-defs.py` structure the new parametrized cases extend; and `_agent_dispatch.resolve_dispatch_mode`/`model_to_tier`. Also confirmed `mill-go/SKILL.md`'s "## Agent-mode dispatch" section is the single cross-referenced source of truth invoked by `mill-start/SKILL.md` and `mill-plan/SKILL.md` for discussion-review and plan-review dispatch respectively — so the Scope's single-site edit (mill-go step 3) is sufficient to cover all three review CLIs, not just code-review, despite living in one file.

All `### Decision:` blocks carry rationale and a rejected alternative; the Q&A log resolves every open question raised in round 1 (including the merge-in scope question) with grounded "why"; Scope In/Out is unambiguous and each Out item is justified against present catalogue state (YAGNI on unused tiers, no schema change needed, gemini path unaffected); the fallback-on-unrecognized-effort path is proven strictly non-regressive against today's always-base behavior; Testing names a concrete TDD path and explicitly justifies the absence of an integration test (Agent-tool effort application is unobservable from `integration_tests/`), deferring verification to code read-through — an accepted, reasoned limitation rather than a silent gap.

No undecided items, no unaddressed failure modes, no scope ambiguity found.

## Verdict

APPROVE
All claims verified against source; decisions grounded with rationale and rejected alternatives; no gaps found.
MILL_REVIEW_END
