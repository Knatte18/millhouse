---
name: mill-go
description: In a spawned worktree with an approved plan, sequentially execute every batch in the plan's DAG. Per batch spawn one implementer Sonnet, run code review, loop with receive-review on REQUEST_CHANGES, halt on stuck. Hand off to mill-finalize.
---

# mill-go

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are the **Builder** — a lean orchestrator. You coordinate per-batch implementation but never read card bodies or diffs yourself. The **Implementer** (spawned per batch) reads its own batch file, implements cards, runs `verify:`, and fixes on receive-review. You read only `status.md`, the Batch Index DAG in `00-overview.md`, and the fenced yaml verdict block of each code review. Keeping your context lean is the whole point — Builder cost is a rounding error next to the Implementer and code-reviewer calls.

## Entry

**Step 0: Verify `CLAUDE_PLUGIN_ROOT`.**

```bash
[ -n "${CLAUDE_PLUGIN_ROOT}" ] || { echo "[mill-go] HALT: CLAUDE_PLUGIN_ROOT is not set" >&2; exit 1; }
```

**Path variable rule:** All Bash tool calls in this skill use `${CLAUDE_PLUGIN_ROOT}` directly — it is an environment variable already present in the shell. Do NOT read or memorize its value. Write the variable reference; the shell expands it at runtime. The full absolute path must never appear in a command string.

1. Read the task slug: `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
   `signature: _marker.slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str`
2. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())`.
3. Load config — load `mill-config.yaml` from the hub root, merged with `.millhouse/config.local.yaml`, via `_review_common.load_config(_paths.resolve_hub_path(), _paths.resolve_hub_path() / ".millhouse")`. Read these keys:
   - `pipeline.auto_merge` — whether to invoke mill-finalize after success.
   - `pipeline.auto_report` — whether to auto-fire mill-self-report at end-of-work. mill-go fires it at Handoff step 6, AFTER any `/mill-merge` invocation in step 5 — including after PR-pending halts. See step 6 for the explicit "do not treat PR-pending as termination" rule.
   - `roles.code-review.batch.rounds` — max review rounds per batch.
   - `roles.code-review.holistic.rounds` — max holistic review rounds (parallel cap for the holistic scope, default 1).
   - `roles.implementer.self_fix_rounds` — passed to the implementer brief.
   - `roles.code-review.holistic.reviewer` — if non-null, run one holistic code review after all batches approve.
   - `roles.code-review.batch.reviewer` — if null (or rounds: 0), skip per-batch code review for all batches.
4. Acquire the builder lock:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
   ```
   On exit code 1: surface the stderr message and halt — a second mill-go will corrupt state.
4.5. **Path Setup.** `worktree_root` is not yet set in prior steps; `slug` is in scope from step 1 and `cfg` was loaded in step 3. Derive:
   ```python
   git_root       = _paths.resolve_git_root()
   container_path = _paths.resolve_container_path(git_root)
   worktree_root  = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)
   status_path   = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
   plan_dir      = _paths.resolve_task_path(worktree_root, cfg['paths']['plan_dir'])
   overview_path = plan_dir / "00-overview.md"
   reviews_dir   = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])
   task_dir      = status_path.parent  # absolute; compute_terminal_dirt relativizes internally
   ```
   Use these variables for all subsequent path references. Exception: the cleanliness snapshot path `_mill/.cleanliness-snapshot-<batch_name>.txt` keeps its `_mill/` literal — `millpy-implement.py` writes it unconditionally to `_mill/` and is out of scope.
5. **Entry phase gate.** Before reading `status_path`, guard against the merge-interrupted state where `_mill/status.md` has been removed by mill-merge's cleanup commit but teardown did not complete -- mirrors mill-merge's own Step 5 fallback. Wiki daemon errors are caught explicitly so a daemon outage surfaces a readable message instead of a raw traceback.
   ```python
   if not status_path.exists():
       import sys
       from wiki import _client
       from wiki import WikiStartupError, WikiProtocolError
       import _phase_gate
       try:
           task = _client.get_task(wiki_path, slug)
       except (WikiStartupError, WikiProtocolError) as e:
           print(f"_mill/status.md absent and wiki daemon unavailable: {e} -- inspect manually.", file=sys.stderr)
           raise SystemExit(1)
       print(_phase_gate.absent_status_halt_message(task, slug), file=sys.stderr)
       raise SystemExit(1)
   ```

   Inspect the phase:
   ```python
   status = _status.read_full(status_path)
   phase = status["yaml"]["phase"]
   blocked_reason = status["yaml"].get("blocked_reason")
   ```
   `signature: _status.read_full(status_path: Path) -> {"yaml": dict, "timeline": list[str]}`

   | phase | action |
   | --- | --- |
   | `planned` | fresh run — continue to Prepare |
   | `implementing` / `reviewing` / `fixing` | resume (see *Resume*) |
   | `blocked` | surface `blocked_reason` from status.md and halt |
   | `discussed` / `discussing` / `planning` | tell user to finish mill-plan and halt |
   | `done` | tell user the task is complete; suggest `/mill-finalize` if auto-merge was off |
   | any other | surface + halt |

6. Read the plan overview from `overview_path`. Confirm `approved: true` in the frontmatter. Extract the Batch Index via `_plan_dag.extract_batch_index(overview_text)`, validate via `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`, then compute `order = _plan_dag.topo_order(batches)`.
   `signature: _plan_dag.extract_batch_index(overview_text: str) -> list[dict]`
   `signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`
   `signature: _plan_dag.topo_order(batches: list[dict]) -> list[str]`

> If mill-go is interrupted mid-run, re-run `/mill-go` — it will auto-reclaim the builder lock for the same task (stale-self-lock detection is built in).

## Prepare

On a fresh run only (no `## Batches` section in status.md):

- `_status.init_batches(status_path, order)` — seeds every batch at `state: pending`.
  `signature: _status.init_batches(status_path: Path, names: list[str]) -> None`
- `_status.append_phase(status_path, "implementing", _timestamp.now_utc_iso())`.
  `signature: _status.append_phase(status_path: Path, phase: str, timestamp: str) -> None`
  `signature: _timestamp.now_utc_iso() -> str`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: prepare for {slug}"`.

## Execute — sequential loop

For each batch in `order`:

## Agent-mode dispatch

When `dispatch == agent`, follow this three-step pattern at each dispatch point:

1. **Resolve dispatch mode:** `dispatch = _agent_dispatch.resolve_dispatch_mode(cfg)`. This reads `cfg["llm"]["claude"]["dispatch"]` and returns one of `"subprocess"`, `"psmux"`, or `"agent"`. If the mode is not `agent`, skip this entire section and use the existing `subprocess`/`psmux` flow unchanged (documented below in each dispatch subsection).

2. **Run prepare stage:** Invoke the CLI with `--stage prepare` and the standard arguments (see each subsection for the exact CLI invocation). Parse the returned JSON line to extract:
   - `brief_path`: absolute file path to the rendered brief
   - `subagent_type`: one of `"mill:mill-implementer"` or `"mill:mill-reviewer"`
   - `model`: Agent-tool tier (`"sonnet"`, `"opus"`, or `"haiku"`)

   Also extract from the envelope: `session_id` (string or null), `round` (integer), and `start_sha` (string or null -- present only when the CLI emits it, e.g. fix and implementer CLIs).

3. **Call Agent tool:** Invoke the Agent tool with:
   - `subagent_type`: the value from step 2
   - `model`: the value from step 2
   - `prompt`: `"Read this file and follow the instructions exactly: <brief_path>"`

   The Agent tool launches a **background** subagent and returns immediately with a message such as "Async agent launched..." — the subagent's final output is NOT available at call time. The orchestrator must then **wait for the completion `<task-notification>`** from that background agent. Read the subagent's final message from the notification payload — that is the text used in steps 4 and 5 below.

   A background agent is a **detached worker** that can be stopped or interrupted independently of the orchestrator. If the `<task-notification>` indicates the subagent was stopped or interrupted (rather than completing normally), treat it the same as a raw API error and apply the one-retry transient path in step 4.

4. **Recover from raw API errors and interruptions:** If the notification message (or the inline tool return on immediate failure) contains a raw API/infrastructure error (text like `API Error` / `Internal server error`, roughly 0 tokens, no `MILL_REVIEW` block and no `status` JSON), OR if the background agent was stopped/interrupted before completing, classify it as `stuck_type: transient` and re-dispatch once using a fresh brief and session (no `--resume`). This applies to implementer, reviewer, and fixer Agent dispatches. On a second consecutive raw API error or interruption: implementer and fixer dispatches escalate per the "Stuck escalation" section; read-only reviewer dispatches (which write no review file) fall back to the subprocess `--stage full` path via `millpy-bg` before escalating.

   **Clean mid-work stop (implementer only):** When the implementer notification is a non-error non-JSON message — meaning the payload contains neither an `API Error` / `Internal server error` marker nor a valid `status` JSON block (clean turn exhaustion: the implementer ran out of budget and stopped before emitting the required JSON report) — do NOT re-dispatch fresh immediately. Instead, write the notification to the `.out.md` file as normal and invoke the `--stage finalize` step (step 6). Finalize will either infer success (if commits were made and the tree is clean) or emit `stuck_type: transient` with a `commits_made` field. If finalize returns `stuck_type: transient` with `commits_made > 0`, route directly to the Stuck escalation `commits_made > 0` path (one retry, then skip to cleanliness gate) — do NOT treat it as the raw-API-error one-retry path. Re-dispatching fresh with a new `start_sha` would discard the partial commit count context and risk a second completeness-gate loop even when partial work exists.

5. **Capture output:** Write **the message captured from the `<task-notification>`** to `<brief_path>.out.md` (utf-8). The response file extends the brief path by replacing the trailing `.md` with `.out.md` — for a brief `foo-r1.md` the response is `foo-r1.out.md`.

6. **Run finalize stage:** Invoke the CLI with `--stage finalize`, the same standard arguments, and `--agent-output <brief_path>.out.md`. The response file follows the same naming rule: `.out.md` replaces the trailing `.md` of the brief path. Parse the returned JSON envelope.

   Additionally thread any applicable prepare-envelope fields into the finalize call: for fix and implementer CLIs, pass `--session-id <session_id>` and `--start-sha <start_sha>` (when `start_sha` is not null in the envelope); for review CLIs, pass `--round <round>`.

7. **Branch on verdict:** Use the JSON envelope to branch identically to the existing `subprocess`/`psmux` flow — the `status`, `verdict`, `stuck_type` handling is identical.

**Agent-mode properties:**
- No log-polling or liveness check required: the orchestrator waits for the `<task-notification>` from the background agent instead of polling a log file.
- A background agent IS a detached worker and CAN be stopped or interrupted. A stopped/interrupted agent produces a notification indicating it did not complete normally — handle that the same as a raw API error via the one-retry transient path in step 4.
- `transient` stuck errors can still be emitted by `finalize` as synthetic JSON (e.g., if the brief write fails).
- The one-retry transient policy applies to both raw API errors and stopped/interrupted agents (see step 4).

**Subprocess/psmux poll-loop max-wait.** When `dispatch == subprocess` or `psmux`, all poll loops that wait for `[mill-bg] EXIT` must have a bounded max-wait (~3600s) to self-terminate if the worker dies without writing the exit marker. Exceedance of the max-wait is a fatal `infrastructure` stuck escalation. The explicit timeout guard prevents infinite polling when the worker session is killed (e.g., logout or crash). This applies to implementer, reviewer, and fixer dispatch in all scopes (per-batch and holistic), and to ERROR-only retries. See individual subsections for the loop structure; all follow the same time-bounded poll-until-EXIT pattern.

**Per-batch session cleanup.** Every time the per-batch implementer reports `success` (immediately after step 2 parse, before step 2b cleanliness gate), AND on every loop terminus (APPROVE, max-rounds blocked, cleanliness-blocked, stuck-blocked), AND when the Builder is about to re-dispatch the implementer with a fresh session (transient-retry-once), invoke the *per-batch cleanup block* defined below — it reaps the psmux TUI session associated with the batch's `implementer_session`, idempotent and failure-swallowing. The post-success invocation is the primary cleanup point now that fix dispatch is cold-start; the terminal invocations remain for defence-in-depth and are idempotent no-ops when the session is already gone.

The per-batch cleanup block:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
sys.path.insert(0, r'${CLAUDE_PLUGIN_ROOT}/scripts')
from pathlib import Path
import _paths, _status, _llm_claude
status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), '_mill/status.md')
batches = _status.read_batches(status_path)
sid = next((b.get('implementer_session') for b in batches if b['name'] == '<batch_name>'), None)
_llm_claude.cleanup_session(sid)
" || true
```

### 0. Wiki health-check

Before launching the implementer / reviewer for this batch, verify a config source is reachable. If the check fails, release the builder lock and halt — a config source became unavailable mid-run and the implementer's downstream error would mask the root cause.

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
import _paths
from wiki import _client
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
if not _client.health_check(wiki_path):
    print('[mill-go] wiki daemon health check failed', file=sys.stderr)
    raise SystemExit(1)
" || {
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
    echo "[mill-go] HALT: no config source reachable -- re-run mill-setup if mill-config.yaml is missing" >&2
    exit 1
}
```

### 1. Implement

Background via millpy-bg:

> **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

Venv-check before per-batch invocation:

```bash
if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
    echo "[mill-go] venv missing -- attempting uv sync"
    uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
    if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
        echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
        exit 1
    fi
fi
```

If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-implement.py` and `<args> = <batch_name>`.

If `dispatch == subprocess` or `psmux`: background via millpy-bg:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
    --slug implement-<batch_name> -- \
    "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
```

Returns immediately with `pid=<N> log=<abs-path>`. Do not use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check with a bounded max-wait (~3600s):
```bash
start_time=$(date +%s)
max_wait=3600
while true; do
  current_time=$(date +%s)
  elapsed=$((current_time - start_time))
  if [ $elapsed -ge $max_wait ]; then
    echo "[mill-go] HALT: subprocess poll loop timeout (max_wait=$max_wait exceeded) — worker died without writing [mill-bg] EXIT. Escalate to infrastructure stuck." >&2
    exit 1
  fi
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
  # parse JSON result and branch: "running" -> sleep; "exit"/"dead" -> exit loop
done
```
Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> sleep briefly then continue polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. If max-wait is exceeded, halt with infrastructure escalation (worker died without EXIT).

The CLI atomically: resolves paths and config, renders the implementer brief, generates a `session_id`, sets batch state → `running`, records `start_sha` and `implementer_session` in status.md, commits and pushes on the task branch, and spawns the implementer. The Builder reads the JSON summary from the log file. Note: the CLI exits 0 when the implementer produced JSON (success or stuck). On exit code 1 the JSON line in the log file still carries a `{"status":"stuck","stuck_type":"transient",...}` line if an LLM-layer failure (timeout, dead session, etc.) occurred — parse it the same way and route through Stuck escalation. Only treat exit 1 as an unrecoverable pre-launch error when the JSON line in the log file is absent.

### 2. Parse implementer report

The implementer's last output line must be JSON:

```json
{"status":"success|stuck","commit_sha":"...","session_id":"...", ...}
```

- `status: success` → continue to Code Review.
- `status: stuck, stuck_type: transient` → auto-retry ONCE: invoke the per-batch cleanup block, then re-invoke `millpy-implement.py <batch_name>` (no `--resume` flag — a fresh batch start). Record `review_round: 0`, do not change batch state. If the second invocation also reports `stuck_type: transient` → escalate per *Stuck escalation* below.
- `status: stuck, stuck_type: verify | logic` → **ask user** per *Stuck escalation*.
- Malformed / missing JSON line → treat as `stuck_type: logic` reason "no structured report".

### 2b. Cleanliness gate

After a `success` report: Before the dirt computation, resolve the parent branch and revert out-of-scope drift.

Inline Python (in step 2b, before compute_new_dirt):
```python
import _parent_branch, _cleanliness
parent_branch = _parent_branch.resolve(status_path, interactive=False)
reverted_paths, remaining_in_scope_lines = _cleanliness.revert_out_of_scope_drift(
    worktree_root, task_dir, parent_branch
)
in_scope_dirt = remaining_in_scope_lines
```

`signature: _parent_branch.resolve(status_path: Path, *, interactive: bool = True) -> str`
`signature: _cleanliness.revert_out_of_scope_drift(worktree: Path, task_dir: Path, parent_branch: str) -> tuple[list[str], list[str]]`

If `in_scope_dirt` is non-empty (genuine implementer-introduced dirt within task scope that did not pre-date the batch):
- `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
- `_status.set_batch_field(status_path, batch_name, "blocked_reason", "uncommitted working tree after implementer report")`
- `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on <batch_name> — dirty tree"`
- Invoke the per-batch cleanup block.
- Go to *Blocked*.

If `in_scope_dirt` is empty, invoke the per-batch cleanup block — the cold-start fixer used in step 4 REQUEST_CHANGES does not need the warm session. Record `commit_sha` via `_status.set_batch_field(status_path, batch_name, "commit_sha", <sha from JSON report>)`. Then continue to "3. Code Review loop" as normal.

### 3. Code Review loop

If `roles.code-review.batch.reviewer` is null (or rounds: 0): set batch state → `approved`, `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: approve batch {batch_name} (per-batch review disabled)"`, and continue to the next batch. Skip the rest of this section.

- Set batch state → `reviewing`, `review_round: 1`.
- `extra_files = []`.

For each round `N` from 1 to `roles.code-review.batch.rounds`:

- `_status.append_phase(status_path, f"reviewing-{batch_name}-r{N}", _timestamp.now_utc_iso())`.

1. **Crash-recovery check.** Before firing the CLI, scan `reviews_dir` for a file matching `*-code-review-{batch_name}-r{N}.md`. If found, validate its freshness: fetch `ref_ts = _status.phase_entry_timestamp(status_path, f"reviewing-{batch_name}-r{N}", occurrence=1)`; treat the file as this round's review ONLY if `ref_ts` is not None AND the file's mtime (UTC) is at or after `ref_ts`. If freshness validation passes, parse its verdict from the fenced yaml block via `_review_common.parse_verdict(file_content)` and skip to step 4 below. This covers the case where mill-go crashed after writing the review but before committing state. If the file is stale (mtime before `ref_ts`) or `ref_ts` is None, ignore the file and fall through to firing the CLI.

   Freshness validation in inline Python:
   ```python
   from datetime import datetime, timezone
   from pathlib import Path
   ref_ts_str = "<iso-timestamp-string>"  # result from phase_entry_timestamp
   file_path = Path("<review-file-path>")
   ref_ts = datetime.fromisoformat(ref_ts_str.strip('"')).replace(tzinfo=timezone.utc) if ref_ts_str else None
   file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
   is_fresh = ref_ts is not None and file_mtime >= ref_ts
   ```

   State explicitly: ERROR-only retries still do NOT consume the round counter; freshness — not counter consumption — is what rejects stale pre-retry files.
   `signature: _review_common.parse_verdict(text: str) -> str`
   `signature: _status.phase_entry_timestamp(status_path: Path, phase: str, *, occurrence: int = 1) -> str | None`

1.5. **Prior-notes digest (round N > 1 only).** If `N > 1`: scan the prior round's review file (from round `N-1`) for every line matching `### [NIT] <title>` (case-insensitive NIT marker). Extract the title text and the next non-empty line (which should contain Location and Issue fields). Build a digest: one line per NIT finding, in format "- Title: issue context" (ASCII-only, all non-ASCII replaced with closest ASCII), write to `<briefs_dir>/prior-nonblocking-<batch_name>-r<N>.txt`, and pass `--prior-notes <digest-path>` to the `millpy-review-code.py` invocation below. The `reviews/` read-ban is unchanged — only the curated digest reaches the reviewer. Round 1 passes no `--prior-notes` (digest defaults to `(none)` in the template).

2. If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name> [--extra-file <p> ...] [--prior-notes <digest-path>]`.

   If `dispatch == subprocess` or `psmux`: background via `millpy-bg`:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-<batch_name>-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
           --batch <batch_name> [--extra-file <p> ...] [--prior-notes <digest-path>]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Do **not** use `run_in_background: true`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears with a bounded max-wait (~3600s), but on each iteration also run a liveness check:
   ```bash
   start_time=$(date +%s)
   max_wait=3600
   while true; do
     current_time=$(date +%s)
     elapsed=$((current_time - start_time))
     if [ $elapsed -ge $max_wait ]; then
       echo "[mill-go] HALT: code-review poll loop timeout (max_wait=$max_wait exceeded) — worker died without writing [mill-bg] EXIT. Escalate to infrastructure stuck." >&2
       exit 1
     fi
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
     # parse JSON result and branch: "running" -> sleep; "exit"/"dead" -> exit loop
   done
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> sleep briefly then continue polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. If max-wait is exceeded, halt with infrastructure escalation. The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.

3. **Builder reads only the JSON envelope verdict, never the findings.** Loading `mill-receiving-review` is the dispatched implementer's job (see Principles below). Builder does not load the skill.

4. Branch on verdict:
   - `APPROVE` — If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:
   
     **NEVER skip the NIT-fix pass, even under time or performance pressure. 'Non-blocking' does NOT mean optional -- deferred nits re-surface as BLOCKING in later rounds and cost more total rounds. Only nits a reviewer explicitly marks 'no action required' may be left.**
   
     If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N> --nits-only`.
     
     If `dispatch == subprocess` or `psmux`: via `millpy-bg`:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<N>-nits -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N> --nits-only
     ```
     Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
     ```
     Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. The fixer loads `mill-receiving-review` and applies the NITs from the APPROVE'd review file. Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior. Do NOT re-review — the NIT fix is trusted. The NIT-fix session commits its own source-file changes atomically; on stuck → escalate via the existing Stuck escalation path. After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): set batch state → `approved`, `review_file: <path>`. `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`. Use the `file` field from `reviews[0]` in the JSON summary (or the crash-recovery scan path) as `<review_file_path>`. Commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"`. Invoke the per-batch cleanup block. Break out of the loop → next batch.
   - `NEED_CONTEXT` — read the `## Missing context` bullets from the review file. For each listed path, if it exists under the worktree, append to `extra_files` for the NEXT round. `_notify.notify("mill-go.review-need-context", f"batch {batch_name} round {N}", slug=slug, files=len(missing))`. Record this gap for mill-self-report (see Handoff). Increment round and continue the loop. If ALL the missing files are paths already in `extra_files` from a prior round (no new info), treat as a stuck-logic failure and break. Reading the structured `## Missing context` bullet list does not require `mill-receiving-review` -- only finding-handling does.
     `signature: _notify.notify(event: str, detail: str, **context) -> None`
   - `REQUEST_CHANGES` — If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>`.

     If `dispatch == subprocess` or `psmux`: background via millpy-bg:

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<N> -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>
     ```
     Returns immediately with `pid=<N> log=<abs-path>`. Do not use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
     ```
     Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

     The CLI atomically: resolves the batch plan, sets batch state → `fixing`, calls `_status.append_phase` for `fixing-{batch_name}-r{N}`, commits and pushes (status.md plus the review file), and dispatches a cold-start fixer session with the fix prompt (which instructs the fixer to load `mill-receiving-review` and apply findings). Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior described under "1. Implement". On stuck → escalate.

4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from sub-step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip sub-step 4 entirely and immediately re-run:

   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name> [--extra-file <p> ...]`.

   If `dispatch == subprocess` or `psmux`:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-<batch_name>-retry-r<N> -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
           --batch <batch_name> [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter `N` is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: code review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors mill-plan's existing step 4.5. *(Closes #228 — rate-limit errors no longer mis-dispatch the implementer with a null review file.)*

5. **Max-rounds exhaustion.** After `roles.code-review.batch.rounds` rounds without APPROVE: `_notify.notify("mill-go.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} after {N} rounds"`. Invoke the per-batch cleanup block. Go to *Blocked* below.

### Stuck escalation

If the deep-merged config has `pipeline.autonomous_mode: true`: for any `stuck_type` (`transient` already-retried, `verify`, `logic`, `infrastructure`): skip the user prompt; auto-handle according to the stuck_type rules below. **For `infrastructure` only**, skip straight to the autonomous-mode handling. For all others, set batch state → `blocked`, `blocked_reason: "autonomous-mode stuck: {stuck_type}"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} (autonomous-mode)"` and push; invoke the per-batch cleanup block; go to *Blocked*.

- **`infrastructure`** (bg worker died, likely logout) — **interactive** mode: surface to user with options `1) Re-fire fresh (Recommended)` / `2) Block`; user picks. On re-fire: invoke the per-batch cleanup block, then re-invoke `millpy-bg` with a fresh CLI (no `--resume` flag — the killed session is dead). If the re-fire also reports `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. **`autonomous_mode: true`**: auto-retry ONCE with a fresh re-fire (no `--resume`). If the re-fire also fails with `infrastructure`: set batch state → `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. State explicitly that the re-fire matches the existing `running`-state Resume (fresh start; killed session cannot be reattached).
- **CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2; the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session). If the second invocation also reports `stuck_type: transient`, escalate per the routing below.
- `transient` (already retried once):
  - **If `commits_made > 0` in the stuck JSON** (the implementer timed out after committing some work):
    - Interactive mode: present options:
      1) Skip to cleanliness gate (Recommended) — commits were made before the timeout; proceed directly to the cleanliness gate then code review
      2) Retry from scratch — re-fire the implementer as a fresh batch start
    - On option 1: skip re-invocation of the implementer; proceed to the per-batch cleanliness gate (scope violations check) then code review as if the implementer had reported success.
    - `autonomous_mode: true`: auto-pick option 1 (skip to cleanliness gate).
    - If `commits_made == 0` or the field is absent: use the existing three-option path below.
  - **Otherwise** (no commits made or timeout before any commit) → surface to user with three options: retry fresh, edit plan and retry, block. User picks.
- `verify` / `logic` → surface to user with three options: edit plan to clarify then retry fresh, skip this batch (block the task), block the task. User picks.
- On user-chosen block: set batch state → `blocked`, `blocked_reason: <reason>`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`. Invoke the per-batch cleanup block. Go to *Blocked*.

### Blocked

- `_notify.notify("mill-go.blocked", f"batch {batch_name}: {blocked_reason}", slug=slug, batch=batch_name)`.
- Release the builder lock:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
  ```
- Tell the user: "Batch X blocked with reason Y. Inspect reviews/ and status.md. Re-run `/mill-go` after resolving, or `/mill-abandon` to wind down." Do not proceed to Handoff.

## Resume

When mill-go's Entry-step 5 phase gate routes here (phase is `implementing`, `reviewing`, or `fixing`), the previous run was interrupted mid-batch. The CLIs that mutate task state (`millpy-implement.py`, `millpy-review-code.py`) are atomic — they record state-mutation commits before the heavy work starts and after each transition — so the resume playbook is simple: read the current batch entry and re-invoke the CLI for the current state.

1. Read `_mill/status.md`; locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
2. Branch on the batch's `state`:
   - **`running`** — the implementer was mid-implementation. Re-invoke:

     If `dispatch == agent`: in agent mode the SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state. The prepare-stage pre-commit makes this idempotent; the brief at `_mill/briefs/<role>-<scope>-r<round>.md` is reused/re-rendered. Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-implement.py` and `<args> = <batch_name>`.

     If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug implement-<batch_name>-resume -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
     ```
     The interrupted implementer session is dead and cannot be re-attached. A fresh batch start is the correct recovery: the CLI re-initialises state -> running, captures a new snapshot, and spawns a fresh implementer session. After parsing the report, continue at Execute step 2b (cleanliness gate).
   - **`reviewing`** — the implementer report was already consumed; the reviewer was running. Re-invoke the per-batch code-review CLI from the start of round `review_round` (read this field from the batch entry):

     If `dispatch == agent`: in agent mode the SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state. Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = --batch <batch_name>`.

     If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug review-code-<batch_name>-r<review_round>-resume -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" --batch <batch_name>
     ```
     The CLI's crash-recovery scan handles a written-but-uncommitted review file. After parsing the JSON verdict, continue at Execute step 3 sub-step 3 (load `mill-receiving-review`) and step 4 (branch on verdict).
   - **`fixing`** — the reviewer returned `REQUEST_CHANGES`; the fix-implementer was running. Re-invoke:

     If `dispatch == agent`: in agent mode the SKILL re-runs the same prepare -> Agent -> finalize flow for the current on-disk state. Follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <review_round>`.

     If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

     > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<review_round>-resume -- \
         "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <review_round>
     ```
     The `<review-file-abs-path>` is the most recent `_mill/reviews/*-code-review-<batch_name>-r<review_round>.md` file. After parsing the report, continue at Execute step 3 sub-step 5 (max-rounds check) or back to step 3 round N+1 if the fix produced an APPROVE-eligible state on next review.
3. **No state mutation before resume.** Do NOT pre-emptively flip `state` or call `_status.append_phase` before re-invoking the CLI. The CLI handles state transitions atomically; double-writes corrupt the timeline.
4. **`mill-receiving-review` remains the fixer's responsibility.** When resume re-dispatches the fixer (`millpy-fix.py --scope batch ...`), the fix-prompt itself instructs the fixer to load the skill before reading findings. Builder still does not load it.

## Holistic code review

**Holistic session cleanup.** Whenever a `millpy-fix.py --scope holistic` invocation completes (success, stuck, or any error path), capture the `session_id` field from the parsed JSON envelope into a local Bash variable `holistic_sid`. At any point where the holistic loop is about to dispatch a NEW `millpy-fix.py --scope holistic` round, AND at every loop terminus (APPROVE, autonomous-mode block, user-block, max-rounds), invoke the *holistic cleanup block* defined below.

The holistic cleanup block:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
sys.path.insert(0, r'${CLAUDE_PLUGIN_ROOT}/scripts')
import _llm_claude
_llm_claude.cleanup_session('${holistic_sid}')
" || true
```

If the captured `holistic_sid` is empty or the literal `unknown`, cleanup is a documented no-op — the implementer brief contract guarantees the id is emitted on the happy path.

**Guard:** The skip semantics have two conditions: `reviewer: null` OR `rounds: 0` means "skip holistic". Only execute this section if `cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("reviewer") is not None`.

`max_holistic_rounds = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("rounds", 1)`. Loop variable `H` starts at 1. `extra_files = []`.

For each round `H` from 1 to `max_holistic_rounds`:

0. Wiki health-check

   Before launching the implementer / reviewer for this batch, verify a config source is reachable. If the check fails, release the builder lock and halt — a config source became unavailable mid-run and the implementer's downstream error would mask the root cause.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import sys
   import _paths
   from wiki import _client
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   if not _client.health_check(wiki_path):
       print('[mill-go] wiki daemon health check failed', file=sys.stderr)
       raise SystemExit(1)
   " || {
       PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
       echo "[mill-go] HALT: no config source reachable -- re-run mill-setup if mill-config.yaml is missing" >&2
       exit 1
   }
   ```

1. **Crash-recovery.** Three-way branch based on what is on disk in `_mill/reviews/` and `.scratch/`:
   - **(a) Review file present.** Scan `reviews/` for a file matching `*-code-review-r{H}.md` (holistic code review files have format `{ts}-code-review-r{N}.md` -- no batch-name segment, no `-holistic-` substring; per-batch files embed `{batch_name}` so the glob never collides). If found, validate its freshness: fetch `ref_ts = _status.phase_entry_timestamp(status_path, "holistic-reviewing", occurrence=H)` (the Hth occurrence corresponds to round H); treat the file as this round's review ONLY if `ref_ts` is not None AND the file's mtime (UTC) is at or after `ref_ts`. If freshness validation passes, skip the CLI and use that file's verdict directly. Proceed to step 4 (verdict branch); do NOT execute step 2 (the phase entry was already appended on the original run) and do NOT execute step 3. If the file is stale or `ref_ts` is None, fall through to branch (b)/(c) handling (fire the CLI). Provide the inline-Python comparison snippet as per the per-batch section above.
   - **(b) No review file, no bg log for round H.** Proceed normally to step 2 (append `holistic-reviewing` phase) and step 3 (fire CLI via `millpy-bg`).
   - **(c) No review file, bg log exists for round H** (matching glob `.scratch/bg-*-review-code-holistic-r{H}.log`). Pick the most recent matching file and call `_bg.is_bg_worker_alive(log_path)`:
      - **Alive** -> poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
        ```bash
        PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
        ```
        Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed to step 4 (parse JSON, branch on verdict); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. Do NOT execute step 2; do NOT execute step 3.
      - **Dead** -> log `[mill-go] previous holistic round H bg worker died (pid=N); re-firing CLI` to stderr, then jump directly to step 3 (fire fresh CLI via `millpy-bg`). Do NOT execute step 2 (the phase entry was already appended on the original run).

   Inline Python helper for branches (a) and (c):

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from pathlib import Path
   import _paths, _bg, json, sys
   hub = _paths.resolve_hub_path()
   reviews_dir = hub / '_mill/reviews'
   scratch_dir = _paths.resolve_git_root() / '.scratch'
   H = ${H}
   # (a) review file scan
   matches = sorted(reviews_dir.glob(f'*-code-review-r{H}.md')) if reviews_dir.exists() else []
   if matches:
       print(json.dumps({'branch': 'a', 'review_file': str(matches[-1])}))
       sys.exit(0)
   # (c) bg log liveness probe
   bg_logs = sorted(scratch_dir.glob(f'bg-*-review-code-holistic-r{H}.log')) if scratch_dir.exists() else []
   if bg_logs:
       alive, pid = _bg.is_bg_worker_alive(bg_logs[-1])
       print(json.dumps({'branch': 'c', 'log_path': str(bg_logs[-1]), 'alive': alive, 'pid': pid}))
       sys.exit(0)
   # (b) nothing on disk
   print(json.dumps({'branch': 'b'}))
   "
   ```

   Parse the JSON line. Branch dispatch is exactly as enumerated above. The helper is one-shot; do not poll it.

2. **Skip this step when step 1 returned branch (a) or any sub-branch of (c).** `_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())`. Commit: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: holistic reviewing round {H}"`.

2.5. **Prior-notes digest (round H > 1 only).** If `H > 1`: scan the prior round's review file (from round `H-1`, matching `*-code-review-r{H-1}.md` with no batch-name segment) for every line matching `### [NIT] <title>` (case-insensitive NIT marker). Extract the title text and the next non-empty line (which should contain Location and Issue fields). Build a digest: one line per NIT finding, in format "- Title: issue context" (ASCII-only, all non-ASCII replaced with closest ASCII), write to `<briefs_dir>/prior-nonblocking-holistic-r{H}.txt`, and pass `--prior-notes <digest-path>` to the `millpy-review-code.py` invocation below. The `reviews/` read-ban is unchanged — only the curated digest reaches the reviewer. Round 1 passes no `--prior-notes` (digest defaults to `(none)` in the template).

3. If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = [--extra-file <p> ...] [--prior-notes <digest-path>]` (no `--batch` flag for holistic scope). Include any accumulated `extra_files` from prior `NEED_CONTEXT` rounds via `--extra-file <p>` (one flag per path).

   If `dispatch == subprocess` or `psmux` (via `millpy-bg`):

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   Venv-check before holistic review invocation:

   ```bash
   if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
       echo "[mill-go] venv missing -- attempting uv sync"
       uv sync --project "${CLAUDE_PLUGIN_ROOT}" || { echo "HALT: uv sync failed"; exit 1; }
       if [ ! -f "${CLAUDE_PLUGIN_ROOT}/.venv/Scripts/python.exe" ]; then
           echo "HALT: venv not found after sync -- run 'uv sync --project \${CLAUDE_PLUGIN_ROOT}' manually."
           exit 1
       fi
   fi
   ```

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
     --slug review-code-holistic-r{H} -- \
     "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
       [--extra-file <p> ...] [--prior-notes <digest-path>]
   ```
   Include any accumulated `extra_files` from prior `NEED_CONTEXT` rounds via `--extra-file <p>` (one flag per path). Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   **Exit handling.** If `[mill-bg] EXIT` reports a non-zero exit AND no JSON summary line is present in the log, halt with "BLOCKED: holistic review pre-launch failure" and surface the last stderr line from the log to the user. If a JSON envelope IS present (even with `verdict: ERROR`), drop through to sub-step 3.5 ERROR-only retry as normal. Matches the per-batch section's "only treat exit 1 as unrecoverable when JSON line is absent" branch.

3.5. **Step 3.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 3 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4 and 5 entirely and immediately re-run:

   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-review-code.py` and `<args> = [--extra-file <p> ...]`.

   If `dispatch == subprocess` or `psmux`:

   > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
     --slug review-code-holistic-retry-r<H> -- \
     "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
       [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line.

   The round counter `H` is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, **first check rate-limit fallback** (see sub-step 3.6 below). If sub-step 3.6 does NOT apply, halt with `BLOCKED: holistic code review ERROR-only round {H}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass.

3.6. **Rate-limit fallback (no round consumed)**

   When sub-step 3.5's second pass returns `verdict: ERROR` AND `roles.code-review.holistic.fallback_reviewer` is not null AND any `reviews[*].error` string contains (case-insensitive) a substring listed in `roles.code-review.holistic.fallback_on` (default `["rate-limit"]`):

   1. Emit `_notify.notify("mill-go.holistic-fallback", f"swap reviewer -> {fallback_name}", slug=slug, round=H)`.
   2. In-memory mutation: `cfg["roles"]["code-review"]["holistic"]["reviewer"] = cfg["roles"]["code-review"]["holistic"]["fallback_reviewer"]`. Do NOT write back to disk -- the swap lasts only for the current mill-go invocation.
   3. Re-run sub-step 3 (the holistic review CLI) with the swapped reviewer. The round counter `H` is **not** consumed.
   4. If the fallback reviewer ALSO returns `verdict: ERROR` on its first pass: halt with `BLOCKED: holistic code review fallback also failed at round {H}` and surface every `reviews[*].error` from BOTH the original and fallback attempts. Do NOT cascade to a second fallback.
   5. If `pipeline.autonomous_mode: true` AND `fallback_reviewer is None` AND a rate-limit was detected on both 3.5 passes: halt with `BLOCKED: holistic rate-limited, no fallback_reviewer configured`. The operator-visible message is intentional -- silent infinite fallback is wrong.

   Operator interactive path (no `autonomous_mode`, no `fallback_reviewer`): user prompt remains identical to today (the existing step 5 ROUND-EXHAUSTION sub-section handles this case).

4. On `APPROVE`: If `nit_count > 0` in the envelope, dispatch one cold-start NIT-only fix pass:
   
   **NEVER skip the NIT-fix pass, even under time or performance pressure. 'Non-blocking' does NOT mean optional -- deferred nits re-surface as BLOCKING in later rounds and cost more total rounds. Only nits a reviewer explicitly marks 'no action required' may be left.**
   
   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <review-file-abs-path> --round {H} --nits-only`.
   
   If `dispatch == subprocess` or `psmux` (via `millpy-bg`):
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug fix-holistic-r{H}-nits -- \
       "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope holistic --review-file <review-file-abs-path> --round {H} --nits-only
   ```
   Poll `cat <log-path>` until `[mill-bg] EXIT` appears, but on each iteration also run a liveness check:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
   ```
   Parse the JSON result as `(status, pid_or_code)` and branch: `"running"` -> keep polling; `"exit"` -> proceed as today (extract JSON); `"dead"` -> classify as `stuck_type: infrastructure` and route to Stuck escalation. Note: `"dead"` only fires when the log has no parseable JSON result line — if EXIT was missing but the worker wrote a valid JSON line, `check_bg_status` returns `("exit", 0)` instead (see `_bg.py` JSON fallback). Once `[mill-bg] EXIT` appears or dead status is detected, run `grep '^{' <log-path> | tail -1` to extract the JSON summary line. The fixer loads `mill-receiving-review` and applies the NITs. Do NOT re-review — the NIT fix is trusted. On stuck → escalate via the existing Stuck escalation path. After the NIT-fix completes successfully (or is skipped because `nit_count = 0`): `_status.append_phase(status_path, "holistic-approved", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: holistic approve {slug}"`, where `<review_file_path>` is the `file` field from `reviews[0]` of the JSON envelope (or the crash-recovery branch (a) scan path). This mirrors the per-batch APPROVE branch, which already stages its review file. If a NIT-fix pass ran for the holistic scope this round, the fixer already committed its own changes; this commit still stages the review file plus the `holistic-approved` status row. Invoke the holistic cleanup block. Proceed to Handoff.

5. On `REQUEST_CHANGES`: the holistic-fix CLI dispatches a fresh fixer; the fixer loads `mill-receiving-review` (see Principles below). Builder does not load the skill. Invoke the holistic cleanup block (reaps the previous round's session before the next one starts). 
   
   If `dispatch == agent`: follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" above) with `<cli> = millpy-fix.py` and `<args> = --scope holistic --review-file <abs-path-to-holistic-review-file> --round {H}`.
   
   If `dispatch == subprocess` or `psmux`: Dispatch:
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-fix.py" --scope holistic --review-file <abs-path-to-holistic-review-file> --round {H}
   ```
   Parse stdout JSON (same last-`{"status":...}`-line pattern as per-batch). The CLI handles `holistic-fixing` phase + commit + push itself.
   - `stuck_type: infrastructure`: **interactive** mode — surface with options `1) Re-fire fresh (Recommended)` / `2) Skip holistic / 3) Block task`; user picks. On re-fire: invoke the holistic cleanup block, then re-invoke `millpy-fix.py --scope holistic` once (fresh). If the re-fire also fails with `infrastructure`: present user with same three options. **`autonomous_mode: true`** — auto-retry ONCE with a fresh re-fire. If the re-fire also fails: invoke the holistic cleanup block, set batch state -> `blocked`, `blocked_reason: "infrastructure: bg worker died (logout?)"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit, and go to *Blocked*. State that the re-fire is fresh (killed session cannot be reattached).
   - `stuck_type: transient`: one-retry policy (re-invoke once). If still transient: surface to user — retry fresh / skip holistic / block task. On user-chosen block: invoke the holistic cleanup block, then go to *Blocked*.
   - `stuck_type: verify` or `logic`: surface to user — edit plan and retry / skip holistic and proceed to Handoff / block task. On user-chosen block: invoke the holistic cleanup block, then go to *Blocked*.
   - On success: increment H and loop.

6. On `NEED_CONTEXT`: apply the same extra-files / notify path as per-batch.

7. **Rounds exhausted** (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned): If the deep-merged config has `pipeline.autonomous_mode: true`: `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; `_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s) (autonomous-mode)")`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (autonomous-mode)"` and push; invoke the holistic cleanup block; halt with "Autonomous mode: holistic review exhausted. Task left as [active]." Otherwise surface to user with a **blocked-task halt** (not blocked-batch):
   > Holistic review exhausted {max_holistic_rounds} round(s). Task is blocked.
   > 1) Rethink — revise discussion and re-run mill-plan.
   > 2) Skip holistic — accept remaining findings and proceed to Handoff.
   > 3) Block — halt and leave for manual resolution.
   On user choice of "3) Block": invoke the holistic cleanup block, then halt and leave for manual resolution. Wait for user choice before proceeding.

## Handoff

**Nit-enforcement gate.** Check for approved scopes with unfixed nits:

```python
from pathlib import Path
import _nit_gate
unfixed_nits = _nit_gate.compute_unfixed_nits(worktree_root, reviews_dir, status_path)
```

If `unfixed_nits` is non-empty, halt with:
`BLOCKED: unfixed nits in scope(s): <scope-list> -- run the NIT-fix pass before completing`
where `<scope-list>` is the joined list of scope names. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can run the NIT-fix pass and re-run `/mill-go`.

If the list is empty, proceed to terminal cleanliness gate.

**Terminal cleanliness gate.** Resolve the parent branch and check for in-scope uncommitted changes:

```python
parent_branch = _parent_branch.resolve(status_path, interactive=False)
in_scope_dirt = _cleanliness.compute_terminal_dirt(worktree_root, task_dir, parent_branch)
```

If `in_scope_dirt` is non-empty, halt with:
`BLOCKED: dirty working tree at task completion -- <N> file(s) uncommitted: <file-list>. Commit or discard before proceeding.`
where `<N>` is the count of dirty lines and `<file-list>` is the filenames extracted from the in-scope dirt. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and fix.

If the list is empty, proceed to scope violations cleanup.

**Scope violations cleanup gate.** Clean up ephemeral build artifacts that may have been left by verify runs:

```python
removed_paths, blocking_paths = _cleanliness.clean_ephemeral_scope_violations(worktree_root)
```

Log the removed artifacts (ASCII-only). If `blocking_paths` is non-empty, halt with:
`BLOCKED: out-of-scope untracked file(s): <file-list>`
where `<file-list>` is the comma-separated list of blocking paths. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can inspect and manually remove the files.

If the list is empty, proceed normally.

**Scope violations handling note.** The `scope_violations` field in the fixer JSON envelope (present when a fixer detects untracked out-of-scope files) is read and surfaced to the orchestrator. It is folded into the generic `stuck_type: logic` envelope; the terminal gate (above) is the authoritative cleanup point for common artifacts like coverage profiling outputs.

**0. Pre-done gate.** Read `(cfg.get("pipeline") or {}).get("done_gate")` (deep-merged config; the `or {}` guard handles the case where `pipeline:` is present but null). If the value is `None` or absent, skip. If it is a non-null string, run the command from `git_root` (not hub dir) as a best-effort verify:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import json, sys, subprocess, platform
import _paths, _config
git_root = _paths.resolve_git_root()
hub_root = _paths.resolve_hub_path()
cfg = _config.load_config(hub_root, git_root)
gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')
if not gate_cmd:
    sys.exit(0)
result = subprocess.run(gate_cmd, cwd=git_root, shell=True, capture_output=True, text=True)
if result.returncode != 0:
    out = (result.stdout + result.stderr).strip()
    reason = out[-2000:] if len(out) > 2000 else out
    print(json.dumps({'status': 'blocked', 'reason': f'done gate failed: {reason}'}))
    sys.exit(1)
# dotnet cleanup: if gate command contains 'dotnet' and we are on Windows,
# run build-server shutdown to release process locks before mill-finalize runs.
if platform.system() == 'Windows' and 'dotnet' in gate_cmd.lower():
    subprocess.run(['dotnet', 'build-server', 'shutdown'], capture_output=True, timeout=30)
"
```

Parse stdout for a JSON line. If the exit code is non-zero and the JSON line has `status: blocked`, halt with: `BLOCKED: done gate failed — <reason>`. Do NOT set `phase: done` when the gate fires; the task remains in its current phase so the operator can investigate the failure. `subprocess.run` with `capture_output=True` does not raise on non-zero exit code — check `result.returncode`.

1. `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add <status_path> _mill/briefs/ && git -C <worktree> commit -m "mill-go: done {slug}"`.

2. Flip Home.md's task line to `[ready-to-merge]` — the new intermediate state signalling 'mill-go done, mill-merge pending':
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from pathlib import Path; import _paths
   from wiki import _client
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   _client.set_phase(wiki_path, '<slug>', 'ready-to-merge')
   "
   ```
3. `_notify.notify("mill-go.done", f"task {slug} complete", slug=slug)`.
4. **Release the builder lock immediately:**
   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
   ```
5. If `pipeline.auto_merge: true` → invoke `/mill-finalize`. Otherwise tell the user: "Task complete. Run `/mill-finalize` to finalize the task (creates a PR or squashes directly, depending on config)." mill-finalize may halt on `pr-pending` in PR mode — that is expected; treat it as completion of step 5 and continue to step 6.
6. If `pipeline.auto_report: true` → invoke `/mill-self-report --auto`. **Always fires** at the end of Handoff, including after a `pr-pending` halt in step 5 — do NOT treat the PR-pending message as task termination. The skill checks `gh auth` itself and bails cleanly if absent. Cross-thread merges and post-PR teardowns are not auto-reflected; user can run `/mill-self-report` manually if wanted.

## Principles

- **Lean Builder.** You never read card bodies, diffs, or source files unless responding to a stuck-logic event on a specific batch. Your context stays small by design — this is what lets Opus be a legitimate Builder choice.
- **Implementer owns receive-review.** On `REQUEST_CHANGES` the implementer (not Builder) loads `mill-receiving-review` and applies findings. Builder passes a pointer to the review file; the implementer's warm session already knows the code.
- **Commits go through `git-commit`.** `implementer-brief.md` already instructs this, but enforce it if the implementer asks for confirmation: every per-card commit invokes the `git-commit` skill so lint + `codeguide-update` run per-commit. Batch N+1's implementer then reads a codeguide that already reflects batch N's additions.
- **One task per worktree.** The builder lock enforces this at runtime. Do not attempt to relax it.
- **Never guess when stuck.** Surface to the user with concrete options; don't invent a recovery.
- **Review files are the ground truth.** Verdict parsing reads only the fenced yaml block; the `## Findings` body is the implementer's job to read, not yours.
- **Helper signatures are documented inline.** Every helper this skill names has an explicit one-line signature in the section that calls it. Never Read or Grep the helper source — the signature is here, and any failure surfaces as an exception. (See `mill:workflow` for the project-wide rule.)
- **TodoWrite items name batches by number.** Emit todo items as `Implement batch N (<batch-slug>)` — e.g. `Implement batch 1 (foundations)` — so progress in the todo list correlates 1:1 with plan files (`NN-<batch-slug>.md`). Bare names without a number force the operator to cross-reference the Batch Index every time.

## Board discipline

- `status_path`, `reviews_dir/<file>`, and `plan_dir/<file>` writes are committed on the **task branch** via `git -C <worktree> add ... && git -C <worktree> commit`. `millpy-implement.py` and `millpy-fix.py` push their own task-branch state commits (batch-start, batch-fix, holistic-fix) to `origin/<task-branch>` immediately after each `git commit`. The Builder's own state commits (Prepare, Approve, blocked, done) and per-card implementer commits do not push — mill-merge pushes the full task branch at task end. Adding push to the Builder's own commits is a follow-up task; this PR scopes the push policy to CLI commits only.
- Wiki phase mutations (the Handoff `[ready-to-merge]` flip) go through `_client.set_phase(wiki_path, slug, "ready-to-merge")`. The daemon serializes all writes and pushes automatically.
- Phase transitions via `_status.append_phase`; batch-state mutations via `_status.set_batch_field`. Hand-editing either yaml block is banned.
- The path-invariant rule from CLAUDE.md is load-bearing: working state never goes to the wiki — only Home.md / _Sidebar.md do.
