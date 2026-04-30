---
name: mill-list
description: print the tasks in the wiki's Home.md, one per line.
---

# mill-list

Reads `Home.md` from the wiki clone and prints one line per task. A `[P]` prefix marks tasks that have a matching `proposal-<slug>.md` at the wiki root. Use this for a quick overview of the backlog before picking a task.

## Run it

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-list.py"
```

No wiki lock taken — read-only. Exits 1 when the wiki is not found or `Home.md` is missing. Exits 0 with `(no tasks)` when the backlog is empty.
