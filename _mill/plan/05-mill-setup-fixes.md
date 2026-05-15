# Batch: mill-setup-fixes

```yaml
task: 55 (A) -- Fix hardcoded _mill/ paths and mill-setup junction/config bugs
batch: mill-setup-fixes
number: 5
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Fix two bugs in `mill-setup/SKILL.md`:
1. **Phase 4 (#293):** `target_root` passed to `_setup.create_hub_links` uses `git rev-parse --show-toplevel` (= git root) instead of `cwd` (= actual hub). In subdirectory-hub mode these differ, causing junctions to land in the git root instead of the hub dir.
2. **Phase 3.1 (#294):** When `config.yaml` exists, the skill skips it entirely without validating required blocks. An existing config missing the `paths:` block causes a `KeyError` in mill-spawn. Fix adds block-level upsert: load existing config + template, copy missing required top-level keys from template, write+commit if any were added.

Both fixes are in the same file (`mill-setup/SKILL.md`). No Python helper changes.

## Cards

### Card 7: Fix Phase 4 target_root to use cwd instead of git rev-parse

- **Context:**
  - `plugins/mill/scripts/_setup.py`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In Phase 4 of `mill-setup/SKILL.md`, make two changes to the `create_hub_links` call:
  1. Change `target_root=Path(r'<hub-path>').resolve()` → `target_root=Path(r'<cwd>').resolve()`.
  2. In the `tokens` dict, change `'HUB_PATH': r'<hub-path>'` → `'HUB_PATH': r'<cwd>'`.
  3. In the Token reference list immediately after the code block, update the `<hub-path>` entry (currently documented as "absolute path to the hub (`git rev-parse --show-toplevel`)") to read: "`<cwd>` — the hub directory. mill-setup is invoked from the hub; `cwd` is the hub by construction. In subdirectory-hub mode, this differs from `git rev-parse --show-toplevel` (the repo root). Use `cwd`, not `git rev-parse --show-toplevel`, for `target_root`." Remove the old `<hub-path>` bullet and replace it with a `<cwd>` bullet.
- **Commit:** `fix(mill-setup): use cwd as target_root in Phase 4 create_hub_links (fixes #293)`

### Card 8: Add Phase 3.1 block-level config.yaml upsert

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/templates/wiki-config.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In Phase 3.1 of `mill-setup/SKILL.md`, replace the current two-step "if exists: skip / else: copy" with the following three-step logic:
  1. **If `<wiki-dir>/config.yaml` does not exist:** copy `${CLAUDE_PLUGIN_ROOT}/templates/wiki-config.yaml` → `<wiki-dir>/config.yaml` verbatim (current behaviour; no change).
  2. **If `<wiki-dir>/config.yaml` exists:** run a block-level upsert:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
     from pathlib import Path
     import yaml, _wiki

     wiki_dir = Path(r'<wiki-dir>').resolve()
     config_path = wiki_dir / 'config.yaml'
     template_path = Path(r'${CLAUDE_PLUGIN_ROOT}/templates/wiki-config.yaml').resolve()

     existing = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
     template  = yaml.safe_load(template_path.read_text(encoding='utf-8')) or {}

     required_keys = ['paths', 'llm', 'pipeline', 'roles', 'notify', 'spawn', 'groom']
     missing = [k for k in required_keys if k not in existing]
     if missing:
         for k in missing:
             existing[k] = template[k]
         config_path.write_text(yaml.dump(existing, allow_unicode=True, sort_keys=False), encoding='utf-8')
         print('upserted blocks:', missing)
     else:
         print('config.yaml validation OK -- all required blocks present')
     "
     ```
     After running: if any blocks were upserted (i.e., `missing` was non-empty), commit and push via `_wiki.write_commit_push`:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
     from pathlib import Path
     import _wiki
     _wiki.write_commit_push(Path(r'<wiki-dir>').resolve(), ['config.yaml'], 'chore: upsert missing config.yaml blocks from template')
     "
     ```
     Log which blocks were added (from the `print('upserted blocks:', ...)` output) so the operator can see the diff.
  3. In the "Why verbatim copy" paragraph that follows, add a sentence: "If `config.yaml` already exists, the upsert step validates and fills any required top-level blocks that are missing (`paths`, `llm`, `pipeline`, `roles`, `notify`, `spawn`, `groom`). This prevents downstream `KeyError` in mill-spawn when an older config.yaml predates a required schema block."
- **Commit:** `fix(mill-setup): add Phase 3.1 block-level config.yaml upsert (fixes #294)`

## Batch Tests

`verify: null` — SKILL.md edits; no runnable test surface. The Phase 3.1 upsert logic uses `yaml.dump` which may reorder keys — operators should verify the upserted config.yaml is readable after re-running mill-setup against a partial config.
