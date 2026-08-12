# Batch: reviewer-kind-finalize-wrappers

```yaml
task: 'millpy-review-plan finalize: usage-error indistinguishability, flag issues, verdict rendering stale'
batch: reviewer-kind-finalize-wrappers
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-plan-flow.py test-review-discussion-flow.py test-review-code-flow.py
depends-on: []
```

## Rename mechanic

N/A — no `Moves:` in this batch.

## Batch Scope

Add `"error_kind": "reviewer"` to the ERROR-shaped dict/`ReviewResult` that each of
`_review_plan.py::finalize`, `_review_discussion.py::finalize`, and `_review_code.py::finalize`
constructs and *returns* (never raises) from its own internal `except ReviewError:` block wrapping
the call to `finalize_scope`. This is the actual, sole site where a `parse_verdict` failure on the
reviewer's own raw text lands — it never reaches `print_error_envelope` (Batch 1/2's contract) or
any outer CLI-level catch, since these `finalize()` wrapper functions return their ERROR result
directly and the CLI's `main()` treats it as a success-path value (`print(json.dumps(...))`,
`return 0`). This batch is independent of Batch 1/2 — it edits a parallel code path that never
calls `print_error_envelope` — and is grouped as one batch because all three files apply the
identical one-key addition to the identical dict-construction pattern, verified by the identical
existing test pattern (a `parse_verdict`-failure fixture) already present in each of the three
`*-flow.py` test files this batch extends.

## Cards

### Card 8: `_review_plan.py::finalize` tags its `except ReviewError` result `error_kind: "reviewer"`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `finalize()`'s `except ReviewError as exc:` block (the one wrapping the call to `finalize_scope(...)`, which builds and returns a dict with keys `"scope"`, `"round"`, `"verdict"`, `"blocking_count"`, `"nit_count"`, `"file"`, `"error"`, `"session_id"`, `"findings"`, `"duration_s"`, `"tool_calls"`, `"cost_usd"`), add a new key `"error_kind": "reviewer"` to that dict literal. Placement within the dict literal does not matter; keep the existing key order and add the new key at the end for a minimal diff.
  - Do not add `error_kind` to the success-path return dict at the end of `finalize()` (the one built from `review_entry[...]`) — only the `except ReviewError` path's dict gets the new key, per the overview's "error_kind defaulting" Shared Decision (a successful review has no error kind to report).
- **Commit:** `fix(review-plan): tag finalize's parse_verdict-failure result error_kind: reviewer`

### Card 9: `_review_discussion.py::finalize` tags its `except ReviewError` result `error_kind: "reviewer"`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `finalize()`'s `except ReviewError as exc:` block, the returned `ReviewResult(...)`'s `reviews=[{...}]` list contains a single dict with keys `"scope"`, `"verdict"`, `"file"`, `"error"`, `"findings"`, `"session_id"`, `"duration_s"`, `"tool_calls"`, `"cost_usd"`. Add a new key `"error_kind": "reviewer"` to that dict literal, keeping the existing key order and appending the new key at the end for a minimal diff.
  - Do not add `error_kind` to the success-path `ReviewResult(...)`'s `reviews=[{...}]` dict later in the same function (the one built from `review_entry[...]`) — only the `except ReviewError` path's dict gets the new key.
- **Commit:** `fix(review-discussion): tag finalize's parse_verdict-failure result error_kind: reviewer`

### Card 10: `_review_code.py::finalize` tags its `except ReviewError` result `error_kind: "reviewer"`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `finalize()`'s `except ReviewError as exc:` block, the returned `ReviewResult(...)`'s `reviews=[{...}]` list contains a single dict with keys `"scope"`, `"verdict"`, `"file"`, `"error"`, `"findings"`, `"session_id"`, `"duration_s"`, `"tool_calls"`, `"cost_usd"`. Add a new key `"error_kind": "reviewer"` to that dict literal, keeping the existing key order and appending the new key at the end for a minimal diff.
  - Do not add `error_kind` to the success-path `ReviewResult(...)`'s `reviews=[{...}]` dict later in the same function (the one built from `review_entry[...]`) — only the `except ReviewError` path's dict gets the new key.
  - This function's `except ReviewError` block is reached the same way for both holistic (`scope is None`) and per-batch (`scope` set) calls — the new key applies uniformly regardless of `scope_label`.
- **Commit:** `fix(review-code): tag finalize's parse_verdict-failure result error_kind: reviewer`

### Card 11: assert `error_kind: "reviewer"` in the existing parse_verdict-failure flow tests

- **Context:**
  - `plugins/mill/scripts/_review_plan.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_code.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `plugins/mill/unit_tests/test-review-plan-flow.py`, in the "Test 20 — holistic parse_verdict failure -> ERROR entry (#185)" case, immediately after the existing `assert "parse_verdict failed" in rv_hol.get("error", "")` assertion, add `assert rv_hol.get("error_kind") == "reviewer", f"expected error_kind 'reviewer', got {rv_hol.get('error_kind')!r}"`. Do not change the existing `print("PASS test20: ...")` message or any other assertion in this test.
  - In `plugins/mill/unit_tests/test-review-discussion-flow.py`, in the parse_verdict-failure test case (the one asserting `r.verdict == "ERROR"` and `"parse_verdict failed" in r.reviews[0].get("error", "")`), immediately after the existing `parse_verdict failed` assertion, add `assert r.reviews[0].get("error_kind") == "reviewer", f"expected error_kind 'reviewer', got {r.reviews[0].get('error_kind')!r}"`. Do not change the existing pass-message print or any other assertion.
  - In `plugins/mill/unit_tests/test-review-code-flow.py`, in "Test 15 — code review parse_verdict failure returns ERROR envelope (#315)", which covers both holistic (`r_hol`) and per-batch (`r_batch`) modes: immediately after the existing `assert "parse_verdict failed" in r_hol.reviews[0].get("error", "")` assertion, add `assert r_hol.reviews[0].get("error_kind") == "reviewer", f"expected error_kind 'reviewer', got {r_hol.reviews[0].get('error_kind')!r}"`; immediately after the existing `assert "parse_verdict failed" in r_batch.reviews[0].get("error", "")` assertion, add `assert r_batch.reviews[0].get("error_kind") == "reviewer", f"expected error_kind 'reviewer', got {r_batch.reviews[0].get('error_kind')!r}"`. Do not change the existing pass-message print or any other assertion.
  - All three additions follow each file's existing `assert ..., f"..."` inline-message style exactly — do not introduce `self.assertEqual` or any other assertion style into these plain-function test files.
- **Commit:** `test(review-flow): assert error_kind: reviewer on parse_verdict-failure results`

## Batch Tests

`verify:` runs `test-review-plan-flow.py`, `test-review-discussion-flow.py`, and
`test-review-code-flow.py` via `run-all.py --only`, scoped to exactly the three files Card 11
extends (each already exercises the real `finalize()`/`run()` call path this batch's source cards
edit, so no new fixture is needed — only new assertions against the existing parse_verdict-failure
scenario each file already constructs).
