---
name: mill-color
description: override the current worktree's VS Code title-bar color.
---

# mill-color

Rewrites `.vscode/settings.json` in the current worktree with the chosen palette color. The existing `window.title` is preserved; if absent it is derived from the repo short name and active slug.

## Run it

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-color.py <color-name>
```

Valid color names: `green`, `purple`, `blue`, `yellow`, `red`, `cyan`, `indigo`, `orange`. Exits 2 on invalid or missing color name, 1 on other errors.
