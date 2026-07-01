---
name: mill-report-to-tasks
description: Drain a local JSON triage report (sandbox-report contract) into Home.md tasks via mill-triage-to-tasks, with no GitHub dependency of any kind.
---

# mill-report-to-tasks

One-shot triage of a local `sandbox-report.json`-shaped file into `Home.md` task entries.

This is the source-agnostic sibling of `mill-ghissues-to-tasks`: instead of fetching open GitHub issues, it reads and validates a local JSON file already shaped on the triage-report contract (see `plugins/mill/templates/triage-report.schema.md`), then hands off to `mill-triage-to-tasks` for the entire group -> propose -> approve -> upsert flow. Unlike `mill-ghissues-to-tasks`, there is nothing to close — `mill-triage-to-tasks`'s report is the final output of this skill.

## Invocation

`/mill-report-to-tasks <path-to-json>` — a required positional argument. There is no default-path fallback; the operator must always name the file explicitly.

## Entry checks

1. `.millhouse/wiki/` junction must exist. If not, stop and tell the user to run `mill-setup`.
2. The given path must exist as a file, parse as JSON, and pass `_sandbox_report.read()` validation. On any failure (missing path, invalid JSON, `SandboxReportError`), stop with the error message `_sandbox_report.read()` raised — do not catch and reword it.

## Step 1 — Read and validate the file

Call `_sandbox_report.read()` on the given path. This one call doubles as entry check 2 and produces the contract dict — do not call it twice.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json
from pathlib import Path
import _sandbox_report
contract = _sandbox_report.read(Path('<path-to-json>'))
print(json.dumps(contract, indent=2))
"
```

The result is the full contract envelope: `{"source": "sandbox-report", "meta": ..., "items": [...], "ref_prefix": "", "detail_hint": None, "embed_body": True}`.

## Step 2 — Empty-items short-circuit

If `contract["items"]` is an empty list, this is the entry skill's own "nothing to do" detection — knowable from the file alone. Print a one-line message and stop:

```
nothing to do -- 0 items in <path>
```

Do NOT write `.scratch/triage-contract.json` and do NOT invoke `mill-triage-to-tasks` in this case.

## Step 3 — Hand off to the shared analysis skill

Write the full contract dict to `.scratch/triage-contract.json` (`json.dump`, indent for readability). Then invoke `mill-triage-to-tasks` via the Skill tool (same pattern used elsewhere in this project to invoke `mill-receiving-review`) and let it run its full Steps 1–7: read the contract, read the current wiki tasks, group into new tasks / fold-ins / skips, present one consolidated proposal, wait for approval, apply the wiki writes, write `.scratch/triage-result.json`, and report. This skill does not re-implement any part of that flow.

## Step 4 — No post-processing

After `mill-triage-to-tasks` completes, this skill performs no further action — there is no GitHub issue to close for `sandbox-report` items. If `.scratch/triage-result.json` exists (meaning at least one item was consumed), this skill does not need to read it; `mill-triage-to-tasks`'s own Step 7 report already covers the operator-visible summary.

Unlike `mill-ghissues-to-tasks`, there is nothing to close — `mill-triage-to-tasks`'s report is the final output of this skill.

## Rules

- **One-shot, no resumable state** — inherited from `mill-triage-to-tasks`: `.scratch/triage-proposal.md` is the only intermediate artefact, and there is no per-item resumable state.
- **Skipped items are untouched** — no wiki write, nothing to undo.
- **Writes only happen after explicit `approve`** — nothing touches the wiki before that, and this skill never writes the wiki directly; `mill-triage-to-tasks` does.
- **No GitHub side effects of any kind** — this skill never imports or shells out to `gh`.
