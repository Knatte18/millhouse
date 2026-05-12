---
name: mill-wiki-push
description: commit and push manual wiki edits, resolving rebase conflicts on the fly.
---

# mill-wiki-push

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

Commits every local change in the wiki repo (config.yaml, proposal-*.md, Home.md, etc.) with an auto-generated message and pushes. If the push is rejected and the rebase produces a conflict, this skill resolves the conflict and continues.

The underlying script (`millpy-wikipush.py`) can also be run manually from `.millhouse/millpy-wikipush.ps1`. In that path it aborts cleanly on conflict ("no harm done") and instructs the operator to invoke this skill — that's why the skill passes `--leave-conflicts`: the wiki is left mid-rebase so the LLM can resolve and continue.

## Run it

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-wikipush.py" --leave-conflicts
```

Capture exit code and stdout/stderr. Branch on exit code:

- **0** — print the script's stdout (one line: `pushed: ...` or `no changes`) and stop.
- **1** — non-conflict failure (lock busy, push error, etc.). Print the script's stderr and stop.
- **2** — rebase conflict. Continue to the resolution steps below.

## Resolve conflict (exit 2)

The wiki repo is in mid-rebase state. Your local commit is on top, and one or more files have conflict markers.

1. **List conflict files:**

   ```bash
   git -C <wiki-path> diff --name-only --diff-filter=U
   ```

   Resolve `<wiki-path>` via:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "
   import _paths
   print(_paths.resolve_wiki_path(_paths.resolve_git_root()))
   "
   ```

2. **For each conflict file, decide based on context:**
   - `_Sidebar.md` — auto-generated. Take *theirs* (the upstream version) — it will be regenerated correctly anyway.
   - `Home.md` — usually structural (e.g. another skill marked a task done while operator edited the description). Merge both sides — keep upstream's structural change AND operator's content edit. Don't drop either side.
   - `config.yaml` / `proposal-*.md` — operator's intentional edit. Prefer *ours* unless upstream made a meaningful change to the same lines (rare).
   - When genuinely uncertain, keep both versions in the file with a brief comment marking the disagreement, then surface it to the operator in the final report.

3. **Stage and continue:**

   ```bash
   git -C <wiki-path> add <resolved-files>
   git -C <wiki-path> rebase --continue
   ```

   If `rebase --continue` fails (additional conflicts surfaced from later commits in the rebase queue), repeat steps 1–3 until the rebase completes.

4. **Push:**

   ```bash
   git -C <wiki-path> push
   ```

5. **Report to the operator:** which files had conflicts, how each was resolved (theirs / ours / merged), and that the push succeeded.
