# Discussion: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly

```yaml
task: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly
slug: ps1-startup-speedup
status: discussing
parent: main
```

## Problem

The `.millhouse/*.ps1` wrappers have become noticeably slow. Every call pays three
layers of overhead: (1) `Get-ChildItem | Sort-Object` to discover the latest plugin
cache version at runtime, (2) `uv run --project $latest` which triggers uv's
project/lockfile resolution before starting Python, and (3) for `millpy-vscode.py`
specifically, a synchronous `powershell.exe` spawn inside `_probe_windows()` that
scans all running VS Code processes. These layers stack on every PS1 invocation.

The fix strategy is benchmark-first: measure each layer with `Measure-Command` before
touching anything, then apply only the fixes whose cost the benchmarks confirm.

## Scope

**In:**
- Benchmark harness — `Measure-Command` script covering every candidate layer; results
  written to `.scratch/benchmark-results.md` before any production code is written.
- mill-setup: new phase that writes a venv activation block to `$PROFILE` delimited by
  `# mill-venv-start` / `# mill-venv-end` markers; idempotent on re-run; creates file
  if it does not exist.
- New `shortcut-wrapper.ps1` template: `uv run --active "<SCRIPT_PATH>" @args` —
  eliminates the `Get-ChildItem` scan and uv project-resolution in one change.
- `_shortcuts.write_all(mill_dir, latest_path: Path)` — add required `latest_path`
  parameter; compute `<SCRIPT_PATH>` from it per script.
- mill-setup SKILL.md Phase 4.7 — update inline Python call to compute and pass
  `latest_path` before calling `write_all`; document the new `$PROFILE` phase.
- mill-setup SKILL.md Phase 8 (Verify + report) — add a verification step that checks
  the `# mill-venv-start` / `# mill-venv-end` block exists in `$PROFILE` after the new
  phase runs. A failed profile write must surface as a visible error, not a silent pass.
- `millpy-vscode.py` — add `--filter-open` CLI flag; gate `_filter_open_worktrees` call
  on the flag; `import _vscode_processes` stays at module level.
- `test-shortcut-wrapper.py` — update all `write_all(mill_dir)` call sites to pass
  `fake_latest_path`; update the standalone `render(TEMPLATE_PATH, {"SCRIPT": ...})`
  call at line 23 to also pass `"SCRIPT_PATH"`; remove `"uv run --project"` assertion,
  add `"uv run --active"` and `<SCRIPT_PATH>` checks.
- `test-millpy-vscode.py` — add tests for `--filter-open` flag: probe not called by
  default; probe called when flag is present. Update existing tests
  `filter_excludes_open_worktree` and `filter_empties_list_calls_spawn_then_opens` to
  call `main(["--filter-open"])` instead of `main([])` (both tests assert probe-based
  filtering which only occurs with the flag).

**Out:**
- No POSIX/macOS changes — PS1 wrappers and `$PROFILE` patching are Windows-only;
  `_probe_posix()` in `_vscode_processes.py` is untouched.
- No daemon or background caching layer.
- No changes to any script's output, flags, or observable behavior beyond
  `--filter-open` in `millpy-vscode.py`.
- No lazy-import changes — `_vscode_processes` import stays at module level.
- No changes to `_vscode_processes._probe_windows()` internals.

## Decisions

### benchmark-first-gate

- **Decision:** Plan batch 0 is a benchmark step. Implementer runs the `Measure-Command`
  harness, writes results to `.scratch/benchmark-results.md`, and includes them in the
  commit message for the first implementation batch so the fix rationale is traceable.
- **Rationale:** Proposal and task description both mandate data-first. Hardcoded in plan
  ordering to prevent accidental skip.
- **Rejected:** Treat benchmarks as optional post-implementation validation.

### uv-run-active-with-profile-activation

- **Decision:** PS1 wrappers call `uv run --active "<hardcoded-script-path>" @args`.
  The venv is activated once at shell startup via a line mill-setup writes to `$PROFILE`.
  This eliminates uv's project/lockfile resolution per call while keeping uv in the
  execution path.
- **Rationale:** uv with `--active` skips all project resolution and uses the already-
  activated venv directly. The plugin-cache venv is not worktree-specific — all
  worktrees share the same venv and the same script paths. Worktree context is discovered
  at runtime via `git rev-parse`. Keeping `uv run` preserves the uv-managed execution
  environment the operator prefers.
- **Rejected (direct Python):** `& "<venv>\python.exe" "<script>" @args` — marginally
  faster (no uv startup), but drops uv from the invocation path, which the operator
  wants to keep.
- **Rejected (uv run --project each time):** current approach — pays full project
  resolution on every call.

### profile-activation-strategy

- **Decision:** mill-setup writes exactly one line to `$PROFILE`, delimited by
  `# mill-venv-start` / `# mill-venv-end` markers. Re-runs replace the block
  (idempotent). Creates `$PROFILE` if it does not exist. The block is:
  ```powershell
  # mill-venv-start — managed by mill-setup, do not edit manually
  . "<latest_path>\.venv\Scripts\Activate.ps1"
  # mill-venv-end
  ```
- **Rationale:** Marker-delimited block is the standard idempotent pattern for
  profile injection. Clear label prevents confusion with user-written lines.
- **Rejected (manual):** user adds activation themselves — error-prone; defeats
  the goal of mill-setup being the single setup action.

### merge-fixes-1-and-3

- **Decision:** Fixes 1 (eliminate uv project-resolution) and 3 (hardcode script path,
  eliminating `Get-ChildItem` scan) are a single template change. New template tokens:
  `<SCRIPT>` (stem, for comment) and `<SCRIPT_PATH>` (full path to the `.py` file).
- **Rationale:** Both fixes target the same PS1 block; combining them avoids an
  intermediate state with no independent value.
- **Rejected:** Separate commits.

### write-all-required-latest-path

- **Decision:** `_shortcuts.write_all(mill_dir: Path, latest_path: Path) -> list[Path]`
  — `latest_path` is a required positional parameter. Computes
  `{"SCRIPT": script, "SCRIPT_PATH": str(latest_path / "scripts" / f"{script}.py")}`
  per script and passes to `_render.render`.
- **Rationale:** Explicit, testable, no hidden filesystem dependencies. mill-setup
  always has this value. Unit tests provide a fake `Path`.
- **Rejected:** Optional param with auto-compute fallback — dead code path never used
  in production.

### filter-open-flag-default-off

- **Decision:** Add `--filter-open` argument to `millpy-vscode.py`'s argparse. Default:
  no PowerShell probe. Only when `--filter-open` is passed does the code call
  `_filter_open_worktrees`. `import _vscode_processes` stays at module level — only the
  *call* to `_filter_open_worktrees` is gated.
- **Rationale:** The PowerShell spawn (`_probe_windows()`) is the dominant overhead.
  The module import itself is negligible; keeping it at module level preserves the
  existing `patch("mill_vscode._vscode_processes...")` mock surface in ~10 existing
  tests. Gating the call achieves the performance goal without disrupting tests.
- **Rejected (lazy import):** Moving `import _vscode_processes` inside the function
  breaks ~10 existing test mock paths via `AttributeError` at patch setup time; import
  cost is not the bottleneck.
- **Rejected (optimize probe):** More complex, out of scope.

## Technical context

**Files changed:**

| File | Change |
|---|---|
| `plugins/mill/templates/shortcut-wrapper.ps1` | New template: `uv run --active "<SCRIPT_PATH>" @args` |
| `plugins/mill/scripts/_shortcuts.py` | `write_all(mill_dir, latest_path)` — required param; `SCRIPT_PATH` token |
| `plugins/mill/scripts/millpy-vscode.py` | Add `--filter-open`; gate `_filter_open_worktrees` call on flag |
| `plugins/mill/skills/mill-setup/SKILL.md` | New `$PROFILE` phase + updated Phase 4.7 call |
| `plugins/mill/unit_tests/test-shortcut-wrapper.py` | Pass fake `latest_path`; updated assertions |
| `plugins/mill/unit_tests/test-millpy-vscode.py` | `--filter-open` behavior tests |

**Key modules:**

- `_shortcuts.py` → `write_all(mill_dir, latest_path)` — only caller is mill-setup
  Phase 4.7. Currently calls `_render.render(_TEMPLATE_PATH, {"SCRIPT": script})`.
- `_render.py` → `render(template_path, values)` — raises `KeyError` on unresolved
  tokens. New template has two tokens; both must be present in every `render` call.
- `millpy-vscode.py` → `_filter_open_worktrees` calls `_vscode_processes.find_open_vscode_paths()`
  at line 70. After change: `_vscode_processes` import stays at module level; the call to
  `_filter_open_worktrees` is only made when `--filter-open` is set.
- `_vscode_processes.py` → `_probe_windows()` spawns `powershell.exe Get-Process Code`.
- mill-setup Phase 4.7 inline Python currently: `_shortcuts.write_all(Path('.millhouse'))`.
  After: compute `latest_path`, call `_shortcuts.write_all(Path('.millhouse'), latest_path)`.

**New template body** (full replacement of `shortcut-wrapper.ps1`):
```
# Wrapper for <SCRIPT> — generated by mill-setup Phase 4.7. Do not edit manually — re-run mill-setup.
uv run --active "<SCRIPT_PATH>" @args
```

**`$PROFILE` block written by mill-setup:**
```powershell
# mill-venv-start — managed by mill-setup, do not edit manually
. "<latest_path>\.venv\Scripts\Activate.ps1"
# mill-venv-end
```

**`latest_path` computation in mill-setup Phase 4.7:**
```python
import os
from pathlib import Path
cache = Path(os.environ["USERPROFILE"]) / ".claude" / "plugins" / "cache" / "millhouse" / "mill"
latest_path = max((p for p in cache.iterdir() if p.is_dir()), key=lambda p: p.name)
```

**Benchmark harness** (run before any code change):
```powershell
# Full wrapper (baseline):
Measure-Command { & "c:/Code/millhouse/wts/millhouse/.millhouse/millpy-status.ps1" }
# uv run --project alone:
$latest = (Get-ChildItem "$HOME\.claude\plugins\cache\millhouse\mill" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
Measure-Command { uv run --project $latest python -c "print('ok')" }
# uv run --active alone (venv must be activated first):
Measure-Command { uv run --active python -c "print('ok')" }
# Direct venv Python alone:
Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "print('ok')" }
# Python import overhead:
Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "import _config, _paths, _tasks_md, _wiki" }
# _probe_windows (PowerShell spawn):
Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "import _vscode_processes; _vscode_processes._probe_windows()" }
```

**Venv sharing across worktrees:** the plugin-cache venv is not worktree-specific.
All `.millhouse/*.ps1` wrappers across all worktrees point to identical script paths
under the same `$latest` cache entry. Worktree context is discovered at runtime via
`git rev-parse --show-toplevel` inside each script.

**mill-setup idempotency:** `$PROFILE` block replaced on re-run (marker-based);
`write_all` skips files with matching content. Re-run after `update-plugins.ps1`
refreshes both the profile activation path and the hardcoded script paths.

## Constraints

- PS1 wrappers and `$PROFILE` patching are Windows-only. No POSIX changes.
- `_render.render` raises `KeyError` if any template token is absent. Both `SCRIPT`
  and `SCRIPT_PATH` must be passed on every `render` call.
- mill-setup SKILL.md inline Python snippets must remain verbatim copy-pasteable.
- Behavior must not change except: `millpy-vscode.py` default no longer filters open
  windows (opt-in via `--filter-open`).
- Existing `test-shortcut-wrapper.py` assertion `"uv run"` still passes (new template
  still contains `uv run`); assertion `"--project"` must be removed or inverted.

## Testing

**`test-shortcut-wrapper.py` — changes required:**
- All `write_all(mill_dir)` → `write_all(mill_dir, fake_latest_path)` where
  `fake_latest_path = Path(tmpdir) / "fake-latest"`.
- Update the standalone `render(TEMPLATE_PATH, {"SCRIPT": "millpy-status"})` call at
  line 23 to also pass `"SCRIPT_PATH": str(fake_latest_path / "scripts" / "millpy-status.py")`.
- Current assertion is `"uv run" in rendered` — this still passes. Add assertion:
  `"uv run --active" in rendered`. Remove any assertion for `"--project"` or add
  `"--project" not in rendered`.
- Add assertion: `str(fake_latest_path / "scripts" / "millpy-status.py") in rendered`.
- Idempotency and legacy-cleanup tests remain valid.

**`test-millpy-vscode.py` — changes required:**
- Update `filter_excludes_open_worktree` (line 535) and
  `filter_empties_list_calls_spawn_then_opens` (line 581): change `main([])` →
  `main(["--filter-open"])`. Both tests assert probe-based filtering, which only occurs
  with the flag. All other existing tests using `main([])` remain unchanged.
- Add new test: without `--filter-open`, mock `_vscode_processes.find_open_vscode_paths`
  and assert it is never called.
- Add new test: with `--filter-open`, assert `find_open_vscode_paths` is called once.
- `patch("mill_vscode._vscode_processes.find_open_vscode_paths", ...)` continues to work
  because the import stays at module level.

**Run all unit tests** via `python plugins/mill/unit_tests/run-all.py` after each batch.

## Q&A log

- **Q:** Should the benchmark step be a mandatory plan batch gating later implementation? **A:** [auto-pick] Yes — plan batch 0 is the benchmark; implementer writes `.scratch/benchmark-results.md` before any code change. **Why:** proposal and task description both mandate data-first.
- **Q:** Should Fixes 1 and 3 be merged into a single template change? **A:** [auto-pick] Yes — single new template with `<SCRIPT_PATH>` token. **Why:** both fixes target the same PS1 block; no value in an intermediate state.
- **Q:** How should `write_all` receive the script path? **A:** [auto-pick] Required `latest_path: Path` parameter. **Why:** explicit, no hidden env-var dependency, unit tests pass a fake Path.
- **Q:** Keep `uv run` in the invocation path? **A:** Yes (operator preference) — use `uv run --active` with profile-level venv activation rather than calling Python directly.
- **Q:** Who activates the venv? **A:** mill-setup writes a marker-delimited block to `$PROFILE`; idempotent on re-run; creates file if missing.
- **Q:** Does this work across worktrees? **A:** Yes — plugin-cache venv is shared; all worktrees use identical script paths; worktree context discovered at runtime.
- **Q:** Should `--filter-open` flip the default in `millpy-vscode.py`? **A:** [auto-pick] Yes — default no-probe, `--filter-open` opts in. **Why:** PowerShell spawn is the dominant overhead; fast path should be the default.
- **Q:** Should `_vscode_processes` be lazily imported? **A:** No — keep module-level import; gate only the `_filter_open_worktrees` call. **Why:** import cost is negligible; lazy import breaks ~10 existing `patch("mill_vscode._vscode_processes...")` mock paths.
