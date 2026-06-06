# Batch: bg-completion-detection

```yaml
task: "Fix millpy-bg EXIT marker missing on wrapper crash"
batch: "bg-completion-detection"
number: 1
cards: 5
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-bg-liveness.py test-bg-json-contract.py
depends-on: []
```

## Batch Scope

This batch closes the residual defect from commit `18ea1ff9`: a `millpy-bg` worker that
finished its work (emitted its trailing JSON summary) but was then hard-killed before writing
`[mill-bg] EXIT` is currently reported by `_bg.check_bg_status` as `("running", pid)` for up to
`_STALE_LOG_SECONDS` (5 minutes), because `is_bg_worker_alive`'s Windows mtime-freshness
fallback masquerades as liveness and shadows the `_has_valid_json_result` completion fallback
(which sits *after* the liveness probe). The batch makes `check_bg_status` recognize completion
on the next poll by letting the trailing-JSON sentinel override an *assumed*-alive verdict while
still respecting an *affirmatively*-alive process.

All production changes are in one module (`_bg.py`) plus comment/docstring clarifications in
`millpy-bg.py`; the rest is test coverage. It is one batch because the logic change and its
regression tests are inseparable and share the same small context. There is no external
interface for a later batch to consume — this is the whole task.

Batch-local decisions: none beyond `## Shared Decisions` in the overview.

## Cards

### Card 1: Expose affirmative-vs-assumed liveness in `_bg`

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Today `is_bg_worker_alive` collapses two distinct "alive" cases into a single
  `True`: (a) **affirmatively alive** — `os.kill(pid, 0)` returned cleanly or raised
  `PermissionError` (the process provably exists); and (b) **assumed alive** — `os.kill` raised
  an inconclusive `OSError`/`SystemError` (the Windows norm) and the code fell back to log-mtime
  freshness (`time.time() - mtime <= _STALE_LOG_SECONDS`). Introduce a way for `check_bg_status`
  to tell these apart without changing the public return shape of `is_bg_worker_alive`
  (`(bool, int|None)`). Add a private helper — suggested `_probe_liveness(log_path: Path) ->
  tuple[str, int | None]` returning one of `"exit"` (EXIT sentinel present),
  `"affirmative-alive"` (kill-probe confirmed), `"assumed-alive"` (mtime-fresh fallback),
  `"dead"` (mtime-stale or no PID) plus the pid — that encapsulates the existing `_PID_RE` /
  `_EXIT_RE` / `os.kill` / mtime logic in one place. Re-implement `is_bg_worker_alive` as a thin
  wrapper over the helper so its existing return values and all current
  `test-bg-liveness.py::TestIsBgWorkerAlive` assertions stay green (`"exit"`/`"dead"` →
  `(False, pid)`, `"affirmative-alive"`/`"assumed-alive"` → `(True, pid)`; no PID → `(False,
  None)`). Preserve the existing DEBUG breadcrumb logged on the `os.kill` inconclusive fallback.
- **Commit:** `refactor(bg): expose affirmative-vs-assumed liveness probe in _bg`

### Card 2: Order JSON-completion sentinel ahead of assumed-alive in `check_bg_status`

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite `check_bg_status` to resolve in this order, reusing the Card 1
  `_probe_liveness` helper and the existing `_has_valid_json_result` / `_EXIT_CODE_RE`:
  (1) log missing → `("dead", None)`; (2) `[mill-bg] EXIT <code>` present → `("exit", code)`;
  (3) probe is `"affirmative-alive"` → `("running", pid)`; (4) a valid trailing JSON result is
  present (`_has_valid_json_result`) → `("exit", 0)`; (5) probe is `"assumed-alive"` →
  `("running", pid)`; (6) otherwise → `("dead", pid)`. The behavioural change vs current code:
  when a worker is `"assumed-alive"` (mtime-fresh, kill-probe inconclusive) AND a valid trailing
  JSON line is present, return `("exit", 0)` on this poll instead of `("running", pid)` —
  eliminating the up-to-5-minute stall for finished-then-hard-killed workers. Keep the existing
  re-read race-guard semantics (re-checking EXIT after the liveness probe is no longer needed
  once EXIT is checked first and the probe is single-shot, but a valid-JSON / EXIT result must
  still win over a stale verdict — verify against the retained `test_check_bg_status_*` cases).
  A genuinely-running worker (`"affirmative-alive"`) that happens to have emitted a JSON-looking
  line mid-stream MUST still return `("running", pid)` — step 3 precedes step 4.
- **Commit:** `fix(bg): recognize completed-but-killed worker via JSON sentinel before mtime`

### Card 3: Correct the EXIT-marker framing in comments and docstrings

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_bg.py`
  - `plugins/mill/scripts/millpy-bg.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Update prose only — no logic change. In `millpy-bg.py`, amend the worker
  `finally`-block comment and the module docstring (the "appends `[mill-bg] EXIT <code>` when the
  process exits" line) to state that the `finally` write is **best-effort**: it covers the clean
  exit and in-process-exception paths but does NOT survive a hard process kill (e.g. psmux
  session teardown / `TerminateProcess`), and that the kill-resilient backstop is the
  trailing-JSON completion sentinel consumed by `_bg.check_bg_status`. In `_bg.py`, update the
  module docstring and the `check_bg_status` docstring to document the resolution order from
  Card 2 and to note that agent-mode dispatch (no detached worker) is the structural resolution
  while subprocess/psmux EXIT-detection is best-effort plus JSON-sentinel backstop. Also document
  the trailing-JSON contract: every CLI dispatched through `millpy-bg` MUST emit a single
  parseable JSON line as its final stdout (the sentinel `_has_valid_json_result` keys on). Keep
  all output ASCII-only.
- **Commit:** `docs(bg): clarify EXIT finally is best-effort; JSON sentinel is the backstop`

### Card 4: Regression and behaviour tests for completion detection

- **Context:**
  - `plugins/mill/scripts/millpy-bg.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-bg-liveness.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add tests to `test-bg-liveness.py` covering the Card 2 behaviour, using the
  existing fixture style (tempfile log, `os.utime` to set mtime, `unittest.mock.patch.object` on
  `_bg.os.kill`). Required cases: (1) **#420/#424 regression** — log with `[mill-bg] WORKER
  PID=<dead> START …` + a valid trailing JSON summary line (e.g. `{"type": "discussion",
  "round": 1, "verdict": "GAPS_FOUND"}`) + NO `[mill-bg] EXIT` + **fresh** mtime, with `os.kill`
  patched to raise `OSError(22, "Invalid parameter")`; assert `check_bg_status` →
  `("exit", 0)` (this currently returns `("running", pid)`); reference issues #420 and #424 in
  the test docstring. (2) **affirmatively-alive not false-completed** — log with `WORKER
  PID=<current>` (use `os.getpid()`, or patch `os.kill` to return cleanly) + a mid-stream
  JSON-looking line + no `EXIT`; assert `("running", pid)`. (3) **killed before JSON, fresh
  mtime** — dead PID, no `EXIT`, no parseable JSON, `os.kill` raising, fresh mtime; assert
  `("running", pid)`. (4) **killed before JSON, stale mtime** — same but mtime backdated past
  `_STALE_LOG_SECONDS`; assert `("dead", pid)`. (5) confirm `EXIT` present still wins over a
  present JSON line (extend or keep `test_check_bg_status_exit_found`). Keep every existing
  `test-bg-liveness.py` case green; if the Card 1 refactor renames internals, update only the
  references, not the asserted outcomes.
- **Commit:** `test(bg): cover JSON-sentinel completion detection for killed workers`

### Card 5: Trailing-JSON contract guard test

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/millpy-review-discussion.py`
  - `plugins/mill/scripts/millpy-implement.py`
  - `plugins/mill/scripts/millpy-fix.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-bg-json-contract.py`
- **Deletes:** none
- **Requirements:** Create `test-bg-json-contract.py` pinning the invariant the completion
  fallback depends on: every `millpy-bg`-dispatched CLI emits a parseable JSON line as its final
  stdout. Two complementary assertions, both in-memory (no subprocess, no git): (1) **consumer
  acceptance** — for one representative terminal envelope of each CLI family (a review envelope
  `{"type": "discussion"|"plan"|"code", "round": 1, "verdict": "APPROVE", ...}`, an implementer
  success `{"status": "success", "commit_sha": "abc", "session_id": "x"}`, and a stuck
  `{"status": "stuck", "stuck_type": "transient", "reason": "..."}`), assert
  `_bg._has_valid_json_result(<log_text_whose_last_brace_line_is_that_envelope>)` returns `True`,
  and assert it returns `False` for a log whose final `{`-line is truncated/invalid JSON.
  (2) **emitter seam guard** — drive `_implementer_common._forward_output` (and/or
  `finalize_from_output`) with a crafted agent-output string for the success and stuck branches
  and capture stdout (e.g. `contextlib.redirect_stdout`), asserting the final printed line
  `json.loads`-es without error. Mock any git/subprocess calls the seam makes (patch the
  `_subprocess_util` / git helper it uses) so the test stays in-memory; if a branch is
  impractical to exercise without real git, fall back to a structural assertion that the seam's
  terminal output statements use `json.dumps`. The test's purpose is to fail loudly if a future
  CLI on the millpy-bg path stops emitting trailing JSON.
- **Commit:** `test(bg): guard trailing-JSON completion contract for dispatched CLIs`

## Batch Tests

`verify:` runs `test-bg-liveness.py` (extended in Card 4 — the liveness probe + `check_bg_status`
completion-ordering behaviour) and the new `test-bg-json-contract.py` (Card 5 — the trailing-JSON
contract guard) via `run-all.py --only`, scoped to exactly the two files this batch touches. No
unbounded `run-all.py` is needed: the change is confined to `_bg.py` plus comment edits in
`millpy-bg.py`, neither of which is a cross-cutting import, so the full suite is unnecessary.
Both test files are pure in-memory/tempfile with mocked `os.kill` and (in the contract test)
mocked git — no real git, LLM, or subprocess.
