MILL_REVIEW_BEGIN
# Review: millpy-implement/bg: Windows baseline-worktree teardown (WinError 145) and stale liveness reporting — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: Claude Sonnet 5 (claude-sonnet-5)
reviewed_file: plan/
date: 2026-09-04
```

## Findings

### [BLOCKING:scope] Card 9 relies on `_status.py` API not listed in its Context
**Location:** batch 4 / Card 9 (`test-implementer-common.py`) **Issue:** Requirements name `_status.set_batch_field`, `_status.read_batches(status_path)`, and instruct following "`_status.py`'s documented `## Batches` format," but Card 9's `Context:` is only `_verify_baseline.py`/`millpy-implement.py` and its `Edits:` is `test-implementer-common.py` — `_status.py` appears in neither, so the implementer cannot read the real function signatures/format without cold-start exploration. **Fix:** Add `plugins/mill/scripts/_status.py` to Card 9's `Context:`, and instruct reuse of the already-established `_status.render_initial(...)` + `_status.init_batches(status_path, ["01-test-batch"])` pattern (used identically in `test-millpy-fix.py`/`test-status.py`) instead of the vague "write the minimal status.md text directly" fallback.

### [NIT:consistency] Card 7's "Add an else:" prose doesn't match the shown elif/else code
**Location:** batch 4 / Card 7 (`_implementer_common.py`) **Issue:** The prose says "Add an `else:` clause after the `if normalized_replay.issubset(normalized_baseline):` block," but the code snippet immediately below shows an `elif start_sha is None: pass` / `else: ...` chain — the prose undersells that a new `elif` branch is also required. **Fix:** Reword the prose to say "extend the `if normalized_replay.issubset(...)` block with an `elif start_sha is None: pass` and a final `else:`" so it matches the verbatim code block exactly.

## Verdict

REQUEST_CHANGES
Card 9's corroboration test cases require `_status.py` API knowledge not present in its declared Context.
MILL_REVIEW_END
