# Batch: reviewer-effort-api

```yaml
task: '11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha'
batch: reviewer-effort-api
cards: 2
verify: python plugins/mill/unit_tests/test-reviewer-modules.py
depends-on: [config-and-subprocess]
```

## Batch Scope

Extend the reviewer module API with an `effort: str | None = None` kwarg on every `run` function. Three reviewer/stub modules are touched. The test file for reviewer module signatures is updated in the same batch. This batch creates the API that batch 03 (`diff-scope-and-effort`) will use — it must be complete before that batch starts.

The change is additive and backwards-compatible: callers that pass no `effort` continue to get the module's internal default (`"max"`). Only `_review_code.run` (in batch 03) will pass a non-None value.

## Cards

### Card 3: Add effort kwarg to reviewer modules

- **Reads:**
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
  - `plugins/mill/scripts/_llm_claude.py`
- **Modifies:**
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In each of the three files, add `effort: str | None = None` as a keyword-only argument to the `run` function signature, after `timeout`. Thread it through as follows:

  **`_reviewer_sonnetmax.py`:** change the `run_bulk(...)` call to pass `effort=effort` instead of `effort="max"`. The module's internal `"max"` is replaced by the default: if the caller passes `None`, `run_bulk` receives `None`, and `_llm_claude._build_argv` omits `--effort` from the subprocess argv (it already handles `effort=None` correctly — verified at line ~95 of `_llm_claude.py`).

  Wait — the current code hardcodes `effort="max"`. If we change to `effort=effort` with `effort: str | None = None`, callers that previously got `"max"` will now get `None` (no `--effort` flag) unless they explicitly pass `effort="max"`. That changes the default behaviour for existing callers.

  To preserve backward-compatibility, use `effort if effort is not None else "max"` as the value passed to `run_bulk`/`run_tool_use`. This way: (a) callers that pass `effort=None` (or nothing) still get `"max"`, and (b) callers that pass an explicit value (e.g. `effort="medium"`) get that value.

  **`_reviewer_sonnetmax_tool.py`:** same pattern — `effort if effort is not None else "max"` passed to `run_tool_use`.

  **`_reviewer_test_stub.py`:** add `effort: str | None = None` to the `run` signature after `timeout`. Add it to the `kwargs` dict captured per call: `kwargs = {"session_id": session_id, "resume": resume, "timeout": timeout, "effort": effort}`. This lets tests assert on what effort value the backend passed to the reviewer.
- **Commit:** `feat(reviewers): add effort kwarg to run signatures for per-call effort override`

### Card 4: Update test-reviewer-modules.py with effort assertions

- **Reads:**
  - `plugins/mill/unit_tests/test-reviewer-modules.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax.py`
  - `plugins/mill/scripts/_reviewer_sonnetmax_tool.py`
  - `plugins/mill/scripts/_reviewer_test_stub.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-reviewer-modules.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the existing `main()` function, add the following assertions after the existing `timeout` assertions for each module:

  For `_reviewer_sonnetmax`:
  - Assert `"effort"` is in `sig.parameters`
  - Assert `sig.parameters["effort"].default is None`

  For `_reviewer_sonnetmax_tool`:
  - Same two assertions

  For `_reviewer_test_stub.run`:
  - Assert `"effort"` is in `sig_stub.parameters`
  - Assert `sig_stub.parameters["effort"].default is None`

  Add a new test case that calls `stub.run("probe", effort="medium")` and asserts `captured_prompts()[0][1]["effort"] == "medium"`. Use `stub.seed(...)` to seed one response before the call. This verifies that the stub captures the `effort` kwarg so downstream tests can assert on it.

  Print `"PASS: _reviewer_sonnetmax effort kwarg"`, etc. for each new assertion to match the existing print-based test style.
- **Commit:** `test(reviewers): add effort kwarg assertions to test-reviewer-modules`

## Batch Tests

`verify: python plugins/mill/unit_tests/test-reviewer-modules.py` — the test file updated in card 4 directly exercises the API changes from card 3. All existing assertions must still pass; new effort assertions must pass too.
