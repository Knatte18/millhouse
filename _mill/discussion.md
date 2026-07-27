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
  passed to every interactive top-level-session launch subprocess identified below.
- Both launch call sites in `millpy-vscode.py`: the interactive picker
  (`main()`, `subprocess.run(code_argv)`) and the spawn-and-open flow
  (`_spawn_and_open()`, `subprocess.run(_build_code_argv(launch_path))`).
- Both launch call sites in `millpy-terminal.py` (found during discussion review,
  round 1): `main()`'s `subprocess.run(["cmd", "/c", "claude", "--name", selected_slug], cwd=launch_path)`
  (Windows, line 118) and `subprocess.run(["claude", "--name", selected_slug], cwd=launch_path)`
  (POSIX, line 121). Same defect class as the VS Code launch sites — `claude --name
  <slug>` is meant to start an independent top-level Claude Code session in the
  selected worktree, one hop more direct than the VS Code case since it launches
  Claude Code itself, not an editor that may or may not later host a Claude session.
- A shared `_scrubbed_env()` helper (see `Decisions > helper-location`), used by all
  four launch sites above.
- Unit test coverage asserting the scrubbed vars are absent from the env passed to
  `subprocess.run` at each of the four sites, while unrelated vars (e.g. `PATH`) are
  preserved.

**Out:**
- `millpy-spawn.py` — confirmed (via grep across the script and both `mill-spawn`/
  `mill-vscode` SKILL.md files) that it never subprocess-spawns `code` itself; it only
  renders and writes `.vscode/settings.json` / `.vscode/tasks.json` via `_vscode.py`.
  The issue's mention of "millpy-spawn.py's vscode-open path" refers to the composed
  flow where `millpy-vscode.py --new` calls into `millpy-spawn.py`'s `main()` and then
  itself spawns `code` — already covered by the `_spawn_and_open` fix above. No change
  needed in `millpy-spawn.py`.
- `_vscode.py` — settings/tasks rendering only, no subprocess spawning; out of scope.
- `_llm_claude.py`'s three `claude -p` subprocess launches (lines 332, 358, 384),
  which already filter `os.environ` through a `STRIP_VARS` frozenset before spawning
  (found during discussion review, round 1 — see `_llm_claude.py:82-90`, "Git env vars
  that must NOT be inherited by spawned Claude sessions", #367). These are the
  subprocess/psmux dispatch mode's own reviewer/implementer/merge-in child-worker
  spawns — by design, those sessions ARE children of the orchestrating mill-go/mill-
  start session (that is the entire point of subprocess/psmux dispatch, as opposed to
  Agent-mode dispatch). Stripping `CLAUDE_CODE_CHILD_SESSION` from them would change
  behavior for a use case that may rely on being correctly marked a child session, with
  no reported symptom that it currently misbehaves. `STRIP_VARS` stays `GIT_*`-only;
  not extended to `CLAUDE_CODE_*` by this task.
- `_subprocess_util.run` — not used by the four in-scope launch sites. Both
  interactive-picker calls (`millpy-vscode.py`, `millpy-terminal.py`) are explicitly
  commented as bypassing it ("must keep its console; do NOT route through
  `_subprocess_util.run`"), and the `_spawn_and_open` call follows the same pattern for
  consistency. No change to `run()` or its defaults — see `Decisions > helper-location`
  for where the new shared scrub helper actually lives instead.
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

- Decision: Add a `scrub_env(prefix: str = "CLAUDE_CODE_") -> dict[str, str]` helper to
  `_subprocess_util.py`, imported by both `millpy-vscode.py` and `millpy-terminal.py`
  at all four launch call sites (see Scope/In).
- Rationale: Originally scoped to a single file (`millpy-vscode.py`) with no second
  consumer, which argued for a local private helper. Discussion review round 1
  surfaced `millpy-terminal.py` as a second file needing the identical scrub (see
  Scope/In) — with two consumer files, a local-to-one-file helper would force either
  duplication or an import of a "private" (`_`-prefixed function name still fine, but
  file-local) helper across files, so the helper moves to a shared module.
  `_subprocess_util.py` is already the shared home for subprocess-launch concerns in
  this codebase (both new call sites already import machinery adjacent to it, and its
  module docstring already centralises "subprocess invocation" concerns), and adding
  a plain filtering function there does not require routing through its `run()`
  wrapper — the interactive launchers still bypass `run()` for the console-ownership
  reason documented at each call site.
- Rejected: Local helper duplicated in both `millpy-vscode.py` and `millpy-terminal.py`
  — avoids adding an import but duplicates identical filtering logic in two files,
  the exact duplication YAGNI was originally invoked to avoid at a smaller scope.
- Rejected: Extend `_llm_claude.py`'s existing `STRIP_VARS` frozenset (see Scope/Out)
  to also cover `CLAUDE_CODE_*` and reuse it here — `STRIP_VARS` is exact-match, not
  prefix-match (see `scrub-scope` decision above for why prefix-match was chosen), and
  `_llm_claude.py`'s spawn sites are a semantically different case (intentional child
  sessions, not top-level independent sessions — see Scope/Out) that this task
  deliberately does not touch. Precedent noted, not reused, per discussion review
  round 1 finding.

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
  elsewhere in the codebase; explicitly bypassed by both interactive launchers (see
  comment at `millpy-vscode.py:274` and `millpy-terminal.py:117`/`:120`). The new
  `scrub_env()` helper (see `Decisions > helper-location`) is added here as a plain
  function alongside `run()`, not a change to `run()`'s own defaults or signature.
- `plugins/mill/scripts/millpy-terminal.py` — the second file with the identical
  defect, found during discussion review round 1:
  - `main()` (`millpy-terminal.py:116-121`): Windows branch
    `subprocess.run(["cmd", "/c", "claude", "--name", selected_slug], cwd=launch_path)`
    (line 118); POSIX branch
    `subprocess.run(["claude", "--name", selected_slug], cwd=launch_path)` (line 121).
    Neither passes `env=`. Same "must keep its console — do NOT route through
    `_subprocess_util.run`" comment pattern as `millpy-vscode.py`.
- `plugins/mill/scripts/_llm_claude.py` — the existing `STRIP_VARS` precedent (see
  Scope/Out), found during discussion review round 1: a `frozenset` of `GIT_*` var
  names (`_llm_claude.py:82-90`), applied via
  `{k: v for k, v in os.environ.items() if k not in STRIP_VARS}` before three
  `claude -p` subprocess launches (lines 332, 358, 384) used by subprocess/psmux
  dispatch mode's reviewer/implementer/merge-in pipeline. Confirmed out of scope for
  this task (see Scope/Out and `Decisions > helper-location`'s rejected alternatives)
  — noted here so mill-plan doesn't independently rediscover and second-guess the
  exclusion.
- `plugins/mill/unit_tests/test-millpy-vscode.py` and
  `plugins/mill/unit_tests/test-millpy-terminal.py` — existing tests in both files
  already mock `subprocess.run` at every call site relevant to this fix (e.g. via
  `patch("mill_vscode.subprocess.run", side_effect=lambda a, **kw: subprocess_calls.append({"argv": a}))`
  and the equivalent `mill_terminal.subprocess.run` patches). These mocks currently
  discard `kwargs` (only capturing `argv`, or in one `test-millpy-terminal.py` case
  only `cwd`); the fix's tests need to capture the full `kwargs` too so they can assert
  on the `env` passed.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- **TDD candidate:** `scrub_env()` helper in `_subprocess_util.py` — pure function,
  no I/O. Test with a fake env dict (do not mutate real `os.environ` in the test)
  containing a mix of `CLAUDE_CODE_*` keys and ordinary keys (e.g. `PATH`, `HOME`);
  assert the `CLAUDE_CODE_*` keys are absent from the result and the ordinary keys are
  preserved unchanged. Also cover the case where no `CLAUDE_CODE_*` keys are present
  (no-op, no error).
- **Integration into existing tests:** extend the `mock_subprocess_run` /
  `side_effect=lambda a, **kw: subprocess_calls.append(...)` call sites in both
  `test-millpy-vscode.py` (interactive picker `--slug`/numeric-selection paths, and
  `--new`/spawn-and-open) and `test-millpy-terminal.py` (auto-select single-worktree
  path, and numeric-picker multi-worktree path) to also capture `kwargs` and assert:
  - `kwargs["env"]` is present (not `None`, i.e. the call sites now always pass an
    explicit scrubbed env rather than falling through to full inheritance).
  - None of `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`,
    `CLAUDE_CODE_ENTRYPOINT` (and generally no `CLAUDE_CODE_*` key) appears in
    `kwargs["env"]`, when the test harness injects one of these into `os.environ` via
    `monkeypatch`/`patch.dict` before invoking `main()`.
  - A control var unrelated to the prefix (e.g. `PATH`) is still present in
    `kwargs["env"]`, proving the scrub is a filter, not a full env drop.
- Cover all four launch sites: `millpy-vscode.py`'s interactive picker
  (`subprocess.run(code_argv)` at line 275) and spawn-and-open flow
  (`subprocess.run(_build_code_argv(launch_path))` at line 132); `millpy-terminal.py`'s
  Windows branch (`subprocess.run(["cmd", "/c", "claude", ...])` at line 118) and POSIX
  branch (`subprocess.run(["claude", ...])` at line 121).
- `_llm_claude.py`'s `STRIP_VARS`-based spawns are out of scope (see Scope/Out) — no
  test changes there.
- No end-to-end test that actually launches `code`, VS Code, or `claude` — out of
  scope, consistent with existing test suite's full mocking of `subprocess.run`.

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
  premature (YAGNI). **[Superseded in round 1 — see the `millpy-terminal.py` gap entry
  below; the helper moved to `_subprocess_util.py` once a second consumer file was
  confirmed.]**
- **Q:** Does `millpy-spawn.py` need its own fix, given the issue brief names it
  alongside `millpy-vscode.py`? **A:** [auto-pick] No — confirmed via grep across
  `millpy-spawn.py` and both `mill-spawn`/`mill-vscode` `SKILL.md` files that
  `millpy-spawn.py` never subprocess-spawns `code`; the brief's phrasing describes the
  composed `millpy-vscode.py --new` flow (which calls into `millpy-spawn.py`'s `main()`
  for worktree creation, then spawns `code` itself), already covered by fixing
  `_spawn_and_open`.
- **Q:** [discussion review round 1, GAP] `millpy-terminal.py` launches
  `claude --name <slug>` via the same unscrubbed `subprocess.run` pattern — is it in
  scope? **A:** [auto-pick] Yes — add to Scope/In and fix identically to the VS Code
  sites; this also moves the scrub helper to `_subprocess_util.py` (see
  `Decisions > helper-location`). **Why:** same defect class, same "must keep its
  console" constraint as the targeted picker, and arguably more severe since it
  launches Claude Code directly rather than an editor that may or may not host a Claude
  session later. Leaving it out while fixing the VS Code path would leave the more
  direct instance of the bug live.
- **Q:** [discussion review round 1, GAP] `_llm_claude.py` already has a `STRIP_VARS`
  env-filtering precedent for its `claude -p` subprocess spawns — should this task
  extend it to cover `CLAUDE_CODE_*`, and should `helper-location` acknowledge it?
  **A:** [auto-pick] Acknowledge the precedent in `helper-location`'s rejected
  alternatives; do not extend `STRIP_VARS` or touch `_llm_claude.py`. **Why:** those
  three spawn sites are the subprocess/psmux dispatch mode's own reviewer/implementer/
  merge-in child-worker sessions — intentionally child sessions of the orchestrator, a
  different case from the top-level independent sessions this task targets. No
  reported symptom that they misbehave; stripping `CLAUDE_CODE_CHILD_SESSION` there
  risks changing behavior outside this bug's scope.
