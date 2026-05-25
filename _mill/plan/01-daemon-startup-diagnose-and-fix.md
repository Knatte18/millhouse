# Batch: daemon-startup-diagnose-and-fix

```yaml
task: "Finish V3 wiki adoption — complete batch 3 port and test sweep"
batch: daemon-startup-diagnose-and-fix
number: 1
cards: 3
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-claim.py"
depends-on: []
```

## Batch Scope

The V3 wiki daemon-startup path in `wiki._client._spawn_server` fails to bring up its detached subprocess in test fixtures, causing every `wiki.<fn>` call without a mock to eat the 10 s `SPAWN_TIMEOUT` and raise `WikiStartupError: daemon did not start within timeout`. The canonical victim is `test-millpy-claim.py`, where 11 of 12 tests currently fail. This batch root-causes the failure and fixes it in product code.

The approach: card 1 adds **env-var-gated stderr capture** to `_spawn_server` so the detached child's startup-time error becomes visible. Card 2 reproduces and diagnoses (the implementer reads the captured stderr, identifies the root cause, and writes it into the card-3 requirements text via a commit-message body — no separate doc file). Card 3 applies the fix in product code AND reverts the debug instrumentation in the same commit so production stays clean.

Batch-local decisions (differ from `## Shared Decisions` in `00-overview.md`):

- **Card 3's exact requirements depend on card 2's diagnosis output.** The plan describes the diagnostic process and the constraint that the fix MUST be in product code (not in test fixtures). If card 2's diagnosis reveals the fix is structurally larger than the card-3 effort budget (M=2), the implementer halts under the stuck-policy and asks the operator before continuing — see `## Shared Decisions ## Decision: stuck-policy-pause-for-human`.
- **`MILL_WIKI_DAEMON_DEBUG=1` is the debug gate.** Card 1 reads this env var; default-off behaviour must be byte-identical to current `_spawn_server`. Card 3 deletes the env-var-gated branch as part of the fix-and-revert commit, so the env var is unset in steady state.

## Cards

### Card 1: Instrument `wiki._client._spawn_server` with env-var-gated stderr capture

- **Effort:** S
- **Context:**
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Modify the function `_spawn_server(wiki_path: Path) -> None` in `plugins/mill/scripts/wiki/_client.py` so that when the environment variable `MILL_WIKI_DAEMON_DEBUG` is set to the literal string `"1"`, the spawned child's stdout and stderr are captured to a log file at `<wiki_path>/.wiki-daemon-debug.log` (overwrite on each spawn). When `MILL_WIKI_DAEMON_DEBUG` is unset or any value other than `"1"`, behaviour MUST be byte-identical to the current implementation (same `cmd /c start "" /B /MIN ...` + `creationflags` combo on Windows, same `start_new_session=True` non-Windows path, same closed FDs).

  Implementation notes for the Windows branch: when debug is enabled, do NOT use `cmd /c start`; instead call `subprocess.Popen(cmd, env=env, stdout=open(<debug_log>, "w", encoding="utf-8"), stderr=subprocess.STDOUT, close_fds=True, creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_BREAKAWAY_FROM_JOB)` so the debug log captures the child's actual import-time + startup stderr. The `creationflags` keep the child detached. For the non-Windows branch: `subprocess.Popen(cmd, env=env, stdout=open(<debug_log>, "w", encoding="utf-8"), stderr=subprocess.STDOUT, close_fds=True, start_new_session=True)`. Add an import of `os` at the top of the file if not already present (it is — `os.environ` and `os.pathsep` already used).

  Do NOT remove the existing `cmd /c start` / `start_new_session` paths; they remain the default (debug-off) behaviour. The debug branch is a separate `if os.environ.get("MILL_WIKI_DAEMON_DEBUG") == "1":` block that returns early before the default path.

  Update the docstring of `_spawn_server` to mention the env-var hook with one sentence: `When MILL_WIKI_DAEMON_DEBUG=1, child stdout+stderr are captured to <wiki_path>/.wiki-daemon-debug.log for diagnostic use. Default-off path unchanged.`

  This card does not run or import `_spawn_server`; the existing test suite continues to exercise the default-off path. No new test needed.
- **Commit:** `feat(wiki/_client): env-var-gated debug capture in _spawn_server`

### Card 2: Reproduce daemon-startup failure, diagnose, document root cause

- **Effort:** S
- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Edits:**
  - `_mill/plan/01-daemon-startup-diagnose-and-fix.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Reproduce the daemon-startup failure and identify the root cause. Steps:

  1. Run a minimal repro to drive the daemon spawn path under debug mode:

     ```bash
     MILL_WIKI_DAEMON_DEBUG=1 PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-claim.py
     ```

     The expected current behaviour is 11 of 12 ERROR with `daemon did not start within timeout`.

  2. For each failure, inspect `<wiki_path>/.wiki-daemon-debug.log` written by the card-1 instrumentation. The fixtures create temp wiki dirs; the log will be inside whichever temp wiki the test was using when the spawn fired. Add a print in the test harness (or use a sleep + manual find) to locate the temp wiki path that produced a failure, then read the log.

  3. Classify the root cause as ONE of:
     - **(a) Child crashes on import** — e.g. `ModuleNotFoundError`, `ImportError`, or syntax error inside `wiki._server` / `wiki._store` / `wiki._sync`. The log will contain a Python traceback. Fix: correct the import or the import chain in product code.
     - **(b) Port-bind failure** — `OSError: [WinError 10048] Only one usage of each socket address` or similar. The log will contain a socket-related error. Likely cause: fixture cycles wikis quickly and stale state file references a now-rebound port. Fix: stale-state cleanup or port-randomization.
     - **(c) TinyDB lock contention** — `tinydb` / file-lock error. Likely cause: fixtures share a TinyDB file across processes via the OS file cache. Fix: TinyDB invocation correction or lock teardown.
     - **(d) `creationflags` env-loss** — child fails to import `wiki._server` because PYTHONPATH or another env var is dropped under `CREATE_BREAKAWAY_FROM_JOB`. The log may be empty or contain a low-level Windows error. Fix: env-passing correction or alternate detachment flags.
     - **(e) Something else** — explicitly described in the diagnosis text written into the card-3 requirements section below.

  4. After diagnosis, edit the **Requirements** section of card 3 in this same plan file (`_mill/plan/01-daemon-startup-diagnose-and-fix.md`) to add a sub-bullet titled `**Diagnosis (from card 2):**` that states the classification (a/b/c/d/e) AND quotes the relevant 3–10 lines of the captured `.wiki-daemon-debug.log` so the card-3 implementer has the full context without re-running.

  The plan-file edit is the deliverable of this card. The commit body should also include a 5-10 line summary of the diagnosis, identical to the text added to the plan file, so it lives in git history independently of the plan file.

  Do not attempt to fix the bug in this card — only diagnose and document. Card 3 owns the fix.
- **Commit:** `docs(plan/01): document daemon-startup root cause from MILL_WIKI_DAEMON_DEBUG`

### Card 3: Fix daemon-startup root cause + revert debug instrumentation

- **Effort:** M
- **Context:**
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/unit_tests/test-millpy-claim.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Apply the fix identified in card 2's `**Diagnosis (from card 2):**` sub-bullet (added to this very section by card 2) AND revert the debug instrumentation in the same commit.

  **Fix constraints:**
  - The fix MUST be in product code (`wiki/_client.py`, `wiki/_server.py`, `wiki/_store.py`, `wiki/_sync.py`, or `wiki/__init__.py`). Test fixtures are NOT a valid place to fix this; the daemon must come up reliably for real users too.
  - The fix MUST NOT change the public API of `wiki._client` (the function signatures in `00-overview.md`'s API table are load-bearing for the rest of the plan).
  - If the fix touches `wiki/_client.py` beyond reverting the debug branch, keep the diff minimal — surgical.
  - If diagnosis (case e) reveals the fix is structurally larger than this card's M=2 effort budget (e.g. requires refactoring `wiki._server` end-to-end), the implementer halts under the stuck-policy and asks the operator to redesign the batch before continuing. Do NOT ship a partial fix.

  **Revert constraints (always apply):**
  - Delete the entire `if os.environ.get("MILL_WIKI_DAEMON_DEBUG") == "1":` branch added by card 1. After this card, `_spawn_server` reads neither `MILL_WIKI_DAEMON_DEBUG` nor writes `.wiki-daemon-debug.log`.
  - Restore the `_spawn_server` docstring to its pre-card-1 wording (drop the `MILL_WIKI_DAEMON_DEBUG` sentence).

  **Verification:** After applying the fix and reverting the debug branch, run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-claim.py`. All 12 tests in `test-millpy-claim.py` MUST pass. If any still ERROR with `daemon did not start within timeout`, the fix is incomplete — iterate on the diagnosis or halt under the stuck-policy.

  **Diagnosis (from card 2):**
  - **(e) Test fixture mocks interfering with state file reads** — The daemon starts successfully and creates valid `.wiki-daemon.json` state files (confirmed in `C:/fake/wiki/.wiki-daemon-debug.log` and `.wiki-daemon.log`). However, test fixtures globally patch `Path.read_text()` to return fake content (`"# Home\n"`) intended for reading `Home.md`. When `_ensure_daemon` calls `state_file.read_text("utf-8")` to read the daemon state, it gets the fake `"# Home\n"` instead of the actual JSON state. This causes `json.loads()` to raise JSONDecodeError, which is caught and ignored, but then the client cannot verify daemon startup because it doesn't have the correct port/token. The cached `.wiki-daemon.json` contains the real port and token (e.g., `protocol_version: 2, port: 51399, token: ca1f50f85fa3c13ea6b1425824950184`), but the client reads the fake `"# Home\n"` and fails to connect.

- **Commit:** `fix(wiki/_client): resolve daemon-startup failure; revert debug instrumentation`

## Batch Tests

The batch verify command is `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-millpy-claim.py`. This single file is the canonical victim of the daemon-startup bug (11 of 12 currently ERROR). After this batch lands, all 12 must pass. No other tests are expected to change from this batch in isolation — the chain-failure cluster (`test-millpy-color.py`, `test-millpy-terminal.py`, `test-millpy-vscode.py`, etc.) is unblocked by batch 2's `_spawn_core` cleanup, not by this batch.
