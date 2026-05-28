# Batch: code-review-nit-envelope

```yaml
task: "mill-go / mill-plan loop hardening"
batch: code-review-nit-envelope
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-review-common.py test-review-code-flow.py
depends-on: [1]
```

## Batch Scope

Fixes the backend half of #360: the code-review JSON envelope must carry a top-level
`nit_count` so the lean Builder can detect APPROVE-with-NITs without reading findings.
Card 3 adds the `nit_count` field to the `ReviewResult` dataclass and its `to_dict`;
card 4 computes the count in `_review_code.run()` and populates it. The Builder-side
dispatch logic (apply NITs on APPROVE) is prose and lives in batch 5 (mill-go-skill),
which depends on this batch.

`depends-on: [1]` because this batch edits `_review_common.py`, which batch 1 also edits
(`ReviewResult` vs the overstep guard) — the edge serializes the two.

External interface consumed downstream: the JSON envelope's new `nit_count` integer
(aggregated NIT count across `reviews[]`), read by mill-go on APPROVE.

## Cards

### Card 3: add nit_count to ReviewResult

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/unit_tests/test-review-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a `nit_count: int = 0` field to the `ReviewResult` dataclass in `_review_common.py` (place it next to the existing `blocking_count: int = 0` field), and add `"nit_count": self.nit_count` to the dict returned by `ReviewResult.to_dict()`. The default `0` keeps every existing construction site (including the ERROR / skipped paths in `_review_code.py` and the discussion/plan backends) valid without change. Add a test to `test-review-common.py` asserting `ReviewResult(...).to_dict()` includes `nit_count`, that it defaults to `0`, and that a non-default value round-trips through `to_dict`.
- **Commit:** `feat(review): add nit_count to ReviewResult envelope (#360)`

### Card 4: populate nit_count in code review

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_code.py`
  - `plugins/mill/unit_tests/test-review-code-flow.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_review_code.run()`, in the success path where `blocking_count = parse_blocking_count(raw, severity="BLOCKING")` is computed (just before `write_review_file`), also compute `nit_count = parse_blocking_count(raw, severity="NIT")` and pass `nit_count=nit_count` to the `ReviewResult(...)` constructed and returned in that same success branch. Leave every ERROR / `LLMError` / parse-failure return path at the default `nit_count=0` (do not add the kwarg there). Do NOT change `millpy-review-code.py` — it already serialises via `result.to_dict()`, so the field flows automatically. Add a test to `test-review-code-flow.py` (follow the file's existing reviewer-stub harness) asserting that a stubbed APPROVE review whose body contains N `### [NIT]` headings yields `result.to_dict()["nit_count"] == N`, and that a body with zero NIT headings yields `0`.
- **Commit:** `feat(review): count NITs in code-review envelope (#360)`

## Batch Tests

`verify:` runs `test-review-common.py` (the `ReviewResult.to_dict` `nit_count` field) and
`test-review-code-flow.py` (end-to-end NIT counting through `_review_code.run()` with the
existing reviewer stub). No real LLM is invoked — `test-review-code-flow.py` uses the
in-repo reviewer test stub.
