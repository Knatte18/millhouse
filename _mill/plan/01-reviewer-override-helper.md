# Batch: reviewer-override-helper

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
batch: reviewer-override-helper
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py
depends-on: []
```

## Batch Scope

This batch adds one shared validation helper, `_reviewers.resolve_reviewer_override(registry, name, *, reject_non_claude)`, to `plugins/mill/scripts/_reviewers.py` (Card 1). It also makes a small, unrelated-in-cause but load-bearing-for-testing fix to `_reviewer_single.py`'s `test_stub`-provider dispatch branch (Card 2): the branch never forwards `effort` to `_reviewer_test_stub.run()`, even though the stub's `run()` signature already accepts an `effort` keyword — every other provider branch in the same function already forwards `effort` (`kwargs["effort"] = spec.get("effort")` at the real-provider dispatch path), so this is a one-line completion of an existing, already-designed parameter, not a new capability. It is included here because the `unit-tests-discussion` and `unit-tests-plan` batches' large-prompt-switch-skip tests (Cards 15 and 17) distinguish which `test_stub`-provider reviewer spec actually dispatched via `stub.captured_prompts()[-1][1]["effort"]` — that assertion is unsatisfiable without this fix, since today the stub always records `effort: None` regardless of the resolved spec.

All four downstream call sites in batches `discussion-review-cli` and `plan-review-cli` (`_review_discussion.py`'s `prepare()`/`run()`, `_review_plan.py`'s `prepare()`/`run()` holistic branches) call `resolve_reviewer_override` with `reject_non_claude=True` from `prepare()` (Agent-mode dispatch is Claude-only by construction) and `reject_non_claude=False` from `run()` (the direct-dispatch path already dispatches non-Claude reviewers via ordinary config today and must keep doing so). This is the only batch with no dependencies other than itself; `discussion-review-cli`, `plan-review-cli`, `unit-tests-discussion`, and `unit-tests-plan` all depend on it.

## Cards

### Card 1: add `_reviewers.resolve_reviewer_override`

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/_reviewers.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a new public function `resolve_reviewer_override(registry: dict, name: str, *, reject_non_claude: bool) -> dict` to `_reviewers.py`, placed immediately after `resolve()` (currently ending at line 407) and before `resolve_role()` (currently starting at line 410). Behavior, in this exact order:
  1. Call `resolve(registry, name)`. Let any `ReviewerError` it raises (unknown name) propagate unchanged.
  2. If the returned `spec.get("type") == "cluster"`: raise `ReviewerError(f"--reviewer {name!r} is cluster type; only single reviewers are supported for a per-round override")`.
  3. If `spec.get("model") is None` (this is the case for the `test_stub` synthetic spec returned by `resolve()`'s special-case branch at lines 382-383, which has no `model` key at all): raise `ReviewerError(f"--reviewer {name!r} has no model (e.g. test_stub); not supported for a per-round override")`. This check MUST run before step 4 — a naive `_agent_dispatch.model_to_tier(spec.get("model"))` call on a spec with no `model` key would fail with `AttributeError` (`None` has no `.startswith(...)` attribute, and `model_to_tier` calls `model.startswith(family)` for each known family) before ever reaching `model_to_tier`'s own `ValueError` path, so the missing-model case needs its own explicit, earlier branch.
  4. If `reject_non_claude` is True: add a local `import _agent_dispatch` inside this function (mirroring the existing local import inside `tier_rank()` at line ~500 — `_agent_dispatch.py` imports `_review_common.py` at module level, so a module-level `import _agent_dispatch` at the top of `_reviewers.py` would need to be checked for cycles; the local-import convention this codebase already established for the same cross-module call is the safe, precedented choice, so follow it rather than adding a new top-level import). Call `_agent_dispatch.model_to_tier(spec["model"])`; catch `ValueError` and re-raise as `ReviewerError(f"--reviewer {name!r}: {exc}")`.
  5. Return `spec`.
  Update the module docstring's `Public API:` list (currently ending with `fixer_weaker_than_reviewer_warning`) to add a one-line entry for `resolve_reviewer_override` in the same style as the existing entries.
- **Commit:** `mill: add _reviewers.resolve_reviewer_override for --reviewer flag validation`

### Card 2: forward `effort` to the `test_stub` provider dispatch branch

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_reviewer_single.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `run()`'s `provider == "test_stub"` branch (currently `return stub.run(prompt_text, session_id=session_id, resume=resume, timeout=timeout)`), add `effort=spec.get("effort")` to the forwarded keyword arguments: `return stub.run(prompt_text, session_id=session_id, resume=resume, timeout=timeout, effort=spec.get("effort"))`. This mirrors the `effort` forwarding every other provider branch in this same function already does (`kwargs["effort"] = spec.get("effort")`, used by the `llm.run_tool_use`/`llm.run_bulk` call a few lines below) — `_reviewer_test_stub.run()`'s signature already accepts an `effort: str | None = None` keyword, so this closes an existing gap in the dispatch contract rather than adding a new one.
- **Commit:** `mill: forward effort to test_stub provider dispatch in _reviewer_single.py`

## Batch Tests

`verify:` runs the existing `test-reviewers.py` suite unchanged (this batch adds no test file — the new tests for `resolve_reviewer_override` are added in batch `unit-tests-discussion`, which depends on this batch; the `effort`-forwarding fix from Card 2 is exercised indirectly by `unit-tests-discussion`'s and `unit-tests-plan`'s large-prompt-switch-skip tests). Running the existing suite here confirms neither change breaks any existing `_reviewers.py`/`_reviewer_single.py` behavior (load/resolve/resolve_role/validate_role_refs/tier_rank, and the existing `test_single_test_stub_forwards_prompt`/`test_single_claude_bulk_mode`/`test_single_claude_tool_use_mode`/`test_single_gemini_bulk_mode` dispatch tests already in `test-reviewers.py`).
