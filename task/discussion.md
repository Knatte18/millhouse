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
cache version at runtime, (2) `uv run --project $latest` which starts the Rust uv
binary before Python, and (3) for `millpy-vscode.py` specifically, a synchronous
`powershell.exe` spawn inside `_probe_windows()` that scans all running VS Code
processes. These layers stack on every PS1 invocation.

The fix strategy is benchmark-first: measure each layer with `Measure-Command` before
touching anything, then apply only the fixes whose cost the benchmarks confirm. The
proposal already identifies four candidates; this task implements all four for the
confirmed bottlenecks and leaves the rest undisturbed.

## Scope

**In:**
- Benchmark harness — `Measure-Command` script covering every candidate layer; results
  written to `.scratch/benchmark-results.md` before any production code is written.
- New `shortcut-wrapper.ps1` template with `<VENV_PYTHON>`, `<SCRIPT_PATH>`, and
  `<SCRIPT>` tokens, replacing the `Get-ChildItem` scan and `uv run` call in one change.
- `_shortcuts.write_all(mill_dir, latest_path: Path)` — add required `latest_path`
  parameter; compute `<VENV_PYTHON>` and `<SCRIPT_PATH>` from it per script.
- mill-setup SKILL.md Phase 4.7 — update inline Python call to compute and pass
  `latest_path` before calling `write_all`.
- `millpy-vscode.py` — add `--filter-open` CLI flag; default to no PowerShell probe;
  move `import _vscode_processes` inside `_filter_open_worktrees` (lazy import).
- `test-shortcut-wrapper.py` — update call sites to pass a fake `latest_path`; update
  assertions (remove `"uv run"` check, add venv Python path checks).
- `test-millpy-vscode.py` — add tests for `--filter-open` flag: probe not called by
  default, probe called when flag is present.

**Out:**
- No POSIX/macOS changes — PS1 wrappers are Windows-only; `_probe_posix()` in
  `_vscode_processes.py` is untouched.
- No daemon or background caching layer.
- No changes to any script's output, flags, or observable behavior beyond
  `--filter-open` in `millpy-vscode.py`.
- No lazy-import changes outside `millpy-vscode.py` — `_spawn_core` and other imports
  in `millpy-status.py`, `millpy-spawn.py`, etc. are needed on every call.
- No changes to `_vscode_processes._probe_posix()` or `_probe_windows()` internals.
- Fixes 2 and 4 (lazy `_vscode_processes` import and `--filter-open` flag) are applied
  regardless of benchmark outcome — even if the probe cost is smaller than expected,
  the default no-probe behavior is strictly better UX (shows all worktrees instantly).

## Decisions

### benchmark-first-gate

- **Decision:** Plan batch 0 is a benchmark step. Implementer runs the `Measure-Command`
  harness (see Technical context), writes results to `.scratch/benchmark-results.md`,
  and includes them in the commit message for the first implementation batch so the fix
  rationale is traceable.
- **Rationale:** Proposal and task description both mandate data-first. Hardcoded in plan
  ordering to prevent accidental skip.
- **Rejected:** Treat benchmarks as optional post-implementation validation — contradicts
  scope.

### merge-fixes-1-and-3

- **Decision:** Fixes 1 (direct venv Python) and 3 (hardcode `$latest`) are a single
  template change. The new template is two lines: a comment and the invocation. Tokens:
  `<SCRIPT>` (stem for comment), `<VENV_PYTHON>` (full path to `python.exe` in venv),
  `<SCRIPT_PATH>` (full path to the script `.py` file). Both are expanded at mill-setup
  time; no runtime PowerShell lookup remains.
- **Rationale:** The two fixes target the same PS1 block. A staged approach produces an
  intermediate state (hardcoded `$latest` + `uv run`) with no independent value.
- **Rejected:** Separate commits — more history noise, no benefit.

### write-all-required-latest-path

- **Decision:** `_shortcuts.write_all(mill_dir: Path, latest_path: Path) -> list[Path]`
  — `latest_path` is a required positional parameter. `_shortcuts.py` does no filesystem
  discovery. `write_all` passes `{"SCRIPT": script, "VENV_PYTHON": str(latest_path /
  ".venv" / "Scripts" / "python.exe"), "SCRIPT_PATH": str(latest_path / "scripts" /
  f"{script}.py")}` to `_render.render`.
- **Rationale:** Explicit is better than hidden env-var dependency. mill-setup always has
  `latest_path`. Unit tests provide a fake `Path` — no real filesystem or env var needed.
- **Rejected:** Optional param with auto-compute fallback — dead code path never used in
  production; env-var dependency makes tests fragile.

### filter-open-flag-default-off

- **Decision:** Add `--filter-open` argument to `millpy-vscode.py`'s argparse. Default:
  no PowerShell probe. Only when `--filter-open` is passed does the code call
  `_filter_open_worktrees` (which in turn calls `_vscode_processes.find_open_vscode_paths`).
  The import `import _vscode_processes` is moved from module level to the top of
  `_filter_open_worktrees`.
- **Rationale:** The PowerShell spawn is the dominant overhead in `millpy-vscode.py`. The
  default path should be the fast path. When users explicitly want open-window filtering
  they pass `--filter-open`. Lazy import ensures the module load doesn't happen on
  non-filter-open invocations.
- **Rejected (faster probe):** Replace `_probe_windows()` with a Win32 ctypes call —
  more complex, harder to maintain, and changes behavior not scope.

### lazy-import-scope

- **Decision:** Only `import _vscode_processes` is made lazy (moved inside
  `_filter_open_worktrees`). No other imports in `millpy-vscode.py` or other scripts are
  changed.
- **Rationale:** `_spawn_core` is called unconditionally in `main()` regardless of flags,
  so deferring it saves nothing. Other scripts' imports are all on the hot path.
- **Rejected:** Broad lazy-import pass across all scripts — YAGNI; benchmarks may show
  Python import is not a meaningful contributor.

## Technical context

**Files changed:**

| File | Change |
|---|---|
| `plugins/mill/templates/shortcut-wrapper.ps1` | New template: 2 lines, 3 tokens (`<SCRIPT>`, `<VENV_PYTHON>`, `<SCRIPT_PATH>`) |
| `plugins/mill/scripts/_shortcuts.py` | `write_all(mill_dir, latest_path)` — add required param; update token dict |
| `plugins/mill/scripts/millpy-vscode.py` | Add `--filter-open` flag; default no-probe; lazy import `_vscode_processes` |
| `plugins/mill/skills/mill-setup/SKILL.md` | Phase 4.7: compute `latest_path` in Python before calling `write_all` |
| `plugins/mill/unit_tests/test-shortcut-wrapper.py` | Pass fake `latest_path` to `write_all`; update assertions |
| `plugins/mill/unit_tests/test-millpy-vscode.py` | Add `--filter-open` behavior tests |

**Key modules:**

- `_shortcuts.py` → `write_all(mill_dir, latest_path)` — only caller is mill-setup
  Phase 4.7. Currently calls `_render.render(_TEMPLATE_PATH, {"SCRIPT": script})`.
- `_render.py` → `render(template_path, values)` — raises `KeyError` on unresolved
  tokens. New template adds two tokens; all must be present in every `render` call.
- `millpy-vscode.py` → `_filter_open_worktrees(active, wiki_path, hub_subpath_default)`
  — calls `_vscode_processes.find_open_vscode_paths()` at line 70. `main()` calls this
  without any guard; after the change it is only called when `--filter-open` is set.
- `_vscode_processes.py` → `_probe_windows()` spawns
  `powershell -NoProfile -Command "Get-Process Code ..."` — the expensive call.
- mill-setup Phase 4.7 inline Python currently: `_shortcuts.write_all(Path('.millhouse'))`.
  After change: compute `latest_path = max(cache.iterdir(), key=lambda p: p.name)` where
  `cache = Path(os.environ["USERPROFILE"]) / ".claude" / "plugins" / "cache" / "millhouse" / "mill"`,
  then call `_shortcuts.write_all(Path('.millhouse'), latest_path)`.

**New template body** (replace entire `shortcut-wrapper.ps1`):
```
# Wrapper for <SCRIPT> — generated by mill-setup Phase 4.7. Do not edit manually — re-run mill-setup.
& "<VENV_PYTHON>" "<SCRIPT_PATH>" @args
```

**Benchmark harness** (from proposal — run before any code change):
```powershell
# Full wrapper (baseline):
Measure-Command { & "c:/Code/millhouse/wts/millhouse/.millhouse/millpy-status.ps1" }
# uv run alone:
$latest = (Get-ChildItem "$HOME\.claude\plugins\cache\millhouse\mill" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
Measure-Command { uv run --project $latest python -c "print('ok')" }
# Direct venv Python alone:
Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "print('ok')" }
# Python import overhead:
Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "import _config, _paths, _tasks_md, _wiki" }
# _probe_windows (PowerShell spawn):
Measure-Command { & "$latest\.venv\Scripts\python.exe" -c "import _vscode_processes; _vscode_processes._probe_windows()" }
```

**mill-setup Phase 4.7 idempotency:** already idempotent (`write_all` skips files with
matching content). Re-run after `update-plugins.ps1` refreshes the hardcoded paths to the
new plugin version — this is the documented and correct workflow.

**Backward compat:** existing `.millhouse/*.ps1` files keep working until mill-setup is
re-run. After re-run, they point directly to the venv Python. No migration step needed
beyond re-running mill-setup.

## Constraints

- PS1 wrappers are Windows-only. No POSIX changes anywhere.
- `_render.render` raises `KeyError` if any token in the template is absent from the
  `values` dict. All three new tokens (`SCRIPT`, `VENV_PYTHON`, `SCRIPT_PATH`) must be
  passed on every `render` call.
- mill-setup SKILL.md is operator-facing documentation — the inline Python snippet shown
  there must stay runnable as a verbatim copy-paste.
- Behavior must not change: same scripts, same flags, same output. Exception: the default
  `millpy-vscode.py` call no longer filters open windows (opt-in via `--filter-open`).
- The `test-shortcut-wrapper.py` assertion `"uv run" in rendered` must be removed or
  inverted. All other idempotency and legacy-cleanup tests remain valid.

## Testing

**`test-shortcut-wrapper.py` — changes required:**
- All `write_all(mill_dir)` calls → `write_all(mill_dir, fake_latest_path)` where
  `fake_latest_path = Path(tmpdir) / "fake-latest"`.
- Remove assertion `"uv run" in rendered`.
- Add assertion: `str(fake_latest_path / ".venv" / "Scripts" / "python.exe") in rendered`.
- Add assertion: `str(fake_latest_path / "scripts" / "millpy-status.py") in rendered`.
- Idempotency tests (same content → no rewrite) still valid; rendered content changes but
  comparison logic is unchanged.
- Legacy `.py` cleanup tests unchanged.

**`test-millpy-vscode.py` — new tests:**
- `--filter-open` not passed: mock `_vscode_processes.find_open_vscode_paths` and assert
  it is never called.
- `--filter-open` passed: assert `find_open_vscode_paths` is called exactly once and
  filtering is applied (existing filtered-worktree behavior tested).
- Existing two-worktree picker tests and `--slug` tests are unaffected.

**Run all unit tests** via `python plugins/mill/unit_tests/run-all.py` after each batch.

## Q&A log

- **Q:** Should the benchmark step be a mandatory plan batch gating later implementation? **A:** [auto-pick] Yes — plan batch 0 is the benchmark; implementer writes `.scratch/benchmark-results.md` before any code change. **Why:** proposal and task description both mandate data-first; ordering in the plan enforces this.
- **Q:** Should Fixes 1 and 3 be merged into a single template change? **A:** [auto-pick] Yes — single new template with `<VENV_PYTHON>` and `<SCRIPT_PATH>` tokens. **Why:** both fixes target the same PS1 block; no value in an intermediate state.
- **Q:** How should `write_all` receive the venv path? **A:** [auto-pick] Required `latest_path: Path` parameter. **Why:** explicit, no hidden env-var dependency, unit tests pass a fake Path.
- **Q:** Should `--filter-open` flip the default in `millpy-vscode.py`? **A:** [auto-pick] Yes — default no-probe, `--filter-open` opts in. **Why:** PowerShell spawn is the dominant overhead; fast path should be the default.
- **Q:** Should lazy import be scoped to `_vscode_processes` only? **A:** [auto-pick] Yes — only `_vscode_processes` in `millpy-vscode.py`. **Why:** `_spawn_core` is on every code path; other scripts' imports are all hot-path.
