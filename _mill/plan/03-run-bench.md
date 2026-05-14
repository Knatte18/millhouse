# Batch: run-bench

```yaml
task: "(A) -- Benchmark Gemini single-reviewers vs sonnetmax baseline"
batch: run-bench
number: 3
cards: 1
verify: null
depends-on: [2]
```

## Batch Scope

This batch runs the completed bench-reviewers.py with all three real Gemini reviewers (g25flash, g3flash_preview, g25pro) across all three review types (discussion, plan, code), and records the results. No code changes — the deliverable is empirical benchmark data written to `_mill/bench-results.md` on the task branch, which can be referenced when deciding whether g3flash_preview or g25pro are viable NORCE-fallback candidates.

## Cards

### Card 4: Run full benchmark and record results

- **Context:**
  - `plugins/mill/integration_tests/bench-reviewers.py`
- **Edits:** none
- **Creates:**
  - `_mill/bench-results.md`
- **Deletes:** none
- **Requirements:**
  - Run `python plugins/mill/integration_tests/bench-reviewers.py` from the worktree root using the defaults (reviewers: g25flash g3flash_preview g25pro; types: discussion plan code; timeout: 300s). Do not set `PYTHONPATH` — the script sets its own sys.path.
  - Confirm `.scratch/bench-<timestamp>.md` is written with 9 rows (3 reviewers × 3 types). If any row shows `ERROR`, re-run that combination once with `--reviewers <name> --types <type>` to distinguish transient from stable failure.
  - Write `_mill/bench-results.md` containing: (1) the full 9-row results table from the bench output, (2) a brief interpretation paragraph (2-4 sentences) noting which reviewers are format-compliant, finding counts, and a recommendation for which model(s) are viable NORCE-fallback candidates.
  - Expected pattern based on preliminary trials: g3flash_preview is fast and format-compliant across all types; g25pro is reliable but slower; g25flash is unstable and may fail format compliance for plan reviews.
- **Commit:** `chore(bench): record benchmark results for bench-gemini-single-reviewers`

## Batch Tests

`verify: null` — this batch produces an analysis file, not a runnable test surface. Correctness is confirmed by visual inspection of `_mill/bench-results.md`: 9 rows present, no unhandled exceptions during the run.
