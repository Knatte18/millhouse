# Batch: posix-portability-fixes

```yaml
task: "Port mill to POSIX, not just Windows"
batch: "posix-portability-fixes"
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py
depends-on: []
```

## Batch Scope

Delivers every small, self-contained POSIX-portability fix identified in
`discussion.md` except the bootstrap-test port: the one real bug (the
`mill-go/SKILL.md` venv-existence check that HALTs on Linux), a new regression
guard that pins the venv-check idiom, the dead `MILL_TEST_PYTHON` config
deletion, and two stale-doc corrections. These are grouped as one batch because
each is an independent one-to-few-line edit that a single Sonnet session holds
trivially, and because Card 2's guard (in `test-guards.py`) must land in the
same batch as Card 1's `mill-go` fix so the batch `verify:` (which runs
`test-guards.py`) sees the fixed file and passes — the guard would FAIL against
an unfixed `mill-go/SKILL.md`. Card ordering within the batch is therefore
significant: the `mill-go` fix (Card 1) precedes the guard (Card 2). No external
interface is produced for a later batch. Several cards have a deliberately small
`Context:` — these are single-file surgical edits whose end-state is fully
determined by the edited file plus the one adjacent file that explains why the
change is safe.

## Cards

### Card 1: Fix mill-go venv-existence check for POSIX

- **Context:**
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-go/SKILL.md` there are exactly
  four occurrences of the shell line
  `if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then` (an outer
  and an inner test in each of two venv-check blocks — the per-batch-invocation
  block and the holistic-review block). Replace every one of the four with
  `if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/bin/python" ] && [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then`
  so the check only fires when NEITHER the POSIX venv (`.venv/bin/python`) NOR
  the Windows venv (`.venv/Scripts/python.exe`) exists. This mirrors the
  canonical dual-existence idiom documented in `mill-setup/SKILL.md:74`
  (`test -f ".../.venv/bin/python" && echo ... || echo ...`). Do not change the
  surrounding `uv sync` body, the echo strings, or the `HALT` messages. Keep the
  two blocks identical to each other after the edit.
- **Commit:** `fix(mill-go): make venv-existence check POSIX-aware`

### Card 2: Add venv-check regression guard to test-guards.py

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-setup/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-guards.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add a fifth check function
  `_check_no_windows_only_venv_check() -> int` to
  `plugins/mill/unit_tests/test-guards.py`, following the shape of the existing
  `_check_no_wiki_cwd` (print `FAIL: <rel>:<lineno>: ...` per hit and a single
  `PASS: ...` line otherwise; return 1 on any hit, 0 otherwise). The check
  scans every `SKILL.md` under `MILL_DIR / "skills"` (use `rglob("SKILL.md")`).
  For each file, detect lines matching the Windows-venv existence-test idiom via
  a compiled regex that requires a shell file-existence test immediately
  referencing the Windows venv path — pattern equivalent to
  `r"(\[\s*!?\s*-f|test\s+-f)[^\n]*\.venv/Scripts/python\.exe"`. If a file
  contains one or more such lines but does NOT contain the POSIX counterpart
  substring `.venv/bin/python` anywhere in the same file, record every matching
  line as a FAIL (the file has a Windows-only venv check with no POSIX branch).
  This is a deliberately coarse per-file tripwire, not a per-block proof, per
  the discussion's Regression-guard decision; note that in a short comment above
  the function. Wire the new check into `main()` with
  `rc |= _check_no_windows_only_venv_check()` after the existing four. Add a
  bullet for the new check to the module-level docstring's `Checks:` list, AND
  update the docstring header sentence "Four checks bundled into one test file"
  (near line 3) to "Five checks bundled into one test file" so the count prose
  matches. Keep all added text ASCII-only (no unicode arrows). After this card,
  `mill-setup/SKILL.md` and the Card-1-fixed `mill-go/SKILL.md` (both contain
  `.venv/bin/python`) must PASS.
- **Commit:** `test(guards): guard against Windows-only venv-existence checks in skills`

### Card 3: Delete dead MILL_TEST_PYTHON config key

- **Context:**
  - `_mill/discussion.md`
- **Edits:**
  - `.claude/settings.json`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Remove the `MILL_TEST_PYTHON` key (a hardcoded
  `C:\...\.venv\Scripts\python.exe` path) from `.claude/settings.json`. It is
  consumed nowhere in the repo (confirmed by grep in the discussion). Removing
  it empties the `env` object, so reduce the file to a valid empty JSON object
  `{}` followed by a trailing newline. Confirm the result parses as JSON before
  committing.
- **Commit:** `chore(config): drop dead MILL_TEST_PYTHON Windows path`

### Card 4: Correct stale pwsh comments in _vscode.py

- **Context:**
  - `plugins/mill/templates/vscode-tasks.json`
- **Edits:**
  - `plugins/mill/scripts/_vscode.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/scripts/_vscode.py`, two docstrings (the
  module docstring's `write_tasks` entry near line 27, and the `write_tasks`
  function docstring near line 123) describe the copied tasks.json as
  "auto-opening a pwsh terminal" / "auto-opens a pwsh terminal on folder open".
  The template (`plugins/mill/templates/vscode-tasks.json`) now uses VS Code's
  per-OS `${env:SHELL}` command, not a hardcoded `pwsh`. Reword both mentions to
  be OS-neutral, e.g. "auto-opening a terminal (via the OS default shell) on
  folder open". Change only the comment wording; do not alter any code or the
  `write_tasks` behavior. Keep the text ASCII-only.
- **Commit:** `docs(vscode): drop stale pwsh wording from _vscode.py comments`

### Card 5: Correct wrapper reference in mill-wiki-push SKILL

- **Context:**
  - `plugins/mill/scripts/_shortcuts.py`
- **Edits:**
  - `plugins/mill/skills/mill-wiki-push/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** `plugins/mill/skills/mill-wiki-push/SKILL.md:12` states the
  script "can also be run manually from `.millhouse/millpy-wikipush.ps1`". This
  is stale on two counts: `_shortcuts.py` renders `.cmd` wrappers and explicitly
  `unlink`s any legacy `.ps1` (see its module docstring and the `.ps1` unlink at
  the end of `write_all`), so a `.ps1` wrapper exists on no platform — the
  Windows wrapper is `millpy-wikipush.cmd`; and those wrappers are generated only
  by the Windows-only wrapper step (`mill-setup` Phase 4.7, skipped on POSIX), so
  no wrapper exists on Linux/macOS at all. Reword the sentence so it names the
  correct Windows wrapper `.millhouse/millpy-wikipush.cmd` (not `.ps1`) and adds
  that on POSIX there is no wrapper — the operator runs `millpy-wikipush.py`
  directly (the same inline `PYTHONPATH=`/`$MILL_PYTHON` form shown in the
  `## Run it` block just below). Do NOT leave any `.ps1` reference in the
  sentence. Keep the text ASCII-only.
- **Commit:** `docs(wiki-push): fix stale .ps1 wrapper ref (now .cmd) and note POSIX invocation`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py`
runs the single guard suite that this batch both extends (Card 2) and must keep
green. `test-guards.py` scans `plugins/mill/scripts/` and
`plugins/mill/skills/` (and `plugins/codeguide/`), so it covers the edits to
`mill-go/SKILL.md`, `test-guards.py`, `_vscode.py`, and `mill-wiki-push/SKILL.md`
against the ASCII-arrow, wiki-cwd, rmtree, anti-weakening, and the newly added
Windows-only-venv-check guards. The `mill-go` fix (Card 1) is validated
specifically by Card 2's new check: an unfixed `mill-go/SKILL.md` (Windows-only
existence test, no `.venv/bin/python`) would FAIL, the fixed one PASSes.
`.claude/settings.json` (Card 3) is not scanned by any guard — it is dead
config with no runnable surface, so its only verification is Card 3's own
JSON-parse confirmation; this is expected and does not weaken the batch gate.
Scoped to the single guard file (not `run-all.py`) because no other test
imports the edited files.
