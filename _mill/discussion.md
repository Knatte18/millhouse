# Discussion: Port mill to POSIX, not just Windows

```yaml
task: Port mill to POSIX, not just Windows
slug: posix-cross-platform-port
status: discussing
parent: hanf/linux-port-more
```

## Problem

millhouse was built on Windows and much of it assumed that platform: hardcoded
`.venv\Scripts\python.exe` paths, `winreg`, `USERPROFILE`, and `pwsh`/`.ps1` as
the only shell target. Bootstrapping the repo from scratch on a fresh native
Ubuntu machine (no WSL) surfaced these one by one. The predecessor branches
already ported the bulk of it: `mill-setup/SKILL.md` (dual-support venv
computation, Windows-only Phase 4.7 skipped on POSIX), `_winenv.py` (guarded
`winreg` import), `_gitignore.py` (symlink-matching glob fix),
`vscode-tasks.json` (per-OS `${env:SHELL}`), `update-plugins.sh`, and a batch
of test-fixture portability fixes.

**Why now:** the original proposal assumed a large remaining sweep — "most skill
docs still show PowerShell-only invocation examples" and "~10 scripts reference
`.venv\Scripts\python.exe`". Re-grepping the repo on this branch shows that fear
is **stale**: the skill docs have since been converted to the portable
`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" …` form, and the
scripts already carry `os.name`/`sys.platform` guards and
`getattr(subprocess, "CREATE_NO_WINDOW", 0)` fallbacks. What actually remains is
small, concrete, and includes one real bug that breaks `mill-go` on Linux
entirely. This task closes those gaps and leaves the port complete for the
supported skills.

## Scope

**In:**

- **`mill-go/SKILL.md` venv-existence check (real bug).** Two blocks (around
  lines 240–246 and 624–630) test *only*
  `${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe`. On POSIX that path never
  exists, so the check runs `uv sync`, re-checks, still fails, and **HALTs** —
  `mill-go` cannot run per-batch or holistic-review invocations on Linux at all.
  Fix both blocks to the dual-existence pattern already used in
  `mill-setup/SKILL.md:74` (`bin/python` OR `Scripts/python.exe`).
- **Root `.claude/settings.json` `MILL_TEST_PYTHON`.** Currently a hardcoded
  `C:\Code\millhouse\...\.venv\Scripts\python.exe`. Grep confirms it is
  **consumed nowhere** in the repo — dead leftover config. Delete the key (and,
  if it leaves an empty `env` object, remove that too, or leave `{}` — see
  Decisions).
- **`plugins/mill/integration_tests/test-bootstrap.ps1` POSIX counterpart.**
  Add a `test-bootstrap.sh` alongside it (same treatment as
  `update-plugins.ps1` → `update-plugins.sh`) so the Layer-01 end-to-end test
  (mill-add produces a single commit touching `Home.md` + `_Sidebar.md`, sidebar
  contains the new task, mill-list prints it back) is runnable on Linux/macOS.
  Uses `.scratch/` for the throwaway wiki+hub pair, never `$env:TEMP`/`/tmp`
  (per `conversation/SKILL.md`). Keep the `.ps1` for Windows. **Preconditions:**
  the `.sh` port drives real scripts via a real synced venv and real `git`, the
  same preconditions as the `.ps1` — it assumes `uv`/venv and `git` are present
  on the runner. It is a manual integration test (not in `run-all.py`); if a
  prerequisite is missing it must **fail loudly** (nonzero exit with a clear
  message naming the missing tool), never silently skip or report a false pass.
- **Stale doc mentions.** `_vscode.py:27` and `_vscode.py:123` docstrings still
  say the tasks.json "auto-opens a pwsh terminal on folder open"; the template
  now uses per-OS `${env:SHELL}`. Correct the comments to be OS-neutral.
  `mill-wiki-push/SKILL.md:12` references `.millhouse/millpy-wikipush.ps1` as the
  manual invocation path — that wrapper is a Windows-only shortcut created by the
  Windows-only wrapper step (`_shortcuts.py`, skipped on POSIX). Add a
  parenthetical that on POSIX the operator runs `millpy-wikipush.py` directly.
- **Regression guard (light).** Add a `test-guards.py` check that flags any
  SKILL.md venv-existence check (a shell `[ ! -f … .venv/Scripts/python.exe ]`
  test, or the equivalent `test -f … Scripts/python.exe`) that is not paired
  with a `.venv/bin/python` test in the same block, so a future Windows-only
  venv check cannot silently reintroduce the `mill-go` bug. This is a **coarse
  per-file tripwire**, not a per-block proof: it is scoped to the venv-existence
  idiom specifically (matching on the `Scripts/python.exe` existence-test text)
  rather than any mention of the string, so a doc that merely *names* the
  Windows path in prose does not trip it. Accepted as sufficient for the two
  known files (`mill-setup`, fixed `mill-go`); if the guard proves awkward to
  scope to the idiom, the fallback is the simpler per-file rule (any line naming
  `Scripts/python.exe` must also name `bin/python` in the same file) with a
  comment stating its coarseness. `mill-setup` and the fixed `mill-go` both
  satisfy either form.

**Out:**

- **psmux / pwsh dispatch.** `mill-config.yaml`'s `llm.claude.dispatch: psmux`,
  `psmux.shell_path: pwsh`, `_psmux.py`, `_psmux_capture.py`,
  `millpy-claude-sub.py`, and their PowerShell wrapper generation. millhouse uses
  **Agent Dispatch** (the default `dispatch: agent`); psmux is unused tooling.
  Explicitly not touched — no POSIX equivalent, no doc note, no code change.
- **`linting/SKILL.md` "PowerShell rules (placeholder)" section.** A genuine
  placeholder for a future `.ps1` convention. Harmless; left as-is.
- **The 5 pre-existing non-platform bugs** listed in the proposal
  (`millpy-merge-in-subagent.py` exit code; `test-language-skills-directive.py`
  stale fixture; `test-millpy-spawn.py`/`test-millpy-claim.py` `Path.exists`
  over-patching; `test-review-cli.py` hub_root/git_root regression). Separate
  work — not caused by this port.
- **Already-completed work** on `main` and parent `hanf/linux-port-more`
  (`mill-setup`, `_winenv.py`, `_gitignore.py`, `vscode-tasks.json`,
  `update-plugins.sh`, the test-fixture fixes). Not re-done.
- **Windows-only guarded code paths** (`_vscode_processes.py` ctypes,
  `_worktree.py` Get-CimInstance, `_subprocess_util.py`/`wiki/_client.py`
  `CREATE_NO_WINDOW`) — already correctly `os.name`/`sys.platform`-guarded.
  Verified, not modified.

## Decisions

### psmux-out-of-scope

- Decision: psmux/pwsh dispatch is entirely out of scope — no code change, no
  documentation note.
- Rationale: millhouse dispatches via Agent Dispatch (`dispatch: agent`, the
  configured default). psmux is unused; spending effort making it POSIX-capable
  or even documenting it as Windows-only adds surface with zero payoff.
- Rejected: (a) declaring it Windows-only with a config-comment note — still
  touches a subsystem nobody runs; (b) making `shell_path` OS-aware / full POSIX
  psmux support — pure scope creep on dead tooling.

### one-modest-task

- Decision: single task, single plan, a small number of batches — not the
  original proposal's large batched DAG.
- Rationale: the sweep the proposal feared is already done. What remains is a
  handful of independent, small edits (one real bug fix, one dead-config
  deletion, one script port, a couple doc fixes, one guard test).
- Rejected: full batched-DAG framing — oversized for the actual remaining work.

### delete-dead-mill-test-python

- Decision: delete the `MILL_TEST_PYTHON` key from root `.claude/settings.json`.
- Rationale: it is consumed nowhere in the repo and points at a nonexistent
  Windows path. Deleting dead config is cleaner than porting a value nothing
  reads. If removing it empties the `env` object, drop the object too so the
  file is `{}` (or a minimal valid settings file).
- Rejected: (a) porting it to a portable/relative value — invents a live meaning
  for a dead var; (b) leaving it — a committed absolute `C:\` path is misleading
  on every non-Windows checkout.

### port-bootstrap-test

- Decision: add `test-bootstrap.sh` as the POSIX counterpart of
  `test-bootstrap.ps1`; keep the `.ps1` for Windows.
- Rationale: it is the only Layer-01 integration test; making it runnable on
  Linux matches the established `update-plugins.ps1` → `.sh` precedent and lets
  the port be verified end-to-end on the machine it was developed on.
- Rejected: leaving it Windows-only — the Layer-01 path would be untestable on
  POSIX, undercutting the dual-support goal.

### fix-both-mill-go-checks-identically

- Decision: apply the dual-existence pattern to *both* venv-check blocks in
  `mill-go/SKILL.md`, worded identically, matching `mill-setup/SKILL.md:74`.
- Rationale: two copies of the same broken check; diverging their fixes invites
  a future half-fix. Reusing the existing, proven `mill-setup` phrasing keeps the
  convention singular.
- Rejected: fixing only the first occurrence, or introducing a new idiom.

## Technical context

- **The dual-existence idiom** (`mill-setup/SKILL.md:74`):
  `test -f "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" && echo … || echo …`. `uv
  sync` produces `.venv/bin/python` on POSIX and `.venv/Scripts/python.exe` on
  Windows; checking which is on disk beats branching on `uname`/`$OS`. The
  `mill-go` fix is the guard form of the same idea:
  ```bash
  if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" ] && \
     [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
      echo "[mill-go] venv missing -- attempting uv sync"
      uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
      if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" ] && \
         [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
          echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
          exit 1
      fi
  fi
  ```
  Applied verbatim to both blocks (≈ lines 240–246 and 624–630); line numbers
  will drift as the file is edited — anchor on the `if [ ! -f
  "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then` text, of which there
  are exactly four occurrences (two outer + two inner across the two blocks).
- **The established `os.name` convention** (`_junction.py`, `_subprocess_util.py`,
  `wiki/_client.py`): add a POSIX branch beside the Windows one; never delete the
  Windows path. This task adds no new script guards — the existing ones are
  already correct — but any change must preserve the pattern.
- **`_shortcuts.py`** writes the `.cmd`/wrapper shortcuts (`millpy-wikipush`
  among them) and is invoked only by the Windows-only wrapper step of
  `mill-setup` (Phase 4.7, skipped on POSIX). Hence there is no
  `millpy-wikipush.ps1` on a POSIX box — the `mill-wiki-push/SKILL.md` doc fix
  must reflect that (run the `.py` directly).
- **`test-bootstrap.ps1`** exercises the M1.1–M1.4 scripts against a throwaway
  wiki + hub pair, asserting mill-add's single-commit behavior, sidebar
  contents, and mill-list output. It runs no pytest/fixtures — it is a
  standalone script driving real scripts via `sys.executable`. The `.sh` port
  reproduces the same assertions in POSIX shell, using `.scratch/` for the
  throwaway pair and `PYTHONIOENCODING=utf-8`.
- **`test-guards.py`** already houses ASCII-only / no-unicode-arrow guards over
  the tree; the new venv-check guard belongs there, following its existing
  file-walk + allowlist structure.
- **Parent branch is `hanf/linux-port-more`** (not yet merged to `main`); this
  task branches from it and inherits the test-fixture fixes. Merge target is the
  parent, per mill's normal flow.

## Constraints

- **Dual support, never replacement.** Every change keeps Windows working. No
  Windows path is deleted; POSIX branches are added beside them.
- **ASCII-only stdout** in any `print()`/`_log()`/shell `echo` added (Windows
  cp1252 crashes on non-ASCII). Use ` -- ` for em dash, ` -> ` for arrows.
- **No `/tmp` / `$env:TEMP`.** The `.sh` test uses `.scratch/` for fixtures.
- **`${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths** in any shell snippet
  (already true of the `mill-go` blocks).
- **Docs/skills are the deliverable surface here** as much as code — SKILL.md
  edits must stay faithful to how the scripts actually behave on each OS.

## Testing

- **`mill-go` venv-check fix:** primary regression protection is the new
  `test-guards.py` check (any SKILL.md line naming `.venv/Scripts/python.exe`
  must also name `.venv/bin/python` in the same file). TDD candidate: write the
  guard first, watch it fail against the current unfixed `mill-go/SKILL.md`, then
  fix the two blocks to green. Also sanity-run the corrected snippet's logic
  mentally/locally on POSIX (the `bin/python` branch must short-circuit the
  HALT).
- **`.claude/settings.json` deletion:** no automated test (dead config). Verify
  by grep that nothing reads `MILL_TEST_PYTHON` post-change and that the file is
  still valid JSON.
- **`test-bootstrap.sh`:** the port *is* the test — run it on this Linux machine
  and confirm it passes (single commit, sidebar contains task, mill-list output).
  It is an integration test (`plugins/mill/integration_tests/`), run manually,
  not part of `run-all.py`. Assumes a synced venv + `git` present (same
  preconditions as the `.ps1`); on a missing prerequisite it exits nonzero with
  a message rather than skipping — a silent skip that looks like a pass is the
  failure mode to avoid.
- **Doc fixes (`_vscode.py`, `mill-wiki-push/SKILL.md`):** no behavioral test;
  the guard suite (`test-guards.py`) must stay green after edits.
- **Whole-suite gate:** `plugins/mill/unit_tests/run-all.py` must stay green
  after all changes (verify command must start with `PYTHONPATH= ` per project
  convention so the subprocess loads worktree code, not the cache).

## Q&A log

- **Q:** psmux/pwsh dispatch — Windows-only note, OS-aware default, or full POSIX
  support? **A:** [auto-pick] Out of scope entirely. **Why:** operator confirmed
  millhouse uses Agent Dispatch and psmux is unused — no code change, not even a
  doc note.
- **Q:** Task shape — one modest task or the original batched DAG? **A:**
  [auto-pick] One modest task, single plan, few batches. **Why:** the feared
  sweep is already done; remaining work is a handful of small independent edits.
- **Q:** `MILL_TEST_PYTHON` dead var — delete, portable-ize, or leave? **A:**
  [auto-pick] Delete the key. **Why:** consumed nowhere; a committed absolute
  `C:\` path is misleading on non-Windows checkouts.
- **Q:** `test-bootstrap.ps1` — add a `.sh` counterpart or leave Windows-only?
  **A:** [auto-pick] Add `test-bootstrap.sh`. **Why:** only Layer-01 integration
  test; matches the `update-plugins.ps1` -> `.sh` precedent and lets the port be
  verified end-to-end on Linux.
- **Q:** Stale doc mentions (`_vscode.py` pwsh comments, `mill-wiki-push`
  `.ps1` path) — fix or leave? **A:** [auto-pick] Fix; leave `linting/SKILL.md`
  placeholder as-is. **Why:** the mentions misdescribe actual OS behavior; the
  linting section is a deliberate future-work placeholder.
