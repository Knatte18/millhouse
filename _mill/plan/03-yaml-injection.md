# Batch: yaml-injection

```yaml
task: "Surface reviewer time/tool-call cost + a review-summary command"
batch: "yaml-injection"
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py
depends-on: []
```

## Batch Scope

Adds the persistence mechanism the three metadata batches and the summary command both depend on:
a `apply_cost_metadata()` function in `_review_common.py` that injects or rewrites `duration_s:`,
`tool_calls:` and `cost_usd:` in a review file's yaml header, plus three new optional
`finalize_scope()` keyword arguments that apply it and surface the values in the returned review
entry. The fence-walking logic is extracted out of `apply_actual_model_override()` into a shared
private helper so there is exactly one copy of it.

This batch touches no provider, backend, or CLI, so it has no dependency on batches 1-2 and can run
in parallel with them. The interface batches 4/5/6/8 consume: `apply_cost_metadata(raw_text, *,
duration_s, tool_calls, cost_usd) -> str` and `finalize_scope(..., duration_s=, tool_calls=,
cost_usd=)` whose returned dict gains the same three keys.

## Cards

### Card 14: extract the inject-or-rewrite helper

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add a private `_inject_or_rewrite_yaml_field(raw_text: str, field: str, value: str) -> str` next to
  `apply_actual_model_override`. It performs today's `apply_actual_model_override` mechanism
  generalised over the field name: build a per-field regex equivalent to `_RE_REVIEWER_MODEL_LINE`
  (`^<field>:[ \t]*\S.*$` with `re.MULTILINE`, the field name regex-escaped, horizontal whitespace
  only — the existing comment above `_RE_REVIEWER_MODEL_LINE` explaining why `[ \t]` and not `\s`
  must be preserved and generalised, since the same bleed-across-newlines hazard applies to every
  field); when a well-formed line exists, substitute it in place with `count=1`; otherwise walk the
  fenced yaml blocks exactly as today (first block whose body has a `^verdict:\s*\S` line, falling
  back to the first ` ```yaml ` fence, returning `raw_text` unchanged when there is no fence at all)
  and insert `<field>: <value>` immediately after the chosen opening fence.
  Cache the compiled per-field patterns in a module-level dict keyed by field name so the four
  supported fields do not recompile on every review.
  Rewrite `apply_actual_model_override` to a thin wrapper: return `raw_text` unchanged when
  `actual_model is None`, else `return _inject_or_rewrite_yaml_field(raw_text, "reviewer_model", actual_model)`.
  Its public behaviour and docstring contract must not change; keep `_RE_REVIEWER_MODEL_LINE` only
  if something else still uses it, otherwise remove it and fold its comment into the new helper.
- **Commit:** `refactor(review): extract yaml field inject-or-rewrite helper`

### Card 15: `apply_cost_metadata` and `finalize_scope` threading

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Add `apply_cost_metadata(raw_text: str, *, duration_s: float | None = None, tool_calls: int | None = None, cost_usd: float | None = None) -> str`.
  It returns `raw_text` unchanged when all three are `None`, and otherwise calls
  `_inject_or_rewrite_yaml_field` once per non-`None` field, in the order `cost_usd`, `tool_calls`,
  `duration_s` — reverse of the desired file order, because each injection lands immediately after
  the opening fence, so applying them in reverse yields a header reading `duration_s:`,
  `tool_calls:`, `cost_usd:` top-to-bottom.
  Value formatting: `duration_s` renders with one decimal place (`f"{duration_s:.1f}"`), `tool_calls`
  renders as a plain integer, `cost_usd` renders with four decimal places. The docstring must state
  that a text with no yaml fence is returned unchanged (the terminal fallback inherited from the
  helper), because parse-failure branches call this on unparsed reviewer output where no
  schema-conformant fence is guaranteed.
  Extend `finalize_scope` with three new keyword-only arguments `duration_s`, `tool_calls`,
  `cost_usd`, all defaulting to `None`. Also add a module-level
  `sum_optional(a: float | int | None, b: float | int | None) -> float | int | None` implementing
  the `None`-absorbing summation rule from the Shared Decision (`None` when both are `None`, the
  non-`None` operand when exactly one is set, their sum when both are); it lives here rather than in
  a backend because batches 5 and 6 both need it and run in parallel. Call `apply_cost_metadata` on `raw_text` immediately after
  the existing `apply_actual_model_override` call and before `parse_verdict`, so the persisted file
  and the parsed verdict see the same text. Add the three values to the returned dict under the keys
  `duration_s`, `tool_calls`, `cost_usd` (passed straight through, unformatted — the dict feeds the
  JSON envelope, which must carry numbers, not display strings). Update the docstring's Args and
  Returns sections.
- **Commit:** `feat(review): persist duration/tool-call/cost metadata into review yaml headers`

### Card 16: unit-test the injection and threading

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Alongside the existing `apply_actual_model_override` cases, add `apply_cost_metadata` cases:
  all-`None` returns the input unchanged (identity, not merely equal); injection into a header block
  with no such fields yields the three lines in the order `duration_s`, `tool_calls`, `cost_usd`
  directly after the opening fence; a header that already carries the three fields has them
  rewritten in place with no duplication; a partial set (only `duration_s`) injects only that field;
  text with no ` ```yaml ` fence at all is returned unchanged; text whose first yaml fence lacks a
  `verdict:` line but a later one has it anchors on the later block, matching
  `apply_actual_model_override`'s existing anchor rule.
  Add cases asserting the exact rendered formatting (`duration_s: 12.3`, `tool_calls: 37`,
  `cost_usd: 0.4212`).
  Add `sum_optional` cases: both `None` -> `None`; one `None` -> the other operand unchanged (not
  coerced to `0`); both set -> their sum.
  Add a `finalize_scope` case (writing into a tmp reviews dir) asserting the three values land both
  in the returned dict and in the written file's yaml header, and one asserting that omitting all
  three leaves the written file byte-identical to today's output for the same input.
- **Commit:** `test(review): cover cost-metadata yaml injection and finalize_scope threading`

## Batch Tests

`verify:` runs `test-review-common.py`, the unit test file that already owns
`apply_actual_model_override`'s coverage and is the only test file this batch edits. The refactor in
card 14 is behaviour-preserving, so the pre-existing `apply_actual_model_override` cases in that file
double as the regression gate for it.
