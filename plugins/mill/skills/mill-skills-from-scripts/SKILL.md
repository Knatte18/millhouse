---
name: mill-skills-from-scripts
description: Regenerate the per-script thin SKILL.md wrappers under plugins/mill/skills/. Reads each user-callable mill script's docstring and writes a tight ~10-15 line skill body. Manual invocation only — no pre-commit hook.
---

# mill-skills-from-scripts

Generates or refreshes the 12 thin SKILL.md files that give Claude Code a compact view of each user-callable mill script. Invoke it after a script's CLI changes (new flags, changed args) or after a new entry is added to `_shortcuts.SHORTCUT_SCRIPTS`. The generator reads each eligible script's docstring, drafts a tight body, and calls `_skill_writer.write_skill_file` to persist it. Always overwrites — re-running is idempotent under stable docstrings.

## Usage

```
/mill-skills-from-scripts
```

## How to invoke the helper

```python
import sys
import _skill_writer
from pathlib import Path
# ${CLAUDE_PLUGIN_ROOT} resolves to <plugin-cache>/mill/
# Its parent is the plugins/ directory: /path/to/plugins/
plugins_root = Path('${CLAUDE_PLUGIN_ROOT}').parent
for script_path in _skill_writer.iter_target_scripts(plugins_root):
    # read docstring, draft body, then write:
    _skill_writer.write_skill_file(skill_name, body, plugins_root)
```

## Steps

1. Load `_skill_writer` as shown above. Call `_skill_writer.iter_target_scripts(plugins_root)` — it returns 12 `Path` objects (one per eligible script). For each path, derive `skill_name = "mill-<X>"` from its stem (`millpy-<X>.py` → `mill-<X>`).

2. Read the script file. Extract line 1 of the module docstring — the first textual line inside the triple quotes, in the canonical shape `mill-<X> — <one-liner>`. The substring after the em-dash (`—`) becomes the skill's `description:` value.

3. Draft a tight ~10–15 line SKILL.md body matching this shape:
   ```
   ---
   name: mill-<X>
   description: <one-liner extracted from line 1>
   ---

   # mill-<X>

   <one short paragraph: what the script does and when CC reaches for it; derived from the script docstring's prose section>

   ## Run it

   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-<X>.py" <args from Usage block>
   ```

   <2–3 lines of must-know constraints — e.g. "no wiki lock taken", "exits 1 if no .millhouse/wiki", or other tight invariants visible in the script docstring>
   ```

4. Call `_skill_writer.write_skill_file(skill_name, body, plugins_root)` for each script. The helper creates the `plugins/mill/skills/<skill_name>/` directory if needed and always overwrites the file.

5. After all 12 are written, run `mill-skills-index` to refresh `SKILLS.md`:
   ```bash
   uv run --project "$CLAUDE_PLUGIN_ROOT" "$CLAUDE_PLUGIN_ROOT/scripts/millpy-skills-index.py"
   ```

6. Commit and push the 12 new SKILL.md files and the regenerated `SKILLS.md` in one commit.

## Rules

- Body length is the contract: ~10–15 lines including frontmatter. Hard ceiling: 25 lines. Never dump the full docstring verbatim — that bloats Claude Code's startup index.
- Use the Unicode em-dash `—` (U+2014) where the source docstring uses it. Never substitute ASCII `--`.
- Path token `${CLAUDE_PLUGIN_ROOT}/scripts/millpy-<X>.py` is mandatory in every generated skill body (CLAUDE.md path-invariant rule).
- Do NOT regenerate skills whose name is in `_skill_writer.SKILL_GENERATOR_SKIP` (today: `mill-add`). The helper's `iter_target_scripts` already excludes them; double-check before writing.
- Skip-listed: `mill-add` (hand-written, judgment-heavy). Excluded one layer up via not being in `SHORTCUT_SCRIPTS`: the 3 review scripts and `mill-skills-index`.
