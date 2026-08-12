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
the call to `finalize_scope`. None of these three sites reach `print_error_envelope` (Batch 1/2's
contract) or any outer CLI-level catch — each `finalize()` wrapper returns its ERROR result
directly and the CLI's `main()` treats it as a success-path value (`print(json.dumps(...))`,
`return 0`). This is the exact scope discussion.md's own Scope section names.

**Scope boundary — `run()`/`_review_one_batch()` are intentionally NOT touched by this batch.**
`_review_plan.py` and `_review_code.py` each also contain a `run()` function (and, for plan,
`_review_one_batch()`) that duplicates `parse_verdict`/`finalize_scope` inline rather than calling
`finalize()` — these build their own, separate ERROR dict literals under their own
`except ReviewError:`/`except LLMError:` blocks. This was flagged as a BLOCKING finding in Plan
Review round 1 (against an earlier draft of Card 11 that asserted `error_kind` against these
`run()`-based paths, which would have failed since `run()` never sets the field). Verified by
direct read: `_review_one_batch()`'s single `except ReviewError:` block wraps its *entire* function
body — not only `parse_verdict`'s raise, but also the `round_n > max_rounds` guard and
`resolve_ref_paths` hard-failures — so tagging that whole block `error_kind: "reviewer"` would
misclassify non-retryable configuration/reference errors as reviewer-output failures, which is not
what the `error_kind` field is for (see Batch 5's retry semantics: `"reviewer"`-kind entries keep
the existing two-pass retry, which is pointless for a deterministic round-guard or missing-file
error). `run()`'s holistic branch has the equivalent problem, plus multiple additional
`except LLMError:` sites that are not `parse_verdict` failures at all. Untangling which `run()`
call sites are genuinely `parse_verdict`-only failures is out of scope for this task — the
discussion (negotiated over five review rounds, see `_mill/discussion.md`'s "error_kind bucketing"
Decision and its round-5 correction) scoped the `error_kind` fix to exactly the three `finalize()`
wrapper functions, and `run()`/`_review_one_batch()`'s duplicate inline logic is not among the
Technical Context sites that Decision names. Card 11 (below) is scoped to call `finalize()`
directly, matching the Testing section's own "unit test calling each `finalize()` wrapper directly"
language, so it exercises exactly what this batch changes and nothing else.

This batch is independent of Batch 1/2 — it edits a parallel code path that never calls
`print_error_envelope` — and is grouped as one batch because all three files apply the identical
one-key addition to the identical dict-construction pattern, verified by the identical direct-call
test shape Card 11 adds per file.

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
  - Do not add `error_kind` to `finalize()`'s success-path return dict at the end of the function (the one built from `review_entry[...]`) — only the `except ReviewError` path's dict gets the new key, per the overview's "error_kind defaulting" Shared Decision (a successful review has no error kind to report).
  - Do not touch `_review_one_batch()` or `run()` anywhere in this file — per this batch's Scope boundary above, only `finalize()`'s `except ReviewError` dict gets the new key.
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
  - This file's `run()` delegates to `finalize()` for its verdict-parsing (unlike plan/code) — no separate inline `except ReviewError` dict-construction site exists in this file, so there is nothing else to change here.
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
  - Do not touch `run()` anywhere in this file — per this batch's Scope boundary above, only `finalize()`'s `except ReviewError` dict gets the new key.
- **Commit:** `fix(review-code): tag finalize's parse_verdict-failure result error_kind: reviewer`

### Card 11: direct-call unit tests asserting `error_kind: "reviewer"` from each `finalize()` wrapper

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
  - These are new, additive test functions calling each `finalize()` wrapper directly — NOT extensions of the existing `run()`-based parse_verdict-failure cases already in each file (Test 20 in `test-review-plan-flow.py`, the parse_verdict-failure case in `test-review-discussion-flow.py`, Test 15 in `test-review-code-flow.py` all go through `run()`, which this batch does not modify — leave all three of those cases completely untouched).
  - In `plugins/mill/unit_tests/test-review-plan-flow.py`, add a new test case (following the file's own `try:`/`except`/`errors += 1` per-case convention already used by every numbered test in this file, with its own `print("PASS ...")` on success) that: creates a fresh `reviews_dir` under a `_test_helpers.safe_temp_dir()` (or equivalent tempdir fixture already used elsewhere in this file); calls `_review_plan.finalize({}, "test-slug", "# Raw prose without any yaml block\n\nNo verdict here.", scope=None, round_n=1, reviews_dir=reviews_dir, mill_dir=reviews_dir.parent, project_root=reviews_dir.parent, wiki_root=reviews_dir.parent, git_root=reviews_dir.parent)` directly (not via `plan_run`/`run()`); and asserts the returned dict's `"verdict"] == "ERROR"` and `["error_kind"] == "reviewer"`.
  - In `plugins/mill/unit_tests/test-review-discussion-flow.py`, add an analogous new test case that calls `_review_discussion.finalize({}, "test-slug", "# Raw prose without any yaml block\n\nNo verdict here.", round_n=1, reviews_dir=reviews_dir, mill_dir=reviews_dir.parent, project_root=reviews_dir.parent, wiki_root=reviews_dir.parent)` directly and asserts the returned `ReviewResult`'s `.verdict == "ERROR"` and `.reviews[0]["error_kind"] == "reviewer"`.
  - In `plugins/mill/unit_tests/test-review-code-flow.py`, add an analogous new test case that calls `_review_code.finalize({}, "test-slug", "# Raw prose without any yaml block\n\nNo verdict here.", scope=None, round_n=1, reviews_dir=reviews_dir, mill_dir=reviews_dir.parent, project_root=reviews_dir.parent, wiki_root=reviews_dir.parent, git_root=reviews_dir.parent)` directly and asserts the returned `ReviewResult`'s `.verdict == "ERROR"` and `.reviews[0]["error_kind"] == "reviewer"`.
  - `reviews_dir` need not pre-exist in any of the three cases — `write_review_file` (called internally by `finalize_scope`) creates it via `mkdir(parents=True, exist_ok=True)`.
  - All three additions follow each file's existing test-case style exactly (this file's own `try:`/`except AssertionError:`/`except Exception:` block shape with `errors += 1` and a `print(..., file=sys.stderr)` on failure) — do not introduce a different test-runner convention into any of these three files.
- **Commit:** `test(review-flow): direct-call finalize() tests asserting error_kind: reviewer`

## Batch Tests

`verify:` runs `test-review-plan-flow.py`, `test-review-discussion-flow.py`, and
`test-review-code-flow.py` via `run-all.py --only`. Card 11's three new direct-`finalize()`-call
cases exercise exactly the code this batch's Cards 8-10 change; every pre-existing case in all
three files (including the `run()`-based parse_verdict-failure cases this batch deliberately leaves
unmodified) continues to pass unchanged, since Cards 8-10 touch only each file's `finalize()`
function.
