# Discussion: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows

```yaml
task: mill-vscode/mill-spawn leak CLAUDE_CODE_CHILD_SESSION into spawned VS Code windows
slug: mill-vscode-spawn-session-leak
status: discussing
parent: main
```

## Problem

`millpy-vscode.py` launches the `code` CLI as a subprocess of the running Claude Code
session (both from the interactive worktree picker and from the spawn-and-open flow).
`subprocess.run` with no `env=` override inherits the full parent process environment,
including `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, and likely other
`CLAUDE_CODE_*` markers set by the *launching* session.

VS Code propagates its own process environment to its extension host and integrated
terminals. So any Claude Code session subsequently started inside the newly-opened
window inherits `CLAUDE_CODE_CHILD_SESSION=1`, flags itself a **child session**,
disables transcript saving ("Transcript saving is off — inherited
CLAUDE_CODE_CHILD_SESSION marker"), and enters manual mode — even though a
spawned worktree window is meant to host an **independent top-level session**.

Root cause: default OS subprocess env inheritance — the launcher never scrubs the
marker before spawning `code`. Source: GitHub issue #719.

## Scope

**In:**
- Strip all `CLAUDE_CODE_*`-prefixed environment variables from the child environment
  passed to the `code` subprocess launch in `millpy-vscode.py`.
- Both launch call sites in `millpy-vscode.py`: the interactive picker
  (`main()`, `subprocess.run(code_argv)`) and the spawn-and-open flow
  (`_spawn_and_open()`, `subprocess.run(_build_code_argv(launch_path))`).
- Unit test coverage asserting the scrubbed vars are absent from the env passed to
  `subprocess.run`, while unrelated vars (e.g. `PATH`) are preserved.

**Out:**
- `millpy-spawn.py` — confirmed (via grep across the script and both `mill-spawn`/
  `mill-vscode` SKILL.md files) that it never subprocess-spawns `code` itself; it only
  renders and writes `.vscode/settings.json` / `.vscode/tasks.json` via `_vscode.py`.
  The issue's mention of "millpy-spawn.py's vscode-open path" refers to the composed
  flow where `millpy-vscode.py --new` calls into `millpy-spawn.py`'s `main()` and then
  itself spawns `code` — already covered by the `_spawn_and_open` fix above. No change
  needed in `millpy-spawn.py`.
- `_vscode.py` — settings/tasks rendering only, no subprocess spawning; out of scope.
- `_subprocess_util.run` — not used by either launch site. The interactive picker call
  is explicitly commented as bypassing it ("must keep its console; do NOT route through
  `_subprocess_util.run`"), and `_spawn_and_open`'s call follows the same pattern for
  consistency. No change to `_subprocess_util.py`.
- Any env vars outside the `CLAUDE_CODE_*` prefix (e.g. `ANTHROPIC_*`, `CLAUDE_PLUGIN_ROOT`)
  — not implicated by the issue, not stripped.

## Decisions

### scrub-scope

- Decision: Strip by prefix match — every environment variable whose name starts with
  `CLAUDE_CODE_` — rather than an explicit allowlist of the 3 named vars
  (`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT`).
- Rationale: The issue itself hedges on the third var ("and likely
  `CLAUDE_CODE_ENTRYPOINT`"), signaling the reporter isn't certain of the complete
  marker set. A spawned VS Code window is meant to be a fully independent top-level
  session — there is no known legitimate case where a `CLAUDE_CODE_*` var from the
  launching session should leak into it. Prefix-based stripping is defensive against
  markers added later without requiring this fix to be revisited.
- Rejected: Explicit 3-var allowlist — matches the issue text most literally, but goes
  stale silently if a new marker is introduced elsewhere in the codebase.

### helper-location

- Decision: Add a private module-level helper (e.g. `_scrubbed_env() -> dict[str, str]`)
  inside `millpy-vscode.py`, used by both `subprocess.run` call sites in that file. Do
  not add a shared helper to `_vscode.py` or `_subprocess_util.py`.
- Rationale: Both real `code`-launch sites already live in `millpy-vscode.py`.
  `millpy-spawn.py` and `_vscode.py` have no launch site to share the helper with (see
  Scope/Out). Adding a cross-file abstraction for a single consumer file is unwarranted.
- Rejected: Shared helper in `_vscode.py` — anticipates a future second launch site
  that doesn't currently exist; violates YAGNI.

### env-copy-semantics

- Decision: Build the scrubbed env as a fresh dict comprehension over
  `os.environ.items()`, filtering out keys with the `CLAUDE_CODE_` prefix, rather than
  mutating a copy with `del`/`pop`. Absence of the vars (e.g. when `mill-vscode` is run
  outside a Claude Code session) is not an error condition — the filter is a no-op in
  that case.
- Rationale: Simplest correct form; no special-casing needed for "var not present".
- Rejected: `os.environ.copy()` + explicit `pop(key, None)` per named var — reintroduces
  the allowlist approach already rejected above.

## Technical context

- `plugins/mill/scripts/millpy-vscode.py` — the two launch sites needing the fix:
  - `_build_code_argv()` (`millpy-vscode.py:37`) builds the argv only; unaffected.
  - `_spawn_and_open()` (`millpy-vscode.py:132`): `subprocess.run(_build_code_argv(launch_path))`
    — no `env=` currently passed.
  - `main()` interactive picker (`millpy-vscode.py:275`): `subprocess.run(code_argv)`
    — no `env=` currently passed; comment at line 274 explicitly notes this call must
    NOT route through `_subprocess_util.run` (needs to keep its console).
- `plugins/mill/scripts/_vscode.py` — `render_settings`/`write_settings`/`write_tasks`
  only; no subprocess spawning, confirmed out of scope.
- `plugins/mill/scripts/millpy-spawn.py` — confirmed via grep it never calls
  `subprocess.run`/`Popen` for `code`; only writes `.vscode/settings.json` and
  `.vscode/tasks.json` through `_vscode.write_settings`/`write_tasks` (lines
  ~280–288). No fix needed here.
- `plugins/mill/scripts/_subprocess_util.py` — the shared `run()` wrapper used
  elsewhere in the codebase; explicitly bypassed by the interactive `code` launch (see
  comment at `millpy-vscode.py:274`), so the fix must scrub env inline in
  `millpy-vscode.py`, not by changing `_subprocess_util.run`'s defaults.
- `plugins/mill/unit_tests/test-millpy-vscode.py` — existing tests already mock
  `mill_vscode.subprocess.run` at every call site relevant to this fix (e.g. via
  `patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a}))`).
  These mocks currently discard `kwargs` (only capturing `argv`); the fix's tests need
  to capture `kwargs` too so they can assert on the `env` passed.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- **TDD candidate:** `_scrubbed_env()` helper in `millpy-vscode.py` — pure function,
  no I/O. Test with a fake env dict (do not mutate real `os.environ` in the test)
  containing a mix of `CLAUDE_CODE_*` keys and ordinary keys (e.g. `PATH`, `HOME`);
  assert the `CLAUDE_CODE_*` keys are absent from the result and the ordinary keys are
  preserved unchanged. Also cover the case where no `CLAUDE_CODE_*` keys are present
  (no-op, no error).
- **Integration into existing tests:** extend the `mock_subprocess_run` /
  `side_effect=lambda a, **kw: subprocess_calls.append(...)` call sites in
  `test-millpy-vscode.py` that exercise the interactive picker (`--slug`, numeric
  selection) and `--new`/spawn-and-open paths to also capture `kwargs` and assert:
  - `kwargs["env"]` is present (not `None`, i.e. the call sites now always pass an
    explicit scrubbed env rather than falling through to full inheritance).
  - None of `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`,
    `CLAUDE_CODE_ENTRYPOINT` (and generally no `CLAUDE_CODE_*` key) appears in
    `kwargs["env"]`, when the test harness injects one of these into `os.environ` via
    `monkeypatch`/`patch.dict` before invoking `main()`.
  - A control var unrelated to the prefix (e.g. `PATH`) is still present in
    `kwargs["env"]`, proving the scrub is a filter, not a full env drop.
- Cover both launch sites: the interactive picker (`subprocess.run(code_argv)` at
  `millpy-vscode.py:275`) and the spawn-and-open flow
  (`subprocess.run(_build_code_argv(launch_path))` at `millpy-vscode.py:132`).
- No end-to-end test that actually launches `code` or VS Code — out of scope,
  consistent with existing test suite's full mocking of `subprocess.run`.

## Q&A log

- **Q:** Which environment variables should be stripped before spawning `code` — the 3
  vars named in the issue, or a broader `CLAUDE_CODE_*` prefix match? **A:** [auto-pick]
  Prefix match on `CLAUDE_CODE_*`. **Why:** the issue itself is uncertain about the
  third var ("likely `CLAUDE_CODE_ENTRYPOINT`"), and a spawned window has no known
  legitimate use for any `CLAUDE_CODE_*` marker from the launcher; prefix stripping
  stays correct if new markers are added later.
- **Q:** Where should the env-scrub logic live — a helper local to `millpy-vscode.py`,
  or a shared helper in `_vscode.py`/`_subprocess_util.py`? **A:** [auto-pick] Local
  helper in `millpy-vscode.py`. **Why:** both real `code`-launch sites already live in
  that file; `millpy-spawn.py` and `_vscode.py` were confirmed (via grep) to have no
  launch site needing to share the helper, so a cross-file abstraction would be
  premature (YAGNI).
- **Q:** Does `millpy-spawn.py` need its own fix, given the issue brief names it
  alongside `millpy-vscode.py`? **A:** [auto-pick] No — confirmed via grep across
  `millpy-spawn.py` and both `mill-spawn`/`mill-vscode` `SKILL.md` files that
  `millpy-spawn.py` never subprocess-spawns `code`; the brief's phrasing describes the
  composed `millpy-vscode.py --new` flow (which calls into `millpy-spawn.py`'s `main()`
  for worktree creation, then spawns `code` itself), already covered by fixing
  `_spawn_and_open`.
