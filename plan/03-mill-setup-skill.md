# Batch: mill-setup-skill

```yaml
task: 18 — par-E — Migrate Python invocation to `uv run`
batch: mill-setup-skill
cards: 1
verify: null
depends-on: [foundation]
```

## Batch Scope

Overhaul the mill-setup SKILL.md so it: (a) verifies `uv` is installed before doing anything; (b) drives Phase 4.7 to write PS1 wrappers (using the foundation batch's `_shortcuts.py` changes) AND set the global `PYTHONPATH` Windows user environment variable; (c) uses the bootstrap inline-prefix pattern (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`) for ALL its `python -c` snippets, because mill-setup is the bootstrapper that creates the global env var and so cannot rely on it within its own session. mill-setup is the *only* skill that uses inline PYTHONPATH; every other skill (batch 04) relies on the global env var. This batch is a single coherent SKILL.md rewrite — one card. `verify: null` because mill-setup is a skill (CC session), not a runnable test target; correctness is verified manually by the operator running `/mill-setup` in a fresh hub clone after the task merges.

## Cards

### Card 7: Overhaul `mill-setup/SKILL.md`

- **Reads:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
  - `plugins/mill/scripts/_shortcuts.py`
  - `discussion.md`
  - `plan/00-overview.md`
- **Modifies:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Requirements:**
  1. **Phase 1 — uv presence check.** Add a step at the top of Phase 1 that runs `uv --version` and halts on non-zero exit with: `> uv is not installed. Install via PowerShell: irm https://astral.sh/uv/install.ps1 | iex — then re-run /mill-setup.` This is the first and hardest precondition.
  2. **Phase 4.7 — PS1 wrappers (semantics already updated in batch 01).** The skill prose says "Phase 4.7 — Shortcut wrappers" and calls `_shortcuts.write_all`. Update the skill prose to say "PS1 shortcut wrappers" instead of just "shortcut wrappers" — the underlying helper now writes `.ps1` files. The `_shortcuts.write_all` call shape stays the same.
  3. **Phase 4.7 — set PYTHONPATH user env var.** Add a new sub-step after `_shortcuts.write_all` that sets the Windows user environment variable `PYTHONPATH` to the scripts directory of the latest installed plugin version. Use Bash-invokes-PowerShell since CC's shell is Bash:
     ```bash
     pwsh -Command "
     \$cache = '$env:USERPROFILE\.claude\plugins\cache\millhouse\mill';
     \$latest = (Get-ChildItem \$cache -Directory | Sort-Object Name -Descending | Select-Object -First 1).FullName;
     \$scripts = Join-Path \$latest 'scripts';
     [System.Environment]::SetEnvironmentVariable('PYTHONPATH', \$scripts, 'User');
     Write-Host \"Set PYTHONPATH (User) = \$scripts\"
     "
     ```
     Log: "Set PYTHONPATH (User) = <scripts>. Note: take effect in NEW CC sessions; current session must keep using the inline PYTHONPATH prefix below."
  4. **Bootstrap pattern — every Python invocation in mill-setup uses inline PYTHONPATH.** Find every `python -c "..."` snippet in mill-setup SKILL.md (they appear in Phases 3.1, 3.7, 4, 4.5b, 4.7, 4.9, 6, 6a, 7) and replace with `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" uv run --project "${CLAUDE_PLUGIN_ROOT}" python -c "..."`. The bare `python "${CLAUDE_PLUGIN_ROOT}/scripts/_sibling.py" wiki "<hub-path>"` invocation in Phase 3 also gets this prefix.
  5. **Remove the session-start `export PYTHONPATH`.** Delete the "How to invoke the helpers" section at lines 46-56 of the current SKILL.md (the `export PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` paragraph). Replace with a brief note explaining that mill-setup uses inline PYTHONPATH prefix because it's the bootstrapper that creates the global env var.
  6. **Phase 8 — verify invariants.** Add a new bullet to the Phase 8 verification checklist: `PYTHONPATH user env var contains <CLAUDE_PLUGIN_ROOT>/scripts (verify via [System.Environment]::GetEnvironmentVariable('PYTHONPATH', 'User'))`. Also add: `Every shortcut wrapper at .millhouse/<script>.ps1 exists (was .py before this migration; legacy .py wrappers should not exist)`.
  7. **Phase 8 — success summary block.** Update the `Shortcut wrappers: N scripts under .millhouse/` line to `Shortcut wrappers: N PS1 scripts under .millhouse/` and add a line `PYTHONPATH (User): <scripts>` showing the value set.
  8. **API audit pass on this file.** While editing, audit every helper-call example in mill-setup SKILL.md against the actual function signatures in `plugins/mill/scripts/_*.py`. Known patterns to verify: `_setup.create_hub_links(...)`, `_wiki.write_commit_push(wiki, paths, msg)` (3-arg), `_sibling.resolve_path`, `_junction.create`, `_gitignore.upsert_split`, `_shortcuts.write_all`, `_sidebar.regenerate`, `_vscode.write_settings`, `_paths.resolve_short_name`. Fix any mismatches.
  9. **Verification grep:** after edits, grep the file for `\bpython\s` (bare python without `uv run`) — should return zero matches. Grep for `export PYTHONPATH` — zero matches. Grep for `\bplugins/mill/scripts/` (repo-relative) — zero matches in invocation lines (paths in commentary that explain "the helpers in plugins/mill/scripts/..." are fine).
- **Commit:** `mill-setup(skill): migrate to uv run + PYTHONPATH bootstrap pattern`

## Batch Tests

`verify: null` — mill-setup is a skill, not a runnable script. End-to-end verification requires the operator to run `/mill-setup` in a fresh hub clone, which is post-merge work outside the scope of mill-go's batch verification loop. The card's per-step requirements provide the implementer's checklist; the post-edit grep checks (item 9 in the card) provide the structural verification. The Phase 8 invariants added in items 6-7 of the card provide the in-skill verification — when an operator does run `/mill-setup`, those checks fire. No automated test is added because mill-setup is inherently interactive (cloning wiki repos, network operations).
