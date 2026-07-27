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
- Strip the named `CLAUDE_CODE_*` session-marker vars (see `Decisions > scrub-scope`)
  from the child environment passed to every interactive top-level-session launch
  subprocess identified below.
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
- A shared `scrub_env()` helper (see `Decisions > helper-location`), used by all
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
- Any env var not in the `scrub-scope` allowlist — including other `CLAUDE_CODE_*`
  vars such as `CLAUDE_CODE_USE_BEDROCK`/`CLAUDE_CODE_USE_VERTEX` (found during
  discussion review, round 2 — see `Decisions > scrub-scope`), and unrelated vars like
  `ANTHROPIC_*`/`CLAUDE_PLUGIN_ROOT` — not implicated by the issue, not stripped.

## Decisions

### scrub-scope

- Decision: Strip an explicit allowlist of exactly 3 named session-marker vars —
  `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT` —
  rather than a blanket `CLAUDE_CODE_*` prefix match.
- Rationale: **Superseded by discussion review round 2.** The original decision chose
  prefix-match on the theory that "there is no known legitimate case where a
  `CLAUDE_CODE_*` var from the launching session should leak into" a freshly spawned
  window. Round 2 review disproved that premise: `CLAUDE_CODE_USE_BEDROCK` and
  `CLAUDE_CODE_USE_VERTEX` are documented persistent-configuration vars (not session
  markers) that a user may export at shell level, expecting every Claude Code session
  they open — including ones spawned inside a fresh VS Code window — to inherit them.
  A blanket prefix strip would silently break Bedrock/Vertex routing for any spawned
  session, which is worse than the bug this task fixes: today's bug degrades a spawned
  session (transcript-off, manual mode); a blanket strip would instead break the
  session's backend configuration outright, with no visible error pointing back to
  `mill-vscode`/`mill-terminal`. An explicit allowlist of the 3 named markers fixes
  exactly the reported leak with a bounded, auditable blast radius and no risk to
  config vars under the same prefix.
- Rejected: Blanket `CLAUDE_CODE_*` prefix match — the original decision; superseded
  above because it collides with real persistent-config vars under the same prefix,
  not merely a hypothetical future marker.
- Accepted trade-off: if a new `CLAUDE_CODE_*` *session-marker* var (as opposed to a
  config var) is introduced elsewhere in the codebase later, this allowlist will not
  catch it automatically — it must be added to the allowlist explicitly. This is
  accepted as the safer default given the round-2 finding; the alternative (prefix
  match with a config-var carve-out list) was considered and rejected as more complex
  without a stronger guarantee, since a future config var also isn't guaranteed to be
  known in advance.

### helper-location

- Decision: Add a `scrub_env(env: dict[str, str] | None = None) -> dict[str, str]`
  helper to `_subprocess_util.py`, imported by both `millpy-vscode.py` and
  `millpy-terminal.py` at all four launch call sites (see Scope/In). When `env` is
  `None` (the production call sites' default), the helper reads `os.environ`
  internally; tests pass a fake dict directly through the `env` parameter instead of
  monkeypatching `os.environ`. The function filters out exactly the 3 allowlisted keys
  from `Decisions > scrub-scope` (`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`,
  `CLAUDE_CODE_ENTRYPOINT`) — no `prefix` parameter, since scrub-scope moved from
  prefix-match to an explicit allowlist.
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
  reason documented at each call site. The `env` parameter was added in round 2 after
  review flagged that the originally-decided no-argument signature (reading
  `os.environ` directly) gave `Testing`'s planned "fake env dict" unit test no seam to
  inject through; an optional parameter defaulting to `None`/`os.environ` satisfies
  both the production call sites (which want zero-argument convenience) and the test
  (which wants an isolated fake dict, per `Testing`'s "do not mutate real `os.environ`
  in the test").
- Rejected: Local helper duplicated in both `millpy-vscode.py` and `millpy-terminal.py`
  — avoids adding an import but duplicates identical filtering logic in two files,
  the exact duplication YAGNI was originally invoked to avoid at a smaller scope.
- Rejected: Extend `_llm_claude.py`'s existing `STRIP_VARS` frozenset (see Scope/Out)
  to also cover the 3 allowlisted `CLAUDE_CODE_*` markers and reuse it here —
  `_llm_claude.py`'s spawn sites are a semantically different case (intentional child
  sessions, not top-level independent sessions — see Scope/Out) that this task
  deliberately does not touch, so sharing one set/function across both would blur that
  intentional distinction. Precedent noted, not reused, per discussion review round 1
  finding.
- Rejected: Monkeypatch/`patch.dict` on real `os.environ` in the unit test instead of
  adding an `env` parameter (the round-2 review's alternative fix for the
  signature/testing gap) — works, but mutating process-global `os.environ` in a unit
  test (even temporarily, even patched) is more fragile under parallel test execution
  than passing an isolated dict; the parameter costs one optional argument.

### env-copy-semantics

- Decision: Build the scrubbed env as a fresh dict comprehension over the source env's
  `.items()` (the `env` parameter when given, else `os.environ` — see
  `Decisions > helper-location`), filtering out keys that match the 3-var allowlist
  from `Decisions > scrub-scope`, rather than mutating a copy with `del`/`pop`. Absence
  of the vars (e.g. when `mill-vscode` is run outside a Claude Code session) is not an
  error condition — the filter is a no-op in that case.
- Rationale: Simplest correct form; no special-casing needed for "var not present".
  A dict comprehension over an allowlist-membership check (`k not in _SCRUBBED_KEYS`)
  is equally simple whether the filter is a prefix test or a set-membership test, so
  this decision is unaffected by `scrub-scope`'s round-2 move from prefix to allowlist.
- Rejected: `os.environ.copy()` + explicit `pop(key, None)` per named var — functionally
  equivalent to the comprehension for an allowlist, but mutates a copy in place instead
  of building the filtered dict directly; no material advantage, so the simpler
  comprehension form stands.

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
  and the equivalent `mill_terminal.subprocess.run` patches). In `test-millpy-terminal.py`
  specifically (corrected during discussion review round 2 — the round-1 draft
  undercounted this): 5 of the file's `subprocess.run` mock lambdas capture only `cwd`
  and discard the rest of `kwargs` (the `mock_subprocess_run` helper function used at
  line 76, plus the inline lambdas at lines 122, 201, 245, 297) and need updating to
  capture full `kwargs` for this fix's `env` assertions; the other 3 (lines 159, 339,
  386) already do `subprocess_calls.append(kw)` and need no signature change, only new
  assertions added on the already-captured `kw["env"]`. `test-millpy-vscode.py`'s mocks
  similarly need auditing per-site for which already capture full `kwargs` vs. `argv`
  only, before deciding which need a signature change.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

## Testing

- **TDD candidate:** `scrub_env()` helper in `_subprocess_util.py` — pure function,
  no I/O. Call it with an explicit fake `env` dict argument (per `Decisions >
  helper-location`'s `env` parameter — do not mutate or monkeypatch real `os.environ`
  in the test) containing a mix of the 3 allowlisted keys
  (`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT`) and
  ordinary keys (e.g. `PATH`, `HOME`, and — per the round-2 finding — a persistent
  config var like `CLAUDE_CODE_USE_BEDROCK` to prove the allowlist does NOT strip
  same-prefix config vars); assert the 3 allowlisted keys are absent from the result
  and all other keys, including `CLAUDE_CODE_USE_BEDROCK`, are preserved unchanged.
  Also cover the case where none of the 3 allowlisted keys are present (no-op, no
  error), and the default (`env=None`) case reading from real `os.environ`.
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
  stays correct if new markers are added later. **[Superseded in round 2 — see the
  `scrub-scope` gap entry below; reverted to the 3-var allowlist after review found a
  real collision with persistent config vars under the same prefix.]**
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
- **Q:** [discussion review round 2, GAP] Does the blanket `CLAUDE_CODE_*` prefix
  strip from `scrub-scope` risk dropping legitimate persistent config, since the
  `claude` CLI documents vars like `CLAUDE_CODE_USE_BEDROCK`/`CLAUDE_CODE_USE_VERTEX`
  under the same prefix? **A:** [auto-pick] Yes, confirmed a real conflict — revert
  `scrub-scope` from prefix-match to an explicit 3-var allowlist
  (`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT`).
  **Why:** `CLAUDE_CODE_USE_BEDROCK`/`CLAUDE_CODE_USE_VERTEX` are persistent backend-
  routing config a user may export at shell level, not session-state markers; a
  blanket prefix strip would silently break Bedrock/Vertex routing for every spawned
  session. An allowlist fixes exactly the reported leak without that risk — see
  `Decisions > scrub-scope`'s "Superseded by discussion review round 2" note for the
  full trade-off.
- **Q:** [discussion review round 2, GAP] `Scope > In` names the helper
  `_scrubbed_env()` while every other section says `scrub_env()` — which is correct?
  **A:** [auto-pick] `scrub_env()` — corrected the stray name in `Scope > In`. **Why:**
  every other section (`Decisions > helper-location`, `Technical context`, `Testing`,
  earlier Q&A entries) already used `scrub_env()`; `Scope > In` had the only
  inconsistent mention.
- **Q:** [discussion review round 2, GAP] The decided `scrub_env()` signature
  (originally `scrub_env(prefix: str = "CLAUDE_CODE_") -> dict[str, str]`, reading
  `os.environ` directly per `env-copy-semantics`) has no parameter for `Testing`'s
  planned "fake env dict" unit test to inject through — how should this be resolved?
  **A:** [auto-pick] Add an `env: dict[str, str] | None = None` parameter (defaulting
  to `os.environ` when omitted); drop the now-unused `prefix` parameter since
  `scrub-scope` moved to an allowlist in this same round. **Why:** gives the unit test
  an isolated seam to pass a fake dict through without mutating real `os.environ`,
  while keeping the production call sites' zero-argument convenience via the default.
  See `Decisions > helper-location`'s rejected alternative (monkeypatching
  `os.environ` instead) for why the parameter was preferred over that option.
