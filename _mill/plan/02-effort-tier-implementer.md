# Batch: effort-tier-implementer

```yaml
task: "Agent-mode dispatch: envelope fields and session/runtime state are unreliable"
batch: effort-tier-implementer
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py test-millpy-fix.py
depends-on: [1]
```

## Batch Scope

This batch surfaces the implementer/fixer registry's `effort` field into the `emit_prepare` envelope helper and the two CLIs (`millpy-implement.py`, `millpy-fix.py`) that call it, the implementer/fixer half of closing #628/#633. It is split out from the review-CLI half (next batch) purely for `pipeline.max_batch_context_tokens` sizing — the combined batch's file set (implementer + review CLIs + `mill-go/SKILL.md`, several of which are large) exceeded the 120000-token cap; splitting on the implementer/fixer-vs-review boundary keeps both halves comfortably under it and matches a real module boundary (dispatch-side envelope emission vs. review-CLI envelope emission). External interface the next batch consumes: `emit_prepare`'s new `effort` kwarg (Card 4) is the shared helper the review-CLI batch's backend `prepare()` functions rely on the same conditional-inclusion convention from.

## Cards

### Card 4: `emit_prepare` gains an `effort` kwarg

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_implementer_common.emit_prepare` (`plugins/mill/scripts/_implementer_common.py:750-793`), add a new keyword parameter `effort: str | None = None` after the existing `start_sha: str | None = None` parameter. Mirror the `start_sha` handling exactly: after the existing `if start_sha is not None: envelope["start_sha"] = start_sha` line, add `if effort is not None: envelope["effort"] = effort`. Update the function's docstring `Args:` block to document `effort` the same way `start_sha` is documented ("Effort tier resolved from the reviewer/implementer registry spec (e.g. `\"high\"`); included in the envelope as `\"effort\"` when not None, omitted otherwise."). In `plugins/mill/unit_tests/test-implementer-common.py`, following the file's existing "Case N" numbered-test convention (see case 64's `nits_only` coverage), add a new case asserting `emit_prepare(..., effort="high")` includes `"effort": "high"` in the printed envelope, and a call omitting `effort` entirely leaves the key absent from the envelope — mirroring case 64's `nits_only` present/absent assertions.
- **Commit:** `feat(implementer-common): add effort kwarg to emit_prepare envelope (#628, #633)`

### Card 5: `millpy-implement.py` threads `effort` into its prepare call

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `millpy-implement.py`'s `if args.stage == "prepare":` branch (the `emit_prepare(...)` call the `implement-prepare-reliability` batch already extended with `start_sha=start_sha`), add `effort=impl_effort` as a further keyword argument. `impl_effort` is already computed at line 313 (`impl_effort = impl_spec.get("effort")`) and currently only consumed by the `--stage full` branch's `_implementer_claude.run(..., effort=impl_effort, ...)` call — no new resolution logic is needed, only threading the existing variable into the prepare-stage call too. In `plugins/mill/unit_tests/test-millpy-implement.py`, extend `TestMillpyImplement` with a case asserting a `--stage prepare` call against a fixture whose configured implementer spec resolves a non-null `effort` (e.g. `sonnethigh`) produces an envelope containing `"effort": "high"`.
- **Commit:** `feat(millpy-implement): thread effort into prepare envelope (#628, #633)`

### Card 6: `millpy-fix.py` threads `effort` into its prepare call

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `millpy-fix.py`'s `if args.stage == "prepare":` branch (`plugins/mill/scripts/millpy-fix.py:503-517`), add `effort=fixer_effort` as a further keyword argument to the `emit_prepare(...)` call. `fixer_effort` is already computed at line 244 (`fixer_effort = fixer_spec.get("effort")`) and currently only consumed by the `--stage full` branch's `_implementer_claude.run(..., effort=fixer_effort, ...)` call at line 524 — thread the existing variable into the prepare-stage call the same way Card 5 does for `millpy-implement.py`. In `plugins/mill/unit_tests/test-millpy-fix.py`, extend `TestMillpyFix` (see its existing `test_stage_prepare_batch_scope`/`test_stage_prepare_holistic_scope` cases around lines 555-635, and the `nits_only` present/absent pair at lines 577-616 for the conditional-field pattern to mirror) with a case asserting a `--stage prepare` call against a fixture whose configured fixer spec resolves a non-null `effort` produces an envelope containing that `effort` value.
- **Commit:** `feat(millpy-fix): thread effort into prepare envelope (#628, #633)`

## Batch Tests

`verify:` runs `test-implementer-common.py` (extend `emit_prepare`'s numbered-case coverage, following the file's existing "Case N" convention seen around case 64's `nits_only` test, with a new case asserting `effort` is present in the envelope when passed and absent when omitted), `test-millpy-implement.py` (extend with a case asserting the envelope's `effort` key matches the configured implementer spec's effort), and `test-millpy-fix.py` (extend with a case asserting the same for the fixer's prepare envelope, mirroring that file's existing `stage_prepare` fixture pattern).
