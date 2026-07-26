# Batch: subagent-type-effort-wiring

```yaml
task: "Agent-tool dispatch discards the effort tier already encoded in mill-agents.yaml (opushigh/opusmedium/opusmax)"
batch: "subagent-type-effort-wiring"
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-agent-dispatch.py test-implementer-common.py test-review-prepare-envelope.py
depends-on: [1]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Close the actual gap: every envelope-construction site that currently hardcodes
`subagent_type` to the flat `SUBAGENT_REVIEWER`/`SUBAGENT_IMPLEMENTER` constant must
instead compute it through a new single helper, `_agent_dispatch.resolve_subagent_type`,
that appends the resolved alias's effort tier as a `-<tier>` suffix. This is the actual
fix for the bug `_mill/discussion.md` describes — note that the true fix site is NOT
`mill-go/SKILL.md` prose (mill-go's orchestration text already just forwards whatever
`subagent_type` the envelope says); the fix is in the five Python call sites that build
that envelope. Card 8 corrects `mill-go/SKILL.md`'s now-stale documentation of this
gap to describe the closed state accurately. Depends on batch 1 because a live
Agent-tool dispatch must never be pointed at a `subagent_type` with no matching
agent-definition file on disk.

## Cards

### Card 5: Add `resolve_subagent_type` to `_agent_dispatch.py`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_agent_dispatch.py`
  - `plugins/mill/unit_tests/test-agent-dispatch.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_agent_dispatch.py`:
  - Add a module-level constant `EFFORT_TIERED_SUBAGENT_TYPES = frozenset({"medium", "high", "max"})`, placed immediately after the existing `MODEL_FAMILIES` dict.
  - Add a new function `resolve_subagent_type(base: str, effort: str | None) -> str`, placed immediately after `model_to_tier` and before `write_brief`:
    - Returns `base` unchanged when `effort` is `None` or not a member of `EFFORT_TIERED_SUBAGENT_TYPES`.
    - Otherwise returns `f"{base}-{effort}"` (e.g. `resolve_subagent_type(SUBAGENT_REVIEWER, "high")` -> `"mill:mill-reviewer-high"`).
    - Docstring must state the fallback-to-base behavior is deliberate and forward-compatible (an unrecognized future tier degrades to today's base behavior rather than raising), matching the overview's Shared Decision "unrecognized effort falls back to the base subagent_type."
  - Add `"resolve_subagent_type"` to `__all__`.
  - Add a `resolve_subagent_type(base: str, effort: str | None) -> str` entry to the module docstring's `Exports` section, in the same style as the existing `model_to_tier` entry (one-line summary + short body).

  In `plugins/mill/unit_tests/test-agent-dispatch.py`, add three new test functions (plain `assert`-based, matching this file's existing style — not `unittest.TestCase`), placed after `test_model_to_tier_raises_on_unknown` and before `test_write_brief_creates_file`:
  - `test_resolve_subagent_type_returns_base_when_effort_none`: asserts `resolve_subagent_type(SUBAGENT_REVIEWER, None) == "mill:mill-reviewer"` and `resolve_subagent_type(SUBAGENT_IMPLEMENTER, None) == "mill:mill-implementer"`.
  - `test_resolve_subagent_type_appends_known_tier`: for each of `"medium"`, `"high"`, `"max"`, asserts `resolve_subagent_type(SUBAGENT_REVIEWER, tier) == f"mill:mill-reviewer-{tier}"` and the equivalent for `SUBAGENT_IMPLEMENTER`.
  - `test_resolve_subagent_type_falls_back_on_unrecognized_tier`: for each of `"low"`, `"xhigh"`, `"bogus"`, asserts `resolve_subagent_type(SUBAGENT_REVIEWER, tier) == "mill:mill-reviewer"` (base, unchanged).

  Each function ends with a `print("PASS ...")` line matching this file's existing convention. Register all three new functions in `main()`'s `tests` list, immediately after the existing `test_model_to_tier_raises_on_unknown` entry.
- **Commit:** `feat(mill): add resolve_subagent_type effort-tier helper`

### Card 6: Wire `resolve_subagent_type` into `emit_prepare`

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `plugins/mill/scripts/_implementer_common.py`'s `emit_prepare` function, change the envelope-construction line:
  ```
  "subagent_type": _agent_dispatch.SUBAGENT_IMPLEMENTER,
  ```
  to:
  ```
  "subagent_type": _agent_dispatch.resolve_subagent_type(_agent_dispatch.SUBAGENT_IMPLEMENTER, effort),
  ```
  using the function's own `effort` parameter (already in scope — no new parameter needed). Do **not** change `emit_prepare_no_dispatch`'s equivalent line — see the overview's Shared Decision "`emit_prepare_no_dispatch` is out of scope."

  In `plugins/mill/unit_tests/test-implementer-common.py`, locate "Case 65" (the block whose comment reads `# Case 65: #628/#633 - emit_prepare threads effort through the prepare envelope.`). It makes two `emit_prepare` calls: the first with `effort="high"`, the second with `effort` omitted. After the existing assertion `assert data["effort"] == "high", (...)` for the first call, add:
  ```python
  assert data["subagent_type"] == "mill:mill-implementer-high", (
      f"expected tier-suffixed subagent_type, got {data}"
  )
  ```
  After the existing assertion `assert "effort" not in data, (...)` for the second call, add:
  ```python
  assert data["subagent_type"] == "mill:mill-implementer", (
      f"expected base subagent_type, got {data}"
  )
  ```
  Do not add a new numbered case — these are additional assertions inside the existing Case 65 block, since it already exercises the exact `emit_prepare` calls this card changes the behavior of.
- **Commit:** `fix(mill): forward effort tier into implementer/fix/merge-in subagent_type`

### Card 7: Wire `resolve_subagent_type` into the three review CLIs

- **Context:**
  - `plugins/mill/scripts/_agent_dispatch.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/unit_tests/test-review-prepare-envelope.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Each of the three review CLIs builds its `--stage prepare` success envelope in an
  identical shape. In each file, change the line:
  ```
  "subagent_type": _agent_dispatch.SUBAGENT_REVIEWER,
  ```
  to:
  ```
  "subagent_type": _agent_dispatch.resolve_subagent_type(_agent_dispatch.SUBAGENT_REVIEWER, prepare_result.get("effort")),
  ```
  Apply this identically in:
  - `plugins/mill/scripts/millpy-review-discussion.py` (inside `main()`'s `--stage prepare` branch)
  - `plugins/mill/scripts/millpy-review-code.py` (inside `main()`'s `--stage prepare` branch)
  - `plugins/mill/scripts/millpy-review-plan.py` (inside `main()`'s `--stage prepare` branch)

  Each site already reads `prepare_result` (the dict returned by the backend's `prepare()` call) and two lines later conditionally copies `prepare_result["effort"]` into `envelope["effort"]` when not `None` — use `prepare_result.get("effort")` directly in the `resolve_subagent_type` call rather than introducing a new local variable.

  In `plugins/mill/unit_tests/test-review-prepare-envelope.py`, update the shared helper `_assert_effort_envelope(review_type: str, effort: str | None) -> bool`. Its current final two lines are:
  ```python
      if effort is None:
          return "effort" not in envelope
      return envelope.get("effort") == effort
  ```
  Change them to also check `subagent_type`:
  ```python
      if effort is None:
          return (
              "effort" not in envelope
              and envelope["subagent_type"] == _agent_dispatch.SUBAGENT_REVIEWER
          )
      return (
          envelope.get("effort") == effort
          and envelope["subagent_type"] == f"{_agent_dispatch.SUBAGENT_REVIEWER}-{effort}"
      )
  ```
  This strengthens the six existing test functions that already call `_assert_effort_envelope` (`test_discussion_prepare_envelope_has_effort`, `test_discussion_prepare_envelope_omits_effort_when_absent`, and the `plan`/`code` equivalents) — no new test functions are needed, since they already parametrize over the exact `effort=None` / `effort="high"` axis this card's fix affects. Do not modify `_assert_success_envelope_shape` or its `subagent_type != _agent_dispatch.SUBAGENT_REVIEWER` check — that helper's fixture always uses `effort=None` (via `_success_prepare_result("holistic")`, no `effort=` kwarg), so `resolve_subagent_type` returns the base unchanged there and the existing assertion stays correct as-is.
- **Commit:** `fix(mill): forward effort tier into reviewer subagent_type`

### Card 8: Correct `mill-go/SKILL.md`'s stale effort-forwarding documentation

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In the `## Agent-mode dispatch` section, step 2's bullet list currently reads:
  ```
     - `brief_path`: absolute file path to the rendered brief
     - `subagent_type`: one of `"mill:mill-implementer"` or `"mill:mill-reviewer"`
     - `model`: Agent-tool tier (`"sonnet"`, `"opus"`, or `"haiku"`)
  ```
  Replace the `subagent_type` bullet with:
  ```
     - `subagent_type`: `"mill:mill-implementer"` or `"mill:mill-reviewer"`, or one of their six `-medium`/`-high`/`-max` tier-suffixed variants (e.g. `"mill:mill-reviewer-high"`) when the resolved alias's `effort` field is `"medium"`, `"high"`, or `"max"` — computed by `_agent_dispatch.resolve_subagent_type`, the single site every envelope-construction call site (implement/fix/merge-in via `emit_prepare`, and each of the three review CLIs) routes through.
  ```

  Later in step 3, the current text contains this sentence (do not touch anything else in step 3 — this is a single-sentence replacement):
  ```
  The envelope's `effort` field (from step 2) has no corresponding Agent-tool parameter to forward it to: the Agent tool call takes only `subagent_type`, `model`, `prompt`, and optionally `isolation`; `effort` is extracted for `subprocess`/`psmux` dispatch parity and audit visibility only, and is a documented, intentional gap under `dispatch: agent`, not a silent one.
  ```
  Replace it with:
  ```
  The Agent tool call still takes only `subagent_type`, `model`, `prompt`, and optionally `isolation` — there is no separate `effort` parameter — but the envelope's `subagent_type` value (from step 2) already encodes the resolved alias's `effort` tier as a suffix, resolved once by `_agent_dispatch.resolve_subagent_type` at envelope-construction time. Forwarding an effort tier means dispatching to one of the six per-tier agent-definition files under `plugins/mill/agents/` (`mill-reviewer-medium.md`/`-high.md`/`-max.md`, `mill-implementer-medium.md`/`-high.md`/`-max.md`), each of which pins a fixed `effort:` in its own frontmatter — not passing effort as a call parameter. `effort` remains present in the envelope for `subprocess`/`psmux` dispatch parity and audit visibility, in addition to now driving `subagent_type`.
  ```

  Leave every other sentence in step 3 (the `agentId` recording, the `model` recording, the "no ack predicate" note, etc.) unchanged — this card is a documentation correction of exactly the one now-inaccurate claim, not a rewrite of the surrounding orchestration text (which never needed to change: it already just forwards "the value from step 2" verbatim, unaware of how that value was computed).
- **Commit:** `docs(mill): correct mill-go SKILL.md's stale effort-forwarding gap note`

## Batch Tests

`verify:` runs the three unit-test files this batch's Python changes affect, scoped via
`run-all.py --only` (three files, not the full suite): `test-agent-dispatch.py` (Card 5's
new `resolve_subagent_type` tests), `test-implementer-common.py` (Card 6's Case 65
extension, plus the full pre-existing suite in that file to guard against regressions in
`emit_prepare`/`emit_prepare_no_dispatch`), and `test-review-prepare-envelope.py` (Card
7's strengthened `_assert_effort_envelope` checks across all three review CLIs). Card 8
(`mill-go/SKILL.md`) is a documentation-only change with no runnable surface — verified
by code read-through during code review of the diff, per `_mill/discussion.md`'s Testing
section.
