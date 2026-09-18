# Batch: status-helpers-core

```yaml
task: "mill-go-base: orchestration robustness gaps"
batch: status-helpers-core
number: 1
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
depends-on: []
```

## Batch Scope

Adds two independent, small additions to `plugins/mill/scripts/_status.py`: a `latest`-occurrence mode on `phase_entry_timestamp` (consumed by batch 5, fixing #1005) and a new `resume_batch` helper (consumed by batch 4, fixing #1013). Both are pure additions — no existing call site or signature changes, no behavior change to any existing caller. Grouped into one batch because both touch the same two large files (`_status.py`, `test-status.py`); estimated context: 2 cards x (61,222 + 74,099 bytes) / 4 ≈ 67,660 tokens, comfortably under the 120,000 cap.

## Cards

### Card 1: `phase_entry_timestamp` latest-occurrence mode

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a keyword-only parameter `latest: bool = False` to `phase_entry_timestamp` (defined at `_status.py`, currently `def phase_entry_timestamp(status_path: Path, phase: str, *, occurrence: int = 1) -> str | None:`). When `latest=True`, ignore `occurrence` entirely and return the timestamp of the LAST timeline row whose phase token equals `phase` (scan every matching row, keep updating a running "last seen" result rather than returning on first match; still strip surrounding quotes exactly as the existing `occurrence`-indexed branch already does) — return `None` if there are zero matches, unchanged from today. When `latest=False` (the default), behavior must be byte-for-byte identical to today's existing `occurrence`-indexed lookup — this is a pure addition, not a rewrite of the existing loop; add the `latest` branch as a distinct code path that does not alter the existing `occurrence` branch's logic at all. Update the function's docstring `Args:` section to document `latest` and state explicitly that `latest=True` takes precedence over `occurrence` (the two are mutually exclusive in effect, `latest` wins when both happen to be passed).
  Add two test functions to `plugins/mill/unit_tests/test-status.py`, following that file's existing fixture conventions (an in-memory/tempfile `status.md` with a `## Timeline` block containing rows, populated via the same helper functions the existing `phase_entry_timestamp` tests in that file already use — locate and reuse them rather than hand-writing raw file content):
  - `test_phase_entry_timestamp_latest_returns_last_matching_occurrence`: build a fixture whose timeline has the same phase token (e.g. `holistic-reviewing`) appended three times at three distinct timestamps; call `phase_entry_timestamp(status_path, "holistic-reviewing", latest=True)` and assert it returns the THIRD (most recent) timestamp — and assert this holds regardless of what `occurrence` value (if any) is also passed alongside `latest=True`.
  - `test_phase_entry_timestamp_latest_none_when_no_match`: build a fixture whose timeline has zero rows matching a given phase token; call with `latest=True` and assert the return value is `None`.
- **Commit:** `status: add latest-occurrence mode to phase_entry_timestamp`

### Card 2: `resume_batch` helper for blocked-batch recovery

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add `resume_batch(status_path: Path, batch_name: str, *, timestamp: str, preserve_start_sha: bool) -> None` to `_status.py`, built entirely from the existing `set_batch_field` and `append_phase` primitives already in this file (no new low-level file-mutation logic):
  1. `set_batch_field(status_path, batch_name, "state", "pending")`.
  2. `set_batch_field(status_path, batch_name, "blocked_reason", None)` — the existing `None`-value convention in `set_batch_field` already removes the field (`if value is None: entry.pop(key, None)`); no new logic needed for this step.
  3. When `preserve_start_sha` is `False`: also call `set_batch_field(status_path, batch_name, "commit_sha", None)` and `set_batch_field(status_path, batch_name, "start_sha", None)`. When `preserve_start_sha` is `True`: skip this step entirely — leave both fields exactly as they are on disk.
  4. `append_phase(status_path, "implementing", timestamp)` — this call's own existing behavior already auto-clears any top-level `blocked_reason:` row in the yaml block when the new phase is not `"blocked"`; do not add a separate top-level-field-clearing step, it would be redundant.
  Let any exception `set_batch_field`/`append_phase` already raise (e.g. `ValueError` for an unknown batch name) propagate unchanged — `resume_batch` adds no new exception handling of its own.
  Write a docstring modeled on `set_blocked`'s existing docstring shape and level of detail (same file) — document the four-step sequence above, the `preserve_start_sha` semantics, and that this is the documented recovery path for a batch an operator has fixed externally while it was `state: blocked` (see the "Resume after external fix" subsection batch 4 adds to `mill-go-base/SKILL.md`).
  Add four test functions to `plugins/mill/unit_tests/test-status.py`, reusing that file's existing batch-fixture helpers (locate the existing `## Batches`-section fixture builder(s) already used by `set_batch_field`'s own tests in this file, and reuse them rather than hand-writing raw file content):
  - `test_resume_batch_resets_state_and_clears_blocked_reason`: fixture batch at `state: blocked` with a `blocked_reason` set; after calling `resume_batch`, read the batch back via `read_batches` and assert `state == "pending"` and `blocked_reason` is absent from the entry dict.
  - `test_resume_batch_preserve_start_sha_true_keeps_existing_sha`: fixture batch with `commit_sha` and `start_sha` both set; call with `preserve_start_sha=True`; assert both fields are unchanged in the read-back entry.
  - `test_resume_batch_preserve_start_sha_false_clears_sha`: same fixture; call with `preserve_start_sha=False`; assert both fields are absent from the read-back entry.
  - `test_resume_batch_appends_implementing_phase_and_clears_top_level_blocked_reason`: fixture `status.md` with top-level `phase: blocked` and a top-level `blocked_reason` set; after calling, assert (via `read_full` or `read_status`) the top-level `phase == "implementing"` and the top-level `blocked_reason` is absent.
- **Commit:** `status: add resume_batch helper for blocked-batch recovery`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-status.py` directly (a single test file, per the "Single test file" scoping pattern) — this file already contains every existing test for `_status.py`'s functions and is the natural, already-scoped regression gate for both cards' additions plus a check that neither addition altered any existing `_status.py` behavior.
