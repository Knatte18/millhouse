# Batch: backend-error-envelope

```yaml
task: "61 (A) -- Review pipeline fixes"
batch: backend-error-envelope
number: 2
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Two related fixes in the review backends: (1) wrap `parse_verdict` failures into the `verdict: "ERROR"` envelope so `mill-go` step 3.5 / 4.5 ERROR-only retry can consume the result, instead of the current bare-raise that crashes the CLI with no JSON on stdout (#315 part 2). The plan-side envelope already exists at `_review_plan.py:607-617` and is verify-only; the code and discussion backends need the same shape added. (2) Audit-and-test that every code-review save path routes through `_review_common.write_review_file` so the `-holistic-review-` filename regression cannot reappear (#316). The single naming gate already exists; the audit is a grep + regression test, no production-code change unless a stray `.write_text` is found.

External interface: the JSON envelope shape (`verdict: "ERROR"`, `reviews=[{...}]`) is already documented in `## Decisions / error-envelope-shape` and consumed by `mill-go` (read-only). No mill-go change is required by this batch.

## Cards

### Card 4: parse_verdict error envelope in _review_code

- **Context:**
  - `_mill/discussion.md`
  - `_mill/plan/00-overview.md`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Locate the `parse_verdict(raw)` call inside `_review_code.run` (current call at `plugins/mill/scripts/_review_code.py:374`, inside the post-LLM block). Wrap it (and the NEED_CONTEXT retry parse at `_review_code.py:374` after the resume try-block) in a `try` / `except ReviewError as exc` block.
  - On `ReviewError`:
    - Call `write_review_file(reviews_dir, "code", round_n, raw, scope=batch_name)` with the raw response so the operator can inspect the unparseable text.
    - Append one dict to a local `_reviews` list (in the existing shape used elsewhere in this function): `{"scope": scope_label, "verdict": "ERROR", "file": str(path), "error": f"parse_verdict failed: {exc}", "session_id": session_id}`.
    - Return `ReviewResult(type="code", round=round_n, verdict=_aggregate_top_verdict(_reviews, "REQUEST_CHANGES"), blocking_count=0, reviews=_reviews)`. Match the existing aggregation pattern in the function -- do NOT introduce a new shape.
  - Add one ASCII-only stderr print: `print(f"[_review_code] parse_verdict failed for {scope_label}: {exc}", file=sys.stderr)` before the `write_review_file` call. No em-dash.
  - The success path (verdict parsed cleanly) is unchanged.
  - The NEED_CONTEXT retry branch (lines 340-373) ends with a second `parse_verdict(raw)` at line 374; that single call site is the one to wrap. There is exactly one `parse_verdict` invocation per code-review flow; one try/except suffices.
- **Commit:** `fix(review-code): emit ERROR envelope on parse_verdict failure (#315)`

### Card 5: parse_verdict error envelope in _review_discussion

- **Context:**
  - `_mill/discussion.md`
  - `_mill/plan/00-overview.md`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_discussion.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Locate the `parse_verdict(raw)` call in `_review_discussion.run` at `plugins/mill/scripts/_review_discussion.py:122`. Wrap it in `try` / `except ReviewError as exc`.
  - On `ReviewError`:
    - Call `write_review_file(reviews_dir, "discussion", round_n, raw)` (no `scope` argument; discussion review has no scope).
    - Return `ReviewResult(type="discussion", round=round_n, verdict="ERROR", blocking_count=0, reviews=[{"scope": "holistic", "verdict": "ERROR", "file": str(review_file), "error": f"parse_verdict failed: {exc}", "session_id": session_id}])`.
  - Add ASCII-only stderr print before `write_review_file`: `print(f"[_review_discussion] parse_verdict failed: {exc}", file=sys.stderr)`.
  - The success path is unchanged (still calls `parse_verdict`, then `parse_blocking_count`, then `write_review_file` with the verdict parsed cleanly).
- **Commit:** `fix(review-discussion): emit ERROR envelope on parse_verdict failure (#315)`

### Card 6: _review_plan parse_verdict envelope audit + regression test

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_review_plan.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Audit `_review_plan.py` for every call site of `parse_verdict`. Confirm each is wrapped in the existing `try` / `except ReviewError` block at lines 607-617 (or an equivalent block). If any call site is unwrapped, add the equivalent envelope using `_review_plan.py:607-617` as the template. As of writing this plan, the existing block covers the only parse_verdict call site; the audit is expected to be a no-op for production code.
  - Add a regression test to `plugins/mill/unit_tests/test-review-plan-flow.py`: `def _test_review_plan_parse_verdict_failure_emits_error_envelope()`. Set up:
    - A minimal `tempfile.TemporaryDirectory()` worktree with a stub `_mill/plan/00-overview.md` (use the rendered template, no real batch files needed -- the test only needs the holistic path).
    - Monkeypatch `_reviewer_single.run` (or `_reviewer_cluster.run` as appropriate) to return a tuple `("no yaml block at all", "fake-session-id")`.
    - Call `_review_plan.run(cfg, slug, mill_dir, project_root, wiki_root)`.
    - Assert: returned `ReviewResult.verdict == "ERROR"` AND `len(result.reviews) >= 1` AND `result.reviews[0]["verdict"] == "ERROR"` AND `"parse_verdict failed" in result.reviews[0]["error"]` AND `result.reviews[0]["file"]` is a valid path that exists on disk.
  - Use the existing project test patterns from `test-review-plan-flow.py`: stub config dict, stub reviewer return value, in-memory paths.
- **Commit:** `test(review-plan): regression for parse_verdict ERROR envelope (#315)`

### Card 7: ERROR envelope flow tests for code and discussion backends

- **Context:**
  - `_mill/discussion.md`
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/scripts/_review_discussion.py`
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-plan-flow.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-review-code-flow.py`
  - `plugins/mill/unit_tests/test-review-discussion-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Add `def _test_review_code_parse_verdict_failure_emits_error_envelope()` to `plugins/mill/unit_tests/test-review-code-flow.py`. Mirror the plan-side test from card 6:
    - Monkeypatch `_reviewer_single.run` to return `("no yaml block at all", "fake-session-id")`.
    - Call `_review_code.run(...)` with a minimal valid config + temp paths + `batch_name=None` (holistic mode) AND a second call with `batch_name="01-test"` (per-batch mode).
    - Assert each call returns a `ReviewResult` with `verdict in {"ERROR", "REQUEST_CHANGES"}` (the aggregate uses `_aggregate_top_verdict(_reviews, "REQUEST_CHANGES")` -- the inner review entry's verdict is "ERROR"). Assert `result.reviews[0]["verdict"] == "ERROR"` AND `"parse_verdict failed" in result.reviews[0]["error"]` AND the saved file exists.
  - Add `def _test_review_discussion_parse_verdict_failure_emits_error_envelope()` to `plugins/mill/unit_tests/test-review-discussion-flow.py`. Mirror the code-side test:
    - Monkeypatch `_reviewer_single.run` to return `("no yaml block at all", "fake-session-id")`.
    - Call `_review_discussion.run(...)`.
    - Assert `result.verdict == "ERROR"` AND `result.reviews[0]["verdict"] == "ERROR"` AND `"parse_verdict failed" in result.reviews[0]["error"]` AND `Path(result.reviews[0]["file"]).exists()`.
  - Add a regression test `def _test_write_review_file_holistic_naming()` to `plugins/mill/unit_tests/test-review-common.py` (in the same batch as card 2 if convenient, otherwise here is acceptable -- the test sits in `test-review-common.py` even when added in this batch):
    - Call `write_review_file(reviews_dir, "code", 1, "raw", scope=None)` -> filename matches `^\d{8}-\d{6}-code-review-r1\.md$`.
    - Call `write_review_file(reviews_dir, "code", 1, "raw", scope="holistic")` -> same shape, no `-holistic-` segment.
    - Call `write_review_file(reviews_dir, "code", 1, "raw", scope="01-foo")` -> filename matches `^\d{8}-\d{6}-code-review-01-foo-r1\.md$`.
    - Assert NONE of the three contain the literal substring `"-holistic-review-"` anywhere in the filename.
  - Run `python plugins/mill/unit_tests/run-all.py` at the end and confirm all tests pass.
- **Commit:** `test(review): error envelope regression for code, discussion, and holistic-filename (#315 #316)`

## Batch Tests

Run `python plugins/mill/unit_tests/run-all.py` from worktree root. All existing tests must continue to pass; the new ERROR-envelope tests verify the wrapped behaviour; the holistic-naming regression test locks in the filename pattern.
