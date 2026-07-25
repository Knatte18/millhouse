# Discussion: Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise

```yaml
task: Wiki daemon error-log leak and stale plugin-cache config validation produce misleading noise
slug: mill-background-noise-and-stale-config
status: discussing
parent: hanf/linux-port-more
```

## Problem

Two unrelated noise/false-positive bugs keep firing during ordinary mill-go /
mill-start agent-dispatch runs, both making healthy operations look broken:

1. **Daemon error-log leak.** The wiki daemon's `_handle_connection` (in
   `_daemon.py`) has an inner guard (added 2026-07-16, commit `4963e527`,
   issue #677 first-pass) that downgrades the literal top-level
   `json.loads(msg_text)` empty/malformed-payload case to debug severity. But
   the *outer* generic `except Exception as exc: ... self._logger.error(...)`
   handler still fires at ERROR for anything else raised inside that same
   try block, and — independently — the daemon process spawned by
   `_spawn_server` (`wiki/_client.py`) inherits the spawning client's
   stdout/stderr (no redirection on the `subprocess.Popen` call), so any log
   line the daemon writes after its spawning client has exited still lands
   in that client's (or its `millpy-bg` log file's) output stream. This has
   been reproduced repeatedly across independent call paths: review prepare
   (#684), `millpy-implement.py --stage finalize` (#687), review-discussion
   prepare (#688) — always the exact string
   `[wiki] exception in _handle_connection: JSONDecodeError('Expecting value: line 1 column 1 (char 0)')`,
   always during stages that can trigger a daemon cold-start. **Caveat:**
   the inner guard is confirmed present in current code, correctly scoped
   to exactly this exception/call-site — so it's possible some or all of
   #684/#687/#688 (filed against `loomyard`, an external consumer repo) or
   even #677 itself (per this project's own CLAUDE.md, `${CLAUDE_PLUGIN_ROOT}`
   always resolves to the installed plugin cache, never the dev tree, even
   for scripts run from within a millhouse dev checkout) reflect a daemon
   that was still running pre-guard cache/publish-lag code rather than a
   live gap in the guard as written today — the same cache-rollout-lag
   mechanism bug 2 exists to fix. The fixes in this task face the identical
   rollout-lag exposure until the plugin cache picks them up; this is
   consistent with the existing Scope §Out note that cache-refresh timing
   itself is not this task's concern.

2. **Stale plugin-cache config validation.** `_config.load_config` was
   patched on 2026-05-31 (commit `22e2d3f5`) to augment its unknown-key
   validation template with the worktree's/hub's own
   `plugins/mill/templates/mill-config.yaml` whenever it exists and differs
   from the installed plugin cache (`${CLAUDE_PLUGIN_ROOT}/templates/...`) —
   this closes the "new key landed in source, cache not yet refreshed"
   false-positive gap. But `_review_common.py` carries a **second,
   independently-maintained copy** of `load_config` (lines 1842-1912) that
   never received that patch. Every script that calls the stale copy
   (`millpy-merge-in-subagent.py`, `millpy-review-plan.py`,
   `millpy-review-code.py`, `millpy-implement.py`, `millpy-fix.py`,
   `millpy-abandon.py`, `millpy-validate-plan.py`) still false-positives
   `[config] unknown key: ...` for any config key that's landed in the
   worktree/hub template but not yet in the cache (#676, #670), even though
   the exact same scenario is already fixed for scripts that call
   `_config.load_config` directly (`millpy-status.py`, `millpy-inspect.py`,
   `millpy-spawn.py`, etc.).

Why now: these are pure noise/false-alarm bugs — every reported instance
self-recovered and the underlying operation succeeded — but the misleading
ERROR/warning lines make it harder for an operator (or an autonomous
mill-go/mill-start run reading its own logs) to trust genuine error output.

## Scope

**In:**
- `_daemon.py`: `_handle_connection`'s exception classification — treat
  connection-level exceptions (`OSError`, `ConnectionResetError`,
  `BrokenPipeError`, `json.JSONDecodeError`, `UnicodeDecodeError`) raised
  in the recv/decode region — between the start of the recv loop and the
  point where `self.handle_request(msg)` is entered — as debug-level
  noise, not just the single `json.loads(msg_text)` line. The benign-type
  list applies only to that pre-dispatch region: ANY exception raised from
  within `self.handle_request(msg)` itself — including one of these same
  types, e.g. a genuine `OSError` from a real git/file failure inside
  request handling — still logs at ERROR. Classification is by source
  region first, exception type second; it is never type-only.
- `wiki/_client.py`: `_spawn_server`'s `subprocess.Popen` call — redirect
  the detached daemon's stdout/stderr to `subprocess.DEVNULL` (not to a
  file of its own; the daemon-logger-consolidation decision below already
  makes the rotating log file the one place daemon diagnostics land, so
  raw stdout/stderr capture would be redundant).
- `_daemon.py` / `wiki/_server.py`: collapse `DaemonBase`'s connection-level
  logger (`logging.getLogger("wiki")`, root-`basicConfig`-configured,
  stderr-bound) and `WikiServer`'s business-logic logger
  (`logging.getLogger("wiki-server")`, dedicated `RotatingFileHandler`,
  `propagate=False`) into one consistent logging destination per daemon
  instance.
- `_review_common.py`: delete the duplicate `load_config` (lines
  1842-1912); delegate to `_config.load_config` for the core
  template/repo/local merge (including the 2026-05-31 cache-lag
  augmentation), preserving `_review_common`'s two review-specific
  behaviors on top: raising `ReviewError` when no config source is found at
  all, and warning on stale `review:` keys in local config. Callers of the
  duplicate that must keep working post-refactor: every script listed
  above, plus `millpy-review-discussion.py:92` (imports `load_config` from
  `_review_common` at line 82) and `_review_common.py`'s own internal
  self-call at line 376 (inside the active-hub path resolver).
- Unit test coverage for both fixes (see Testing).

**Out:**
- Changing the wire protocol, token auth, or any other part of
  `_handle_connection` unrelated to exception classification.
- Changing `resolve_plugin_template_path` itself or its other caller
  (`_reviewers.py`'s `mill-agents.yaml` template load) — that call site
  wants cache-first content semantics (it's loading real template content
  to merge, not validating against a source of truth) and is out of scope.
- Auditing/fixing every other possible cache-lag site beyond the two
  `load_config` implementations — grep confirmed only these two call
  `warn_unknown_keys`, and both are covered by this task.
- Any change to how/when the plugin cache itself gets refreshed (that's a
  separate publishing-process concern, not a code fix).

## Decisions

### daemon-exception-classification

- Decision: Broaden `_handle_connection`'s benign-vs-genuine exception
  split to cover the whole recv/decode region, not just the literal
  `json.loads(msg_text)` line. A tuple of benign types
  (`OSError, json.JSONDecodeError, UnicodeDecodeError`) — note
  `ConnectionResetError`/`BrokenPipeError` are `OSError` subclasses, so
  listing `OSError` covers them — raised ANYWHERE between the recv loop and
  the point where `self.handle_request(msg)` is entered should log at
  debug and return cleanly, without attempting to construct/send an error
  response (matching the existing inner-guard behavior). This benign-type
  list does NOT extend into `self.handle_request(msg)`: ANY exception
  surfaced from within `handle_request` — including one of the same benign
  types, e.g. a real `OSError` from a git/file failure during request
  handling — keeps today's behavior, logging at ERROR and attempting a
  `server_error` response. The split is by source region (pre-dispatch vs.
  dispatch-and-beyond) first; exception type only narrows within the
  pre-dispatch region.
- Rationale: The exact original escaping line was not conclusively
  reproduced during discussion (a hand-rolled bare-connect-close probe
  against a live in-process daemon did NOT reproduce the leak — see
  Technical context), so a fix that only patches one specific line risks
  leaving the real trigger unfixed. Widening the classification by
  exception *type* rather than by exact *call site* closes off the whole
  class of "benign connection hiccup" errors regardless of exactly where
  they originate, which is more robust than chasing one line.
- Rejected: Instrumenting first to find the exact original line before
  fixing — more conservative but slower, and the fd-inheritance and
  dual-logger issues (see below) are independently confirmed bugs
  regardless of that line, so they need fixing either way.

### daemon-stdio-redirection

- Decision: `_spawn_server`'s `subprocess.Popen(...)` call must redirect
  the detached daemon's `stdout`/`stderr` to `subprocess.DEVNULL` instead
  of inheriting the spawning client's file descriptors. Not redirected to
  a file of its own — the daemon-logger-consolidation decision below
  already makes the rotating log file the one destination for daemon
  diagnostics, so a second raw-stdio capture file would be redundant.
- Rationale: Confirmed by reading `_spawn_server` — no `stdout=`/`stderr=`
  kwargs are passed to `Popen`, so the daemon (a detached, long-lived
  background process) writes to whatever fd 1/2 happened to be at spawn
  time. Because cold-start spawns happen specifically during `--stage
  prepare`/`--stage finalize` calls (matching every reported repro), the
  daemon's later stderr writes bleed into that command's own
  output/log — this is true independent of what triggers the daemon to log
  at all, so it must be fixed even if the exception-classification fix
  above eliminates the specific JSONDecodeError case. **Unverified
  assumption (Windows):** the POSIX branch's `Popen(cmd, stdout=DEVNULL,
  stderr=DEVNULL, ...)` unambiguously redirects the daemon. The Windows
  branch instead wraps the real command in `cmd /c start "" /B /MIN
  <cmd>` — whether `stdout=`/`stderr=DEVNULL` on that *outer* `Popen` call
  actually propagates to the process `start` launches, or gets reset by
  `start`'s own console/handle handling, was not confirmed by any repro
  during discussion (no Windows environment available). Treat this as an
  assumption to verify manually on Windows post-implementation; the
  Testing section's Windows-branch case only asserts the kwargs are passed
  to `Popen`, not that output is actually suppressed end-to-end.
- Rejected: Leaving fd inheritance as-is and relying solely on the
  exception-classification fix — would still let any future genuine
  daemon-side ERROR bleed into an unrelated client's output, which is the
  actual operator-facing symptom being reported.

### daemon-logger-consolidation

- Decision: Route `DaemonBase`'s connection-level logging through the same
  destination `WikiServer` already uses for business logic (the
  `"wiki-server"` logger's rotating file handler at
  `<wiki_path>/.wiki-daemon.log`), rather than maintaining a second,
  independently-configured logger (`"wiki"`, root-`basicConfig`, stderr).
  **Mechanism: rename, not inject.** `WikiServer.__init__` calls
  `super().__init__("wiki", ...)` (`wiki/_server.py:58`) *before*
  constructing its own `"wiki-server"` logger/handler
  (`wiki/_server.py:64-85`) — but `logging.getLogger(name)` returns the
  same process-wide singleton regardless of construction order, and no
  other code in the repo references `logging.getLogger("wiki")` by that
  literal name (grep confirmed, repo-wide; the only reference to the name
  is `_daemon.py:29`'s `logging.getLogger(self._name)`, parameterized by
  whatever the subclass passes in). So the fix is simply: `WikiServer`
  passes `"wiki-server"` instead of `"wiki"` to `super().__init__(...)`'s
  existing `name` parameter. No `DaemonBase.__init__` signature change,
  no new logger-injection parameter — `self._logger` inside
  `_handle_connection` then resolves to the exact same `Logger` object
  `WikiServer` already configured with the rotating file handler,
  automatically. Additionally, delete `DaemonBase.run()`'s
  `logging.basicConfig(level=logging.INFO, format="[%(name)s]
  %(message)s")` call (`_daemon.py:62-65`) as dead code: it becomes a
  no-op once the connection-level logger shares `"wiki-server"`'s
  `propagate=False` handler, `WikiServer` is the only `DaemonBase`
  subclass that exists today, and nothing else in `wiki/_server.py`'s
  process makes a bare root-level `logging.*` call that depends on it
  (grep confirmed) — keeping it around as a "future subclass" fallback
  would be designing for a hypothetical that doesn't exist yet.
- Rationale: This split is what makes connection-level daemon logs visible
  externally *at all* once `_spawn_server`'s fd-inheritance bug is fixed —
  without it, an operator loses ALL daemon diagnostics (including genuine
  ERROR-level ones) the moment stdio redirection lands, since nothing else
  would print them anywhere reachable. Consolidating onto the existing
  rotating-file pattern keeps genuine errors discoverable (in the log file)
  while guaranteeing they never again leak into unrelated CLI output. The
  rename-only mechanism was chosen over a heavier logger-injection
  redesign because it is provably sufficient (verified via grep that no
  other code depends on the `"wiki"` name or on construction order) and
  needs no `DaemonBase` API change — the smaller change that fully solves
  the problem beats a broader one that doesn't add anything beyond it.
- Rejected: Have `DaemonBase.__init__` accept an injected `Logger` object
  (or a logger-name hook parameter) from its subclass — would require
  reordering `WikiServer.__init__` (build the logger/handler before
  calling `super().__init__`) and widens `DaemonBase`'s public API for a
  generality no current or planned subclass needs; the rename achieves the
  identical runtime result with a one-line change and zero API surface.
- Rejected: Leave the two loggers separate — would silently swallow all
  daemon-side ERROR-level diagnostics once stdio redirection lands, trading
  "loud in the wrong place" for "invisible everywhere," which is worse for
  debugging future daemon issues.

### review-common-load-config-dedup

- Decision: Delete `_review_common.py`'s independent `load_config`
  implementation. Replace it with a thin wrapper that calls
  `_config.load_config(hub_root, mill_dir.parent)` for the core
  template/repo/local merge (this automatically inherits the 2026-05-31
  cache-lag augmentation and any future fixes to that logic), then adds
  `_review_common`'s two extra behaviors on top: raise `ReviewError` when
  neither the plugin template nor a repo-layer config exists at all, and
  warn on stale top-level `review:` keys found in
  `mill_dir / "config.local.yaml"`. **Missing-source check mechanism:**
  `_config.load_config` never raises and carries no "was a source found"
  signal in its return value — it returns `{}` both when nothing exists
  AND when a legitimately-present template/config happens to be empty
  (confirmed: `_config.py:215`'s `yaml.safe_load(...) or {}`). The wrapper
  must therefore NOT infer "missing" from an empty returned dict — that
  would misfire on the legitimately-empty case. Instead it performs its
  own existence check before/alongside delegating, using
  `resolve_plugin_template_path` and `resolve_repo_config_path` — both
  already imported in `_review_common.py` (lines 71-72, currently used
  only by the duplicate being deleted) — and raises `ReviewError` itself
  when both `resolve_plugin_template_path("mill-config.yaml").exists()`
  is false and `resolve_repo_config_path(hub_root, mill_dir.parent)` is
  `None`, mirroring the duplicate's existing lines 1880-1885 check but
  performed independently of (not inferred from) the delegate's return.
- Rationale: The bug that caused #676/#670 was exactly this — a second copy
  of `load_config` drifting out of sync after `_config.load_config` was
  patched. Point-fixing `_review_common.load_config` again just recreates
  the same drift risk for the next fix to the shared merge logic. `_config`
  and `_review_common` already end with the identical last two steps
  (`apply_env_overrides`, `_apply_dispatch_shim`) — the implementations
  were near-duplicates even before this bug, confirming the duplication was
  never load-bearing.
- Rejected: Port the 2026-05-31 augmentation block into
  `_review_common.load_config` as a second, separate point-fix — faster
  short-term but repeats the exact failure mode being fixed.

## Technical context

- `_daemon.py:131-179` (`DaemonBase._handle_connection`) — the recv loop,
  inner `json.loads` guard, and outer generic exception handler all live
  here. `self._logger = logging.getLogger(self._name)` is set in
  `DaemonBase.__init__` (line 29); `self._name` is `"wiki"` for
  `WikiServer` (passed via `super().__init__("wiki", ...)` in
  `wiki/_server.py:58`). `DaemonBase.run()` (line 62-65) calls
  `logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")`
  if root has no handlers yet — this is what produces the observed
  `[wiki] exception in _handle_connection: ...` prefix on stderr.
- `wiki/_server.py:39-104` (`WikiServer.__init__`/`on_start`/`on_stop`) —
  the separate `"wiki-server"` logger with `RotatingFileHandler` at
  `wiki_path / ".wiki-daemon.log"`, `propagate=False`. This is the
  destination to consolidate onto.
- `wiki/_client.py:666-694` (`_spawn_server`) — the `subprocess.Popen` call
  needing stdio redirection. Has a Windows branch (`cmd /c start ... /B
  /MIN`) and a POSIX branch (`start_new_session=True`) — both need the
  redirection, and the fix must not break the existing
  `close_fds=True`/`start_new_session=True`/`CREATE_NEW_PROCESS_GROUP`
  behavior those branches already rely on for detachment.
- `wiki/_client.py:105-129` (`wait_for_socket_reachable`) and
  `wiki/_client.py:763-796` (`_is_stale`) are the two remaining
  intentional bare-connect probes (per `eed505d9`'s commit message) that
  can trigger the daemon's empty-payload path during cold-start polling —
  useful context for understanding *when* connection noise is expected,
  even though the fix here is classification-based rather than
  probe-elimination-based. A hand-written repro against a live in-process
  `DaemonBase` subclass performing exactly this connect-then-close pattern
  did NOT reproduce an ERROR-level leak (see below) — the inner guard does
  correctly catch and silence the literal empty-payload case today. The
  outer-handler leak must therefore come from some other exception raised
  in the same try block (or a timing/platform variant not reproduced
  locally, e.g. Windows RST-vs-FIN close semantics), which is exactly why
  the recommended fix classifies by exception type across the whole block
  rather than patching one specific call site.
- `_config.py:193-276` (`load_config`) — the reference implementation with
  the working cache-lag augmentation (lines 220-231) and the
  `warn_unknown_keys` call (line 265) to mirror/delegate to.
- `_config.py:113-127` (`warn_unknown_keys`) and `_config.py:130-149`
  (`resolve_plugin_template_path`) — shared by both `load_config`
  implementations; not modified by this task (only `_review_common`'s
  caller of them changes).
- `_review_common.py:1842-1912` (`load_config`) — the duplicate to
  delete/replace. Note its second positional arg is `mill_dir` (a
  `.millhouse` directory), not `worktree_root` directly —
  `_config.load_config` expects `worktree_root`, so the delegating wrapper
  must pass `mill_dir.parent`. The stale-`review:`-key check (lines
  1888-1899) reads `mill_dir / "config.local.yaml"` directly before
  merging; since the delegate does its own internal local-config read
  without exposing it, the wrapper will need its own (cheap, read-only)
  peek at that same file to preserve the stale-key warning — this doesn't
  need to be the merge-authoritative read, just enough to check for a
  `review:` key.
- `_review_common.py` callers to verify still work post-refactor:
  `millpy-implement.py`, `millpy-abandon.py`, `millpy-review-code.py`,
  `millpy-validate-plan.py`, `millpy-fix.py`,
  `millpy-merge-in-subagent.py`, `millpy-review-plan.py`,
  `millpy-review-discussion.py:92` (imports `load_config` from
  `_review_common` at line 82), and `_review_common.py`'s own internal
  self-call at line 376 (inside the active-hub path resolver — see the
  docstring at lines 355-361 explaining why `cfg` is sourced from the
  hub's own `.millhouse/` there).

## Testing

- `plugins/mill/unit_tests/test-wiki-daemon.py`: existing checks (w)/(x)
  at lines ~643-683 already cover the literal empty/malformed top-level
  `json.loads(msg_text)` payload → debug, no error. Add: (1) a mocked
  `conn.recv()` that raises a benign type (e.g. `OSError`/
  `ConnectionResetError`) from the recv loop itself, i.e. before
  `handle_request` is ever entered — must log debug, no ERROR, no crash
  (this is the recv-loop half of the widened pre-dispatch region the (w)/
  (x) checks don't cover, since those only exercise the `json.loads` line);
  (2) a fake `handle_request` that raises a benign type (e.g. `OSError`) —
  must still log ERROR and attempt the `server_error` response, proving
  the benign-type list does not extend past the dispatch boundary; (3) a
  fake `handle_request` that raises a non-benign type (e.g. `KeyError`) —
  must also log ERROR, confirming genuine bugs of any type stay visible
  once inside `handle_request`. TDD candidates: (2) and (3) should already
  pass against current code (baseline, since today everything from
  `handle_request` already logs ERROR); (1) should fail before the fix
  (today an `OSError` from `recv()` is uncaught by the inner guard and
  falls through to the outer ERROR handler).
- `_daemon.py` / `wiki/_server.py` (daemon-logger-consolidation): add a
  case asserting that after consolidation, a debug- or error-level
  connection log emitted via `DaemonBase`'s logger reaches the same
  `wiki-server` rotating-file destination `WikiServer` already uses — not
  root/`basicConfig`-configured stderr. This is the test the review found
  missing: none of the other cases above verify *where* the log lands,
  only whether it's emitted at all.
- `wiki/_client.py`/`_spawn_server`: add a test (likely in
  `test-wiki-daemon.py` alongside the existing `_spawn_server`-mocking
  tests at lines ~232/274/316/570, or a new section) that patches
  `subprocess.Popen` directly and asserts the call's `stdout`/`stderr`
  kwargs are `subprocess.DEVNULL`, for both the POSIX and Windows
  branches.
- `plugins/mill/unit_tests/test-config.py`: `test_worktree_template_augments_template_cfg`
  (line 749) is the existing reference case for `_config.load_config`'s
  augmentation behavior — no changes needed here, it's the behavior being
  delegated to.
- `plugins/mill/unit_tests/test-review-common.py` (and/or
  `test-review-common-guard.py`): add the equivalent of
  `test_worktree_template_augments_template_cfg` for
  `_review_common.load_config`, proving the delegation actually picks up
  the augmentation. Also keep/verify existing coverage for the two
  preserved review-specific behaviors (missing-source `ReviewError`, stale
  `review:`-key warning) continues to pass post-refactor.

## Q&A log

- **Q:** How should the daemon's outer-handler noise (bug 1) be fixed —
  broaden exception classification across the whole connection-handling
  block, instrument first to find the exact line, or only fix the
  fd-inheritance/logging side? **A:** [auto-pick] Fix all three together
  (broaden classification, redirect spawned daemon's stdio, consolidate
  loggers). **Why:** each is independently confirmed by direct code
  reading; a hand-rolled repro of the literal empty-payload case did not
  reproduce the leak, meaning the exact original trigger line is unproven,
  so classifying by exception type is more robust than a single-line
  patch, and the fd-inheritance/dual-logger issues are real regardless of
  that trigger.
- **Q:** Should the spawned wiki daemon's stdout/stderr be redirected away
  from the client that spawned it? **A:** [auto-pick] Yes — redirect
  instead of inheriting. **Why:** confirmed via code reading that
  `_spawn_server`'s `Popen` call has no stdio redirection, which is the
  mechanism by which daemon-side logs (of any severity, from any cause)
  reach unrelated CLI output at all.
- **Q:** Should `DaemonBase`'s connection-level logger be consolidated with
  `WikiServer`'s existing rotating-file logger? **A:** [auto-pick] Yes.
  **Why:** without consolidation, fixing stdio redirection would make ALL
  daemon-side diagnostics (including genuine errors) invisible, since
  nothing else prints them anywhere reachable.
- **Q:** How should `_review_common.load_config`'s stale duplication of
  `_config.load_config` (bug 2) be resolved — delete and delegate, or
  point-fix the duplicate again? **A:** [auto-pick] Delete the duplicate;
  delegate to `_config.load_config` and layer the two review-specific
  behaviors on top. **Why:** the bug was caused by exactly this kind of
  duplication drifting out of sync after a point-fix; a second point-fix
  recreates the same risk for the next change to the shared merge logic.
- **Q:** Are there other config-validation call sites beyond the two
  `load_config` implementations that need the same fix? **A:** [auto-pick]
  No — grep confirmed only `_config.py` and `_review_common.py` call
  `warn_unknown_keys`; `_reviewers.py`'s use of
  `resolve_plugin_template_path` is for `mill-agents.yaml` content
  merging, not validation, and is out of scope. **Why:** confirmed by
  direct grep across `plugins/mill/scripts/*.py`, not assumed.
- **Q:** What testing approach should this task use? **A:** [auto-pick]
  Extend the existing test files (`test-wiki-daemon.py`, `test-config.py`,
  `test-review-common.py`) with targeted new cases rather than manual
  verification only. **Why:** matches this repo's existing unit_tests/
  conventions and TDD expectations; the relevant files and reference test
  cases (e.g. `test_worktree_template_augments_template_cfg`) already
  exist to mirror.
- **Q:** [round 1 review, GAP] Does the affected/verify caller list for the
  `_review_common.load_config` refactor cover every call site of the
  duplicate being deleted? **A:** [auto-pick] No — it was missing
  `millpy-review-discussion.py:92` (imports `load_config` from
  `_review_common` at line 82) and `_review_common.py`'s own internal
  self-call at line 376. Added both to Scope §In and Technical context.
  **Why:** confirmed by grep — both are real, unlisted callers of the
  function being deleted; omitting them would have left the refactor
  incomplete.
- **Q:** [round 1 review, GAP] Does Testing cover the
  daemon-logger-consolidation decision? **A:** [auto-pick] No — none of
  the listed cases verified *where* a connection-level log lands post-
  consolidation, only whether it's emitted. Added a case asserting
  `DaemonBase` connection logs reach the `wiki-server` rotating-file
  destination, not root/stderr. **Why:** the consolidation decision's own
  rationale says this routing is load-bearing (it's what keeps errors
  discoverable once stdio redirection ships), so it needs direct test
  coverage, not just an assumption that the other cases exercise it.
- **Q:** [round 2 review, GAP] How does the `_review_common.load_config`
  wrapper determine "no config source found" post-delegation, given
  `_config.load_config` never raises and returns `{}` for both "nothing
  found" and "found but empty"? **A:** [auto-pick] The wrapper performs
  its own existence check via the already-imported
  `resolve_plugin_template_path`/`resolve_repo_config_path`, independent
  of the delegate's return value, and raises `ReviewError` itself when
  both report absent. **Why:** confirmed via code reading that both
  functions are already imported in `_review_common.py` (lines 71-72) and
  that `_config.load_config` genuinely carries no found/missing signal
  (`_config.py:215`'s `yaml.safe_load(...) or {}`) — inferring "missing"
  from an empty dict would misfire on a legitimately-empty config.
- **Q:** [round 2 review, GAP] What is the concrete mechanism for routing
  `DaemonBase`'s connection-level logger to `WikiServer`'s existing
  rotating-file destination — inject a `Logger` object, add a
  logger-name hook, or something else? **A:** [auto-pick] Rename only —
  `WikiServer` passes `"wiki-server"` instead of `"wiki"` to
  `super().__init__(...)`'s existing `name` parameter; no `DaemonBase`
  API change. **Why:** confirmed via grep that no other code references
  `logging.getLogger("wiki")` by that literal name, and that
  `logging.getLogger(name)` returns the same singleton regardless of
  construction order — so the rename alone makes `_handle_connection`'s
  logger resolve to the exact same configured `Logger` `WikiServer`
  already builds, with a one-line change and no widened API surface.
