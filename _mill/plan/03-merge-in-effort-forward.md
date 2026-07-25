# Batch: merge-in-effort-forward

```yaml
task: "Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)"
batch: "merge-in-effort-forward"
number: 3
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
depends-on: []
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Fix the narrower, second instance of this task's bug class found during discussion
review round 1: `millpy-merge-in-subagent.py`'s two Agent-mode `--stage prepare` call
sites never pass `impl_effort` into `emit_prepare`, even though `impl_effort` is
already computed and correctly forwarded to the non-agent-mode subprocess path in the
same functions. This means merge-in's Agent-mode envelope never carries an `effort`
key today, regardless of the `subagent-type-effort-wiring` batch's fix — that batch
makes `emit_prepare` *capable* of tier-suffixing `subagent_type` from an `effort`
argument, but merge-in never supplies one. This batch is independent of (and has no
file overlap with) `subagent-type-effort-wiring` — its own test only asserts the
`effort` key appears in the envelope with the correct value, not the resulting
`subagent_type`, so it does not need that batch to have landed first.

## Cards

### Card 8: Forward `impl_effort` into merge-in's Agent-mode prepare envelope

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/millpy-merge-in-subagent.py`:
  - In `_run_conflicts`, change:
    ```python
    return emit_prepare(briefs_dir, "merge", "conflicts", 1, prompt_text, model_tier, session_id)
    ```
    to:
    ```python
    return emit_prepare(briefs_dir, "merge", "conflicts", 1, prompt_text, model_tier, session_id, effort=impl_effort)
    ```
  - In `_run_verify_fix`, change:
    ```python
    return emit_prepare(briefs_dir, "merge", "verify-fix", 1, prompt_text, model_tier, session_id)
    ```
    to:
    ```python
    return emit_prepare(briefs_dir, "merge", "verify-fix", 1, prompt_text, model_tier, session_id, effort=impl_effort)
    ```
  - Both functions already receive `impl_effort: str | None` as a parameter (`_run_conflicts(args, project_root, plugin_root, cfg, timeout, impl_model, impl_effort, stage="full")` and the equivalent `_run_verify_fix` signature) — no new parameter threading needed, only the two call-site edits above.
  - Do **not** change the `emit_prepare_no_dispatch` call in `_run_verify_fix` (the verify-passes prepare branch) — it takes no `effort` argument at all (see `subagent-type-effort-wiring`'s Shared Decision on `emit_prepare_no_dispatch` being out of scope for the identical reason: no dispatch happens on that path).

  In `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py`:
  - In `test_12_stage_prepare_conflicts`, after the existing `self.assertEqual(data["scope"], "conflicts")` line, add:
    ```python
    self.assertEqual(data["effort"], "high")
    ```
    (The `setUp` fixture's `_reviewers.resolve` mock already returns `{"effort": "high", ...}` — see the `self.mock_reviewers_resolve` patch — so `impl_effort` is `"high"` for every test in this file; this call exercises the conflicts prepare path.)
  - In `test_14_stage_prepare_verify_fix_fails` (the verify-fails prepare path, which reaches the `emit_prepare` call this card fixes — `test_13_stage_prepare_verify_fix_passes` reaches `emit_prepare_no_dispatch` instead and needs no change), after the existing `self.assertEqual(data["scope"], "verify-fix")` line, add:
    ```python
    self.assertEqual(data["effort"], "high")
    ```
- **Commit:** `fix(mill): forward effort tier into merge-in Agent-mode prepare envelope`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-millpy-merge-in-subagent.py` directly
(single file, matches the SKILL.md's documented single-test-file `verify:` pattern) —
it is the only test file covering `millpy-merge-in-subagent.py`'s CLI `main()`, and
its `setUp` fixture already supplies an `effort: "high"` reviewer spec, making it the
correct place to assert the new `effort` forwarding without needing a new fixture.
