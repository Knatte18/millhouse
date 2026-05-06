# Discussion: 5 (A) — mill-bg.py: project-lokal backgrounding

```yaml
task: 5 (A) — mill-bg.py: project-lokal backgrounding
slug: mill-bg-helper
status: discussing
parent: main
```

## Problem

When the agent uses the Bash tool's `run_in_background: true` flag to launch a long-running command (e.g. `millpy-review-plan.py`), CC's harness writes stdout/stderr to `AppData\Local\Temp\claude\<session>\tasks\<id>.output`. This path is outside mill's control, inaccessible via normal polling, and violates the `.scratch/` convention that all ephemeral files must live in the project-local `.scratch/` directory. The user wants to keep `run_in_background: true` as a capability — backgrounding long review calls is important — so the fix must provide an alternative that controls where output lands, not eliminate backgrounding entirely.

## Scope

**In:**
- New `plugins/mill/scripts/millpy-bg.py` CLI script (launcher + worker mode, self-contained)
- Add `"millpy-bg"` to `SHORTCUT_SCRIPTS` in `plugins/mill/scripts/_shortcuts.py`
- Unit tests at `plugins/mill/unit_tests/test-millpy-bg.py`
- Update `plugins/mill/skills/mill-go/SKILL.md` to document `millpy-bg` as the required backgrounding method for review calls
- Update `plugins/mill/skills/mill-start/SKILL.md` to document `millpy-bg` for the discussion-review phase

**Out:**
- No changes to `_subprocess_util.py` — `millpy-bg` does its own Popen without that helper
- No changes to review scripts (`millpy-review-*.py`) themselves
- No changes to `_review_*.py` backend helpers
- No re-running of mill-setup (shortcut PS1 generation is Phase 4.7; updating `SHORTCUT_SCRIPTS` is sufficient — the next mill-setup run picks it up)
- No `mill-plan` or `mill-merge` SKILL.md changes

## Decisions

### Script name: `millpy-bg.py`

- Decision: Name the script `millpy-bg.py`, not `mill-bg.py`.
- Rationale: Every other user-callable CLI script in `plugins/mill/scripts/` uses the `millpy-` prefix. `_shortcuts.py` wraps `millpy-*` stems. Consistency removes a special case.
- Rejected: `mill-bg.py` (proposed name) — inconsistent with all sibling scripts.

### Self-worker architecture

- Decision: `millpy-bg.py` runs in two modes. **Launcher mode** (default): resolves the log path, spawns `sys.executable millpy-bg.py --_worker --log <path> -- <cmd>` as a detached process, prints `pid=<N> log=<path>` to stdout, exits immediately. **Worker mode** (`--_worker` flag): opens the log file, runs `<cmd>` synchronously via `subprocess.run`, appends the sentinel, exits. The worker uses only stdlib.
- Rationale: Directly spawning `<cmd>` cannot append a sentinel after it exits. The self-invocation approach stays in one file, avoids a separate `_bg_worker.py` helper, and keeps the worker mode independently testable.
- Rejected: Separate `_bg_worker.py` helper module (more files, no gain); directly spawning `<cmd>` (no sentinel possible).

### Completion sentinel

- Decision: Worker mode appends `\n[mill-bg] EXIT <code>\n` to the log after `<cmd>` exits.
- Rationale: The agent polls by reading the log and checking for `[mill-bg] EXIT`. Without the sentinel, the agent must check PID liveness (fragile; PIDs recycle on Windows). With it, a simple string search in the log is unambiguous.
- Rejected: No sentinel (agent must infer completion from the child's own output, e.g. the JSON line from review scripts — too fragile).

### Windows process detachment flags

- Decision: On Windows, spawn the worker with `creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB`. On non-Windows, use `start_new_session=True`.
- Rationale: CC on Windows likely runs under a Job Object. Without `CREATE_BREAKAWAY_FROM_JOB`, child processes remain in that job and are killed when CC's job terminates. On machines where the job doesn't permit breakaway, the flag is silently ignored — no error.
- Rejected: Omitting `CREATE_BREAKAWAY_FROM_JOB` — risks the background process being killed when CC's session ends, defeating the purpose.

### Stdout format

- Decision: Launcher prints exactly `pid=<N> log=<path>` on a single line to stdout. Nothing else.
- Rationale: Simple key=value; the agent reads these two values to track the process. Not JSON — this is a tiny utility, not part of the structured JSON pipeline used by review scripts.
- Rejected: JSON output — overkill for two values.

### Log path format

- Decision: `<git_root>/.scratch/bg-<YYYYMMDD-HHMMSS>-<slug>.log`
- Rationale: Timestamp ensures uniqueness across repeated invocations with the same slug. `.scratch/` is the canonical ephemeral directory. The slug makes the file human-identifiable.
- Rejected: Using only the slug (non-unique across runs); using only a timestamp (non-identifiable).

### Monitoring pattern in SKILL.md

- Decision: After invoking `millpy-bg`, the agent polls by issuing a regular synchronous Bash `cat .scratch/bg-*.log` call and checking for `[mill-bg] EXIT`. Document this in the updated SKILL.md files.
- Rationale: Simple; no extra tool dependency. The CC Monitor tool would also work but adds complexity.
- Rejected: CC Monitor tool (more elegant but not necessary).

### SKILL.md update scope

- Decision: Update both `mill-go/SKILL.md` and `mill-start/SKILL.md`.
- Rationale: mill-go calls code-review scripts synchronously per batch — these can run for several minutes and the agent may need to background them. mill-start's discussion-review phase has the same issue. Both must document the `millpy-bg` pattern so the agent does not fall back to `run_in_background: true`.
- Rejected: mill-go only (mill-start has the same backgrounding need); neither (leaves the bug unaddressed in SKILL.md).

## Technical context

**`millpy-bg.py` — new script:**
- Launcher mode: uses `argparse`. `--slug` names the log file. Everything after `--` is the command to background. Resolves `<git_root>` via `git rev-parse --show-toplevel` (subprocess call). Creates `.scratch/` if absent. Spawns the worker via `subprocess.Popen` with no stdin/stdout/stderr (all devnull in launcher; the worker opens its own log). Prints `pid=<N> log=<path>`.
- Worker mode (`--_worker --log <abs-path> -- <cmd>`): opens log in write mode, runs `<cmd>` via `subprocess.run(stdout=log, stderr=subprocess.STDOUT)`, appends sentinel. Imports only stdlib. No mill helpers imported in worker mode.
- Top-level imports in the file must be guarded or deferred so the worker path (`--_worker`) can execute without `pyyaml` or any mill module on sys.path.

**`_shortcuts.py` — `plugins/mill/scripts/_shortcuts.py`:**
- `SHORTCUT_SCRIPTS` list: add `"millpy-bg"` at an appropriate position. The template `shortcut-wrapper.ps1` needs no change — it's already parameterised by script name.
- `write_all()` needs no change.

**`_timestamp.py`:** Use `_timestamp.now_utc_iso()` in launcher mode for the log filename timestamp? No — `_timestamp` is a mill helper. Use `datetime.utcnow().strftime("%Y%m%d-%H%M%S")` directly in the launcher to keep the launcher's git-root resolution path free of mill imports. (Worker mode uses stdlib only anyway.)

**Shortcut wrappers in `.millhouse/`:** existing `.py` wrappers are legacy. The next `mill-setup` run (Phase 4.7) will generate the `.ps1` wrapper. This task does not run mill-setup.

**SKILL.md invocation example (for mill-go and mill-start):**
```powershell
# Background the review call — do NOT use run_in_background: true
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.ps1" `
    --slug review-discussion-r1 -- `
    uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
# Returns: pid=<N> log=<abs-path>
# Poll until done:
#   cat <log-path>  → look for "[mill-bg] EXIT"
```

Wait — the shortcut wrapper is a PS1 file that itself calls `uv run`. The agent invokes the PS1 directly via Bash, not via `uv run`. The command above should be:
```powershell
.millhouse/millpy-bg.ps1 --slug review-discussion-r1 -- uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
```
Or, since the agent uses Bash (not PS1 directly), use the `uv run` form:
```bash
uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
    --slug review-discussion-r1 -- \
    uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-discussion.py"
```

**`_subprocess_util.py`:** Not used by `millpy-bg.py`. The launcher does its own minimal Popen; the worker does `subprocess.run`. This avoids importing mill infrastructure in the worker path.

**Argument parsing edge case:** `argparse` with `nargs=argparse.REMAINDER` does not reliably handle `--` as a separator. Instead, find `"--"` in `sys.argv` manually and split there.

## Testing

**`test-millpy-bg.py` — unit tests:**

Launcher mode tests (mock `subprocess.Popen`, mock `git rev-parse`):
- Correct log path format: `bg-<YYYYMMDD-HHMMSS>-<slug>.log` under `.scratch/`
- `.scratch/` created if absent
- Popen called with correct detachment flags on Windows (mock `os.name == "nt"`)
- Popen called with `start_new_session=True` on non-Windows
- Stdout contains `pid=<N> log=<path>` and nothing else
- `--slug` missing → exits non-zero with message
- No `--` separator → exits non-zero with message

Worker mode tests (no mocking needed; run in a tempdir):
- Runs a simple command (`python -c "print('hello')"`)
- Log file contains the command's stdout
- Log file ends with `[mill-bg] EXIT 0`
- Non-zero exit command → sentinel shows correct code (`[mill-bg] EXIT 1`)
- Log file is created if parent dir exists

**`test-shortcut-wrapper.py` — existing test:**
- After adding `"millpy-bg"` to `SHORTCUT_SCRIPTS`, the existing count assertion will fail until updated. Update expected count from 13 to 14.

## Q&A log

- **Q:** Script name `mill-bg.py` or `millpy-bg.py`? **A:** `millpy-bg.py` — consistent with all other CLI scripts.
- **Q:** Should `run_in_background: true` be forbidden entirely and replaced with synchronous calls? **A:** No — the user explicitly wants backgrounding as a capability. `millpy-bg` is the right fix.
- **Q:** Completion sentinel needed? **A:** Yes — `[mill-bg] EXIT <code>` makes polling unambiguous.
- **Q:** Windows `CREATE_BREAKAWAY_FROM_JOB` flag? **A:** Yes — CC likely runs in a Job Object; without it the background process gets killed when CC's session ends.
- **Q:** Which SKILL.md files to update? **A:** Both mill-go and mill-start — both call review scripts that can take minutes.
- **Q:** Monitoring pattern? **A:** Bash polling (`cat <log>`, check for sentinel string).
