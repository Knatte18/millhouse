# Batch: reviewer-override-helper

```yaml
task: 'Review dispatch: no per-round reviewer override, and reviewer_model echoes the dispatch flag instead of the model that ran'
batch: reviewer-override-helper
number: 1
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-reviewers.py
depends-on: []
```

## Batch Scope

This batch adds one shared validation helper, `_reviewers.resolve_reviewer_override(registry, name, *, reject_non_claude)`, to `plugins/mill/scripts/_reviewers.py`. It is the single place that resolves a `--reviewer` CLI value and rejects the three cases the discussion decided are unusable for a per-round override (cluster-type specs, the model-less `test_stub` synthetic spec, and — only when `reject_non_claude` is True — non-Claude-provider specs that `_agent_dispatch.model_to_tier` cannot classify). All four downstream call sites in batches `discussion-review-cli` and `plan-review-cli` (`_review_discussion.py`'s `prepare()`/`run()`, `_review_plan.py`'s `prepare()`/`run()` holistic branches) call this one helper with `reject_non_claude=True` from `prepare()` (Agent-mode dispatch is Claude-only by construction) and `reject_non_claude=False` from `run()` (the direct-dispatch path already dispatches non-Claude reviewers via ordinary config today and must keep doing so). This is the only batch with no dependencies other than itself; both `discussion-review-cli` and `plan-review-cli` depend on it.

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
  3. If `spec.get("model") is None` (this is the case for the `test_stub` synthetic spec returned by `resolve()`'s special-case branch at lines 382-383, which has no `model` key at all): raise `ReviewerError(f"--reviewer {name!r} has no model (e.g. test_stub); not supported for a per-round override")`. This check MUST run before step 4 — a naive `_agent_dispatch.model_to_tier(spec.get("model"))` call on a spec with no `model` key would fail with `TypeError` (None is not a valid argument to `model.startswith`) before ever reaching `model_to_tier`'s own `ValueError` path, so the missing-model case needs its own explicit, earlier branch.
  4. If `reject_non_claude` is True: add a local `import _agent_dispatch` inside this function (mirroring the existing local import inside `tier_rank()` at line ~500 — `_agent_dispatch.py` imports `_review_common.py` at module level, so a module-level `import _agent_dispatch` at the top of `_reviewers.py` would need to be checked for cycles; the local-import convention this codebase already established for the same cross-module call is the safe, precedented choice, so follow it rather than adding a new top-level import). Call `_agent_dispatch.model_to_tier(spec["model"])`; catch `ValueError` and re-raise as `ReviewerError(f"--reviewer {name!r}: {exc}")`.
  5. Return `spec`.
  Update the module docstring's `Public API:` list (currently ending with `fixer_weaker_than_reviewer_warning`) to add a one-line entry for `resolve_reviewer_override` in the same style as the existing entries.
- **Commit:** `mill: add _reviewers.resolve_reviewer_override for --reviewer flag validation`

## Batch Tests

`verify:` runs the existing `test-reviewers.py` suite unchanged (this batch adds no test file — the new tests for `resolve_reviewer_override` are added in batch `unit-tests`, which depends on this batch). Running the existing suite here confirms the new function does not break any existing `_reviewers.py` behavior (load/resolve/resolve_role/validate_role_refs/tier_rank) and that the module still imports cleanly.
