# Discussion: Set MILL_PYTHON via mill-setup, use in all skill invocations

```yaml
task: Set MILL_PYTHON via mill-setup, use in all skill invocations
slug: mill-python-env-var
status: discussing
parent: main
```

## Problem

Every mill SKILL.md and both CLAUDE.md files reference the mill Python executable
as the literal string `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"`. With
33 occurrences in mill-go alone and 18 in mill-setup, this path fills Claude's
context window on multi-step tasks and must be re-typed when the plugin cache
path changes.

The fix is to introduce a single env var, `MILL_PYTHON`, that holds the expanded
path. mill-setup writes it to `~/.claude/settings.json` (global user-level CC
settings) so it is available in every CC session on the machine — including task
worktrees whose git root differs from the hub. All skill invocations then
reference `"$MILL_PYTHON"` instead of the full path. mill-setup refreshes the
value on every re-run, so updating the plugin version via `update-plugins.ps1`
and re-running `/mill-setup` is all that is needed to keep the path current.

## Scope

**In:**

- `plugins/mill/skills/mill-setup/SKILL.md` — add Phase 4.8 (write `MILL_PYTHON`
  to `~/.claude/settings.json`), update Phase 8 verification check, and update
  the "How to invoke helpers" parenthetical on line 69 (currently says "mill-go
  uses an equivalent form with `$MILL_PYTHON`, an alias defined in its Step 0
  block" — replace with "a CC env var written by mill-setup")
- `plugins/mill/skills/mill-go/SKILL.md` — replace all 33 occurrences
- 22 other `plugins/mill/skills/*/SKILL.md` files — replace 1–14 occurrences each
  (full list: git-commit, mill-abandon, mill-add, mill-autofix, mill-claim,
  mill-cleanup, mill-color, mill-fold, mill-ghissues-to-tasks, mill-groom,
  mill-inspect, mill-merge-in, mill-plan, mill-resume, mill-skills-from-scripts,
  mill-skills-index, mill-spawn, mill-start, mill-status, mill-terminal,
  mill-vscode, mill-wiki-push)
- `CLAUDE.md` (hub project root) — update Script invocation canonical form and
  exception note
- `~/.claude/CLAUDE.md` (user-level) — update the mill script path reference

**Out:**

- `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix — stays inline in every
  command; moving it to the env block is a separate concern
- Renaming `CLAUDE_PLUGIN_ROOT` — that name is set by the CC plugin system;
  mill does not own it
- Python scripts under `plugins/mill/scripts/` — no runtime code changes; this
  is documentation-only
- Unit tests — no code paths change; verification is a grep check

## Decisions

### target-env-file

- **Decision:** Write `MILL_PYTHON` to the `"env"` block of `~/.claude/settings.json`
  (global user-level CC settings).
- **Rationale:** CC loads this file for every session on the machine regardless of
  which project or worktree is active. Task worktrees (e.g. `wts/mill-python-env-var`)
  have their own git root and do NOT inherit a hub-level `.claude/settings.local.json`,
  so a project-level file would silently fail for all mill-plan / mill-go runs.
  The Phase 4.8 snippet uses `setdefault('env', {})` to create the `env` block
  if absent — no prior bootstrapping is required.
- **Rejected:** Hub's `.claude/settings.local.json` — not inherited by task
  worktrees; Windows User env var (same mechanism as PYTHONPATH) — takes effect
  only in new terminal sessions opened after mill-setup, not in the current CC
  session.

### mill-setup-bootstrapper-exception

- **Decision:** mill-setup's own SKILL.md keeps the full
  `"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"` form for all its Bash
  commands. All other SKILL.md files use `"$MILL_PYTHON"`.
- **Rationale:** mill-setup is the skill that WRITES the env var. On a fresh
  machine `MILL_PYTHON` is not yet set when mill-setup first runs. Writing the
  variable and then using it within the same CC session is not possible because
  CC reads `settings.json` at startup; the env var only becomes active after a
  restart. Using a self-bootstrapping fallback (`MILL_PYTHON=${MILL_PYTHON:-"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"}`)
  was considered but adds complexity to every command block without benefit once
  mill-setup has been run.
- **Rejected:** Self-bootstrapping fallback header in mill-setup — more code,
  still doesn't eliminate the full path from the skill.

### settings-json-write-mechanism

- **Decision:** Phase 4.8 of mill-setup uses an inline Python snippet to
  read `~/.claude/settings.json`, update `.env.MILL_PYTHON`, and write it back.
- **Rationale:** mill-setup already uses inline Python for all its other mutations.
  The operation is a simple JSON read-modify-write; no new script is warranted.
  Python's `json` module is available through the venv. The write is idempotent:
  if the existing value matches the computed path, no write occurs.
- **Rejected:** New `millpy-settings-env.py` script — over-engineered for a
  single key; `jq` one-liner — `jq` may not be present on Windows.

### pythonpath-prefix-stays-inline

- **Decision:** The `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` prefix remains
  in every command unchanged.
- **Rationale:** Moving it is out of scope. PYTHONPATH is already set as a
  Windows User env var by Phase 4.7, so the inline prefix is redundant but
  harmless. Removing it would widen the diff with no correctness benefit.
- **Rejected:** Moving PYTHONPATH to the env block — separate task.

## Technical context

### Files changed

All changes are in `plugins/mill/skills/` and the two `CLAUDE.md` files. No
Python scripts in `plugins/mill/scripts/` are modified.

### Phase 4.8 logic

Insert as a new phase between Phase 4.7 (PS1 wrappers + PYTHONPATH User env var)
and Phase 4.9 (hub_relative_path). The snippet:

```python
import json, os
from pathlib import Path

mill_python = str(Path(os.environ['CLAUDE_PLUGIN_ROOT']) / '.venv' / 'Scripts' / 'python.exe')
settings_path = Path.home() / '.claude' / 'settings.json'

data = json.loads(settings_path.read_text(encoding='utf-8'))
env_block = data.setdefault('env', {})
if env_block.get('MILL_PYTHON') == mill_python:
    print(f'MILL_PYTHON already correct: {mill_python}')
else:
    env_block['MILL_PYTHON'] = mill_python
    settings_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f'MILL_PYTHON set: {mill_python}')
```

The snippet must be wrapped in the standard mill command prefix:
`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" -c "..."`.
(mill-setup cannot use `$MILL_PYTHON` here — bootstrapper exception.)

After writing, emit the note: "MILL_PYTHON set in ~/.claude/settings.json. Takes
effect in the next CC session — existing sessions must restart to pick it up."

### Phase 8 verification addition

Add a check: read `~/.claude/settings.json`, confirm `.env.MILL_PYTHON` equals
`${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` (where `CLAUDE_PLUGIN_ROOT` is
the runtime-expanded value). Print the verified path in the success summary
alongside PYTHONPATH.

### CLAUDE.md (hub) changes

`CLAUDE.md` line 48 — canonical form changes from:
```
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"
```
to:
```
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-X.py"
```

Line 51 — the exception note "mill-go uses `$MILL_PYTHON`; nested calls after
`--` in millpy-bg inherit PYTHONPATH automatically and must not carry the prefix."
Update: `$MILL_PYTHON` is now the standard for all skills; mill-setup is the
bootstrapper exception; nested `--` calls still do not carry the prefix.

Add to the Script invocation section a one-line bootstrapper note: "Exception:
mill-setup's own Bash commands keep the full path — it is the skill that writes
the env var and cannot use it in the same session."

### ~/.claude/CLAUDE.md change

Line 7 currently reads: "For mill scripts, always use the explicit cache venv:
`${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe`."

Update to: "For mill scripts, use `$MILL_PYTHON` (set by mill-setup in
`~/.claude/settings.json`). Exception: mill-setup itself uses the full path
`${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe` since it is the bootstrapper."

### Replacement pattern

In every non-mill-setup SKILL.md, replace:
```
"${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe"
```
with:
```
"$MILL_PYTHON"
```
This is a simple global string substitution — no surrounding context needs to
change. The `PYTHONPATH=` prefix before each command is untouched.

### Idempotency

Phase 4.8 is idempotent: compares existing `.env.MILL_PYTHON` against the
computed value; writes only if they differ. Re-running mill-setup after
`update-plugins.ps1` installs a new plugin version will update `MILL_PYTHON` to
reflect the new `CLAUDE_PLUGIN_ROOT`.

## Testing

No unit tests are required — this is a documentation-only change affecting
SKILL.md files and CLAUDE.md. Verification is:

1. **Grep check** (plan should include this as a verify step): after all
   replacements, `grep -r '\.venv/Scripts/python\.exe' plugins/mill/skills/`
   should return hits ONLY in `mill-setup/SKILL.md`. Zero hits elsewhere.

2. **Phase 4.8 manual verification**: run `/mill-setup` on this machine; confirm
   `python -c "import json; d=json.load(open('~/.claude/settings.json')); print(d['env']['MILL_PYTHON'])"` returns the correct path.

3. **Roundtrip check**: in a fresh CC session after mill-setup, run
   `echo $MILL_PYTHON` in a Bash tool call and confirm it expands to the expected path.

## Q&A log

- **Q:** Which settings file should receive `MILL_PYTHON`? **A:** `~/.claude/settings.json` (global user-level) — task worktrees don't inherit hub-level `.claude/settings.local.json`, so user-level is the only option that works everywhere.
- **Q:** Should mill-setup's own SKILL.md use `$MILL_PYTHON` in its commands? **A:** No — mill-setup is the bootstrapper; it keeps the full path form. All other skills use `$MILL_PYTHON`.
- **Q:** Should `PYTHONPATH=` prefix also move to the env block? **A:** No — stay inline; separate concern; PYTHONPATH already handled as Windows User env var in Phase 4.7.
- **Q:** Should `CLAUDE_PLUGIN_ROOT` be renamed? **A:** No — it is set by the CC plugin system; mill does not control the name.
- **Q:** How should Phase 4.8 write settings.json? **A:** Inline Python — read/modify/write with `json` module; idempotent; no new script needed. Claude may prompt for permission to access `~/.claude/settings.json`; that is acceptable.
