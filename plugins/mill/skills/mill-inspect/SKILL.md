---
name: mill-inspect
description: deep dump of every active task's status.md.
---

# mill-inspect

Dumps the full YAML block and timeline from each active task's `status.md`, augmented with worktree path and Home.md marker. Use it when you need timeline detail or blocked reason — `mill-status` gives the summary, `mill-inspect` gives the full picture.

## Run it

```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-inspect.py" [<slug>] [--json] [--since <phase>]
```

Narrow to one task with `<slug>`; filter to a phase and later with `--since`. Exits 0 (with a message) when no active tasks are found. `--json` emits structured output for scripting.
