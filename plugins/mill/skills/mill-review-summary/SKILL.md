---
name: mill-review-summary
description: "print a per-task table of review rounds: verdict, model, effort, duration, tool-calls, cost."
---

# mill-review-summary

Prints one row per review file for the active task's `reviews_dir` — round, type, scope, verdict,
model, effort, duration, tool-calls, cost.
Reach for it when you need to see how much a task's review rounds actually cost, or to spot a
round that burned an unusual amount of time or tool calls before its verdict landed.
It reads only what is already on disk, so it works on any task at any point in its lifecycle.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-summary.py" [--slug <slug>] [--json] [--no-color] [--sort {round,scope}]
```

Outputs colored text by default (VERDICT column only);
`--no-color` disables ANSI. `--json` emits a JSON array with raw numeric values for scripting.
Sorts by `round` (default) or `scope`.

## Reading the table

Some cells are legitimately `n/a`, not an error:

- Every cell, for a review file written before this feature existed.
- `TOOLS` and `COST`, for any round dispatched in agent-mode or through psmux.
- `TOOLS` and `COST`, for every gemini-provider round.
- `EFFORT`, when the file's `reviewer_model:` names something the reviewer registry does not
  resolve (e.g. a bare Agent-tool tier such as `sonnet`, which `--actual-model` can write).
