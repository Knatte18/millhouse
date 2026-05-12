# Benchmark Results

Machine: Windows 11, mill cache `2.0.0` at `C:\Users\hanf\.claude\plugins\cache\millhouse\mill\2.0.0`  
Date: 2026-05-12  
Method: 3 runs each, median TotalMilliseconds reported

| Benchmark | Run 1 (ms) | Run 2 (ms) | Run 3 (ms) | Median (ms) |
|---|---|---|---|---|
| Full wrapper (baseline) | 1230 | 1097 | 933 | 1097 |
| uv run --project alone | 224 | 210 | 213 | 213 |
| uv run --active alone | 166 | 152 | 170 | 166 |
| Direct venv Python | 109 | 109 | 98 | 109 |
| Python import overhead (_config _paths _tasks_md _wiki) | 171 | 153 | 156 | 156 |
| _probe_windows (powershell.exe Get-Process Code) | 1300 | 1417 | 1302 | 1302 |

## Summary Table

| Benchmark | Median (ms) |
|---|---|
| Full wrapper (baseline) | 1097 |
| uv run --project alone | 213 |
| uv run --active alone | 166 |
| Direct venv Python | 109 |
| Python import overhead (_config _paths _tasks_md _wiki) | 156 |
| _probe_windows (powershell.exe Get-Process Code) | 1302 |

## Notes

- The full wrapper (~1097 ms) pays: `Get-ChildItem` scan + `uv run --project` resolution + Python startup + imports.
- `uv run --project` alone (~213 ms) is the project-resolution cost + Python startup.
- `uv run --active` alone (~166 ms) saves ~47 ms over `--project` (no lockfile resolution).
- Direct venv Python (~109 ms) saves ~57 ms over `uv run --active` (no uv overhead at all).
- Python import overhead (~156 ms) — this is *additive* on top of Python startup, measured with direct venv Python as the base.
- `_probe_windows` (~1302 ms) — the dominant overhead: spawns `powershell.exe Get-Process Code`. This alone accounts for most of the full wrapper cost when `millpy-vscode.py` is called.
- The `Get-ChildItem` scan (difference between full wrapper and `uv run --project`) is approximately `1097 - 213 = 884 ms` absorbed by process startup + scan; the actual runtime scan adds to cold-start cost.
- Key fix: switch to `uv run --active` with profile-level activation saves ~47 ms per call on the project-resolution path; gating `_probe_windows` behind `--filter-open` saves ~1190 ms for the common case.
