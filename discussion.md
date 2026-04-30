# Discussion: 18 — par-E — Migrate Python invocation to `uv run`

```yaml
task: 18 — par-E — Migrate Python invocation to `uv run`
slug: migrate-to-uv
status: discussing
parent: main
```

## Problem

Python startup on Windows is 100–200 ms per invocation. `uv` (Rust-written Python runner from astral-sh) starts in ~10 ms — a 10–20× improvement that will matter as mill moves toward a subprocess-heavy CLI architecture (50+ subprocess calls per task → 7.5 s vs 0.5 s startup overhead).

Secondary gain: `uv` manages the venv and dependencies via `pyproject.toml`, eliminating the PYTHONPATH setup friction that has caused recurring PowerShell-vs-Bash errors across multiple sessions (issue #35).

A third deliverable is folded in: SKILL.md helper call shapes are out of sync with actual Python signatures (issue #70), causing TypeErrors in live mill-go runs. The uv migration touches every SKILL.md, making this the cheapest possible moment to audit and fix those shapes.

## Scope

**In:**
- `plugins/mill/pyproject.toml` — new; declares Python version and runtime dependencies (PyYAML).
- `plugins/mill/templates/shortcut-wrapper.ps1` — new PS1 template replacing the existing `.py` template.
- `plugins/mill/scripts/_shortcuts.py` — updated to write `.ps1` wrappers; delete old `.py` wrappers.
- mill-setup SKILL.md — Phase 1 adds `uv` presence check; Phase 4.7 updated (PS1 wrappers + PYTHONPATH Windows user env var); all `python -c` snippets → `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c`.
- All other SKILL.md files — update every `python … millpy-X.py` invocation to `uv run --project "${CLAUDE_PLUGIN_ROOT}" …`; `PYTHONPATH=… python -c` → `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c`; ensure all skills consistently use `${CLAUDE_PLUGIN_ROOT}/scripts/` (not repo-relative `plugins/mill/scripts/`).
- SKILL.md API call-shape audit (issue #70) — fix all helper-call examples that are wrong against real function signatures.
- `plugins/mill/integration_tests/test-bootstrap.ps1` — update to `uv run`.
- Python integration tests (`test-spawn.py` etc.) — update subprocess invocations to `uv run`; remove explicit PYTHONPATH overrides.
- `plugins/mill/SCRIPTS.md` — new; auto-generated from `--help` output of all `millpy-*.py` scripts.
- `CLAUDE.md` — add convention: "Mill scripts are invoked via `uv run`, not `python`."

**Out:**
- Refactoring helper modules into a proper installable Python package (eliminates PYTHONPATH, but is a big restructure — deferred).
- CMD wrappers — PS1 only.
- `update-plugins.ps1` — no changes; it re-installs the plugin but does not update wrappers or PYTHONPATH (operator re-runs mill-setup after a plugin update).
- `plugins/mill/unit_tests/run-all.py` — no changes; it uses `sys.executable` to invoke tests, which is correct when run under `uv run`.
- Any changes to the Python scripts themselves — migration is invocation-only.

## Decisions

### wrapper-format

- Decision: PS1 only (`.ps1`), not `.py` or `.cmd`.
- Rationale: Windows 11 / PowerShell 5; the machine shell is PowerShell. CMD is legacy and less expressive. Python wrappers (`runpy`) add a Python-invokes-Python indirection that PS1 eliminates.
- Rejected: CMD (.cmd) — limited syntax; Python (.py) — defeats the purpose of eliminating Python startup cost for the wrapper itself.

### wrappers-are-human-only

- Decision: `.millhouse/millpy-X.ps1` wrappers are NEVER invoked by Claude Code. CC always references `${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py` directly via the installed plugin.
- Rationale: CC resolves `${CLAUDE_PLUGIN_ROOT}` to the real installed plugin path at skill load time. The `.millhouse/` directory is an operator convenience (human terminal use). This separation is already enforced for the existing `.py` wrappers and must be preserved.
- Rejected: Having CC use the wrapper — would add an indirection layer and make CC dependent on the local `.millhouse/` state.

### pyproject-location

- Decision: `plugins/mill/pyproject.toml` (plugin root level, above `scripts/`).
- Rationale: Covers scripts, unit_tests, and integration_tests under one project. `uv run --project plugins/mill` (or `--project "${CLAUDE_PLUGIN_ROOT}"`) resolves from this file. Matches the plugin cache layout: `$HOME/.claude/plugins/cache/millhouse/mill/<version>/pyproject.toml`.
- Rejected: `plugins/mill/scripts/pyproject.toml` — would exclude tests from the managed venv.

### pythonpath-mechanism

- Decision: Permanent Windows user environment variable set by mill-setup Phase 4.7 (and re-set when mill-setup is re-run). Value: the `scripts/` dir of the current latest semver version in the plugin cache.
- Rationale: All processes including CC inherit it automatically; no per-call setup; no session-start manual step. `uv run` passes inherited env vars through to the Python subprocess, so `import _active` works without any extra plumbing.
- Rejected: (A) Session-start `export PYTHONPATH=…` — requires manual step per CC session. (B) `.env` file in plugin root — PYTHONPATH with relative paths is unreliable across working directories. (C) Proper package install — large refactor, out of scope.
- Edge case: After `update-plugins.ps1` installs a new plugin version, PYTHONPATH still points to the old version's scripts. Operator must re-run mill-setup to update PYTHONPATH. Document this in the output of `update-plugins.ps1` and in mill-setup Phase 4.7 success message.

### cc-call-shape

- Decision: SKILL.md "Run it" blocks and all inline invocations change to `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"`. Inline `python -c` becomes `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "…"`.
- Rationale: Consistent, explicit, no per-session setup needed (PYTHONPATH is global), and CC never needs to know about `.millhouse/`.
- Rejected: Using `.millhouse/` PS1 wrappers from CC — violates the wrapper-is-human-only decision.

### ps1-wrapper-design

- Decision: PS1 wrapper finds the latest installed plugin version at runtime via semver-sort on `$HOME\.claude\plugins\cache\millhouse\mill`, then calls `uv run --project $pluginRoot "$pluginRoot\scripts\<SCRIPT>.py" @args`. No need to set PYTHONPATH in the wrapper — it's a global Windows env var.
- Rationale: Semver-sort means the wrapper automatically picks up new versions without regeneration. Static version hardcode would require `update-plugins.ps1` to regenerate wrappers, which contradicts the decision that `update-plugins.ps1` does not touch wrappers.
- Rejected: Hardcoded version path — would go stale after every plugin update.

### scripts-md

- Decision: Generate `plugins/mill/SCRIPTS.md` from `--help` output of all `millpy-*.py` scripts as part of this task. Maintained manually (update when script signatures change).
- Rationale: Folded from the proposal; eliminates the need to read source to discover CLI signatures. Small effort during the uv sweep.
- Rejected: Deferring — the sweep already touches all scripts, making this the cheapest moment.

### api-audit

- Decision: Audit and fix all helper call shapes in SKILL.md files against real Python signatures. Known errors are the starting list; implementation agent must grep for others.
- Rationale: Issue #70 documents TypeErrors in live runs; this task already touches every SKILL.md file. Not fixing now means another full-sweep task later.
- Rejected: Deferring — unjustifiable cost given that all SKILL.md files are already open.

## Technical context

### Codebase layout

```
plugins/mill/
  pyproject.toml          ← NEW (this task)
  SCRIPTS.md              ← NEW (this task)
  scripts/
    millpy-*.py           ← 19 user-callable CLI scripts
    _*.py                 ← 36 helper modules (flat, no __init__.py)
  templates/
    shortcut-wrapper.py   ← REPLACED by shortcut-wrapper.ps1
    shortcut-wrapper.ps1  ← NEW (this task)
  skills/*/SKILL.md       ← ALL updated (this task)
  unit_tests/
    run-all.py            ← no changes needed
    test-*.py             ← no changes needed (add scripts to sys.path themselves)
  integration_tests/
    test-bootstrap.ps1    ← updated (this task)
    test-*.py             ← updated (this task)
```

### Shortcut wrapper generation

`_shortcuts.py::write_all(mill_dir: Path) -> list[Path]` renders a template for each script in `SHORTCUT_SCRIPTS` and writes to `mill_dir/<script>.{py→ps1}`. The template path is `_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "shortcut-wrapper.py"` — this must update to `.ps1`.

New behavior: after writing PS1 wrappers, delete any `.py` wrappers in `mill_dir` whose names match `SHORTCUT_SCRIPTS` entries (idempotent cleanup).

### mill-setup Phase 4.7 — new responsibilities

In addition to calling `_shortcuts.write_all()`, Phase 4.7 must:
1. Find the latest installed mill plugin version:
   ```powershell
   $cache = "$env:USERPROFILE\.claude\plugins\cache\millhouse\mill"
   $latest = (Get-ChildItem $cache -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
   $scripts = Join-Path $latest "scripts"
   ```
2. Set the PYTHONPATH Windows user env var:
   ```powershell
   [System.Environment]::SetEnvironmentVariable("PYTHONPATH", $scripts, "User")
   ```
3. Log: `Set PYTHONPATH (User) = <scripts>. Re-run mill-setup after updating the plugin to refresh.`

This must be expressed as a Bash command (CC's shell) that invokes PowerShell:
```bash
powershell -Command "[System.Environment]::SetEnvironmentVariable('PYTHONPATH', '$scripts_path', 'User')"
```

Alternatively, mill-setup Phase 4.7 can instruct the operator to run the PowerShell command manually — the skill is a CC session, and setting a Windows env var from a CC Bash session requires `powershell -Command`.

### pyproject.toml contents

```toml
[project]
name = "mill"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["pyyaml>=6.0"]

[tool.pytest.ini_options]
pythonpath = ["scripts"]
```

The `pythonpath` setting under pytest lets unit/integration tests that use pytest discover `_*.py` helpers without PYTHONPATH being set in the test process. The runtime scripts still need the global PYTHONPATH env var.

### Known API shape errors (issue #70 starting list)

The implementation agent must search every SKILL.md for these patterns and correct them:

| Wrong | Correct | Where found |
|---|---|---|
| `python -m millpy.entrypoints.regenerate_sidebar` | `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "from pathlib import Path; import _sidebar; _sidebar.regenerate(Path(r'<wiki-dir>').resolve())"` | mill-resume SKILL.md line 147 |
| `_config.load(mill_dir)` | `_config.load_config(wiki_path, git_root)` | Reported in #70; grep SKILL.md to confirm location |
| `_wiki.write_commit_push(wiki_path, msg)` (2-arg) | `_wiki.write_commit_push(wiki_path, relative_paths, commit_msg)` (3-arg) | Reported in #70; grep SKILL.md |
| `$env:PYTHONPATH = …; python plugins/mill/scripts/millpy-X.py` | `uv run --project plugins/mill plugins/mill/scripts/millpy-X.py` | mill-add SKILL.md |
| `python plugins/mill/scripts/millpy-X.py` (repo-relative path in a skill) | `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"` | mill-go, mill-plan, mill-start, mill-skills-index, mill-skills-from-scripts |

### PS1 template shape

```powershell
# Wrapper for <SCRIPT> — generated by mill-setup Phase 4.7. Do not edit manually — re-run mill-setup.
$cache = "$HOME\.claude\plugins\cache\millhouse\mill"
$latest = (Get-ChildItem $cache -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
if (-not $latest) { Write-Error "[mill] plugin cache not found at $cache"; exit 1 }
uv run --project $latest "$latest\scripts\<SCRIPT>.py" @args
```

No `$env:PYTHONPATH` line — the global Windows env var is already in scope.

### Integration tests

**test-bootstrap.ps1**: Remove `$env:PYTHONPATH = $scripts`. Change `python "$scripts/millpy-X.py"` → `uv run --project $millRoot "$scripts\millpy-X.py"` where `$millRoot = Split-Path -Parent $scripts` (= `plugins/mill/`). The test sets `$scripts = Join-Path $millRoot 'scripts'` already.

**Python integration tests (test-spawn.py, test-cleanup.py, etc.)**: Currently call `subprocess.run([sys.executable, str(SCRIPTS / "millpy-X.py")], env={**os.environ, "PYTHONPATH": str(SCRIPTS)})`. Change to `subprocess.run(["uv", "run", "--project", str(PLUGIN_ROOT), str(SCRIPTS / "millpy-X.py")])`. `PLUGIN_ROOT = HUB / "plugins" / "mill"` (or equivalent derivation from SCRIPTS). Remove explicit PYTHONPATH from env override — global env var covers it.

### SCRIPTS.md generation

Loop all `millpy-*.py` scripts, run `uv run --project plugins/mill plugins/mill/scripts/<script>.py --help`, capture output, format into a Markdown table or fenced-code sections. Write to `plugins/mill/SCRIPTS.md`. Commit with the rest of the changes.

## Constraints

- **No Python script changes** — uv is a transparent runner; zero changes to `.py` files except test infrastructure.
- **`${CLAUDE_PLUGIN_ROOT}` in all intra-plugin paths** — no `plugins/mill/…` hardcodes in SKILL.md (CLAUDE.md constraint).
- **Wrappers are never used by CC** (CLAUDE.md + this task's decision).
- **`uv` must be present** — mill-setup Phase 1 must verify `uv --version` succeeds before proceeding. Install instruction: `irm https://astral.sh/uv/install.ps1 | iex`.

## Testing

**Smoke test (every script):** `uv run --project plugins/mill plugins/mill/scripts/<script>.py --help` must exit 0. The implementation agent runs this for all 19 scripts after creating `pyproject.toml`.

**Shortcut wrapper smoke:** Verify `.millhouse/millpy-spawn.ps1` is generated and that invoking it from a PowerShell terminal returns the script's help output.

**PYTHONPATH env var:** Verify `[System.Environment]::GetEnvironmentVariable("PYTHONPATH", "User")` returns the scripts path after mill-setup Phase 4.7 runs.

**Integration tests:** `pwsh plugins/mill/integration_tests/test-bootstrap.ps1` must PASS. Each Python integration test must PASS via `uv run --project plugins/mill plugins/mill/integration_tests/test-X.py`.

**Unit tests:** `uv run --project plugins/mill plugins/mill/unit_tests/run-all.py` must print `PASS — all N unit tests`.

**API shape audit:** After SKILL.md fixes, the implementation agent must grep for the known-wrong patterns and confirm none remain.

## Q&A log

- **Q:** PS1 or CMD wrappers? **A:** PS1 only.
- **Q:** pyproject.toml in `plugins/mill/` or `plugins/mill/scripts/`? **A:** `plugins/mill/` — covers scripts + tests.
- **Q:** PYTHONPATH still needed? **A:** Yes; flat module imports require it. Globally set as Windows user env var by mill-setup — no per-call setup.
- **Q:** Does CC use `.millhouse/` wrappers? **A:** Never. CC always references `${CLAUDE_PLUGIN_ROOT}/scripts/` directly. Wrappers are human-terminal convenience only.
- **Q:** Does `update-plugins.ps1` regenerate wrappers or update PYTHONPATH? **A:** No. It only re-installs the plugin. Operator re-runs mill-setup after plugin updates to refresh PYTHONPATH and wrappers.
- **Q:** Semver-sort or hardcoded version in PS1 wrapper? **A:** Semver-sort at runtime — wrapper auto-picks latest version without regeneration.
- **Q:** SCRIPTS.md in scope? **A:** Yes.
- **Q:** SKILL.md API audit in scope? **A:** Yes.
