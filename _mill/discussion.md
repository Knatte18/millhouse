# Discussion: Green the unit test suite on wiki-v3-adoption so it can merge to main

```yaml
task: Green the unit test suite on wiki-v3-adoption so it can merge to main
slug: wiki-v3-test-suite-green
status: discussing
parent: hanf/wiki-v3-adoption
```

## Problem

Branch `hanf/wiki-v3-adoption` carries the V3 wiki-module adoption work and is otherwise complete -- the two prerequisite sub-tasks (verify-isolation `7e10ddb`, batch3-finish `20027ed`) have already landed -- but `verify` is not green. The project rule "no defective code on main" blocks the merge until the suite is fully green. This task closes that gap.

Reproducing from this worktree (which branches off the same parent):

```bash
PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
```

reports **11 of 77 fail**, distributed across **four root causes** (issue #377 enumerates three; the fourth -- `test-spawn-core.py`'s two failing `discover_active_worktrees` cases -- was discovered during exploration and is in scope here because the merge gate is "fully green", not "green except the documented three").

The post-task expectation is a single line at the bottom of `run-all.py` output: `Ran 77 tests in <N>s  OK` (or the runner's equivalent) and exit code 0.

## Scope

**In:**

- Fix the four root causes below so `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` reports 77/77 pass.
- One production-code change: close logging handlers in `WikiServer.on_stop()` so the `RotatingFileHandler`-held lock on `.wiki-daemon.log` is released before the daemon process exits.
- Test-fixture changes in `test-bg-launcher.py`, `test-spawn-core.py`, `test-fold.py`, plus a shared low-`idle_timeout` + daemon-exit-wait pattern usable by any daemon-touching test fixture.

**Out:**

- Wider test-coverage expansion. Only the existing 11 reds are in scope; new tests are added only when a fix requires them (e.g. a regression test asserting `on_stop` closes handlers).
- Production-code refactors beyond the minimum `on_stop` change. No reshuffling of `_daemon.py`, `WikiServer`, the wiki client, or the V3 `tasks.json` schema.
- Anything outside `plugins/mill/`. The V3 wiki module under `plugins/mill/scripts/wiki/` is touchable only via the targeted `on_stop` fix.
- Changing `parse_home_md`'s accepted syntax. The fixture is wrong (uses V2's `[[slug]] [active]` form); `parse_home_md` already matches the rendered V3 form `[slug] [active]`.
- Renaming/removing failing test cases. Each red turns green by fixing the underlying cause; no test is deleted as a shortcut.
- Adding test-fold.py to `ALLOWED_FILES` in `test-no-direct-rmtree.py`. Migration through `_safe_rmtree.safe_rmtree` is the correct fix once RC1 lands.

## Decisions

### RC1-prod -- WikiServer.on_stop closes log handlers

- Decision: Extend `WikiServer.on_stop()` (`plugins/mill/scripts/wiki/_server.py:79-81`) to (a) log the shutdown line, then (b) iterate `self._log.handlers[:]` and call `handler.close(); self._log.removeHandler(handler)` for each. This releases the `RotatingFileHandler`'s OS handle on `.wiki-daemon.log` before `DaemonBase.run()`'s `finally` block unlinks the state file and the process exits.
- Rationale: The lock is held by the daemon process, not the test process. Closing handlers in the daemon itself is the only way to release it from inside the daemon's address space. Doing it in `on_stop` is correct in production too (daemon may be restarted, log files may be rotated externally). Issue #377 root cause 1 names this fix.
- Rejected: (a) Kill daemon via `os.kill` from fixture -- breaks the clean idle-exit contract and risks orphaned state files. (b) Move handler ownership to `DaemonBase` so the base class closes it -- production refactor beyond minimum.

### RC1-test -- fixtures wait for daemon process exit before tempdir teardown

- Decision: Add a shared helper, `_test_helpers.wait_for_daemon_exit(wiki_path: Path, *, timeout: float = 5.0) -> None`, that polls for absence of `wiki_path / ".wiki-daemon.json"` (the daemon's state file, which `DaemonBase.run()` unlinks in `finally` after `on_stop()` completes). Returns silently on absent file or on timeout (treats timeout as a no-op rather than a hard failure so existing teardown paths still run). Every fixture that triggers daemon work (`test-bg-launcher.py`, `test-fold.py`, the eight RC1-affected tests if their fixtures trigger daemon work, `test-marker.py`'s setup, etc.) calls `wait_for_daemon_exit(wiki_path)` *after* the last wiki operation and *before* tempdir teardown.
- Rationale: `on_stop` closing handlers is necessary but not sufficient -- the daemon process must actually run `on_stop` and exit before the tempdir is deleted. Polling the state-file absence is the cleanest exit signal because `DaemonBase.run()`'s `finally` block guarantees the state file is unlinked after `on_stop()`. Cross-platform, no PID polling, no extra RPC surface. Pairs with RC1-low-idle (below) so the wait completes in ~1-2s.
- Rejected: (a) PID-based polling with `os.waitpid` -- the daemon is not a direct child of the test process (it's launched detached), so `waitpid` doesn't work; `psutil.pid_exists` would add a dependency. (b) New `OP_STOP` daemon RPC -- production surface for a test-only need.

### RC1-seed -- fixtures whose tests exercise list_tasks_brief must seed tasks.json

- Decision: Every RC1-affected test fixture whose assertions traverse `wiki.list_tasks_brief` / `slug_from_branch` / `_marker.task_data` / `discover_active_worktrees` (any code path that reads the V3 `tasks.json` TinyDB) must register the test task via `wiki.upsert_task(wiki_path, slug, title=title, status="active")` -- the same seeding mechanism as RC2. Specifically: `test-marker.py`'s `_make_task_worktree` (and any happy-path test that calls `slug_from_branch`), and any other RC1 fixture the planner identifies during plan-time audit. Fixtures that only assert on rendered Home.md text (no V3-client call) can keep their raw `Home.md` writes; those that go through the daemon must seed.
- Rationale: Issue #377 attributed the RC1 reds entirely to the daemon log lock, but happy-path tests in `test-marker.py` (and likely others in the eight-file set) fail for a second, distinct reason: the V3 `wiki.list_tasks_brief` reads `tasks.json`, not `Home.md`. With an empty TinyDB, `slug_from_branch` raises `MarkerError("branch slug ... not present in Home.md")` and the assertion never reaches the lock-error path. Fixing only `on_stop` would leave these reds in a different failure mode. Seeding via `upsert_task` is the same correction RC2 already applies; this decision generalises it to all RC1 fixtures that touch the V3 wiki client.
- Rejected: (a) Have `slug_from_branch` fall back to parsing Home.md when `tasks.json` is empty -- reintroduces V2 dual-source ambiguity in production. (b) Hand-write `tasks.json` JSON in the fixture -- couples the test to TinyDB internals.

### RC1-low-idle -- test fixtures construct WikiServer / start daemon with idle_timeout ~= 1s

- Decision: Wherever a test fixture starts (or causes the wiki daemon to start), pass `idle_timeout=1` to the constructor or the equivalent CLI arg. With the standard 600s default, `wait_for_daemon_exit` would block tests for ten minutes.
- Rationale: `DaemonBase.run()`'s accept loop exits as soon as `time.monotonic() - last_activity > self._idle_timeout`. With `idle_timeout=1`, the daemon exits within ~1-2s of the last RPC, which `wait_for_daemon_exit` then observes via state-file absence. Test wall-clock impact: a few seconds per affected test file, acceptable.
- Rejected: (a) Default-change `idle_timeout` to 1s -- production daemons would churn. (b) Send a SIGTERM-equivalent from fixture -- noisier and not cross-platform.

### RC2 -- test-bg-launcher fixture registers slug via wiki.upsert_task (not raw Home.md)

- Decision: In `_make_container_form_worktree` (`plugins/mill/unit_tests/test-bg-launcher.py:18-109`), after the wiki clone is initialised, call `wiki.upsert_task(wiki_path, slug, title=title, status="active")` so the slug lands in the V3 `tasks.json` TinyDB store. (Signature at `plugins/mill/scripts/wiki/_client.py:41-50` is `upsert_task(wiki_path, slug, *, title=None, brief=None, body=None, group=None, status=None)` -- `slug` is positional; the lifecycle keyword is `status`, not `phase`.) The raw `Home.md` write at line 101-102 becomes redundant once `upsert_task` runs (the daemon renders Home.md from tasks.json); remove it. Keep `_test_helpers.seed_wiki_config(wiki_path, include_roles=False)` -- it's still needed.
- Rationale: `_marker.slug_from_branch` (`plugins/mill/scripts/_marker.py:52`) calls `wiki.list_tasks_brief(wiki_path)`, which is now backed by `tasks.json`, not Home.md text parsing. The fixture must drive the same code path producers use in real worktrees. Aligns the fixture with the V3 contract.
- Rejected: (a) Teach `list_tasks_brief` to fall back to Home.md when `tasks.json` is absent -- reintroduces V2 dual-source ambiguity, breaks render determinism. (b) Pre-seed `tasks.json` by hand-writing TinyDB JSON -- couples the fixture to TinyDB's internal layout.

### RC3 -- migrate test-fold.py rmtree callsites to _safe_rmtree.safe_rmtree

- Decision: Replace the callsite at `plugins/mill/unit_tests/test-fold.py:97` (`shutil.rmtree(td.name, ignore_errors=True)`) with `_safe_rmtree.safe_rmtree(Path(td.name), allowed_root=Path(td.name), ignore_errors=True)`. Line 95 is the explanatory comment, not a callsite -- one `shutil.rmtree` call exists in the file. Import `_safe_rmtree` at top of file alongside the existing scripts-path setup. Do **not** add `test-fold.py` to `ALLOWED_FILES` in `test-no-direct-rmtree.py`. With RC1 in place, the daemon-lock fallback path the wrapper exists to handle should rarely fire, but `ignore_errors=True` keeps the existing safety net.
- Rationale: `safe_rmtree` already strips junctions then runs `shutil.rmtree`, which is exactly what the existing wrapper attempts -- migration is one-for-one and preserves intent. Allowlisting would expand the surface of code that bypasses junction-stripping, contradicting issue #100's lesson.
- Rejected: (a) Add `test-fold.py` to `ALLOWED_FILES` -- weakens the gate for the wrong reason. (b) Remove the wrapper entirely (rely on RC1 to make `original_cleanup()` always succeed) -- works in theory but loses the safety net; cost of the migration is ~3 lines.

### RC4 -- test-spawn-core fixture uses V3 Home.md syntax

- Decision: In `test_discover_active_worktrees_standard_layout` (`plugins/mill/unit_tests/test-spawn-core.py:894`) and `test_discover_active_worktrees_subfolder_install` (line 915), change the inlined `home_md` strings from `[[my-task]] [active]` (V2 wiki-link form, no longer matched) to `[my-task] [active]` (V3 rendered form). `wiki._parse.parse_home_md` (`plugins/mill/scripts/wiki/_parse.py:39-47`) accepts `[slug]` for active tasks and `[[slug]](proposal-<slug>.md)` only for the proposal-link variant -- the bare `[[slug]]` form the fixture used was never valid in V3.
- Rationale: The test is testing `discover_active_worktrees` (correct), but it feeds parsed Home.md tasks through `parse_home_md`. With the V2-form input, `parse_home_md` returns `[]`, so `slugs_in_home` is empty, so the porcelain branch never matches a slug. Two-character fix; production code stays untouched.
- Rejected: (a) Teach `parse_home_md` to accept the V2 form -- regresses the parser to a syntax that's no longer produced anywhere. (b) Pre-seed via `wiki.upsert_task` and parse the rendered Home.md back -- adds an unnecessary daemon round-trip to a unit test that only exercises porcelain parsing.

### Verification command and bar

- Decision: After all four root causes are fixed, the canonical command is `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py`, run from the worktree root. Pass condition: exit code 0 AND the runner's final line is `Ran 77 tests in <N>s  OK` (or runner-equivalent) AND no `FAIL` lines in the output.
- Rationale: This is the same command issue #377 uses and the same command mill-merge's pre-merge gate runs. The `PYTHONPATH=` literal-empty prefix is mandated by CLAUDE.md (`## Script invocation`, "Verify command shape") so the subprocess does not inherit the cache PYTHONPATH and load V3-cache modules instead of worktree code. The `_plan_validate.py` `verify-not-isolated` check enforces this in the plan file.
- Rejected: (a) Per-file `python plugins/mill/unit_tests/test-X.py` invocations -- skips the gate's coverage of file discovery and doesn't match how verify runs in mill-merge. (b) Running tests inside the cache via `${CLAUDE_PLUGIN_ROOT}` -- tests must validate worktree code, not cache code.

## Technical context

**Production code touched (exactly one file):**

- `plugins/mill/scripts/wiki/_server.py` -- `WikiServer.on_stop` (lines 79-81). Logger setup at lines 60-72 creates the `RotatingFileHandler` that holds the lock. Pattern for closing in `on_stop`:

  ```python
  def on_stop(self) -> None:
      self._log.info("wiki-server stopping")
      for handler in list(self._log.handlers):
          try:
              handler.close()
          except Exception:
              pass
          self._log.removeHandler(handler)
  ```

  Iterate over `list(...)` because `removeHandler` mutates `self._log.handlers`. Swallow `handler.close()` errors -- best-effort cleanup, the alternative is a tempdir teardown failure for the test that is already exiting cleanly.

**Test infrastructure to add (one helper):**

- `plugins/mill/unit_tests/_test_helpers.py` -- add `wait_for_daemon_exit(wiki_path: Path, *, timeout: float = 5.0) -> None`. Polls `wiki_path / ".wiki-daemon.json"` every ~50ms until missing or timeout. Returns silently on either. No exception on timeout (best-effort wait).

**Test files modified:**

- `plugins/mill/unit_tests/test-bg-launcher.py` -- fixture seeds slug via `wiki.upsert_task`; teardown calls `wait_for_daemon_exit`; daemon idle-timeout reduced for fixture-spawned daemons (via `WikiServer(idle_timeout=1, ...)` if test instantiates directly, or by setting an env var the daemon reads -- see "Idle-timeout plumbing" below).
- `plugins/mill/unit_tests/test-fold.py` -- import `_safe_rmtree`, replace both `shutil.rmtree(td.name, ignore_errors=True)` calls with `_safe_rmtree.safe_rmtree(Path(td.name), allowed_root=Path(td.name), ignore_errors=True)`.
- `plugins/mill/unit_tests/test-spawn-core.py` -- change two inlined `home_md` strings from `[[my-task]] [active]` to `[my-task] [active]`.
- The eight RC1 files (`test-marker.py`, `test-millpy-spawn.py`, `test-review-cli.py`, `test-review-code-flow.py`, `test-review-common.py`, `test-review-discussion-flow.py`, `test-review-plan-flow.py`, `test-setup-hub-links.py`) -- audit fixtures along **two dimensions**: (1) any that trigger daemon work via `wiki.upsert_task` / `wiki.list_tasks_brief` / similar must call `wait_for_daemon_exit(wiki_path)` before tempdir teardown; (2) any whose tests assert through `wiki.list_tasks_brief` / `slug_from_branch` / `_marker.task_data` / `discover_active_worktrees` (i.e. read paths that hit `tasks.json`) must seed the task via `wiki.upsert_task(wiki_path, slug, title=title, status="active")` per RC1-seed. `test-marker.py`'s `_make_task_worktree` is a known case for (2) -- its happy-path tests currently fail in part because `tasks.json` is empty, not only because of the log lock. Plan-time investigation step: grep each failing test for wiki/daemon entry points and apply each fix where applicable; the two fixes are independent (a test can need wait, seed, both, or neither).

**Idle-timeout plumbing.** The daemon process is typically launched by the wiki client transparently (first wiki RPC starts it). Two variants to handle in fixtures:

1. **Direct instantiation** (test imports `WikiServer` and calls `.run()` in a thread or subprocess): pass `idle_timeout=1`.
2. **Indirect via client** (test only calls `wiki.upsert_task(...)`): the daemon is auto-spawned with whatever default the launcher uses. Plan-time task: locate the launcher (likely a helper in `wiki/_client.py` or alongside), and verify whether it reads an `idle_timeout` arg / env var. If not, the minimal addition is a env var `WIKI_DAEMON_IDLE_TIMEOUT` honored by `_server.py`'s `__main__` block (the fallback already reads `sys.argv[2]`, so wiring an env var is one line). Tests set the env var in their fixture; production unaffected.

**Files referenced for the planner:**

- `plugins/mill/scripts/wiki/_server.py:34-81` -- WikiServer lifecycle + handler setup.
- `plugins/mill/scripts/_daemon.py:57-102` -- DaemonBase.run / on_stop / state-file unlink ordering.
- `plugins/mill/scripts/_marker.py:29-71` -- slug_from_branch via list_tasks_brief.
- `plugins/mill/scripts/_safe_rmtree.py:69-145` -- safe_rmtree signature and refusal cases.
- `plugins/mill/scripts/_spawn_core.py:149-214` -- discover_active_worktrees porcelain parser.
- `plugins/mill/scripts/wiki/_parse.py:6-60` -- parse_home_md accepted syntax.
- `plugins/mill/scripts/wiki/_client.py:41-` -- upsert_task / list_tasks_brief signatures (planner: confirm exact kwargs at plan time).
- `plugins/mill/unit_tests/test-no-direct-rmtree.py:22-38` -- BANNED_PATTERNS + ALLOWED_FILES (do not edit ALLOWED_FILES).
- `plugins/mill/unit_tests/_test_helpers.py` -- existing fixture helpers; add `wait_for_daemon_exit` here.

**Gotchas:**

- Repeat from CLAUDE.md `## Script invocation`: every `verify:` command in the eventual plan MUST start with `PYTHONPATH=` (literal, empty value) so the test subprocess loads worktree code, not cache code. `_plan_validate.py` enforces this; mill-plan auto-prepends on validator failure.
- Repeat from CLAUDE.md `## Hard constraints` / `## Path invariants`: never `rm -rf` a worktree; use `_safe_rmtree` (already what we're enforcing in RC3).
- ASCII-only stdout in `print()` / `_log()` (CLAUDE.md `## Conventions`). The `on_stop` log line is fine; any new diagnostic prints must avoid `--`, `->`, etc. raw.
- `_log.info(...)` calls before handler close in `on_stop` still need to flush. `handler.close()` flushes implicitly, so logging the shutdown line before the handler-close loop is safe.
- `_walk_strip_reparse_points` in `_safe_rmtree` already handles the test-fold scenario; no need to add a "wait for daemon" step inside `safe_rmtree` itself.

## Constraints

- **CLAUDE.md `## Hard constraints`**: no plugin code outside `${CLAUDE_PLUGIN_ROOT}` references; never pass junctions to Python helpers; working state stays on the task branch.
- **CLAUDE.md `## Script invocation`**: verify-not-isolated rule -- all plan `verify:` commands prefix with `PYTHONPATH=` (literal empty).
- **CLAUDE.md `## Path invariants`**: never recursive-delete without junction-stripping; that's exactly what RC3 enforces in tests.
- **Project rule (project_memory: `feedback_never_merge_defective.md`)**: no defective code on main. The task does not finish until 77/77 pass. No "merge with known failures" fallback.
- **`mill-config.yaml` hub file and plugin template stay in sync** (CLAUDE.md `## Conventions`). Not affected by this task -- no config schema changes.

## Testing

Per-module test approach. None of the four root causes require fundamentally new test files; three of them are *test bugs* whose fix is "make the test work". RC1 is a production bug whose fix wants a small regression test.

**RC1 regression test (new, small):**

- Add `plugins/mill/unit_tests/test-wiki-server-on-stop.py` (or fold into existing `test-wiki-daemon.py` if the planner judges the file is the right home). One test case: instantiate `WikiServer` in-process, attach a sentinel attribute that records whether handlers were closed, call `on_stop()`, assert (a) `self._log.handlers == []` AND (b) the underlying `RotatingFileHandler`'s `stream` is closed (`handler.stream.closed is True` after `handler.close()` on the original instance). The latter is the load-bearing assertion -- the file lock release is what RC1 cares about. TDD candidate: write this test first, watch it fail against the current `on_stop`, then implement the close loop and watch it pass.
- Avoid: starting a real daemon, real socket bind, or a real log file. Use a tempfile path for the log if needed but tear it down explicitly in the test.

**RC1 fixture-side coverage** is implicit in the existing eight test files turning green. Adding a "fixture waits for daemon" unit test of its own would test `wait_for_daemon_exit` directly: create a tempdir, drop a `.wiki-daemon.json` file, spawn a background thread that removes it after 200ms, call `wait_for_daemon_exit(path, timeout=2.0)`, assert it returns within ~250ms. Optional -- planner's call.

**RC2 verification**: `test_launcher_accepts_valid_task_worktree` in `test-bg-launcher.py` already exists and currently fails for the right reason ("branch slug 'test-task' not present in Home.md"). It becomes the test for RC2 once the fixture seeds via `upsert_task`. No new test needed.

**RC3 verification**: `test-no-direct-rmtree.py` itself is the test. Currently fails because of the two `shutil.rmtree` callsites in `test-fold.py`. After migration to `_safe_rmtree.safe_rmtree`, the gate passes. Additionally, `test-fold.py`'s own tests must keep passing -- the cleanup behavior is unchanged, just routed through a different helper.

**RC4 verification**: `test_discover_active_worktrees_standard_layout` and `test_discover_active_worktrees_subfolder_install` in `test-spawn-core.py` already exist and currently fail with `expected 1 result, got 0: []`. They become green after the two-character fixture fix.

**Whole-suite verification**: `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` reports `0 failures across 77 tests` (or runner-equivalent). This is the merge gate.

**Test ordering caveat**: `run-all.py` runs each test file as a subprocess; daemon state files live under tempdirs, so cross-test contamination is unlikely. The planner should still check that adding `wait_for_daemon_exit` to one fixture doesn't change another fixture's daemon-startup behavior (e.g. via a shared `.wiki-daemon.json` path) -- specifically, every test must use its own tempdir-rooted wiki path (existing pattern already does this).

## Q&A log

- **Q:** Include RC4 (test-spawn-core, 2 reds undocumented in #377) in scope? **A:** Yes -- "fully green" is the merge gate; partial green still blocks the merge by project rule.
- **Q:** RC1 fix on production-only, test-only, or both? **A:** Both. `on_stop` closing handlers is correct on its own merits; fixture wait avoids races even if a future handler is added; defense in depth.
- **Q:** RC1 daemon-exit signal -- state-file polling vs PID polling vs new stop RPC? **A:** Poll `.wiki-daemon.json` absence. `DaemonBase` unlinks it after `on_stop()`; cross-platform; no new RPC surface; no PID/psutil dependency.
- **Q:** RC1 fixture idle_timeout for test daemons? **A:** Lower to ~1s. Pass `idle_timeout=1` on direct WikiServer construction; for client-spawned daemons, plan-time task to wire an env var (`WIKI_DAEMON_IDLE_TIMEOUT`) honored by `_server.py`'s `__main__`. Production untouched.
- **Q:** RC2 -- raw Home.md vs `wiki.upsert_task` in bg-launcher fixture? **A:** `wiki.upsert_task`. V3's source of truth is `tasks.json`; the daemon renders Home.md from it. Aligning the fixture with the production contract removes the divergence.
- **Q:** RC3 -- migrate to `_safe_rmtree` or allowlist `test-fold.py`? **A:** Migrate. Allowlisting weakens the gate for the wrong reason; migration is one-for-one and keeps the `ignore_errors=True` safety net via the helper's own kwarg.
- **Q:** RC4 -- accept V2 `[[slug]] [active]` syntax in parser, or fix the fixture? **A:** Fix the fixture (two characters). V2 syntax is no longer produced anywhere; teaching the parser to re-accept it would regress determinism.
- **Q:** Operator-given direction for this task? **A:** "Just fix everything. Make sure all tests turn green." Implication: all recommended options accepted; planner has authority to make plan-time investigation calls (e.g. which of the eight RC1 files genuinely need `wait_for_daemon_exit` in their fixture vs which were red purely because the daemon process didn't release the log lock).
