# Batch: review-duration-derivation

```yaml
task: "Misc infra/wiki/PR/self-hosting reliability bugs"
batch: review-duration-derivation
number: 5
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-review-common.py
depends-on: []
```

## Batch Scope

Fixes #1097: an Agent-mode review round's `--duration-s` is orchestrator-supplied by hand and
recorded verbatim with no derivation or cross-check, so a mismeasured value (missed start timestamp)
is silent and permanent in the review file and `/mill-review-summary`'s timing table. Stamps the
prepare stage's wall-clock start time to disk and derives `duration_s` from it at finalize time,
keeping `--duration-s` only as a disagreement-tolerant override. Applies uniformly to plan,
discussion, and code review, since all three route through the same `_agent_dispatch.write_brief` /
per-CLI `finalize` wrapper functions.

## Cards

### Card 13: prepare-stage wall-clock stamp and duration derivation helper

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Deliberate deviation from `_mill/discussion.md`'s `review-duration-derived-not-trusted` Decision:
  that Decision names `_review_common.py` as the new helper's home, but this card places it in
  `_agent_dispatch.py` instead, alongside the two functions it composes with (`output_path_for`,
  `write_brief`) — all three brief-path-derived-suffix helpers stay co-located in the module that
  already owns the brief-file lifecycle, rather than splitting that lifecycle across two modules.
  `_review_common.py` remains available to `derive_duration_s`'s callers exactly as before; nothing
  about this relocation changes which module the three review CLIs import.

  In `_agent_dispatch.py`:
  1. Add `import sys` and `import time` to the module's imports.
  2. Add `prepare_ts_path_for(brief_path: Path) -> Path`, placed immediately after `output_path_for`,
     mirroring its exact shape: `return Path(brief_path).with_suffix(".prepare_ts")`. Document in its
     docstring that this is the brief-path-relative sibling of `output_path_for`'s `.out.md` mapping —
     both derive from the same brief path, `.md` -> `.out.md` and `.md` -> `.prepare_ts`
     independently (NOT chained off each other).
  3. In `write_brief`, immediately after the existing `output_path_for(brief_path).unlink(missing_ok=True)`
     line, add `prepare_ts_path_for(brief_path).write_text(str(time.time()), encoding="utf-8")` —
     unconditional, on every call, regardless of `output_contract`, mirroring the "two behaviours run
     on every call" framing already in this function's docstring (extend it to three). This runs for
     every role (implement/fix/merge-in/review) — writing an unused stamp file for a non-review role
     is harmless and intentionally not special-cased.
  4. Add `derive_duration_s(agent_output_path: Path, fallback: float | None) -> float | None`, placed
     after `prepare_ts_path_for`. Derive the sibling `.prepare_ts` path from `agent_output_path` (a
     `...out.md` path) by chaining `with_suffix("")` twice: `prepare_ts_path =
     Path(agent_output_path).with_suffix("").with_suffix(".prepare_ts")` — the first call strips the
     trailing `.md` (leaving `...out`), the second strips `.out` and appends `.prepare_ts`, landing on
     exactly the same path `write_brief` wrote via `prepare_ts_path_for(brief_path)`. (A single
     `with_suffix(".prepare_ts")` call on `agent_output_path` directly would be wrong — it only
     strips one suffix level, landing on `....out.prepare_ts`, not the file `write_brief` wrote.) If
     `prepare_ts_path` does not exist, return `fallback` unchanged (no stamp available — the only
     dispatch path with no `write_brief` call, if one is ever added, degrades to today's
     caller-supplied behavior). Otherwise read and `float()`-parse its content (catch
     `(OSError, ValueError)`, returning `fallback` on either); compute `derived = time.time() -
     prepare_ts`. When `fallback is None`, return `derived`. Otherwise compare: tolerance =
     `max(derived * 0.20, 5.0)` (20% relative or a 5-second absolute floor, whichever is greater, to
     allow for brief-write/process-launch overhead); if `abs(derived - fallback) > tolerance`, print a
     one-line ASCII warning to stderr naming both values and that the derived value wins (e.g.
     `f"[review] duration_s mismatch: caller supplied {fallback:.1f}s, derived {derived:.1f}s from
     prepare-stage stamp; using derived value"`). In every case where the stamp file exists and
     parses, return `derived` — `fallback` is used only when no stamp is available or it fails to
     parse.
- **Commit:** `feat(agent-dispatch): stamp prepare-stage start time and derive review duration_s (#1097)`

### Card 14: wire `derive_duration_s` into the three review CLIs' finalize stage

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In each of `millpy-review-plan.py`, `millpy-review-discussion.py`, and `millpy-review-code.py`'s
  `--stage finalize` branch, `_agent_dispatch` is already imported at the top of `main()` (used by
  the `--stage prepare` branch) and `agent_output_path = Path(args.agent_output)` is already computed
  immediately before the `finalize(...)`/`result = finalize(...)` call in each file. Change the
  `duration_s=args.duration_s,` keyword argument on that call (one occurrence per file) to
  `duration_s=_agent_dispatch.derive_duration_s(agent_output_path, args.duration_s),` — a one-line
  change, three times, no other lines in the `finalize(...)` call touched. `finalize_scope` itself
  (in `_review_common.py`) and each file's own `finalize` wrapper (`_review_plan.py`,
  `_review_discussion.py`, `_review_code.py`) need no signature change — `duration_s` already accepts
  a plain `float | None` and this substitutes what value flows into it.
- **Commit:** `fix(review): derive duration_s from prepare-stage stamp at finalize (#1097)`

## Batch Tests

- Card 13: extend `plugins/mill/unit_tests/test-agent-dispatch.py`'s `tests` list (the free
  `test_*`-function collection in `main()`) with: `test_write_brief_writes_prepare_ts_stamp`
  (asserts the `.prepare_ts` sibling file exists after `write_brief` and its content parses as a
  float close to `time.time()`); `test_prepare_ts_path_for_maps_md_to_prepare_ts` (mirrors
  `test_output_path_for_maps_md_to_out_md`'s exact assertion shape for the new function);
  `test_derive_duration_s_returns_derived_when_no_fallback`; `test_derive_duration_s_uses_derived_on_mismatch`
  (write a `.prepare_ts` stamp far enough in the past that the derived value and an intentionally-wrong
  `fallback` disagree beyond tolerance, assert the derived value wins and a warning is printed to
  stderr); `test_derive_duration_s_falls_back_when_stamp_missing` (no `.prepare_ts` file on disk,
  assert the passed `fallback` is returned unchanged).
- Card 14: extend `plugins/mill/unit_tests/test-review-common.py` (or add cases alongside its
  existing finalize-stage coverage) with one integration-shaped case per CLI's `--stage finalize`
  invocation (or a single parametrized case covering the shared code shape across all three, since
  the change is byte-identical in each file): a `.prepare_ts` stamp exists and no `--duration-s` was
  passed — assert the persisted review file's `duration_s:` header is the derived value, not absent;
  a `.prepare_ts` stamp exists and `--duration-s` disagrees wildly — assert the derived value is
  what's written, not the passed one.
