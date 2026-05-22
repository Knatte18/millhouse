# Batch: mill-setup bootstrap

```yaml
task: Set MILL_PYTHON via mill-setup, use in all skill invocations
batch: mill-setup bootstrap
number: 1
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Modifies `plugins/mill/skills/mill-setup/SKILL.md` in three places: (1) inserts new Phase 4.8 between Phase 4.7 and Phase 4.9, (2) updates the "How to invoke the helpers" section parenthetical on the line mentioning `$MILL_PYTHON`, and (3) updates Phase 8 to add the `MILL_PYTHON` invariant check, add `MILL_PYTHON` to the success summary block, and add an idempotency note. mill-setup keeps the full `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` form throughout — it is the bootstrapper exception. This batch delivers the canonical source of truth for the `MILL_PYTHON` mechanism; all other batches reference this.

## Cards

### Card 1: Add Phase 4.8 and update "How to invoke" parenthetical in mill-setup SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  **Edit A — insert Phase 4.8.**

  Locate the paragraph that begins with `**Note:** After running \`update-plugins.ps1\`` (end of Phase 4.7) followed by a blank line and `### Phase 4.9`. Use Edit to replace the two-blank-line gap between that Note and `### Phase 4.9` with the Phase 4.8 block below. The old_string to match is:

  ```
  **Note:** After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` to refresh PYTHONPATH and the PS1 wrappers to the new version. If upgrading from a pre-PS1 hub (one where `.millhouse/` still contains `.py` wrappers), re-run `/mill-setup` — Phase 4.7 is idempotent and will replace the `.py` wrappers with `.ps1` wrappers in a single pass, and Phase 8 will verify their absence.


  ### Phase 4.9 — Seed `hub_relative_path` in `config.local.yaml`
  ```

  The new_string is the same text with the Phase 4.8 section inserted between:

  ```
  **Note:** After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` to refresh PYTHONPATH and the PS1 wrappers to the new version. If upgrading from a pre-PS1 hub (one where `.millhouse/` still contains `.py` wrappers), re-run `/mill-setup` — Phase 4.7 is idempotent and will replace the `.py` wrappers with `.ps1` wrappers in a single pass, and Phase 8 will verify their absence.


  ### Phase 4.8 — Write `MILL_PYTHON` to `~/.claude/settings.json`

  Sets the `MILL_PYTHON` environment variable in the global Claude Code settings so every other mill skill can reference `"$MILL_PYTHON"` instead of the full venv path. This phase is the bootstrapper exception: mill-setup cannot use `$MILL_PYTHON` in its own commands because the variable is not yet active in the current CC session (CC reads `settings.json` at startup). All other mill skills use `"$MILL_PYTHON"`.

  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
  import json, os
  from pathlib import Path

  mill_python = str(Path(os.environ['CLAUDE_PLUGIN_ROOT']) / '.venv' / 'Scripts' / 'python.exe')
  settings_path = Path.home() / '.claude' / 'settings.json'

  data = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
  env_block = data.setdefault('env', {})
  if env_block.get('MILL_PYTHON') == mill_python:
      print(f'MILL_PYTHON already correct: {mill_python}')
  else:
      env_block['MILL_PYTHON'] = mill_python
      settings_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
      print(f'MILL_PYTHON set: {mill_python}')
  "
  ```

  Log the result. After writing, emit: `MILL_PYTHON set in ~/.claude/settings.json. Takes effect in the next CC session -- existing sessions must restart to pick it up.`


  ### Phase 4.9 — Seed `hub_relative_path` in `config.local.yaml`
  ```

  **Edit B — update "How to invoke the helpers" parenthetical.**

  In the `## How to invoke the helpers` section, locate the sentence that reads:

  ```
  This direct-binary form is used by every mill SKILL.md (mill-go uses an equivalent form with `$MILL_PYTHON`, an alias defined in its Step 0 block). The source-tree form (`uv run --project plugins/mill ...`) remains the documented exception for cases where the cache path is unavailable — for example, running unit tests from the millhouse repo itself.
  ```

  Replace it with:

  ```
  This direct-binary form is used by mill-setup only (bootstrapper exception — Phase 4.8 writes `MILL_PYTHON` to `~/.claude/settings.json`; all other mill skills use `"$MILL_PYTHON"`). The source-tree form (`uv run --project plugins/mill ...`) remains the documented exception for cases where the cache path is unavailable — for example, running unit tests from the millhouse repo itself.
  ```

  **Edit C — update `# RIGHT` comment in the same code block.**

  In the `## How to invoke the helpers` section, within the fenced bash block, locate the comment line:

  ```
  # RIGHT — invokes from cache (the canonical mill-script form, shared with every other mill SKILL.md)
  ```

  Replace it with:

  ```
  # RIGHT — invokes from cache (mill-setup bootstrapper exception; all other skills use "$MILL_PYTHON")
  ```

- **Commit:** `docs(mill-setup): add Phase 4.8 MILL_PYTHON write + update invoke-helpers note`

### Card 2: Update Phase 8 verification and idempotency in mill-setup SKILL.md

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**

  **Edit A — add MILL_PYTHON invariant to Phase 8 checklist.**

  In `### Phase 8 — Verify + report`, locate the bullet:

  ```
  - `PYTHONPATH` user env var contains `<CLAUDE_PLUGIN_ROOT>/scripts` (verify via `[System.Environment]::GetEnvironmentVariable('PYTHONPATH', 'User')`)
  ```

  Replace it with (adding the new bullet immediately after):

  ```
  - `PYTHONPATH` user env var contains `<CLAUDE_PLUGIN_ROOT>/scripts` (verify via `[System.Environment]::GetEnvironmentVariable('PYTHONPATH', 'User')`)
  - `.env.MILL_PYTHON` in `~/.claude/settings.json` equals `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` (runtime-expanded value); verify via: `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "import json; from pathlib import Path; d=json.loads((Path.home()/'.claude'/'settings.json').read_text(encoding='utf-8')); print(d['env']['MILL_PYTHON'])"`
  ```

  **Edit B — add MILL_PYTHON to Phase 8 success summary block.**

  In the success summary block in Phase 8, locate:

  ```
    Shortcut wrappers: N PS1 scripts under .millhouse/
    PYTHONPATH (User): <scripts>
  ```

  Replace with:

  ```
    Shortcut wrappers: N PS1 scripts under .millhouse/
    PYTHONPATH (User): <scripts>
    MILL_PYTHON:       <python-path>
  ```

  **Edit C — add Phase 4.8 idempotency note.**

  In the `## Idempotency` section, locate the bullet:

  ```
  - PYTHONPATH user env var re-set to the current latest plugin version on every run.
  ```

  Replace with (adding new bullet after):

  ```
  - PYTHONPATH user env var re-set to the current latest plugin version on every run.
  - Phase 4.8 is idempotent: compares existing `.env.MILL_PYTHON` against computed value; writes only if they differ.
  ```

- **Commit:** `docs(mill-setup): add MILL_PYTHON to Phase 8 verification and idempotency`

## Batch Tests

Documentation-only batch; `verify: null`. After implementing, manually confirm:
1. Phase 4.8 heading appears in `plugins/mill/skills/mill-setup/SKILL.md` between Phase 4.7 and Phase 4.9.
2. The "How to invoke the helpers" sentence no longer attributes `$MILL_PYTHON` to mill-go's Step 0 block.
3. Phase 8 checklist contains a bullet referencing `.env.MILL_PYTHON` in `~/.claude/settings.json`.
4. The Phase 8 summary block shows `MILL_PYTHON: <python-path>`.
5. Idempotency section has the Phase 4.8 note.
