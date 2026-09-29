# Batch: update-plugins

```yaml
task: Migrate mill's generic skills to the shared scribe plugin
batch: update-plugins
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-load-directive-convention.py && bash -n update-plugins.sh
depends-on: [2]
```

## Batch Scope

Makes the operator's existing post-merge step, `./update-plugins.sh` / `update-plugins.ps1`, bring an installed `scribe@scribe` up to the version mill declares, and point out `<name>@millhouse` installs that no longer exist in `marketplace.json` (the removed `python`, `csharp`, `golang` plugins).
`CLAUDE.md` records the new behaviour and the qualified build-skill names.
One batch: the two scripts are twins that must match in behaviour, and `CLAUDE.md` documents them.
It reads the dependency batch 1 wrote into `plugins/mill/.claude-plugin/plugin.json`.
Batch-local decision: the scripts print hints and warnings only; they never uninstall a plugin, and a failing `claude` command never aborts the sync.

## Cards

### Card 12: update-plugins.sh refreshes scribe and lists orphaned installs

- **Context:**
  - `plugins/mill/.claude-plugin/plugin.json`
  - `.claude-plugin/marketplace.json`
- **Edits:**
  - `update-plugins.sh`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Keep the script's style: `set -euo pipefail`, JSON handled by inline `python3 -c` blocks, ASCII-only output.
  Define `INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"` and `MILL_MANIFEST="$SCRIPT_DIR/plugins/mill/.claude-plugin/plugin.json"` next to `MANIFEST_PATH`.
  Update the header comment to mention the scribe refresh and the orphan hint in one sentence each.

  **Scribe step, before the sync loop.**
  1. If `INSTALLED_JSON` exists and its top-level `plugins` object has the key `scribe@scribe`: run `claude plugin marketplace update scribe`, then `claude plugin update scribe@scribe`.
     Wrap each as `if ! <cmd>; then echo "WARNING: '<cmd>' failed -- continuing"; fi` so a failure (including `claude` missing from PATH) never aborts the script.
  2. Then, in one inline `python3 -c` block: re-read `INSTALLED_JSON`; take the lowest `version` across the `scribe@scribe` records (each key maps to a list of per-scope records; compare as integer tuples);
     read the minimum from `MILL_MANIFEST`'s `dependencies` entry for scribe — an object with `name == "scribe"` and `marketplace == "scribe"`, or the bare string `"scribe@scribe"`;
     strip a leading `^`, `~`, `>=` or `=` from its `version` and parse the rest as a dotted integer tuple.
     Skip the comparison when the entry has no `version` (bare string form) or no dependency entry exists.
     Below the minimum, print `WARNING: scribe@scribe is <v>, mill needs <min> -- run 'claude plugin marketplace update scribe' and 'claude plugin update scribe@scribe'.`
  3. If `scribe@scribe` is not installed (file missing or key absent), print `scribe@scribe is not installed -- mill fails to load without it. Add and install it: '/plugin marketplace add Knatte18/scribe', then '/plugin install scribe@scribe'.` and continue.

  **Orphan step, after the sync loop and before the `MILL_PYTHON` update.**
  In one inline `python3 -c` block: if `INSTALLED_JSON` exists, for each key `<name>@<marketplace>` in its `plugins` object whose marketplace equals `$MARKETPLACE` and whose name is not among `marketplace.json`'s plugin names, print `Orphaned: <name>@<marketplace> is no longer in this marketplace -- run 'claude plugin uninstall <name>@<marketplace>'.`
  Print only.

  **Verification — never run the script against the real `HOME`** (it would rsync this worktree's unmerged `plugins/` into the live cache that sibling sessions read).
  - `bash -n update-plugins.sh` exits 0.
  - Stub `claude`: create `.scratch/update-plugins-bin/claude` containing `#!/usr/bin/env bash` and `exit 1`, `chmod +x` it, and prefix every run below with `PATH="$PWD/.scratch/update-plugins-bin:$PATH"` so no real `claude` runs under a fixture `HOME`.
  - Fixture 1: `.scratch/update-plugins-home-1/.claude/plugins/installed_plugins.json` = `{"version": 2, "plugins": {"python@millhouse": [{"scope": "user", "version": "1.0.0"}]}}`, no `cache/` directory.
    `HOME="$PWD/.scratch/update-plugins-home-1" ./update-plugins.sh` must print the scribe not-installed line, "Skipped (not installed)" for every millhouse plugin, and the `Orphaned: python@millhouse` line.
  - Fixture 2: same layout under `.scratch/update-plugins-home-2` with `plugins` = `{"scribe@scribe": [{"scope": "user", "version": "1.0.0"}]}`.
    The run must print both refresh `WARNING:` lines (from the stub) followed by `WARNING: scribe@scribe is 1.0.0, mill needs 1.1.0 ...`.
  - Report both runs' output.
- **Commit:** `feat: update-plugins.sh refreshes scribe and lists orphaned millhouse installs`

### Card 13: update-plugins.ps1 mirrors the scribe refresh and orphan hint

- **Context:**
  - `update-plugins.sh`
  - `plugins/mill/.claude-plugin/plugin.json`
- **Edits:**
  - `update-plugins.ps1`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Reimplement card 12's two steps natively in PowerShell, matching the `.sh` in behaviour, order and message text, and this script's existing style (`ConvertFrom-Json`, `Write-Host`, no Python):
  - `$installedPath = Join-Path $env:USERPROFILE ".claude\plugins\installed_plugins.json"`, `$millManifestPath = Join-Path $PSScriptRoot "plugins\mill\.claude-plugin\plugin.json"`.
  - Scribe step before the `foreach` sync loop: key lookup on `$installed.plugins.PSObject.Properties.Name`;
    run `claude plugin marketplace update scribe` and `claude plugin update scribe@scribe`, each inside `try { ... } catch { ... }` plus a `$LASTEXITCODE -ne 0` check, printing the same `WARNING:` line on either failure;
    lowest installed version via `[version]` over the per-scope records;
    minimum from the mill manifest's scribe dependency with the leading `^`, `~`, `>=` or `=` stripped, compared as `[version]`;
    same skip rules and same below-minimum and not-installed messages as the `.sh`.
  - Orphan step after the sync loop and before the environment-variable block: same selection and message as the `.sh`.
  - Update the header comment the same way as the `.sh`.
  - Verification: when `pwsh` is on PATH, `pwsh -NoProfile -Command "[scriptblock]::Create((Get-Content -Raw update-plugins.ps1)) | Out-Null"` exits 0;
    otherwise say so in the report.
    Then compare the two scripts side by side and confirm the order of steps and every printed message match.
- **Commit:** `feat: update-plugins.ps1 refreshes scribe and lists orphaned millhouse installs`

### Card 14: CLAUDE.md names the scribe build skills and the scribe refresh

- **Context:**
  - `update-plugins.sh`
- **Edits:**
  - `CLAUDE.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Hard-constraints bullet "A `main`-merged plugin fix isn't live ...": after the sentence ending "is the existing mechanism to force that refresh.", add "It also refreshes `scribe@scribe`, mill's declared dependency, before syncing, and lists `<name>@millhouse` installs no longer in `marketplace.json` with the uninstall command."
  - Conventions: "(when `csharp-build` isn't loaded)" -> "(when `scribe:csharp-build` isn't loaded)";
    "(when a project-specific `python-build` override isn't in place)" -> "(when a project-specific `scribe:python-build` override isn't in place)".
  - Semantic line breaks for the added sentence; leave the surrounding lines' wrapping alone.
- **Commit:** `docs: CLAUDE.md names scribe build skills and the scribe refresh`

## Batch Tests

`verify:` re-runs `test-load-directive-convention.py`, whose forbidden-name scan covers `CLAUDE.md` (card 14), and `bash -n update-plugins.sh` (card 12).
The `update-plugins` scripts have no unit test: they shell out to `claude` and rsync into the real cache.
Cards 12 and 13 verify them with the stubbed-`claude` fixture runs and the PowerShell parse check described in their Requirements.
