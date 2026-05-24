# Handoff — wiki-v3-adoption

```yaml
date: 2026-05-24
branch: hanf/wiki-v3-adoption
phase: implementing (batch 3 in progress; not fully done)
builder_lock: held (release before tomorrow's resume OR before spawning a new task)
github_issue_filed: https://github.com/Knatte18/millhouse/issues/371
```

## Snapshot

Batch 1 (`wiki-module-refactor`) and batch 2 (`migration-script`) are **approved and committed**, all tests green. Batch 3 (`v2-deletion-and-port`) has **31 commits** but is **not complete**. Verify fails: 15 of 77 unit tests fail.

## Batch 3 — done vs. not done

| Card | Description | Status |
|---|---|---|
| 15 | `read_junctions`/`read_hardlinks` -> `_junction.py` | done |
| 16 | `clone_or_init` -> `_setup.py` | done |
| 17 | `_setup.py` callers switched to `_junction` | done |
| 18 | `millpy-cleanup.py:636` caller switched | done |
| 19 | `_config.py` — drop `wiki/config.yaml` fallback | done |
| 20 | `_review_common.py` — drop `wiki/config.yaml` fallback | done |
| 21 | `millpy-add.py` -> `wiki.upsert_task` | done |
| 22 | `millpy-claim.py` -> `wiki.list_tasks_brief` | done |
| 23 | `millpy-cleanup.py` -> `wiki.set_phase` / `list_tasks_brief` | done |
| 24 | `millpy-fold.py` -> V3 wiki API | done |
| **25** | `millpy-spawn.py` port | **NOT DONE** (still has `import _tasks_md`/`_wiki`) |
| **26** | `_spawn_core.py` port | **PARTIAL** — `_task_to_dict` helper added; full `wiki.merge_tasks` / `set_phase` work missing |
| 27 | `_marker.py` -> `list_tasks_brief` / `get_task` | done |
| **28** | small CLIs port (`inspect`/`status`/`terminal`/`vscode` + `wikipush` sliver) | **NOT DONE** |
| **29** | docstring/error text fixes (`_paths.py`, `_junction.py`, `_worktree.py`) | **NOT DONE** |
| 30 | Delete `_wiki.py`, `_tasks_md.py`, `_sidebar.py` | done (committed early, before all callers ported — see "key insight #2" below) |
| 31 | Delete `millpy-migrate-config.py` + test | done |
| 32 | Delete `millpy-migrate-layout.py` | done |
| 33 | Templates/skill docs — drop `wiki/config.yaml` refs | done |
| 34 | Test fixtures — drop `wiki/config.yaml` | done |
| 35 | Delete V2-only tests; port per-CLI tests | done |
| **36** | Test sweep pass 1 — delete V2 imports / replace direct calls | **PARTIAL** (a few files done; ~25 remain) |
| **37** | Test sweep pass 2 — `mock.patch` retargeting | **NOT DONE** |
| **38** | Test sweep pass 3 — `Task(...)` -> dict fixtures + dead-test deletion | **NOT DONE** |

Remaining: cards 25, 26 (finish), 28, 29 + 36/37/38 test-sweep + a substantive V3-daemon-startup bug.

## Key insights discovered during this session

### Insight #1 — Planner produced batches too large for implementer context

Batch 3 had 24 cards (38 counting sub-cards). The haiku implementer's `claude -p` print-mode session has no auto-compact (auto-compact only exists in the interactive Claude Code REPL). Each implementer dispatch self-reported "token budget reached" after 3–9 cards. Four sequential dispatches got us 31 commits, then a CLI timeout (1800s) on the fourth.

**Filed as [issue #371](https://github.com/Knatte18/millhouse/issues/371).** Fix should land in the planner: hard cap on cards per batch (suggested 12–15) AND/OR token-budget estimate at plan time.

### Insight #2 — PYTHONPATH cache-leakage corrupts test runs

Worktree's `plugins/mill/scripts/_wiki.py`, `_tasks_md.py`, `_sidebar.py` are deleted (card 30). But shipping scripts in worktree (`millpy-spawn.py`, `millpy-inspect.py`, etc.) still have `import _tasks_md` / `import _wiki` because cards 25/28 weren't ported yet.

These imports still **succeed** because the shell's `PYTHONPATH` is set to the plugin cache:

```
PYTHONPATH=C:\Users\hanf\.claude\plugins\cache\millhouse\mill\2.0.0\scripts
```

(set by every mill skill via the documented `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` pattern.)

When verify runs `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`, the subprocess **inherits** the parent shell's PYTHONPATH. So tests load a Frankenstein mix:
- V2 cache copy of `_config`, `_tasks_md`, `_wiki`, etc.
- V3 worktree copy of `wiki/` subpackage

That mixed state is the root cause of many of the 15 failing tests — including `test-millpy-claim.py` (11 tests fail with "daemon did not start within timeout"), because V2 cache `_paths`/`_config` don't agree with V3 worktree `wiki/_daemon` about file layout.

**Fix is one-line: prepend `PYTHONPATH=""` to the verify command in the plan / mill-config.** Or use `uv run --no-project-pythonpath` or similar isolation. Then tests test the worktree code only.

### Insight #3 — daemon-startup timeout may still be real even after PYTHONPATH fix

Some daemon-related tests time out (`WinError 32` on `.wiki-daemon.log`, "daemon did not start within timeout"). Whether this survives a clean-PYTHONPATH run is open. Investigate first before fixing test fixtures.

## Plan going forward

**Recommendation: don't merge this branch as-is.** Cards 25/26/28/29 are not done; shipping code in fresh checkouts would crash on import. Tests don't pass.

Two options for the user to decide tomorrow:

### Option A — keep this branch, spawn one focused follow-up task

1. Block this task (`wiki-v3-adoption`) with reason "batch 3 not complete; see _mill/handoff.md".
2. Spawn a new task — suggested slug **`wiki-v3-batch3-finish`** — based off `hanf/wiki-v3-adoption` branch (not `main`). The new task keeps all 31 commits and adds the missing work.
3. The new discussion should reference issue #371 explicitly so planner uses smaller batches. Suggested split:
   - **Batch A — verify-isolation + daemon-bug investigation.** Card 1: prepend `PYTHONPATH=""` to verify in mill-config / plan template. Card 2-N: rerun tests; if daemon-startup still times out, root-cause it. ~3-6 cards.
   - **Batch B — finish shipping-code port.** Cards 25, 26-finish, 28, 29. ~6-8 cards.
   - **Batch C — test sweep pass 1+2.** Cards 36/37 across ~25 files. ~10-15 cards.
   - **Batch D — test sweep pass 3 + final green-verify.** Card 38 + smoke. ~8-12 cards.

### Option B — keep this branch, fix manually in Opus thread

Spawn an Opus subagent (or open a new chat with full context) to fix the remaining work. Faster but skips the planner discipline; risk of repeating the over-batching problem in a less-structured form.

I lean toward Option A. Opus-fix-manually is what we tried this evening and we learned more than we fixed.

## Operational state to clean up before tomorrow's resume

1. **Builder lock held by this task** (`wiki-v3-adoption`). Release with:
   ```bash
   PYTHONPATH="c:/Code/millhouse/wts/millhouse/plugins/mill/scripts" "$MILL_PYTHON" "c:/Code/millhouse/wts/millhouse/plugins/mill/scripts/millpy-builder-lock.py" release
   ```
   Re-`/mill-go` tomorrow auto-reclaims for the same slug, but a clean release lets you choose to start a different task instead.

2. **Worktree is clean.** Last commit: `010363a test(test-spawn-core): port Task attribute access to dict-key access`. WIP from the timed-out implementer #4 has been committed.

3. **Stale pyc files for `_wiki.py`, `_tasks_md.py`, `_sidebar.py` were deleted** from `plugins/mill/scripts/__pycache__/`. They will not regenerate (source is gone). No action needed.

4. **`__pycache__/_test_helpers.cpython-313.pyc`** still references V2 — will get refreshed automatically the next time tests touch the helper.

5. **Issue #371 ([planner-too-large-batches](https://github.com/Knatte18/millhouse/issues/371))** is filed and open. It should be linked from the new task's discussion.

6. **TaskList in this session:** task #3 (Implement batch 3) is in_progress. Tasks #4 (Holistic) and #5 (Handoff) are pending. They don't survive this session — start fresh tomorrow.

## What NOT to do tomorrow

- Don't run `/mill-merge` on this branch. It would merge a half-done batch 3 to main.
- Don't run `/mill-go` and expect it to complete in one go. The current plan says batch 3 is 24 cards and planner thinks it's runnable in one batch — that's the bug we filed.
- Don't delete the plugin cache to "fix" the PYTHONPATH leakage. The cache is the correct runtime for mill skills; the fix is in the verify command, not in cache layout.
