# Batch: status-phase-timestamp

```yaml
task: "mill-go / mill-plan loop hardening"
batch: status-phase-timestamp
number: 4
cards: 1
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-status.py
depends-on: []
```

## Batch Scope

Adds the helper the #373 crash-recovery freshness probe needs: a way to read the timestamp
of a specific phase-entry row from `status.md`'s timeline, including the Hth occurrence of a
repeated phase name (`holistic-reviewing` repeats once per holistic round). The mill-go
SKILL prose that consumes this (the freshness comparison and the per-round
`reviewing-{batch}-r{N}` row) lives in batch 5.

External interface consumed downstream (batch 5): `_status.phase_entry_timestamp(status_path,
phase, *, occurrence=1) -> str | None`.

## Cards

### Card 9: add phase_entry_timestamp to _status

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/unit_tests/test-status.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `phase_entry_timestamp(status_path: Path, phase: str, *, occurrence: int = 1) -> str | None` to `_status.py`. Read the timeline via the existing `read_full(status_path)["timeline"]` (a list of raw rows like `holistic-reviewing  '2026-05-28T21:13:36Z'`). For each row, split into the leading phase token and the remainder with `row.split(None, 1)`; a row matches when its first token equals `phase`. Return the timestamp of the `occurrence`-th matching row (1-indexed, in timeline order), stripped of surrounding single/double quotes; return `None` when fewer than `occurrence` rows match or the matched row has no timestamp field. Do not raise on a missing phase — return `None` so the caller can fall back to re-firing the review. Add tests to `test-status.py`: single occurrence returns its timestamp; the 2nd occurrence of a repeated phase returns the 2nd timestamp; `occurrence` beyond the match count returns `None`; an absent phase returns `None`.
- **Commit:** `feat(status): add phase_entry_timestamp timeline lookup (#373)`

## Batch Tests

`verify:` runs `test-status.py`. The helper is pure (in-memory / tempfile status.md
fixtures, no git or LLM), so the occurrence-selection and missing-phase paths are covered
directly.
