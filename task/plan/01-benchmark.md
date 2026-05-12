# Batch: benchmark

```yaml
task: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly
batch: benchmark
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

This batch runs the PS1 startup benchmark harness before any production code is touched. The implementer executes six `Measure-Command` measurements (from discussion.md § Technical context), records the median elapsed milliseconds for each, and commits the results to `task/benchmark-notes.md` on the task branch. `task/benchmark-notes.md` is removed by mill-merge's cleanup commit and never merges to main — its purpose is to have the numbers available for batch 02's commit message. No production files are modified in this batch; `verify: null` because the deliverable is a data file, not runnable code.

## Cards

### Card 1: Run benchmark harness and commit results to task/benchmark-notes.md

- **Context:** none
- **Edits:** none
- **Creates:**
  - `task/benchmark-notes.md`
- **Deletes:** none
- **Requirements:**
  - Run the six `Measure-Command` benchmarks specified in discussion.md § Technical context, in a PowerShell session where the latest mill venv is available (so the `uv run --active` measurement is valid). The six benchmarks are:
    1. Full wrapper baseline: `Measure-Command { & "c:/Code/millhouse/wts/millhouse/.millhouse/millpy-status.ps1" }`
    2. `uv run --project` alone: set `$latest` via `Get-ChildItem`, then `Measure-Command { uv run --project $latest python -c "print('ok')" }`
    3. `uv run --active` alone (activate venv first): `Measure-Command { uv run --active python -c "print('ok')" }`
    4. Direct venv Python: `Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "print('ok')" }`
    5. Python import overhead: `Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "import _config, _paths, _tasks_md, _wiki" }`
    6. `_probe_windows` (PowerShell spawn): `Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "import _vscode_processes; _vscode_processes._probe_windows()" }`
  - Write results to `task/benchmark-notes.md` with this structure:
    ```markdown
    # Benchmark Results

    | Benchmark | Median (ms) |
    |---|---|
    | Full wrapper (baseline) | ... |
    | uv run --project alone | ... |
    | uv run --active alone | ... |
    | Direct venv Python | ... |
    | Python import overhead (_config _paths _tasks_md _wiki) | ... |
    | _probe_windows (powershell.exe Get-Process Code) | ... |
    ```
  - Run each benchmark 3–5 times and record the median `TotalMilliseconds`.
  - The file is committed on the task branch so it is available to the batch 02 implementer when composing the commit message.
- **Commit:** `benchmark: record PS1 wrapper startup measurements for ps1-startup-speedup`

## Batch Tests

`verify: null` — this batch creates a data file, not runnable code. The implementer verifies correctness by inspecting `task/benchmark-notes.md` for the presence of all six benchmark rows.
