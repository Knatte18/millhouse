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

**Known residual limitation (found during discussion review round 4 — see
`Decisions > instance-reuse-limitation`):** this fix only guarantees a clean
environment when `code <path>` actually spawns a brand-new top-level VS Code process.
VS Code's CLI defaults to single-instance behavior: if an instance is already running,
`code <path>` forwards the request over IPC to that existing instance, which opens the
new window using whatever environment *that* instance originally started with — not
the freshly-scrubbed environment this task's `subprocess.run` call now passes, since no
new OS process is created in that path. mill's own multi-worktree-window workflow
(`--filter-open` / `_vscode_processes.find_open_vscode_paths`) means this is a real,
not corner-case, path. See Scope/Out and Constraints.

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
  `subprocess.run`, while unrelated vars (e.g. `PATH`) are preserved — at 3 exemplars,
  not all four production sites (reworded in discussion review round 5 to match
  `Testing`'s round-4-narrowed scope): the interactive-picker call site
  (`millpy-vscode.py:275`), the spawn-and-open call site (`millpy-vscode.py:132`), and
  the POSIX branch of `millpy-terminal.py`'s call site (`millpy-terminal.py:121`).
  `millpy-terminal.py`'s Windows branch (`millpy-terminal.py:118`) is not
  unit-test-covered by this task — see `Testing`'s closing note and `Technical
  context`'s note on the pre-existing lack of `os.name` mocking in either test file.

**Out:**
- `millpy-spawn.py` — confirmed (via grep across the script and both `mill-spawn`/
  `mill-vscode` SKILL.md files) that it never subprocess-spawns `code` itself; it only
  renders and writes `.vscode/settings.json` / `.vscode/tasks.json` via `_vscode.py`.
  The issue's mention of "millpy-spawn.py's vscode-open path" refers to the composed
  flow where `millpy-vscode.py --new` calls into `millpy-spawn.py`'s `main()` and then
  itself spawns `code` — already covered by the `_spawn_and_open` fix above. No change
  needed in `millpy-spawn.py`.
- `_vscode.py` — settings/tasks rendering only, no subprocess spawning; out of scope.
- `_llm_claude.py`'s three `STRIP_VARS`-filtered subprocess launches (lines 332, 358,
  384) — two direct `claude -p` calls (358, 384, via `_build_argv`) plus one
  psmux-wrapper call (332, via `_build_psmux_argv`, argv
  `[sys.executable, millpy-claude-sub.py, ...]`, not `claude -p` directly; corrected in
  discussion review round 6 — the earlier "three `claude -p`" phrasing was imprecise
  about line 332). All three already filter `os.environ` through a `STRIP_VARS`
  frozenset before spawning
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
- Making the fix effective when VS Code's CLI reuses an already-running instance
  instead of spawning a fresh process (found during discussion review round 4 — see
  Problem and `Decisions > instance-reuse-limitation`). No `--new-window`/`-n` flag or
  running-instance detection is added by this task; the fix is accepted as scoped to
  the fresh-process spawn path only.

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
- `CLAUDE_CODE_ENTRYPOINT` confirmed session-scoped (discussion review round 3): unlike
  `CLAUDE_CODE_USE_BEDROCK`/`CLAUDE_CODE_USE_VERTEX` — boolean backend-routing toggles
  a user deliberately sets and expects to persist across every session they start —
  `CLAUDE_CODE_ENTRYPOINT` records *how the current process was invoked* (e.g. CLI vs.
  SDK vs. another entrypoint), a fact the Claude Code binary determines and sets itself
  at process start. A user exporting it manually in a shell profile would only
  misrepresent how the session was actually launched; it has no persistent-config use
  case analogous to Bedrock/Vertex routing, so keeping it on the allowlist alongside
  the two confirmed session markers is correct.

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

### instance-reuse-limitation

- Decision: Do not add `--new-window`/`-n` (or any other flag) to `_build_code_argv`'s
  or `millpy-terminal.py`'s launch argv, and do not add running-instance detection
  before launching. Accept and document (Problem, Scope/Out) that this fix only
  guarantees a clean environment when `code <path>`/`claude --name <slug>` actually
  spawns a fresh top-level OS process.
- Rationale: `--new-window` does not solve the underlying env-propagation gap — it
  changes window-management behavior (force a new window vs. reuse/focus an existing
  one for the same workspace) but does not force VS Code to spawn a genuinely separate
  top-level process with its own environment; by default, `code --new-window` still
  communicates with an already-running instance's Electron main process over the same
  IPC channel used for a plain `code <path>`. Adding it would give a false impression
  the gap is closed while leaving the actual defect (env comes from whenever the
  existing instance was first started) untouched. True process isolation would require
  something like a distinct `--user-data-dir` per window, which changes VS Code's
  user-data isolation semantics far beyond what this bug fix should touch, and
  contradicts mill's own anticipated usage — `_vscode_processes.find_open_vscode_paths`
  and `--filter-open` exist specifically because multiple worktree windows sharing one
  running VS Code instance is the expected pattern, not an edge case to design around.
- Rejected: Add `--new-window` to the launch argv — doesn't fix the env-propagation gap
  (see Rationale), only changes window-focus behavior.
- Rejected: Detect an already-running VS Code instance (reusing
  `_vscode_processes.find_open_vscode_paths`, already used for `--filter-open`) and
  warn or block when the reuse path would apply — over-engineering for this task; the
  original issue's own documented workaround (fully close the window and reopen from a
  clean parent, or launch via `env -u CLAUDE_CODE_CHILD_SESSION -u ... code <path>`)
  already covers this residual case without new detection machinery.
- Accepted limitation: a spawned VS Code window opened while another VS Code instance
  is already running may still inherit that other instance's original environment
  (clean only if that instance itself was started clean). This fix eliminates the leak
  for the reported/common case — spawning the first/only window, or any window when no
  VS Code instance is currently running — but not the instance-reuse case. Not closed
  by this task.

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
  subprocess launches (lines 332, 358, 384) used by subprocess/psmux dispatch mode's
  reviewer/implementer/merge-in pipeline — two direct `claude -p` calls (358, 384) and
  one psmux-wrapper call (332, `[sys.executable, millpy-claude-sub.py, ...]`; see
  Scope/Out for the round-6 correction to this description). Confirmed out of scope for
  this task (see Scope/Out and `Decisions > helper-location`'s rejected alternatives)
  — noted here so mill-plan doesn't independently rediscover and second-guess the
  exclusion.
- `plugins/mill/unit_tests/test-millpy-vscode.py` and
  `plugins/mill/unit_tests/test-millpy-terminal.py` — existing tests in both files
  mock `subprocess.run`, but **only one exemplar test per real production call site
  needs a mock-signature change and a new `env` assertion** — see `Testing` for the
  named exemplars (narrowed in discussion review round 4; the round-3 text implied a
  file-wide mechanical change across every mock site, which overstated the actual
  work). The remaining mock sites in both files are unaffected by this fix and need no
  change:
  - `test-millpy-vscode.py` has 18 total `subprocess.run` mock sites (lines 74, 120,
    158, 200, 246, 298, 342, 389, 424, 522, 569, 615, 662, 720, 772, 812, 863, 903), all
    discarding `kwargs` today (audited in round 3) — of these, only the two exemplars
    named in `Testing` (covering the interactive-picker call site at
    `millpy-vscode.py:275` and the spawn-and-open call site at `millpy-vscode.py:132`)
    get a signature change; the other 16 keep testing `argv`/`cwd` only, unchanged.
  - `test-millpy-terminal.py` has 8 total `subprocess.run` mock sites: 5 don't capture
    full `kwargs` — 4 inline lambdas (122, 201, 245, 297) store only the bare `cwd`
    value, and the `mock_subprocess_run` helper at line 76 stores `{"argv": argv,
    "cwd": cwd}` (both fields, but still not full `kwargs`, so `env` is dropped there
    too — corrected in discussion review round 5, which had been miscounted as
    identical to the other 4 in round 2) — and 3 already capture full `kwargs` (159,
    339, 386) (audited in round 2) — of these, only the exemplar named in `Testing`
    (covering the POSIX
    `subprocess.run(["claude", ...], cwd=launch_path)` call site at
    `millpy-terminal.py:121`) gets a signature change; the rest are unaffected. Neither
    test file mocks `os.name`, so the Windows branches (`millpy-terminal.py:118`,
    `millpy-vscode.py`'s `_build_code_argv` `nt` branch) are untested today regardless
    of this fix — a pre-existing test-infrastructure gap, out of scope for this task
    (see `Testing`'s closing note). The env scrub itself is applied identically
    regardless of which OS branch builds `argv`, so exercising the POSIX branch
    exercises the same env-scrub code path.

## Constraints

No `CONSTRAINTS.md` present at the hub root.

Accepted constraint (found during discussion review round 4 — see
`Decisions > instance-reuse-limitation`): this fix cannot guarantee a clean spawned-
window environment when VS Code's CLI reuses an already-running instance instead of
spawning a fresh process. Scoped as a known, documented limitation rather than
addressed in this task.

## Testing

- **TDD candidate:** `scrub_env()` helper in `_subprocess_util.py` — pure function,
  no I/O. Tested in `plugins/mill/unit_tests/test-subprocess-util.py`, the existing
  dedicated test file for `_subprocess_util.py` (found during discussion review round
  6; currently `from _subprocess_util import _GRACE_SECONDS, popen_detached, run` —
  add `scrub_env` to that import). Call it with an explicit fake `env` dict argument (per `Decisions >
  helper-location`'s `env` parameter — do not mutate or monkeypatch real `os.environ`
  in the test) containing a mix of the 3 allowlisted keys
  (`CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_ENTRYPOINT`) and
  ordinary keys (e.g. `PATH`, `HOME`, and — per the round-2 finding — a persistent
  config var like `CLAUDE_CODE_USE_BEDROCK` to prove the allowlist does NOT strip
  same-prefix config vars); assert the 3 allowlisted keys are absent from the result
  and all other keys, including `CLAUDE_CODE_USE_BEDROCK`, are preserved unchanged.
  Also cover the case where none of the 3 allowlisted keys are present (no-op, no
  error), and the default (`env=None`) case reading from real `os.environ`.
- **Integration into existing tests — exactly these exemplars, not a file-wide sweep**
  (narrowed in discussion review round 4 — see `Technical context` for the reconciled
  scope): extend the mock `side_effect` at exactly these existing test sections to also
  capture full `kwargs` and add the `env` assertions below; no other mock site in
  either file changes.
  - `test-millpy-vscode.py`: the "two worktrees, user picks first" test (mock at line
    74) — covers the interactive-picker call site (`millpy-vscode.py:275`). The "no
    active worktrees, no flags -> spawn called, new worktree opened" test (mock at
    line 342) — covers the spawn-and-open call site (`millpy-vscode.py:132`).
  - `test-millpy-terminal.py`: the "single worktree -> auto-selected, subprocess
    called without prompt" test (mock at line 122) — covers the POSIX call site
    (`millpy-terminal.py:121`), the only branch any existing test exercises (see
    `Technical context`'s closing note on the untested Windows branch).
  - Assertions to add at each of the three exemplars above:
    - `kwargs["env"]` is present (not `None`, i.e. the call sites now always pass an
      explicit scrubbed env rather than falling through to full inheritance).
    - None of `CLAUDE_CODE_CHILD_SESSION`, `CLAUDE_CODE_SESSION_ID`,
      `CLAUDE_CODE_ENTRYPOINT` appears in `kwargs["env"]`, when the test harness
      injects one of these into `os.environ` via `monkeypatch`/`patch.dict` before
      invoking `main()`.
    - A control var unrelated to the allowlist (e.g. `PATH`) is still present in
      `kwargs["env"]`, proving the scrub is a filter, not a full env drop.
- **Real-world coverage scope covered by the 3 exemplars above:** the interactive
  picker call site (`millpy-vscode.py:275`), the spawn-and-open call site
  (`millpy-vscode.py:132`), and the POSIX branch of `millpy-terminal.py`'s single call
  site cluster (`millpy-terminal.py:121`). `millpy-terminal.py`'s Windows branch
  (`millpy-terminal.py:118`) and `millpy-vscode.py`'s Windows `argv`-building branch in
  `_build_code_argv` are not separately unit-tested by this task — see `Technical
  context`'s closing note: neither test file mocks `os.name` today (pre-existing gap),
  and `scrub_env()` is applied identically before either OS branch builds its `argv`,
  so the POSIX-branch exemplars exercise the same env-scrub code the Windows branches
  would run.
- `_llm_claude.py`'s `STRIP_VARS`-based spawns are out of scope (see Scope/Out) — no
  test changes there.
- No end-to-end test that actually launches `code`, VS Code, or `claude` — out of
  scope, consistent with existing test suite's full mocking of `subprocess.run`. This
  also means the round-4 `code`-instance-reuse limitation (see `Constraints`) is
  undetectable by this test suite by construction — mocking `subprocess.run` cannot
  observe VS Code's own IPC-based window-reuse behavior, since that behavior happens
  entirely inside the real `code` binary this task's tests never invoke.

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
- **Q:** [discussion review round 3, GAP] `Technical context`'s note on
  `test-millpy-vscode.py`'s mock-kwargs audit was deferred ("needs auditing per-site...
  before deciding") even though `test-millpy-terminal.py`'s parallel note gives an
  exact per-line breakdown — should `test-millpy-vscode.py` get the same precision?
  **A:** [auto-pick] Yes — audited and stated plainly: unlike `test-millpy-terminal.py`
  (which has a 5-vs-3 split), all 18 of `test-millpy-vscode.py`'s `subprocess.run` mock
  sites discard `kwargs` entirely, so 100% need the signature change, not a per-site
  decision. **Why:** leaving it deferred risked a plan writer assuming a
  terminal.py-like partial split applies to vscode.py too, undercounting the actual
  test-update work. **[Superseded in round 4 — see the "Testing scope narrower than
  Technical context" gap entry below; the "100% need updating" framing was itself
  narrowed to exemplar-only coverage.]**
- **Q:** [discussion review round 4, GAP] `Technical context` implied every mock site
  in both test files needs a signature change (26 sites total), but `Testing` only
  named ~4 exemplar scenarios for actual new `env` assertions — which scope is
  correct? **A:** [auto-pick] `Testing`'s narrower exemplar scope is correct;
  `Technical context` was rewritten to match — exactly one exemplar per real
  production call site (2 in `test-millpy-vscode.py`, 1 in `test-millpy-terminal.py`,
  since terminal.py's two originally-listed exemplars both hit the same POSIX call
  site) gets a mock-signature change and new `env` assertions; every other mock site is
  unaffected. **Why:** one assertion per real call site is sufficient to prove
  `scrub_env()` is wired in correctly; a file-wide mechanical sweep across every test
  would be needless churn with no additional coverage value, since the other tests
  already cover argv/cwd/control-flow concerns unrelated to this fix.
- **Q:** [discussion review round 4, GAP] Neither launch site passes `--new-window`;
  VS Code's default CLI behavior reuses an already-running instance rather than
  spawning a fresh process, so the newly-scrubbed `env=` on this task's `subprocess.run`
  call wouldn't apply in that path — should this be fixed or scoped as a known
  limitation? **A:** [auto-pick] Scope as a known, documented limitation (see
  `Decisions > instance-reuse-limitation`); do not add `--new-window` or running-
  instance detection. **Why:** `--new-window` only changes window-focus behavior, not
  process isolation — it does not actually close the gap, and would misleadingly
  suggest it does. True process isolation (e.g. per-window `--user-data-dir`) is out of
  proportion to this bug fix and conflicts with mill's own anticipated multi-window/
  single-instance usage pattern (`--filter-open`). The issue's own documented
  workaround already covers this residual case.
- **Q:** [discussion review round 5, GAP] `Scope > In`'s test-coverage bullet still
  said assertions land "at each of the four sites," but `Testing` (narrowed in round
  4) covers only 3 exemplars and explicitly leaves `millpy-terminal.py:118` (Windows
  branch) unit-test-uncovered — round 4's narrowing reached `Technical context` but
  missed this bullet. **A:** [auto-pick] Reworded `Scope > In`'s bullet to state the
  3-exemplar scope explicitly, matching `Testing` and `Technical context`. **Why:** a
  stale "four sites" claim left in `Scope > In` would contradict the already-narrowed
  `Testing`/`Technical context` sections and risk a plan writer trusting the wrong one.
- **Q:** [discussion review round 6, GAP] `Testing`'s `scrub_env()` TDD-candidate plan
  never named a target test file, despite an existing dedicated file
  (`test-subprocess-util.py`) for `_subprocess_util.py` — which file should the new
  unit tests go in? **A:** [auto-pick] `plugins/mill/unit_tests/test-subprocess-util.py`
  — add `scrub_env` to its existing `from _subprocess_util import ...` line. **Why:**
  that file already exists specifically for `_subprocess_util.py` (imports
  `_GRACE_SECONDS, popen_detached, run`); creating a separate file for one more
  function in the same module would be an unnecessary split.
