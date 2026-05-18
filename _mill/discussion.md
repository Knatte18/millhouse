# Discussion: Keep psmux TUI alive across calls for session continuity

```yaml
task: Keep psmux TUI alive across calls for session continuity
slug: psmux-session-keepalive
status: discussing
parent: main
```

## Problem

Task 58 (`claude-psmux-activate`) routed `_llm_claude._invoke()` through
`millpy-claude-sub.py` so claude calls are billed against the operator's
subscription instead of API credits. The wrapper creates a fresh psmux
session per call and tears it down in `finally`. That works for one-shot
calls, but it makes `resume=True` semantically useless on the psmux path:
the wrapper currently rejects `resume=True` outright (`_invoke` raises
`LLMError("psmux path does not support session resume...")`), because
even if it did not, the underlying psmux session was killed after the
previous round so there is nothing to resume into.

`mill-go`'s implement-review-fix loop relies on `session_id` + `resume=True`
to keep the implementer's warm context across rounds. With `via_psmux:true`
that whole code path is dead, which silently degrades review-fix quality
(every round starts from scratch). The operator wants `via_psmux:true` to
become the default routing eventually, so the keepalive gap has to close
before that switch.

A secondary motivation, mentioned by the operator: claude can absorb a
follow-up prompt sent into the still-running TUI without `--resume`. So
psmux session reuse subsumes the `--resume` mechanism on this path — we
just need to leave the TUI alive between calls and paste the next prompt
when it returns to its idle `❯` prompt.

## Scope

**In:**

- `plugins/mill/scripts/millpy-claude-sub.py` — two new flags
  (`--psmux-session <name>`, `--keep-alive`), session-reuse short-circuit
  in the boot sequence, and refactored cleanup so on-error kill is
  unconditional while on-success kill is gated by `--keep-alive`.
- `plugins/mill/scripts/_llm_claude.py` — deterministic
  `mill-{session_id[:12]}` derivation; pass `--psmux-session` and
  `--keep-alive` to the wrapper whenever `session_id` is set; map
  wrapper non-zero exit to `LLMSessionError` when `resume=True` (plain
  `LLMError` otherwise); read new config key `llm.claude.psmux.reuse_idle_timeout_s`.
- `plugins/mill/scripts/_llm_claude.py` — new public helper
  `cleanup_session(session_id)` that derives the psmux name and kills
  the session if it exists (idempotent, swallows `PsmuxError`).
- `mill-go` call site — invoke `_llm_claude.cleanup_session(session_id)`
  at the end of each implement-review-fix loop (after the loop terminates
  on APPROVE, error, or max-rounds) so sessions never accumulate beyond
  one logical batch.
- Config schema: promote `via_psmux` into a nested `psmux:` sub-block.
  Both `mill-config.yaml` (hub root) and
  `plugins/mill/templates/mill-config.yaml` (plugin template) gain
  `llm.claude.psmux.via_psmux: false` and
  `llm.claude.psmux.reuse_idle_timeout_s: 10`. Update the inline comment
  to drop "resume flows unsupported" and to mention automatic cleanup.
- `plugins/mill/scripts/_config.py` — if it normalises this section,
  fold the migration through (see Technical context below).
- `plugins/mill/unit_tests/test-llm-claude.py` — keepalive-path argv
  assertions and the `cleanup_session` helper.
- `plugins/mill/unit_tests/test-claude-sub.py` — new file with unit
  tests for the wrapper's reuse / keep-alive / on-error-kill logic.

**Out:**

- Anything inside `_psmux.py` or `_psmux_capture.py`. The new flow uses
  the existing public helpers (`list_sessions`, `capture_pane`,
  `send_keys`, `paste_buffer`, `kill_session`).
- Gemini provider. `_llm_gemini.py` keeps its current behaviour; no
  psmux story there.
- Cross-process / cross-host session sharing. Sessions are local
  per-machine; `cleanup_session` only touches the local psmux server.
- A separate `mill-cleanup-psmux` skill / sweeper command. mill-go's
  per-loop cleanup plus the wrapper's on-error kill cover the operator's
  "do not make me manage processes" requirement. A periodic sweeper can
  be added later if accumulation ever becomes a real problem.
- Removing `--resume` from `_build_argv` on the direct-CLI path. The
  direct-CLI path still uses `--resume` semantics; only the psmux path
  routes resume through session-reuse.
- Backwards-compatibility shim for the old flat `llm.claude.via_psmux`
  key. The config-schema move from flat → nested is a hard cutover; any
  existing local `config.local.yaml` overlays must be updated as part
  of this PR. The operator confirmed there are no other consumers.

## Decisions

### session-name derivation

- Decision: `psmux_name = f"mill-{session_id[:12]}"`, verbatim slice with
  no normalisation. `_llm_claude` always passes this name as
  `--psmux-session` whenever `session_id` is set (either chosen by
  caller or auto-generated when the caller relies on the default-UUID
  branch).
- Rationale: deterministic, debuggable, and `session_id` is a UUID4 in
  every existing caller — its character set (`[0-9a-f-]`) is fully
  legal in psmux session names. Visual continuity between the
  `session_id` printed in `[_llm_claude]` log lines and the psmux name
  helps when the operator runs `psmux ls`.
- Rejected: regex-normalisation (over-engineering for the closed set
  of callers we have) and SHA1-hashing (opaque names defeat
  debuggability without adding real collision resistance for UUID
  inputs).

### keep-alive default

- Decision: `--keep-alive` defaults to `false` on the wrapper. The
  wrapper sets it from a CLI flag; the wrapper never infers it. The
  `_llm_claude` layer is the only place that decides whether to pass
  `--keep-alive` to the wrapper, and does so iff `session_id is not None`.
- Rationale: pairs cleanly with the cleanup model. `session_id` carries
  the operator's intent ("I plan to make more calls with this id"); a
  single one-shot call (no `session_id`, no `--psmux-session`,
  auto-generated id inside the wrapper) follows today's tear-down
  semantics unchanged.
- Rejected: tying keep-alive to `resume=True` only — this would defeat
  the first call of a multi-round loop (no resume yet, so the wrapper
  would create-and-kill, then the second round would fail to find a
  session to reuse). Rejected: defaulting `--keep-alive` true at the
  wrapper — bad ergonomics for callers that genuinely want one-shot
  semantics.

### cleanup model

- Decision: layered cleanup with three rules.
  1. **Wrapper, on success path:** kill the session iff `--keep-alive`
     is not set. Same semantics as today for the `session_id=None`
     branch.
  2. **Wrapper, on error path:** always kill the session, regardless of
     `--keep-alive`, **but only if the wrapper itself created it this
     run**. If the wrapper entered an already-existing session via
     `--psmux-session` and then failed, do not kill — the session
     belongs to the previous caller (and that caller's
     `cleanup_session` will reap it). Implementation: track a
     `session_owned_by_us: bool` flag in main(), set true on
     `new_session()` success, false on the reuse short-circuit.
  3. **Caller, on logical-session-end:** mill-go calls
     `_llm_claude.cleanup_session(session_id)` after each implement-
     review-fix loop terminates (APPROVE, REQUEST_CHANGES exhaustion,
     stuck, error). The helper derives the psmux name, checks
     `list_sessions()`, and calls `kill_session` if present.
     `cleanup_session` swallows `PsmuxError` so cleanup is fire-and-
     forget.
- Rationale: the operator explicitly refused to manage processes
  manually. The three rules together guarantee that the only psmux
  sessions left alive are ones currently mid-use by a still-running
  mill-go batch. On crash of mill-go itself, sessions could survive,
  which is acceptable — operator falls back to `psmux kill-server`.
- Rejected: `atexit` hook in the calling Python process — mill-go's
  Python process and the subprocesses it spawns are different OS
  processes, so atexit in the child does not see the parent's
  registrations. Rejected: pure on-error-only kill (accumulates idle
  sessions across the success path).

### reuse short-circuit and idle check

- Decision: when `--psmux-session <name>` is given and `name` is in
  `_psmux.list_sessions()`, skip Steps 6–9 of the current boot
  sequence (`new_session`, `set_history_limit`, claude-binary check,
  claude launch). Instead, call `_wait_for_idle_prompt(name,
  REUSE_IDLE_TIMEOUT_S)`. If true → proceed straight to Step 10 (paste
  prompt + Enter). If false → raise `RuntimeError(f"cannot reuse psmux
  session {name}: not idle within {REUSE_IDLE_TIMEOUT_S}s")`. The
  RuntimeError propagates to `_invoke()` as a non-zero wrapper exit,
  which the LLM layer then maps per the error-mapping rule.
  `REUSE_IDLE_TIMEOUT_S` is read from
  `cfg["llm"]["claude"]["psmux"]["reuse_idle_timeout_s"]` and falls
  through to a module-default of `10` if the key is absent.
- Rationale: `_wait_for_idle_prompt` already encodes the precise
  signal we need (last 10 lines contain a lone `❯`); reusing it
  avoids duplicating polling logic. 10 seconds is well above normal
  redraw latency yet fails fast on a wedged TUI. Operator wanted this
  configurable in case some terminals need more headroom.
- Rejected: hardcoded constant (operator wanted a config key).
  Rejected: short 5 s default (false-fails on slow renders).
  Rejected: blocking forever (defeats the point of timeout).

### error mapping in `_llm_claude._invoke()` (psmux branch)

- Decision: in the `via_psmux` branch of `_invoke`, when the wrapper
  exits non-zero, raise `LLMSessionError` iff `resume=True` was passed
  in, otherwise raise plain `LLMError`. Drop the existing
  `if resume: raise LLMError("psmux path does not support session
  resume...")` guard — psmux now supports resume.
- Rationale: mirrors the direct-CLI path's behaviour. mill-go's fix
  loop already handles `LLMSessionError` by falling back to a fresh
  session; same behaviour now works for the psmux path. Plain
  `LLMError` on fresh-call failure is correct: there is nothing to
  fall back to since no prior session existed.
- Rejected: always raise `LLMSessionError` when `session_id` is set
  (broader than necessary; misleads on first-call failures).
  Rejected: keep the existing "resume unsupported" guard (defeats the
  whole task).

### config schema move

- Decision: promote `via_psmux` from flat `llm.claude.via_psmux` to
  `llm.claude.psmux.via_psmux`, and add a sibling
  `llm.claude.psmux.reuse_idle_timeout_s: 10`. Update the inline
  comment to mention automatic cleanup. Hard cutover — no
  compatibility shim, no read of the old flat key. Both the hub
  `mill-config.yaml` and the template
  `plugins/mill/templates/mill-config.yaml` change in lock-step
  (CLAUDE.md "template mirrors hub schema" rule).
- Rationale: a single new config key in the same area is enough to
  justify the nested block; we expect more psmux knobs (e.g. response
  timeouts override, cleanup sweep interval) and a flat namespace
  collects junk. The hard cutover keeps `_llm_claude._get_via_psmux_flag`
  simple — exactly one lookup path.
- Rejected: keep flat, add `psmux_reuse_idle_timeout_s` next to
  `via_psmux` (works, but invites further namespace pollution).
  Rejected: schema-migration shim that reads either key location
  (per CLAUDE.md "Don't add error handling for scenarios that can't
  happen" / "Don't use … backwards-compatibility shims when you can
  just change the code").

### documentation placement

- Decision: update the inline comment in `mill-config.yaml` and the
  matching template comment to describe the new keepalive behaviour
  and that mill-go reaps sessions automatically. No new doc file, no
  edit to root `CLAUDE.md`.
- Rationale: co-locates the doc with the schema; the operator hits
  the comment whenever they read the config, which is exactly the
  moment they need to understand the behaviour. Project convention
  keeps root CLAUDE.md terse.
- Rejected: a new plugin README (no existing plugins/mill/README.md
  in the repo). Rejected: split between CLAUDE.md and config comments
  (two places to update is two places to drift).

## Technical context

**Existing files touched (read carefully before edit):**

- `plugins/mill/scripts/millpy-claude-sub.py` (218 lines) — current
  boot sequence is Steps 1–12 in a try/finally. The cleanup refactor
  must keep the `prompt_path.unlink(missing_ok=True)` cleanup in
  finally (independent of session lifetime) while moving
  `_psmux.kill_session` out of `finally:` and into explicit success-
  / error-path calls gated by `--keep-alive` and `session_owned_by_us`.
- `plugins/mill/scripts/_llm_claude.py` (~497 lines) — the
  `via_psmux` branch starts at the `if _get_via_psmux_flag():` block
  in `_invoke()`. Both `_get_via_psmux_flag()` and
  `_build_psmux_argv()` need updating; the latter gains a
  `keep_alive: bool` parameter and emits `--psmux-session` /
  `--keep-alive` accordingly. `cleanup_session(session_id)` is a new
  module-level public function added after the existing public API
  block.
- `plugins/mill/scripts/_psmux.py` (helpers exposed:
  `new_session`, `set_history_limit`, `send_keys`, `load_buffer`,
  `paste_buffer`, `capture_pane`, `kill_session`, `list_sessions`,
  exception `PsmuxError`). No new helpers needed.
- `plugins/mill/scripts/_config.py` — verify whether it has a
  `via_psmux` accessor or hard-codes the path. If it does, update to
  the nested location.
- `mill-go` call site — locate the loop where `session_id` is held
  across rounds (around the implement-review-fix sequence). Add
  `_llm_claude.cleanup_session(session_id)` in a `finally` outside
  the loop so it runs once per logical session.

**Existing test patterns to mirror:**

- `plugins/mill/unit_tests/test-llm-claude.py` already mocks
  `_subprocess_util.run` and `_llm_claude._get_via_psmux_flag`. New
  keepalive cases extend the existing `# --- psmux branch tests ---`
  section.
- The new `test-claude-sub.py` needs heavier mocking: `_psmux`'s
  module-level functions (`new_session`, `set_history_limit`,
  `send_keys`, `list_sessions`, `capture_pane`, `kill_session`,
  `load_buffer`, `paste_buffer`) plus `_wait_for_marker_in_pane` and
  `_wait_for_idle_prompt`. Use `unittest.mock.patch.object` on the
  imported `_psmux` module reference inside `millpy-claude-sub`.
  Drive `main()` by setting `sys.argv` + capturing
  stdin/stdout/stderr. See `test-millpy-bg.py` for the argv-driven
  CLI test pattern.

**Gotchas discovered during exploration:**

- The wrapper has both `_wait_for_marker_in_pane` (used for the
  `CLAUDE_READY` boot check) and `_wait_for_idle_prompt` (used for
  post-launch idle). The reuse path uses only `_wait_for_idle_prompt`
  — we skip the `CLAUDE_READY` step entirely because the claude
  binary is already running inside the reused session.
- The current wrapper auto-generates `session_name = f"mill-{uuid.uuid4().hex[:8]}"`
  inside `main()`. With `--psmux-session` set, that line is short-
  circuited. Without it, today's 8-hex behaviour is preserved.
- `_invoke()`'s `via_psmux` branch generates `session_id = str(uuid.uuid4())`
  when `session_id is None`. Today that id is only used for the
  `--session-id` arg passed to the wrapper (claude CLI session id, not
  the psmux session name). With keepalive, this auto-generated id is
  passed to `--psmux-session` too — but since no caller can hold this
  generated id for a later call (the value never escapes the function),
  the session is effectively one-shot anyway. The wrapper still needs
  `--keep-alive=false` in this case. The rule from the keep-alive
  default decision handles this: `_llm_claude` only passes
  `--keep-alive` when the caller-provided `session_id` was non-None.
  Verify the implementation distinguishes "caller-provided id" from
  "auto-generated id" — store the original arg in a local before the
  auto-generation step.
- The `--psmux-session` flag accepts any string. `_llm_claude` always
  derives `mill-{id[:12]}` so there is exactly one production caller
  pattern; the wrapper itself does no sanitisation. Tests pass synthetic
  names directly.
- `_psmux.list_sessions()` raises `PsmuxError` if the psmux server is
  not running. Treat that as "session does not exist" for the reuse
  check — i.e. catch and proceed to create. The existing `_wait_for_*`
  helpers already swallow `PsmuxError`.
- `cleanup_session` must not raise. It does
  `try: ... except _psmux.PsmuxError: pass`. Document this contract
  in the docstring so mill-go callers do not wrap it in their own
  try.
- The config-load path: `_get_via_psmux_flag` currently reads
  `cfg["llm"]["claude"]["via_psmux"]`. After the schema move it reads
  `cfg["llm"]["claude"]["psmux"]["via_psmux"]`. There is no
  `via_psmux: false` default elsewhere — `_config.load_config`
  produces the deep-merged dict from `wiki/config.yaml` (shared) and
  `.millhouse/config.local.yaml` (overlay). The template's `false`
  default is the source of truth.

**ASCII-only stdout/stderr rule:** the wrapper currently uses
`[millpy-claude-sub]` prefixes only — no em-dashes / arrows in the
existing log lines. New log lines (`"reusing psmux session ..."`,
`"cleanup_session: kill mill-..."`) must also be ASCII-only per the
CLAUDE.md rule.

## Constraints

From root `CLAUDE.md`:

- **All `print()` / `_log()` strings ASCII-only.** New status lines
  in the wrapper and in `cleanup_session` must follow this.
- **Template `mill-config.yaml` mirrors the hub-root file's schema.**
  The config-key migration touches both files in the same commit.
- **`${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths.** Not directly
  relevant — this task touches scripts that already run inside
  `${CLAUDE_PLUGIN_ROOT}/scripts`; no new path references needed.
- **No backwards-compat shims when you can just change the code.**
  Config-key migration is a hard cutover.

From the conversation:

- No manual session management for the operator. The cleanup model
  (decision above) is load-bearing for this constraint.

No `CONSTRAINTS.md` is present at the hub root.

## Testing

**TDD candidates (write tests first):**

1. **`test-llm-claude.py` — keepalive argv assertions.** Extend the
   `# --- psmux branch tests ---` section.
   - Test K1: `via_psmux=True`, `session_id="abc-123-…"` (caller-
     provided), `resume=False` → argv contains
     `--psmux-session mill-abc-123-…` (first 12 chars) and
     `--keep-alive`.
   - Test K2: `via_psmux=True`, `session_id=None` → argv contains
     `--session-id <auto-uuid>` (today's behaviour) and does NOT
     contain `--psmux-session` or `--keep-alive`. Regression guard.
   - Test K3: `via_psmux=True`, `session_id="…"`, `resume=True` →
     argv contains `--psmux-session ...` and `--keep-alive`, AND
     wrapper non-zero now maps to `LLMSessionError` (NOT plain
     `LLMError`). Today this case raises early; the new behaviour
     calls the wrapper, sees the mocked failure, and re-raises as
     `LLMSessionError`.
   - Test K4: `via_psmux=True`, `session_id="…"`, `resume=False`,
     wrapper non-zero → raises plain `LLMError` (not
     `LLMSessionError`).
   - Test K5: `cleanup_session("abc-123…")` calls
     `_psmux.kill_session("mill-abc-123-…")` when
     `list_sessions()` returns the name; is a no-op when it does
     not; swallows `PsmuxError` from `kill_session`.

2. **`test-claude-sub.py` — new file, wrapper logic.** Mock
   `_psmux.*` entirely. Drive `main()` via `sys.argv` and feed a
   short prompt on stdin.
   - Test S1: existing-idle short-circuit. `--psmux-session existing-idle`,
     `list_sessions()` returns `["existing-idle"]`,
     `_wait_for_idle_prompt` returns True. Assert: `new_session`,
     `set_history_limit`, the `CLAUDE_READY` send-keys, and the
     `claude` launch send-keys are NOT called; `load_buffer` +
     `paste_buffer` + `Enter` ARE called.
   - Test S2: existing-busy raise. `--psmux-session existing-busy`,
     `list_sessions()` returns `["existing-busy"]`,
     `_wait_for_idle_prompt` returns False → wrapper exits non-zero
     with stderr containing `cannot reuse psmux session existing-busy: not idle`.
   - Test S3: existing-busy reuse does NOT kill the session.
     Combine S2's setup with assertion that `kill_session` is not
     called on the existing-busy session (the wrapper did not own
     it).
   - Test S4: `--keep-alive` true, success path → `kill_session`
     not called. `prompt_path.unlink` still called (separate cleanup).
   - Test S5: `--keep-alive` true, error mid-call → `kill_session`
     IS called when the wrapper owned the session (no `--psmux-session`
     reuse). Simulate error by mocking `_wait_for_idle_prompt` after
     claude launch to return False.
   - Test S6: no `--psmux-session`, no `--keep-alive` → today's
     behaviour: `new_session` then `kill_session` in finally
     (regression guard).
   - Test S7: `--psmux-session new-name`, `list_sessions()` returns
     `[]` → wrapper creates the session with that exact name.
   - Test S8: `_psmux.list_sessions()` raises `PsmuxError` (server
     not running) → wrapper proceeds to `new_session` (treats as
     "session not present").
   - Test S9: `REUSE_IDLE_TIMEOUT_S` is read from config when
     present; falls back to the module default when absent. (Use a
     `_config` mock; only validates the value-plumbing, not the
     timing loop itself.)

3. **Integration check (manual, no automated test):** verify the
   keepalive path against a real claude binary outside the test
   suite. Acceptance: two successive `run_implementer` calls with
   the same `session_id` produce a single `mill-{id[:12]}` psmux
   session that survives between calls and is killed exactly once
   by `cleanup_session`.

**Test isolation requirements:**

- No real `psmux` invocations in unit tests. Mock at the
  `_psmux.*` module-attr level.
- No real `claude` invocations. The wrapper's success path can be
  driven by mocking `_psmux_capture.extract_response` to return a
  canned string immediately, plus mocking `_psmux.capture_pane` to
  return a string containing the begin/end markers.
- Use `tempfile.TemporaryDirectory` for `scratch_dir`; do not write
  into the repo's `.scratch/`.

**Existing tests that must keep passing:**

- `test-llm-claude.py` (all eleven existing psmux tests, listed in
  the file's `# --- psmux branch tests ---` section). Test 6 (the
  `via_psmux + resume=True raises LLMError before subprocess`) must
  be UPDATED rather than left alone, because the new behaviour calls
  the subprocess on resume=True. Rewrite as Test K3 above; mark the
  rewrite explicitly in the commit.
- `test-llm-claude-argv.py` — untouched; direct-CLI argv shape does
  not change.
- `test-psmux-driver.py`, `test-psmux-capture.py` — untouched.

## Q&A log

- **Q:** Idle timeout for reuse — fixed constant or config? **A:** Config key,
  `llm.claude.psmux.reuse_idle_timeout_s: 10`, with `10` as the module-default
  fallback.
- **Q:** Cleanup-on-error semantics with `--keep-alive`? **A:** Wrapper always
  kills on error when it owns the session, even if `--keep-alive` is set.
  Operator-driven cleanup is rejected.
- **Q:** Where do mill-go-scale logical-session-end kills happen? **A:** New
  `_llm_claude.cleanup_session(session_id)` helper; mill-go calls it after
  each implement-review-fix loop.
- **Q:** Psmux-session-name derivation? **A:** `mill-{session_id[:12]}`,
  verbatim, no normalisation.
- **Q:** Error-mapping for the psmux branch when the wrapper exits non-zero?
  **A:** `LLMSessionError` iff `resume=True`, plain `LLMError` otherwise.
- **Q:** Should `--keep-alive` default to true at the wrapper or only be
  set by `_llm_claude` based on `session_id`? **A:** Wrapper default false;
  `_llm_claude` passes `--keep-alive` iff caller-provided `session_id` is
  not None.
- **Q:** Config schema for the new key — flat or nested? **A:** Nested:
  promote `via_psmux` into `llm.claude.psmux.*` and add `reuse_idle_timeout_s`
  next to it. Hard cutover, no compat shim.
- **Q:** Where does the documentation note about keepalive accumulation
  live? **A:** Inline comments in `mill-config.yaml` (hub) and the matching
  template. No new doc file; root `CLAUDE.md` stays terse.
- **Q:** When a reused psmux session fails mid-call (paste, response timeout),
  do we kill it? **A:** No. The wrapper only owns sessions it created this
  run; reused sessions belong to the previous caller and are reaped by
  that caller's `cleanup_session`.
