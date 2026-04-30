# Batch: tests-and-docs

```yaml
task: 18 — par-E — Migrate Python invocation to `uv run`
batch: tests-and-docs
cards: 4
verify: uv run --project plugins/mill plugins/mill/unit_tests/run-all.py
depends-on: [foundation, path-fix, mill-setup-skill, skills-sweep]
```

## Batch Scope

Final polish: migrate the integration-test infrastructure to `uv run`, generate the auto-derived `SCRIPTS.md` reference doc, and document the new convention in `CLAUDE.md`. Test changes split into two cards (PS1 test-bootstrap vs Python integration tests) because the transformations differ. SCRIPTS.md and CLAUDE.md each get their own card. This batch depends on every previous batch because: (a) tests need `pyproject.toml` from foundation; (b) test-bootstrap.ps1 covers code that batches 01–04 modify; (c) SCRIPTS.md is generated from `--help` output of scripts modified in batch 02; (d) CLAUDE.md should reflect the final completed state. `verify:` runs the unit-test suite via `uv run` — the canonical end-of-task smoke test.

## Cards

### Card 19: Migrate `test-bootstrap.ps1` to uv run

- **Reads:**
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
  - `plugins/mill/pyproject.toml`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/integration_tests/test-bootstrap.ps1`
- **Creates:** none
- **Requirements:** (1) Delete the line `$env:PYTHONPATH = $scripts` (line ~33) — global env var covers it. (2) Add `$millRoot = Split-Path -Parent $scripts` near the top of the test (immediately after `$scripts = Join-Path $millRoot 'scripts'` is computed — wait, that's circular; the actual existing line is `$scripts = Join-Path $millRoot 'scripts'` where `$millRoot` is `Split-Path -Parent $PSScriptRoot`'s output. The test already has `$millRoot` defined at line ~19. Reuse it.) (3) Replace every `python "$scripts/millpy-X.py" …` invocation with `uv run --project $millRoot "$scripts/millpy-X.py" …` — preserve PowerShell quoting and argument flags exactly. There are several call sites (lines ~119, ~127, ~181, ~203). (4) Replace `python -c "from pathlib import Path; import _junction; …"` calls (lines ~97, ~103, ~221) with `uv run --project $millRoot python -c "..."` — these don't need explicit PYTHONPATH because the global env var (set by mill-setup) covers them when the test runs in a normal CC session. (5) Smoke-check: `pwsh plugins/mill/integration_tests/test-bootstrap.ps1` exits with PASS.
- **Commit:** `test(bootstrap): migrate test-bootstrap.ps1 to uv run`

### Card 20: Migrate Python integration tests to uv run

- **Reads:**
  - `plugins/mill/integration_tests/test-review-code.py`
  - `plugins/mill/integration_tests/test-review-discussion.py`
  - `plugins/mill/integration_tests/test-review-plan.py`
  - `plugins/mill/integration_tests/test-spawn.py`
  - `plugins/mill/integration_tests/test-cleanup.py`
  - `plugins/mill/integration_tests/test-abandon.py`
  - `plugins/mill/integration_tests/test-status.py`
  - `plugins/mill/integration_tests/test-inspect.py`
  - `plugins/mill/integration_tests/test-worktree-sibling-resolution.py`
  - `plugins/mill/integration_tests/test-go-assets.py`
  - `plugins/mill/integration_tests/test-plan-assets.py`
  - `plugins/mill/integration_tests/test-merge.py`
  - `plugins/mill/pyproject.toml`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/integration_tests/test-review-code.py`
  - `plugins/mill/integration_tests/test-review-discussion.py`
  - `plugins/mill/integration_tests/test-review-plan.py`
  - `plugins/mill/integration_tests/test-spawn.py`
  - `plugins/mill/integration_tests/test-cleanup.py`
  - `plugins/mill/integration_tests/test-abandon.py`
  - `plugins/mill/integration_tests/test-status.py`
  - `plugins/mill/integration_tests/test-inspect.py`
  - `plugins/mill/integration_tests/test-worktree-sibling-resolution.py`
  - `plugins/mill/integration_tests/test-go-assets.py`
  - `plugins/mill/integration_tests/test-plan-assets.py`
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Requirements:** Two transformation patterns apply. (1) **All 12 files**: add a constant `PLUGIN_ROOT = HUB / "plugins" / "mill"` immediately after the existing `SCRIPTS = HUB / "plugins" / "mill" / "scripts"` constant (top-of-file region). Replace every subprocess invocation `[sys.executable, str(SCRIPTS / "millpy-X.py"), …]` with `["uv", "run", "--project", str(PLUGIN_ROOT), str(SCRIPTS / "millpy-X.py"), …]`. (2) **Review tests only** (`test-review-code.py`, `test-review-discussion.py`, `test-review-plan.py`): in addition to (1), remove ONLY the line `env["PYTHONPATH"] = str(SCRIPTS)` (or equivalent direct dict mutation) from the subprocess setup. **Keep `env["PYTHONIOENCODING"] = "utf-8"` intact** — it ensures UTF-8 output on Windows consoles and is unrelated to the migration. Keep the `env=` kwarg passed to `subprocess.run` since `PYTHONIOENCODING` still needs to flow through. (3) Verify each test by running `uv run --project plugins/mill plugins/mill/integration_tests/<test>.py` — each must pass on its own. Several tests require network or specific external state (test-review-* require claude CLI access); skip those if the local env doesn't allow, and document which were verified.
- **Commit:** `test(integration): migrate Python integration tests to uv run`

### Card 21: Generate `plugins/mill/SCRIPTS.md`

- **Reads:**
  - `plugins/mill/scripts/millpy-abandon.py`
  - `plugins/mill/scripts/millpy-add.py`
  - `plugins/mill/scripts/millpy-claim.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/millpy-color.py`
  - `plugins/mill/scripts/millpy-fetch-issues.py`
  - `plugins/mill/scripts/millpy-inspect.py`
  - `plugins/mill/scripts/millpy-list.py`
  - `plugins/mill/scripts/millpy-migrate-layout.py`
  - `plugins/mill/scripts/millpy-review-code.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-review-plan.py`
  - `plugins/mill/scripts/millpy-skills-index.py`
  - `plugins/mill/scripts/millpy-spawn.py`
  - `plugins/mill/scripts/millpy-status.py`
  - `plugins/mill/scripts/millpy-terminal.py`
  - `plugins/mill/scripts/millpy-validate-plan.py`
  - `plugins/mill/scripts/millpy-vscode.py`
  - `plugins/mill/scripts/millpy-worktree.py`
  - `plugins/mill/pyproject.toml`
- **Modifies:** none
- **Creates:**
  - `plugins/mill/SCRIPTS.md`
- **Requirements:** Generate a Markdown reference doc at `plugins/mill/SCRIPTS.md` that lists every `millpy-*.py` script with its `--help` output. Format:
  ```
  # mill scripts reference
  Auto-generated from `--help` output. Re-generate when CLI signatures change.
  ## millpy-abandon
  ```
  <output of `uv run --project plugins/mill plugins/mill/scripts/millpy-abandon.py --help`>
  ```
  ## millpy-add
  ```
  ...
  ```
  Sort sections alphabetically by script name. Generate by running `uv run --project plugins/mill plugins/mill/scripts/<script>.py --help` for each script in `plugins/mill/scripts/millpy-*.py` and capturing stdout. The implementer can use a one-shot Python or shell script to drive the generation; do not commit the generation script (this is a manual-refresh artefact, not auto-generated on commit). Include a leading paragraph explaining the file is generated and how to refresh it. Do NOT include scripts that error out on `--help` (if any) — note them in a final "Generation notes" section. Verify: `plugins/mill/SCRIPTS.md` exists and contains exactly one `## ` section per `millpy-*.py` script.
- **Commit:** `docs(mill): add SCRIPTS.md auto-generated CLI reference`

### Card 22: Update `CLAUDE.md` with uv-run convention

- **Reads:**
  - `CLAUDE.md`
  - `discussion.md`
- **Modifies:**
  - `CLAUDE.md`
- **Creates:** none
- **Requirements:** Add a new bullet under the "Conventions worth carrying" section in `CLAUDE.md` (worktree root, the project-level CLAUDE.md). Bullet text:
  > **Mill scripts are invoked via `uv run`, not `python`.** All SKILL.md examples use `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py" [args]`; inline helpers use `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`. PYTHONPATH is set globally as a Windows user environment variable by `mill-setup` Phase 4.7; CC inherits it automatically — no per-session export needed. Exception: `mill-setup` itself is the bootstrapper and uses an inline `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix on each call.
  Place the bullet after the existing `${CLAUDE_PLUGIN_ROOT}` bullet (which already discusses intra-plugin paths) — they are conceptually related.
- **Commit:** `docs(CLAUDE.md): document uv run convention and PYTHONPATH bootstrap`

## Batch Tests

`verify:` runs `uv run --project plugins/mill plugins/mill/unit_tests/run-all.py` — the canonical end-of-task smoke test. This passes if every existing unit test passes when invoked through uv (which it should, since uv is a transparent runner for Python). Test-bootstrap.ps1 is verified per-card by `pwsh plugins/mill/integration_tests/test-bootstrap.ps1` exiting PASS. Python integration tests are verified per-card by running each via `uv run` (some require external state and are documented as such). SCRIPTS.md is verified by visual inspection (one section per script). CLAUDE.md is verified by visual inspection (new bullet present, placement correct).
