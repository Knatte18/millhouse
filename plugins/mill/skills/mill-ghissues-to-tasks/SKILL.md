---
name: mill-ghissues-to-tasks
description: Drain the GitHub issue queue into Home.md. One-shot: the assistant groups all open issues into a few tasks (new or folded-in) and asks for one combined approval, then closes consumed issues with a pointer comment. Skipped issues are left alone.
---

# mill-ghissues-to-tasks

One-shot triage of the repo's open GitHub issues into `Home.md` task entries.

The assistant fetches all open issues, analyzes the full set, and proposes a natural grouping of related issues into a small number of tasks (plus fold-ins and skips), presented as a single consolidated proposal. The operator gives one combined approval. On approval, the grouped tasks are written to Home.md, committed and pushed via the wiki, and every consumed issue is closed with a comment pointing at its task slug. Skipped issues are untouched.

Leaving claimed-but-open issues on GitHub is a forgetting hazard — that's why the closed-with-comment model is preferred over a "tracked" label.

## Entry checks

1. `gh auth status` must succeed. If not, stop:
   > `gh` is not authenticated. Run `gh auth login` and re-invoke `/mill-ghissues-to-tasks`.
2. `.millhouse/wiki/` junction must exist. If not, stop and tell the user to run `mill-setup`.

## Step 1 — Fetch and build the contract

Use the `_gh_issues` library. From the hub root:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json, _gh_issues, _paths
git_root = _paths.resolve_git_root()
issues = _gh_issues.fetch(limit=100, git_root=git_root)
repo = _gh_issues.detect_repo(git_root=git_root)
contract = _gh_issues.to_contract(issues, repo)
with open('.scratch/triage-contract.json', 'w') as f:
    json.dump(contract, f, indent=2)
print(json.dumps({'repo': repo, 'issue_count': len(issues)}))
"
```

Record `repo` (printed above) for the close step (Step 3). `.scratch/triage-contract.json` is the canonical handoff file `mill-triage-to-tasks` reads next. Optionally also write `.scratch/issues.json` (the raw `fetch()` output) as a debugging aid — no downstream step reads it.

## Step 2 — Hand off to the shared analysis skill

Invoke `mill-triage-to-tasks` via the Skill tool (same pattern used by `mill-report-to-tasks`) and let it run its full Steps 1–7 against `.scratch/triage-contract.json`: read the contract, read the current wiki tasks, group into new tasks / fold-ins / skips, present one consolidated proposal, wait for operator approval, apply the wiki writes (new tasks + fold-ins), write `.scratch/triage-result.json`, and report. This skill performs no grouping, proposal-writing, or wiki-write logic of its own anymore — that entire flow now lives in `mill-triage-to-tasks`.

## Step 3 — Close consumed issues

After `mill-triage-to-tasks` completes, check whether `.scratch/triage-result.json` exists:

- **Does not exist:** zero items were consumed (either the contract had zero items, or the shared skill's all-skipped short-circuit fired). Report zero closes and stop.
- **Exists:** parse the JSON array — `[{"ref": "<issue-number-as-string>", "route": "new_task"|"fold_in", "slug": "<slug>"}, ...]`. For each entry, map `route` to the exact close-comment string:
  - `new_task` → `Consolidated into wiki task: <slug>`
  - `fold_in` → `Folded into wiki task: <slug>`

  Then, for each entry, call:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  import _gh_issues, _paths
  _gh_issues.close_with_comment(<int(entry['ref'])>, '<comment>', git_root=_paths.resolve_git_root())
  "
  ```
  `to_contract()` stored `ref` as `str(issue["number"])` — cast it back to `int` before calling `close_with_comment`.

  On any individual close failure, log the issue number + error and continue to the next entry — do not abort the loop. Collect all failures for Step 4's report. This preserves today's exact close-on-approval-only invariant: `mill-triage-to-tasks` already gated every wiki write behind operator `approve`, so by the time this step runs, every entry in `.scratch/triage-result.json` is already committed to the wiki.

## Step 4 — Report

Summarize what this skill itself is responsible for — issues closed and any close failures. The new-task/fold-in/skip counts were already reported to the operator by `mill-triage-to-tasks`'s own Step 7 during the handoff; do not re-derive or re-print them here, to avoid two divergent counts in the same conversation.

```
Revision applied.
  <Z> issues closed on GitHub
  <F> failed to close (see stderr)
```

## Rules

- **Close only on approval + actual write** — only issues listed in `.scratch/triage-result.json` are closed, and `mill-triage-to-tasks` only writes that file after operator approval and a successful wiki write.
- **Close-comment strings** — new-task → `Consolidated into wiki task: <slug>`; fold-in → `Folded into wiki task: <slug>` (byte-identical to `/mill-fold`'s fold-in comment).
