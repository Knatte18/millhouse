# Discussion: Fix millpy-bg EXIT marker and implementer reliability

```yaml
task: Fix millpy-bg EXIT marker and implementer reliability
slug: millpy-bg-and-implement-fixes
status: discussing
parent: main
```

## Problem

Seven related bugs accumulated across multiple mill-go runs on Windows. The common
thread: the `[mill-bg] EXIT` sentinel is never written to the log even when workers
complete successfully, causing `check_bg_status` to return `("dead", pid)` instead of
`("exit", 0)`. Mill-go then escalates every successful bg completion to Stuck/infrastructure,
and the operator must manually confirm the JSON result is valid before proceeding. In
parallel, the implementer and fixer emit incomplete stuck JSON on timeout (no `commits_made`
field), so mill-go always retries from scratch even when cards were already committed. A
hardcoded 600–1800 s response-poll timeout in `millpy-claude-sub.py` is not overridable for
tasks with long-running integration-test verify steps. Startup races on Windows (psmux
session teardown race) cause the first fire of a batch to crash immediately, and the re-fire
creates a duplicate "mill-go: start batch" commit.

This task also covers wiki task 8 (mill-bg-exit-marker, #420), which is a narrower
description of the same EXIT-marker root cause.

## Scope

**In:**
- `_bg.py` — add JSON-presence fallback to `check_bg_status`: dead+no-EXIT+JSON-present → `("exit", 0)`
- `millpy-bg.py` — the `try/finally` for EXIT writing is already in place (commit 77f26ca3); no new change here
- `millpy-implement.py` — add `commits_made` count to stuck JSON on `LLMError`; skip duplicate "start batch" commit on re-fire
- `millpy-fix.py` — add `commits_made` count to stuck JSON on `LLMError`
- `millpy-claude-sub.py` — make `RESPONSE_POLL_TIMEOUT_S` per-mode overridable via config
- `mill-config.yaml` template — add `llm.claude.psmux.response_poll_timeout_s` nested dict
- `mill-go SKILL.md` — update every "dead → infrastructure escalation" call-out to document that "dead" now only fires when no JSON is present; add `commits_made > 0` routing for timeout-stuck
- Unit tests for `_bg.py` JSON fallback and `millpy-implement.py` commits_made + duplicate-commit skip
- Wiki task 8 closed as "covered by this task" after merge

**Out:**
- The root cause of the hard-kill (Windows job object / psmux session teardown) is not fixed — we mitigate its effect via the JSON fallback, not by preventing the kill
- Mill-start SKILL.md changes beyond what the `_bg.py` fix already handles automatically
- Per-batch `timeout_s` override (issue asks only for `response_poll_timeout_s`, which covers the only known timeout class)
- `millpy-merge-in-subagent.py` timeout handling (separate concern)

## Decisions

### JSON fallback in check_bg_status

- **Decision:** When `check_bg_status` detects a dead PID with no EXIT sentinel, re-read the
  log and check if the last `{`-prefixed line is valid JSON. If so, return `("exit", 0)`.
- **Rationale:** The EXIT sentinel is written by `_worker_main`'s `finally` block. On Windows
  the worker process can be hard-killed between the subprocess completing and the `finally`
  running (job object teardown, VS Code session exit). The JSON result line is written by the
  inner subprocess synchronously before the wrapper runs cleanup; its presence reliably indicates
  the worker's main job completed. This is Fix 1 from #420. Fix 2 (`try/finally`) is already done.
- **Rejected:** (a) Making `check_bg_status` return a new status like `"json_complete"` — adds API
  churn across every calling skill with no benefit over transparent `"exit"`. (b) Using file
  presence of the review/result file instead of JSON — domain-specific and unavailable for
  implement workers. (c) Adding OS-level guards to prevent the kill — not feasible without
  restricting job-object breakaway flags we deliberately set.

### JSON detection heuristic

- **Decision:** Scan the log in reverse for the first line starting with `{`; try `json.loads`
  on it. If valid JSON, report as complete. Partial writes (incomplete `}`) will fail the parse
  and return `("dead", pid)` as before.
- **Rationale:** The convention in all mill CLI scripts is that the result is the last line
  starting with `{`. Parsing to validate avoids false positives from mid-run JSON fragments.
  Import `json` in `_bg.py` (stdlib only, no new deps).
- **Rejected:** A simple `^{` regex without parse — would match partial writes.

### commits_made in stuck JSON

- **Decision:** In `millpy-implement.py` and `millpy-fix.py`, when catching `LLMError`,
  run `git rev-list --count <start_sha>..HEAD` and include `"commits_made": N` in the stuck JSON.
  `start_sha` is already captured before the implementer launches.
- **Rationale:** Lets mill-go distinguish "timeout before any commits" (retry from scratch) from
  "timeout after commits" (optionally skip to cleanliness gate). Addresses #416.
- **Rejected:** Including full SHA list — adds log noise; count is sufficient for routing.

### Mill-go routing for commits_made > 0

- **Decision:** When stuck JSON has `commits_made > 0` AND `stuck_type: transient` (timeout),
  present an explicit "skip to cleanliness gate" option in interactive mode; auto-skip in
  `autonomous_mode: true`. The cleanliness gate + code review still run; only re-implementation
  is skipped.
- **Rationale:** If any commits were made, the implementer likely completed the implementation
  work and the timeout fired during verify. Code review will catch incomplete implementations.
- **Rejected:** Always retry from scratch — the issue explicitly asks for skip-to-cleanliness
  when commits were made. Rejected: checking commit count against expected card count — mill-go
  has no "expected commits per card" metric.

### Skip duplicate "start batch" commit on re-fire (#412)

- **Decision:** Before the "mill-go: start batch `<batch>`" commit in `millpy-implement.py`,
  check if `git log -1 --pretty=%s` already equals `mill-go: start batch <batch>`. If so, skip
  the commit+push step (batch already started; this is a re-fire).
- **Rationale:** The first-fire crash happens after the git commit in the rare psmux-race case;
  re-fire without this guard creates a duplicate commit. The actual psmux race is transient and
  handled by the existing stuck_type: transient auto-retry.
- **Rejected:** Adding a sleep at the start of the batch — flaky; doesn't address the duplicate
  commit root cause.

### Configurable response_poll_timeout_s (#415)

- **Decision:** Add `llm.claude.psmux.response_poll_timeout_s` as a nested dict in `mill-config.yaml`
  with per-mode keys matching `RESPONSE_POLL_TIMEOUT_S`. In `millpy-claude-sub.py`, add
  `_resolve_response_poll_timeout_s(mode)` that loads from config with fallback to the hardcoded
  defaults. Pattern mirrors the existing `_resolve_reuse_idle_timeout_s()`.
- **Rationale:** Long integration-test verify steps can exceed the 600 s (tool-use) or 1800 s
  (implementer) defaults. The config key allows opt-in extension without changing defaults for
  all tasks.
- **Rejected:** A flat per-task `bg_timeout_s` key — too coarse; the issue is specifically the
  per-mode psmux response-poll, not the overall subprocess timeout which is already at 3600 s.

### Task 8 disposition

- **Decision:** Task 8 (mill-bg-exit-marker) is resolved as a subset of this task. After this
  task merges to main, close task 8 via `_client.set_phase(wiki_path, "mill-bg-exit-marker", "done")`.
- **Rationale:** Task 8's body describes the same `[mill-bg] EXIT` missing-marker symptom and
  proposes the same two fixes (try/finally + skill fallback). Both are covered here.
- **Rejected:** Implementing task 8 on a separate branch — redundant; all changes are
  co-located in the same files.

## Technical context

**`_bg.py`** (`plugins/mill/scripts/_bg.py`)
- `check_bg_status(log_path)` → `(status_str, pid_or_code_or_None)`. Currently: dead+no-EXIT →
  `("dead", pid)`. After fix: also checks last JSON line.
- `is_bg_worker_alive(log_path)` — unchanged.
- The JSON scan goes in the final re-read block (after the dead+no-EXIT re-read) so it only
  fires when the race guard also failed to find EXIT.

**`millpy-bg.py`** (`plugins/mill/scripts/millpy-bg.py`)
- `_worker_main`: already has `try/finally` writing EXIT. No change.
- Launcher: no change.

**`millpy-implement.py`** (`plugins/mill/scripts/millpy-implement.py`)
- `start_sha` is captured at line 132; `session_id` at line 137.
- `LLMError` is caught at line 195–198. Add `git rev-list --count` call there.
- "start batch" commit is at lines 148–156. Add last-commit check before it.

**`millpy-fix.py`** (`plugins/mill/scripts/millpy-fix.py`)
- `start_sha` captured at line 281. `LLMError` caught at line 298–300. Same `commits_made` injection.

**`millpy-claude-sub.py`** (`plugins/mill/scripts/millpy-claude-sub.py`)
- `RESPONSE_POLL_TIMEOUT_S` dict at lines 31–35. Single call site at line 325.
- Add `_resolve_response_poll_timeout_s(mode: str) -> float` using the same
  `_config.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path())` pattern as
  `_resolve_reuse_idle_timeout_s()`. Config path: `llm.claude.psmux.response_poll_timeout_s.<mode>`.

**`mill-config.yaml` template** (`plugins/mill/templates/mill-config.yaml`)
- New keys under `llm.claude.psmux`:
  ```yaml
  response_poll_timeout_s:
    bulk: 300
    tool-use: 600
    implementer: 1800
  ```

**`mill-go SKILL.md`** (`plugins/mill/skills/mill-go/SKILL.md`)
- Pattern `"dead" -> classify as stuck_type: infrastructure` appears 8–9 times. After the
  `_bg.py` fix, "dead" only fires when there truly is no JSON (genuine failure). Each
  occurrence needs a clarifying note: "dead means the log has no JSON result line, not just
  missing EXIT."
- Add `commits_made` routing: after parsing a `stuck_type: transient` report, check for
  `commits_made > 0`; if present, branch to "skip-to-cleanliness" path.

**`_implementer_common.py`** — no change needed. `_forward_output` already handles the
  inferred-success path. The `commits_made` field is added upstream (in the LLMError handler)
  before `_forward_output` is even reached.

## Testing

**`test-bg-liveness.py`** (existing) — add test cases for `check_bg_status`:
- dead + no EXIT + valid last-JSON-line → `("exit", 0)`
- dead + no EXIT + partial/invalid JSON → `("dead", pid)`
- dead + no EXIT + no JSON at all → `("dead", pid)` (existing behavior unchanged)
- dead + EXIT present → `("exit", code)` (existing; verify unaffected)

**`test-millpy-implement.py`** (existing) — add test cases:
- `commits_made` present in stuck JSON when `LLMError` fires after some commits
- `commits_made: 0` when `LLMError` fires with no new commits
- Skip-commit logic: second call with same last-commit message → no second commit

**`test-millpy-bg.py`** (existing) — confirm `try/finally` still writes EXIT on normal exit
  (already covered by `913bdfaa` tests; verify tests still pass).

No new test file needed for `millpy-claude-sub.py` timeout — the config-read path is identical
to the existing `_resolve_reuse_idle_timeout_s` which is already tested indirectly.

## Q&A log

- **Q:** Task 8 is listed as a separate wiki task. Should it be implemented separately or merged here?
  **A:** Merged. Task 8 is a strict subset of the EXIT-marker issues in this task.

- **Q:** Should `check_bg_status` return a distinct status (e.g. `"json_complete"`) vs. `("exit", 0)`?
  **A:** Return `("exit", 0)`. Transparent to all callers; no skill changes needed for the basic case.

- **Q:** For `commits_made` routing in mill-go, should "skip to cleanliness gate" be automatic or interactive?
  **A:** Interactive in normal mode (option 1: skip, option 2: retry); automatic (`skip`) in `autonomous_mode: true`.

- **Q:** Should `millpy-fix.py` also get the duplicate-commit skip guard?
  **A:** No. The fixer's commit pattern is different (it commits after each fix, not a single "start" commit); the duplicate-commit risk is specific to `millpy-implement.py`'s batch-start commit.
