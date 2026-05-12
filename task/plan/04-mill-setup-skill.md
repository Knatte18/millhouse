# Batch: mill-setup-skill

```yaml
task: 53 (A) — Speed up PS1 wrappers by invoking venv Python directly
batch: mill-setup-skill
number: 4
cards: 2
verify: null
depends-on: [2]
```

## Batch Scope

This batch updates `mill-setup/SKILL.md` to document two changes: (1) Phase 4.7 now computes `latest_path` and passes it to `_shortcuts.write_all`; (2) a new Phase 4.8 writes a marker-delimited venv activation block to `$PROFILE`, making `uv run --active` work in new shell sessions. Phase 8 verification gains one new check for the `# mill-venv-start` / `# mill-venv-end` block. The batch depends on batch 02 because Phase 4.7's inline Python snippet now calls the new `write_all(mill_dir, latest_path)` signature — the SKILL.md must be consistent with the shipped code. `verify: null` — docs-only batch with no runnable surface.

## Cards

### Card 6: Update Phase 4.7 inline Python to compute latest_path and pass to write_all

- **Context:**
  - `plugins/mill/scripts/_shortcuts.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Locate Phase 4.7 (heading `### Phase 4.7 — PS1 shortcut wrappers`, around line 275).
  - Replace the existing inline Python block:
    ```python
    import _shortcuts
    written = _shortcuts.write_all(Path('.millhouse'))
    print(f'wrote {len(written)} wrappers' if written else 'wrappers up to date')
    ```
    with:
    ```python
    import os
    import _shortcuts
    from pathlib import Path
    cache = Path(os.environ["USERPROFILE"]) / ".claude" / "plugins" / "cache" / "millhouse" / "mill"
    latest_path = max((p for p in cache.iterdir() if p.is_dir()), key=lambda p: p.name)
    written = _shortcuts.write_all(Path('.millhouse'), latest_path)
    print(f'wrote {len(written)} wrappers' if written else 'wrappers up to date')
    ```
    The `from pathlib import Path` import is already present in the surrounding `uv run python -c "..."` context (via the PYTHONPATH prefix), but must be explicit in the inline snippet for copy-paste correctness.
  - Update the Phase 4.7 section heading description if it mentions the old "locates the latest installed millhouse plugin cache" wording — replace with wording consistent with the new approach (hardcoded path at write time). The phrase "do not edit manually — re-run mill-setup" in the wrappers remains accurate.
  - Do NOT modify the `powershell -Command` block that sets the `PYTHONPATH` user env var (same block, lines ~293–300). That block is unchanged.
- **Commit:** `docs(mill-setup): update Phase 4.7 snippet to compute latest_path and pass to write_all`

### Card 7: Add Phase 4.8 ($PROFILE venv activation) and update Phase 8 verification

- **Context:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - **Insert new `### Phase 4.8 — Venv activation in $PROFILE`** immediately after Phase 4.7 and before Phase 4.9. Full phase text:

    ```
    ### Phase 4.8 — Venv activation in $PROFILE

    Writes a marker-delimited venv activation block to PowerShell `$PROFILE` so that
    `uv run --active` works in every new shell session without manual activation.
    Idempotent: re-run replaces the existing block (if any). Creates `$PROFILE` if
    it does not exist.

    ```powershell
    $profilePath = $PROFILE
    $latest = (Get-ChildItem "$HOME\.claude\plugins\cache\millhouse\mill" -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName
    $activateLine = ". `"$latest\.venv\Scripts\Activate.ps1`""
    $startMarker = "# mill-venv-start — managed by mill-setup, do not edit manually"
    $endMarker = "# mill-venv-end"
    $block = "$startMarker`n$activateLine`n$endMarker"

    if (-not (Test-Path $profilePath)) {
        New-Item -ItemType File -Path $profilePath -Force | Out-Null
        Write-Host "[mill-setup] Created $profilePath"
    }
    $content = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
    if ($content -match [regex]::Escape($startMarker)) {
        $content = $content -replace "(?s)$([regex]::Escape($startMarker)).*?$([regex]::Escape($endMarker))", $block
        Set-Content $profilePath $content -NoNewline
        Write-Host "[mill-setup] Updated mill-venv block in $profilePath"
    } else {
        Add-Content $profilePath "`n$block"
        Write-Host "[mill-setup] Added mill-venv block to $profilePath"
    }
    ```
    (triple-backtick fence for the powershell block)

    Log `Updated mill-venv block in <path>` or `Added mill-venv block to <path>` per the script output.

    **Note:** This phase hardcodes the path of the currently-latest cache entry into `$PROFILE`. After running `update-plugins.ps1` to install a new plugin version, re-run `/mill-setup` — Phase 4.8 is idempotent and will update the activation path to the new version.
    ```

  - **Update Phase 8 verification list**: add one bullet after the `PYTHONPATH` check:
    ```
    - `$PROFILE` contains the `# mill-venv-start` / `# mill-venv-end` block (verify via `Select-String -Path $PROFILE -Pattern "mill-venv-start" -Quiet`)
    ```
  - **Update Phase 8 success summary block**: add one line after `PYTHONPATH (User):`:
    ```
      Profile activation: $PROFILE — mill-venv-start block present
    ```
- **Commit:** `docs(mill-setup): add Phase 4.8 ($PROFILE venv activation) and Phase 8 verification`

## Batch Tests

`verify: null` — docs-only batch. The implementer verifies by reading the updated SKILL.md and confirming: (1) Phase 4.7 inline Python references `latest_path` and calls `write_all(Path('.millhouse'), latest_path)`; (2) Phase 4.8 exists between 4.7 and 4.9; (3) Phase 8 bullet list includes `# mill-venv-start` check.
