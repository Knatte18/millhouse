---
name: mill-fetch-issues
description: thin CLI over _gh_issues.fetch.
---

# mill-fetch-issues

Fetches open GitHub issues for the current repo via the `gh` CLI and writes them to a JSON file. Invoke before `/mill-ghissues-to-tasks` or whenever you need a fresh issue snapshot.

## Run it

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fetch-issues.py [--limit <N>] [--out <path>]
```

Default output is `<git_root>/.scratch/issues.json`. Prints the absolute output path to stdout on success. Exits 1 if `gh` is not authenticated or the fetch fails.
