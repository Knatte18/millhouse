# Review: 1 — Implementer dispatch-CLI + Agent-resume fix (conflicts with 8) — 02-tests-and-skill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-tests-and-skill
date: 2026-05-05
```

## Findings

### [BLOCKING] `_make_fixture` missing `## Timeline` block
**Step:** Card 4, `_make_fixture` helper spec
**Issue:** The fixture `status.md` is specified with a top yaml block and `## Batches` section only. `_status.append_phase` — called by the CLI in the resume path (Test 4: "calls `_status.append_phase` for `fixing-{batch_name}-r{N}`") — requires a ```` ```text ```` fenced `## Timeline` block to exist; without it, `_split_fences(tl_text, _TIMELINE_FENCE)` raises `ValueError: No ```text block in status file`. Test 4 will error at runtime, not at the assertion.
**Fix:** Add a `## Timeline` section with a ```` ```text ```` fence and at least one row (e.g. `implementing  2026-01-01T00:00:00Z`) to the `status.md` produced by `_make_fixture`. `_status.append_phase` is not patched, so the real implementation runs against the fixture.

### [NIT] Stuck escalation section has stale "catch LLMError" guidance
**Step:** Card 5, Edit 2 (and implicit non-edit of `### Stuck escalation`)
**Issue:** After Edits 1 and 2 migrate both dispatch and resume to CLI invocations, the Builder no longer calls `_implementer_sonnet.run` directly. The Stuck escalation section still says "catch `_llm_claude.LLMError` specifically (not bare `Exception`) so genuine programmer errors still propagate." The Builder reads JSON from CLI stdout — it never catches Python exceptions. The note is now meaningless guidance.
**Fix:** Replace the LLMError catch note with "When the CLI outputs `stuck_type: transient`, apply the one-retry policy (re-invoke CLI with a fresh batch-name argument, no `--resume`)."

### [NIT] "Follow the exact pattern" conflicts with "class-level setUp"
**Step:** Card 4, Requirements preamble
**Issue:** The plan says "Follow the exact pattern of `test-millpy-validate-plan.py`" but that file uses per-function `with unittest.mock.patch(...)` blocks; the plan then prescribes "module-level patches applied to all tests (via `setUp` or class-level)", which requires `unittest.TestCase`. These are structurally incompatible; an implementer reading both instructions will need to guess which takes precedence.
**Fix:** Drop "Follow the exact pattern of `test-millpy-validate-plan.py`" as the framing sentence; replace with "Use `unittest.TestCase` with a `setUp` that applies all common patches via `self.patcher_*` / `addCleanup`." Retain the importlib loading pattern reference from the existing file explicitly.

## Verdict

REQUEST_CHANGES
One BLOCKING: `_make_fixture` omits the required `## Timeline` section; Test 4 will error at runtime.