# Batch: review-plan-counting-fix

```yaml
task: 'Plan review verdict correctness: unverified platform claims and missing nit_count in subprocess dispatch'
batch: review-plan-counting-fix
number: 1
cards: 6
verify: null
depends-on: []
```

## Batch Scope

Fix `_review_plan.py`'s subprocess/psmux `run()`/`_review_one_batch()`/`_scan_approved_batches()` dispatch path so it computes and aggregates `nit_count` correctly, matching the already-correct Agent-mode `finalize()`/`finalize_scope()` path (#709). This batch touches exactly one file — `_review_plan.py` — across its 4 successful-parse write sites (refactored to call the shared `finalize_scope()` helper), 6 error-path sites (schema-parity `nit_count: 0` added, no refactor), the skip-approved carryforward site (`_scan_approved_batches()`, computes both counters properly), and the final `ReviewResult` aggregation. No template, validator, or test file changes belong in this batch — those are review-plan-counting-tests (Batch 2, depends on this one), plan-review-templates (Batch 3), and plugin-manifest-validator (Batch 4).

## Cards

_One `### Card N` per card, numbered globally across all batches._

### Card 1: `_scan_approved_batches()` — compute both counters for skip-approved carryforward

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_scan_approved_batches()` (currently lines 70-119), inside the `for batch_stem, (n, path) in best.items():` loop, after the existing `verdict = parse_verdict(raw)` call succeeds and `verdict == "APPROVE"`, compute `blocking_count = parse_blocking_count(raw, severity="BLOCKING") + count_unrecognized_severity_findings(raw, blocking_severity="BLOCKING", nit_severity="NIT")` and `nit_count = parse_blocking_count(raw, severity="NIT")` (mirroring the exact math used at every other site in this file, e.g. `_review_one_batch()`'s terminal computation). Replace the carryforward dict's hardcoded `"blocking_count": 0` with the computed `blocking_count`, and add a `"nit_count": nit_count` key (the dict currently has no `nit_count` key at all). `parse_blocking_count` and `count_unrecognized_severity_findings` are already imported into this module (see the `from _review_common import (...)` block at the top of the file) — no new import needed.
- **Commit:** `fix(review-plan): compute real blocking_count/nit_count for skip-approved carryforward`

### Card 2: `_review_one_batch()` — refactor terminal write site to `finalize_scope()`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_one_batch()`, replace the terminal block that currently computes `blocking_count = parse_blocking_count(raw, severity="BLOCKING")` + `count_unrecognized_severity_findings(...)`, calls `write_review_file(reviews_dir, "plan", round_n, raw, scope=batch_path.stem)`, and returns a dict with `"blocking_count": blocking_count` (no `nit_count` key) — with a single call `review_entry = finalize_scope(reviews_dir, "plan", round_n, raw, scope=batch_path.stem)`. Update the `print(f"[_review_plan] batch {batch_path.stem}: verdict=...")` line to read `review_entry["verdict"]` and `Path(review_entry["file"]).name` instead of the now-removed local `verdict`/`path` variables. Update the function's final `return` dict to use `review_entry["verdict"]`, `review_entry["blocking_count"]`, and a new `"nit_count": review_entry["nit_count"]` key, and `"file": review_entry["file"]` (already a `str`, no `str()` wrap needed). Keep `"scope"`, `"round"`, and `"session_id"` unchanged. `finalize_scope` is already imported into this module.
- **Commit:** `refactor(review-plan): _review_one_batch terminal write uses finalize_scope`

### Card 3: `_review_one_batch()` — schema-parity `nit_count: 0` on the 3 error-return sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `_review_one_batch()`, add a `"nit_count": 0` key to the literal dict at each of these 3 `return` statements (none has a successful raw response to compute real counts from, so each stays hardcoded `"blocking_count": 0` and gains `"nit_count": 0` for schema parity with `finalize()`'s equivalent `except ReviewError` catch in this same file, which already sets both counters explicitly): (1) the `except LLMError as exc:` immediately following the first `_reviewer_single.run(batch_spec, prompt_text, ...)` call; (2) the `except LLMError as exc:` immediately following the NEED_CONTEXT resume-retry `_reviewer_single.run(batch_spec, retry_prompt, ...)` call; (3) the function-level `except ReviewError as exc:` at the end of `_review_one_batch()` (comment above it reads `# ERROR shape verified 20250517 to match Shared Decisions (#338)`). Do not change any other key in these 3 dicts.
- **Commit:** `fix(review-plan): add nit_count schema parity to _review_one_batch error paths`

### Card 4: `run()` holistic block — refactor 3 success-path write sites to `finalize_scope()`

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `run()`'s holistic block, replace the inline `blocking_count = parse_blocking_count(raw, severity="BLOCKING")` + `count_unrecognized_severity_findings(...)` + `write_review_file(reviews_dir, "plan", round_n, raw, scope="holistic")` + `print(...)` + `reviews.append({...})` sequence at each of these 3 sites with a call to `review_entry = finalize_scope(reviews_dir, "plan", round_n, raw, scope="holistic")`, followed by `print(f"[_review_plan] holistic: verdict={review_entry['verdict']} file={Path(review_entry['file']).name}", file=sys.stderr)` and `reviews.append({"scope": "holistic", "round": round_n, "verdict": review_entry["verdict"], "blocking_count": review_entry["blocking_count"], "nit_count": review_entry["nit_count"], "file": review_entry["file"], "session_id": session_id})`. The 3 sites (identify each by its surrounding comment/branch, not by line number, since Cards 1-3 in this same batch shift line numbers below this point): (a) the branch reached after a NEED_CONTEXT resume retry succeeds (`else:` following `try: raw, session_id = _reviewer_single.run(holistic_spec, retry_prompt, session_id=session_id, resume=True, timeout=resolved_timeout)`) — this branch also reassigns `verdict = parse_verdict(raw)` immediately before the write-site logic; keep that reassignment, it is still needed for the retry-success control flow; (b) the `else:` branch reached when `missing_paths` resolves empty (comment `# No resolvable paths to re-attach — propagate NEED_CONTEXT.`); (c) the final `else:` branch reached when `verdict != "NEED_CONTEXT"` (the "holistic normal" path). `Path` is already imported at module level (`from pathlib import Path`).
- **Commit:** `refactor(review-plan): run() holistic success sites use finalize_scope`

### Card 5: `run()` holistic block — schema-parity `nit_count: 0` on the 3 remaining error-path sites

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `run()`'s holistic block, add a `"nit_count": 0` key to the literal dict appended to `reviews` at each of these 3 sites: (1) the `except LLMError as exc:` immediately following the first holistic `_reviewer_single.run(holistic_spec, prompt_text, timeout=resolved_timeout)` call; (2) the `except LLMError as exc:` immediately following the holistic NEED_CONTEXT resume-retry `_reviewer_single.run(holistic_spec, retry_prompt, ...)` call; (3) the outer `except ReviewError as exc:` that wraps the whole verdict-parsing block (it calls `path = write_review_file(reviews_dir, "plan", round_n, raw, scope="holistic")` then appends a dict with `"verdict": "ERROR"`, `"blocking_count": 0`, `"error": f"parse_verdict failed: {exc}"`). None of these 3 sites has a successful raw response to compute real counts from — this is schema-parity only, no `finalize_scope()` call, matching `finalize()`'s equivalent catch in this same file. Do not change any other key in these 3 dicts.
- **Commit:** `fix(review-plan): add nit_count schema parity to run() holistic error paths`

### Card 6: `run()` — aggregate `nit_count` into the final `ReviewResult`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_review_plan.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `run()`, immediately after the existing `aggregate_blocking = sum(r.get("blocking_count", 0) for r in reviews)` line (near the end of `run()`, just before the final `return ReviewResult(...)`), add `aggregate_nit = sum(r.get("nit_count", 0) for r in reviews)`. Add `nit_count=aggregate_nit` as a new keyword argument to the `ReviewResult(type="plan", round=agg_round, verdict=aggregate, blocking_count=aggregate_blocking, reviews=reviews)` constructor call. `ReviewResult`'s `nit_count` field already defaults to `0` and accepts this keyword (see its `@dataclass` definition in `_review_common.py`, imported into this module already) — no signature change needed there.
- **Commit:** `fix(review-plan): aggregate nit_count into final ReviewResult`

## Batch Tests

`verify:` runs `test-review-plan-flow.py` (the existing flow-harness test file covering `_review_plan.run()`'s per-batch/holistic/resume/carryforward paths) to confirm the refactor in Cards 1-6 does not change any existing `verdict`/`blocking_count`/aggregation behavior. This batch does not add new `nit_count` assertions itself — that is Batch 2 (review-plan-counting-tests), which depends on this batch and extends the same test file with the new counter coverage. Running the existing (unmodified-by-this-batch) test file here catches any regression in `verdict`/`blocking_count` semantics introduced by the `finalize_scope()` refactor before Batch 2 adds coverage for the new `nit_count` field.
