# Batch: status-batch-baseline-field

```yaml
task: Improve diagnosability of plan-validate errors and finalize verify-replay failures
batch: status-batch-baseline-field
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-status.py
depends-on: []
```

## Batch Scope

Adds a new `verify_baseline_failures: list[str]` field on each `## Batches` entry in `status.md`, the storage location Gap 2's per-batch baseline mechanism needs (`_mill/discussion.md`'s `gap2-per-batch-baseline-storage` Decision). `_serialise_batches` is a hand-rolled writer over a fixed `order` list, not a generic `yaml.safe_dump` round-trip — a field added only to `_BATCH_ALLOWED_KEYS` would round-trip in memory for one call but be silently dropped on every actual write to disk, so both the allowed-keys set AND the serializer's `order` list plus a new list-value branch must change together. This batch is independent of every other batch in this plan.

## Cards

### Card 4: Allow `verify_baseline_failures` as a batch field

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add the string `"verify_baseline_failures"` to the `_BATCH_ALLOWED_KEYS` set literal (`_status.py:533-541`). Widen `set_batch_field`'s `value` parameter type hint (`_status.py:965`) from `str | int | None` to `str | int | list[str] | None`, and `set_batch_fields`'s `fields` parameter type hint (`_status.py:998`) from `dict[str, str | int | None]` to `dict[str, str | int | list[str] | None]`. No change to either function's body in this card — `entry[key] = value` already assigns generically regardless of value type; only the allowed-keys set and the two type hints change here.
- **Commit:** `feat(status): allow verify_baseline_failures as a batch field`

### Card 5: Serialize list-valued batch fields correctly

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_serialise_batches` (`_status.py:601-636`), add the string `"verify_baseline_failures"` to the `order` list (`_status.py:608-617`), immediately after `"blocked_reason"`. In the per-key value-writing branch (`_status.py:624-631`), the existing code reads `if isinstance(value, str): ... else: ...` (the `else` covers ints/bools via raw `str(value)`). Change this into a three-way chain: make the list check the new LEADING `if`, demoting the existing string check to an `elif`, and keep the existing `else` last — i.e. `if isinstance(value, list): parts.append(f"{prefix}{key}: {yaml.safe_dump(value, default_flow_style=True).strip()}") elif isinstance(value, str): <existing quote_scalar line, unchanged> else: <existing raw str(value) line, unchanged>` (the `yaml` module is already imported in this file). This ensures a list value serializes as a proper flow-sequence yaml scalar instead of falling through to the raw-`str(value)` branch, which would emit a fragile Python-repr-shaped string. The existing `isinstance(value, str)` and raw-`str()` branches' own bodies are otherwise unchanged — only their position in the if/elif/else chain shifts to make room for the new leading list check.
- **Commit:** `feat(status): serialize list-valued batch fields as flow-sequence yaml`

### Card 6: Round-trip test for `verify_baseline_failures`

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Following the existing `set_batch_field`/`read_batches` round-trip pattern in this file (see the `blocked_reason`-quoting and `review_round`-int assertions around `test-status.py:339-384`), add a test confirming: `set_batch_field(sp, "foundation", "verify_baseline_failures", ["--- FAIL: TestFoo", "FAILED tests/test_x.py::test_y"])` followed by `read_batches(sp)` returns that identical list (same order) on the `"foundation"` entry, AND that this write does not corrupt any other batch field already set earlier in the same test (assert an unrelated field, e.g. `state` or `blocked_reason`, is unchanged after this write). Also assert that setting an EMPTY list (`[]`) round-trips as an empty list (present, not dropped as if the value were `None`) — this distinguishes "clean baseline" from "field never computed."
- **Commit:** `test(status): cover verify_baseline_failures round-trip`

## Batch Tests

`verify:` runs `run-all.py --only test-status.py`, the sole test file covering `_status.py`'s batch-field read/write machinery this batch modifies.
