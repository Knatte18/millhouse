# Batch: cleanup-robustness

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: cleanup-robustness
number: 4
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-cleanup.py test-worktree.py
depends-on: []
```

## Batch Scope

Makes mill-cleanup robust: orphan-worktree detection uses the git worktree
registry instead of a raw directory scan (#434), and stale poll-loop
processes holding handles into a worktree are killed before removal (#417,
Fix 2), plus a self-terminating timeout is documented for the remaining
subprocess/psmux poll loops (#417, Fix 1). Touches `millpy-cleanup.py`,
`_worktree.py`, and `mill-go/SKILL.md`.

## Cards

### Card 10: Orphan detection via `git worktree list --porcelain`

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `millpy-cleanup.py` `build_plan` (the orphan-worktree
  scan over `<container>/wts/` that currently uses `iterdir()` and treats
  every subdir as a worktree), cross-reference against
  `_worktree.list_worktrees(hub_root)` (already exists; parses
  `git worktree list --porcelain`). Only report a `wts/` entry as an
  "orphan worktree" when it IS a registered git worktree that lacks an
  active marker. Plain directories under `wts/` that are NOT in the
  registry (e.g. an empty `millhouse.worktrees` leftover) must be ignored
  silently -- they are never reported as an orphan worktree and never
  surfaced for `git worktree remove`. (Deterministic single behavior: do
  not emit a separate "unexpected directory" message; just skip them.)
  Preserve the existing in-use-marker handling.
- **Commit:** `fix(cleanup): use git worktree registry for orphan detection`

### Card 11: Kill stale processes before worktree removal

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Edits:**
  - `plugins/mill/scripts/_worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a pure matcher to `_worktree.py` (e.g.
  `processes_holding_path(worktree, process_records)`) that takes an
  injected iterable of process records (each with a pid and a command-line
  string) and returns the pids whose command line references the worktree
  path (normalized comparison). Records whose command line is `None` or
  empty (CIM returns `CommandLine = None` for elevated processes queried
  from a non-elevated shell) MUST be silently skipped -- they cannot match
  any path (guard before any substring check to avoid `TypeError`). Add a best-effort, failure-swallowing
  `kill_stale_holders(worktree, *, enumerate_processes=<default>)` that
  enumerates processes, filters via the pure matcher, and terminates them
  (`taskkill /PID <pid> /F` on Windows), swallowing all errors. Matching
  requires each process's COMMAND LINE (to find bash poll-loops that
  reference the worktree path), so the default real enumerator MUST obtain
  command-line text. Use PowerShell
  `Get-CimInstance Win32_Process | Select-Object ProcessId,CommandLine`
  (the supported replacement for the removed-on-Windows-11 `wmic`; do NOT
  use `wmic`, and do NOT use `tasklist`, which exposes only the window
  title, not the command line) via `_subprocess_util`, parsing ProcessId +
  CommandLine. On non-Windows the enumerator may be a no-op (the bug is
  Windows-specific). The enumerator and kill steps are best-effort and must
  never raise. Call `kill_stale_holders(path)`
  inside `remove_safe` AFTER junction stripping and BEFORE
  `git worktree remove`. The kill step must never raise; a failure to kill
  must not abort removal. ASCII-only messages.
- **Commit:** `fix(cleanup): kill stale poll-loop processes before worktree remove`

### Card 12: Document a max-wait on subprocess poll loops

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the subprocess/psmux poll-loop instructions in
  `mill-go/SKILL.md` (the "Poll `cat <log-path>` until `[mill-bg] EXIT`"
  blocks), add a bounded max-wait so the loop self-terminates (e.g.
  ~3600s) instead of polling forever if the worker dies without writing
  `[mill-bg] EXIT`, with an explicit halt/escalation message on timeout.
  Note that agent-mode dispatch (the default) is synchronous and does not
  use these loops, so this guard applies to the subprocess/psmux fallback
  only. Do not alter the agent-mode dispatch section. ASCII-only.
- **Commit:** `docs(mill-go): bound subprocess poll loops with a max-wait`

### Card 13: Tests for cleanup + worktree process matching

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
  - `plugins/mill/unit_tests/test-worktree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-worktree.py`: unit-test `processes_holding_path`
  with injected process records -> only records whose command line
  references the given worktree path are returned; and `kill_stale_holders`
  with an injected enumerator + an injected/monkeypatched kill function ->
  the right pids are passed to kill, and an enumerator/kill that raises is
  swallowed (no exception). In `test-cleanup.py`: drive the orphan-detection
  logic with an injected/monkeypatched `list_worktrees` result and a set of
  on-disk `wts/` dirs -> only registered-but-unmarked worktrees are reported
  as orphans; a non-registry plain dir is not reported as an orphan
  worktree. Follow existing fixture style.
- **Commit:** `test(cleanup): cover registry-based orphans and stale-process matching`

## Batch Tests

`verify:` runs `test-cleanup.py` and `test-worktree.py`. Process killing
and `git worktree list` are exercised only through injected
enumerators/monkeypatched helpers -- no real processes are killed and no
real git runs.
