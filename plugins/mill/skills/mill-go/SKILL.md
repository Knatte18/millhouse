---
name: mill-go
description: In a spawned worktree with an approved plan, sequentially execute every batch in the plan's DAG. Per batch spawn one implementer Sonnet, run code review, loop with receive-review on REQUEST_CHANGES, halt on stuck. Hand off to mill-finalize.
---

# mill-go

> Wiki access: never `cd .wiki/`. Use the documented helpers — see CLAUDE.md `## Wiki access`.

You are the **Builder** — a lean orchestrator. You coordinate per-batch implementation but never read card bodies or diffs yourself. The **Implementer** (spawned per batch) reads its own batch file, implements cards, runs `verify:`, and fixes on receive-review. You read only `status.md`, the Batch Index DAG in `00-overview.md`, and the fenced yaml verdict block of each code review. Keeping your context lean is the whole point — Builder cost is a rounding error next to the Implementer and code-reviewer calls.

## Entry

**Step 0: Resolve `PLUGIN_ROOT`.**

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
if [ -z "$PLUGIN_ROOT" ]; then
    PLUGIN_ROOT="$(git rev-parse --show-toplevel)/plugins/mill"
    echo "[mill-go] CLAUDE_PLUGIN_ROOT unset; resolved to: $PLUGIN_ROOT"
    echo "[mill-go] NOTE: source-tree venv must exist at $PLUGIN_ROOT/.venv — run 'uv sync --project $PLUGIN_ROOT' if not."
fi
MILL_PYTHON="${PLUGIN_ROOT}/.venv/Scripts/python.exe"
```

Use `$PLUGIN_ROOT` in place of `$CLAUDE_PLUGIN_ROOT` for all subsequent `uv run` commands in this skill.

1. Read the task slug: `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)`. On `MarkerError` → halt with "this worktree was not created by mill-spawn".
   `signature: _marker.slug_from_branch(git_root: Path, wiki_path: Path, cfg: dict) -> str`
2. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())`. Sync the wiki clone: `_wiki.sync_pull(wiki_path, slug=slug)`.
   `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None`
3. Load config — deep-merge `<wiki_path>/config.yaml` with `.millhouse/config.local.yaml` via `_review_common.load_config(wiki_path, Path(".millhouse"))`. Read these keys:
   - `pipeline.auto_merge` — whether to invoke mill-finalize after success.
   - `pipeline.auto_report` — whether to auto-fire mill-self-report at end-of-work. mill-go fires it at Handoff step 6, AFTER any `/mill-merge` invocation in step 5 — including after PR-pending halts. See step 6 for the explicit "do not treat PR-pending as termination" rule.
   - `roles.code-review.batch.rounds` — max review rounds per batch.
   - `roles.code-review.holistic.rounds` — max holistic review rounds (parallel cap for the holistic scope, default 1).
   - `roles.implementer.self_fix_rounds` — passed to the implementer brief.
   - `roles.code-review.holistic.reviewer` — if non-null, run one holistic code review after all batches approve.
   - `roles.code-review.batch.reviewer` — if null (or rounds: 0), skip per-batch code review for all batches.
4. Acquire the builder lock:
   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
   ```
   On exit code 1: surface the stderr message and halt — a second mill-go will corrupt state.
4.5. **Path Setup.** `worktree_root` is not yet set in prior steps; `cfg` was loaded in step 3. Derive:
   ```python
   worktree_root = _paths.resolve_git_root()
   status_path   = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
   plan_dir      = _paths.resolve_task_path(worktree_root, cfg['paths']['plan_dir'])
   overview_path = plan_dir / "00-overview.md"
   reviews_dir   = _paths.resolve_task_path(worktree_root, cfg['paths']['reviews_dir'])
   task_dir      = status_path.parent
   ```
   Use these variables for all subsequent path references. Exception: the cleanliness snapshot path `_mill/.cleanliness-snapshot-<batch_name>.txt` keeps its `_mill/` literal — `millpy-implement.py` writes it unconditionally to `_mill/` and is out of scope.
5. **Entry phase gate.** Inspect the phase:
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

### 0. Wiki health-check

Before launching the implementer / reviewer for this batch, verify the wiki is intact. If the check fails, release the builder lock and halt — the wiki disappeared mid-run and the implementer's downstream "Missing config" error would mask the root cause.

```bash
PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
import sys
import _paths, _wiki
wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
try:
    _wiki.health_check(wiki_path)
except _wiki.WikiHealthError as e:
    print(f'[mill-go] wiki health check failed: {e}', file=sys.stderr)
    raise SystemExit(1)
" || {
    PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
    echo "[mill-go] HALT: wiki appears missing or corrupted — re-run mill-setup to restore it" >&2
    exit 1
}
```

### 1. Implement

Background via millpy-bg:

```bash
PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
    --slug implement-<batch_name> -- \
    "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
```

Returns immediately with `pid=<N> log=<abs-path>`. Do not use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll the log file with `cat <log-path>` until `[mill-bg] EXIT` appears. Once it does, read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log).

The CLI atomically: resolves paths and config, renders the implementer brief, generates a `session_id`, sets batch state → `running`, records `start_sha` and `implementer_session` in status.md, commits and pushes on the task branch, and spawns the implementer. The Builder reads the JSON summary from the log file. Note: the CLI exits 0 when the implementer produced JSON (success or stuck). On exit code 1 the JSON line in the log file still carries a `{"status":"stuck","stuck_type":"transient",...}` line if an LLM-layer failure (timeout, dead session, etc.) occurred — parse it the same way and route through Stuck escalation. Only treat exit 1 as an unrecoverable pre-launch error when the JSON line in the log file is absent.

### 2. Parse implementer report

The implementer's last output line must be JSON:

```json
{"status":"success|stuck","commit_sha":"...","session_id":"...", ...}
```

- `status: success` → continue to Code Review.
- `status: stuck, stuck_type: transient` → auto-retry ONCE by re-invoking `millpy-implement.py <batch_name>` (no `--resume` flag — a fresh batch start). Record `review_round: 0`, do not change batch state. If the second invocation also reports `stuck_type: transient` → escalate per *Stuck escalation* below.
- `status: stuck, stuck_type: verify | logic` → **ask user** per *Stuck escalation*.
- Malformed / missing JSON line → treat as `stuck_type: logic` reason "no structured report".

Record `commit_sha` from a successful report on the batch entry.

### 2b. Cleanliness gate

After a `success` report: compute new dirt via `_cleanliness.compute_new_dirt(<worktree>, <worktree>/_mill/.cleanliness-snapshot-<batch_name>.txt)`. If the returned list is non-empty (genuine implementer-introduced dirt that did not pre-date the batch):
- `_status.set_batch_field(status_path, batch_name, "state", "blocked")`
- `_status.set_batch_field(status_path, batch_name, "blocked_reason", "uncommitted working tree after implementer report")`
- `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`
- Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on <batch_name> — dirty tree"`
- Go to *Blocked*.

`signature: _cleanliness.compute_new_dirt(worktree: Path, snapshot_path: Path) -> list[str]`

If the returned list is empty, continue to "3. Code Review loop" as normal.

### 3. Code Review loop

If `roles.code-review.batch.reviewer` is null (or rounds: 0): set batch state → `approved`, `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: approve batch {batch_name} (per-batch review disabled)"`, and continue to the next batch. Skip the rest of this section.

- Set batch state → `reviewing`, `review_round: 1`.
- `_status.append_phase(status_path, f"reviewing-{batch_name}-r1", _timestamp.now_utc_iso())`.
- `extra_files = []`.

For each round `N` from 1 to `roles.code-review.batch.rounds`:

1. **Crash-recovery check.** Before firing the CLI, scan `reviews_dir` for a file matching `*-code-review-{batch_name}-r{N}.md`. If found, treat it as this round's review file — parse its verdict from the fenced yaml block via `_review_common.parse_verdict(file_content)` and skip to step 4 below. This covers the case where mill-go crashed after writing the review but before committing state.
   `signature: _review_common.parse_verdict(text: str) -> str`

2. Background via `millpy-bg`:

   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-<batch_name>-r<N> -- \
       "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-review-code.py" \
           --batch <batch_name> [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Do **not** use `run_in_background: true`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then extract the JSON summary line (last non-empty, non-sentinel line). The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.

3. **Before reading any review file, load the `mill-receiving-review` skill.** Non-negotiable.

4. Branch on verdict:
   - `APPROVE` — batch state → `approved`, `review_file: <path>`. `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`. Use the `file` field from `reviews[0]` in the JSON summary (or the crash-recovery scan path) as `<review_file_path>`. Commit on the task branch: `git -C <worktree> add <status_path> <review_file_path> && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"`. Break out of the loop → next batch.
   - `NEED_CONTEXT` — read the `## Missing context` bullets from the review file. For each listed path, if it exists under the worktree, append to `extra_files` for the NEXT round. `_notify.notify("mill-go.review-need-context", f"batch {batch_name} round {N}", slug=slug, files=len(missing))`. Record this gap for mill-self-report (see Handoff). Increment round and continue the loop. If ALL the missing files are paths already in `extra_files` from a prior round (no new info), treat as a stuck-logic failure and break.
     `signature: _notify.notify(event: str, detail: str, **context) -> None`
   - `REQUEST_CHANGES` — Background via millpy-bg:
     ```bash
     PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<N> -- \
         "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume --round <N> --review-file <review-file-abs-path>
     ```
     Returns immediately with `pid=<N> log=<abs-path>`. Do not use `run_in_background: true` on the Bash tool — that routes output to CC's temp dir. Poll the log file with `cat <log-path>` until `[mill-bg] EXIT` appears. Once it does, read the log and extract the JSON summary line (the last non-empty, non-sentinel line in the log).

     The CLI atomically: reads `implementer_session` from status.md, sets batch state → `fixing`, calls `_status.append_phase` for `fixing-{batch_name}-r{N}`, commits and pushes (status.md plus the review file), and resumes the warm implementer session with the fix prompt (which instructs the implementer to load `mill-receiving-review` and apply findings). Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior described under "1. Implement". On stuck → escalate.

4.5. **Step 4.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from sub-step 2 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip sub-step 4 entirely and immediately re-run:

   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-<batch_name>-retry-r<N> -- \
       "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-review-code.py" \
           --batch <batch_name> [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then extract the JSON summary line from the log.

   The round counter `N` is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: code review ERROR-only round {N}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors mill-plan's existing step 4.5. *(Closes #228 — rate-limit errors no longer mis-dispatch the implementer with a null review file.)*

5. **Max-rounds exhaustion.** After `roles.code-review.batch.rounds` rounds without APPROVE: `_notify.notify("mill-go.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} after {N} rounds"`. Go to *Blocked* below.

### Stuck escalation

If the deep-merged config has `pipeline.autonomous_mode: true`: for any `stuck_type` (`transient` already-retried, `verify`, `logic`): skip the user prompt; set batch state → `blocked`, `blocked_reason: "autonomous-mode stuck: {stuck_type}"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name} (autonomous-mode)"` and push; go to *Blocked*.

- **CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2; the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session). If the second invocation also reports `stuck_type: transient`, escalate to user with the regular `transient` three-option prompt (retry fresh, edit plan and retry, block).
- `transient` (already retried once) → surface to user with three options: retry fresh, edit plan and retry, block. User picks.
- `verify` / `logic` → surface to user with three options: edit plan to clarify then retry fresh, skip this batch (block the task), block the task. User picks.
- On user-chosen block: set batch state → `blocked`, `blocked_reason: <reason>`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`. Go to *Blocked*.

### Blocked

- `_notify.notify("mill-go.blocked", f"batch {batch_name}: {blocked_reason}", slug=slug, batch=batch_name)`.
- Release the builder lock:
  ```bash
  PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
  ```
- Tell the user: "Batch X blocked with reason Y. Inspect reviews/ and status.md. Re-run `/mill-go` after resolving, or `/mill-abandon` to wind down." Do not proceed to Handoff.

## Resume

When mill-go's Entry-step 5 phase gate routes here (phase is `implementing`, `reviewing`, or `fixing`), the previous run was interrupted mid-batch. The CLIs that mutate task state (`millpy-implement.py`, `millpy-review-code.py`) are atomic — they record state-mutation commits before the heavy work starts and after each transition — so the resume playbook is simple: read the current batch entry and re-invoke the CLI for the current state.

1. Read `_mill/status.md`; locate the current batch entry (the single entry whose `state` is non-terminal: `running`, `reviewing`, or `fixing`).
2. Branch on the batch's `state`:
   - **`running`** — the implementer was mid-implementation. Re-invoke (via `millpy-bg`):
     ```bash
     PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug implement-<batch_name>-resume -- \
         "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume
     ```
     The CLI re-attaches the warm session via the stored `implementer_session`. If `LLMSessionError` propagates (visible as `stuck_type: transient` in the JSON), apply the standard one-retry-fresh policy from Stuck escalation. After parsing the report, continue at Execute step 2b (cleanliness gate).
   - **`reviewing`** — the implementer report was already consumed; the reviewer was running. Re-invoke the per-batch code-review CLI from the start of round `review_round` (read this field from the batch entry):
     ```bash
     PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug review-code-<batch_name>-r<review_round>-resume -- \
         "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-review-code.py" --batch <batch_name>
     ```
     The CLI's crash-recovery scan handles a written-but-uncommitted review file. After parsing the JSON verdict, continue at Execute step 3 sub-step 3 (load `mill-receiving-review`) and step 4 (branch on verdict).
   - **`fixing`** — the reviewer returned `REQUEST_CHANGES`; the fix-implementer was running. Re-invoke:
     ```bash
     PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
         --slug fix-<batch_name>-r<review_round>-resume -- \
         "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume --round <review_round> --review-file <review-file-abs-path>
     ```
     The `<review-file-abs-path>` is the most recent `_mill/reviews/*-code-review-<batch_name>-r<review_round>.md` file. After parsing the report, continue at Execute step 3 sub-step 5 (max-rounds check) or back to step 3 round N+1 if the fix produced an APPROVE-eligible state on next review.
3. **No state mutation before resume.** Do NOT pre-emptively flip `state` or call `_status.append_phase` before re-invoking the CLI. The CLI handles state transitions atomically; double-writes corrupt the timeline.
4. **`mill-receiving-review` is still mandatory.** When resume lands you at any point that reads a review file, load the skill first (per the existing rule at Execute step 3 sub-step 3 and Holistic step 5).

## Holistic code review

**Guard:** The skip semantics have two conditions: `reviewer: null` OR `rounds: 0` means "skip holistic". Only execute this section if `cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("reviewer") is not None`.

`max_holistic_rounds = cfg.get("roles", {}).get("code-review", {}).get("holistic", {}).get("rounds", 1)`. Loop variable `H` starts at 1. `extra_files = []`.

For each round `H` from 1 to `max_holistic_rounds`:

0. Wiki health-check

   Before launching the implementer / reviewer for this batch, verify the wiki is intact. If the check fails, release the builder lock and halt — the wiki disappeared mid-run and the implementer's downstream "Missing config" error would mask the root cause.

   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import sys
   import _paths, _wiki
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   try:
       _wiki.health_check(wiki_path)
   except _wiki.WikiHealthError as e:
       print(f'[mill-go] wiki health check failed: {e}', file=sys.stderr)
       raise SystemExit(1)
   " || {
       PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
       echo "[mill-go] HALT: wiki appears missing or corrupted — re-run mill-setup to restore it" >&2
       exit 1
   }
   ```

1. **Crash-recovery.** Scan `reviews/` for a file matching `*-code-review-r{H}.md` (holistic code review files have format `{ts}-code-review-r{N}.md` — no batch-name segment, no `-holistic-` substring; per-batch files embed `{batch_name}` so the glob never collides). If found, skip the CLI and use that file's verdict directly.

2. `_status.append_phase(status_path, "holistic-reviewing", _timestamp.now_utc_iso())`. Commit: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: holistic reviewing round {H}"`.

3. Background via `millpy-bg`:
   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
     --slug review-code-holistic-r{H} -- \
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-review-code.py" \
       [--extra-file <p> ...]
   ```
   Include any accumulated `extra_files` from prior `NEED_CONTEXT` rounds via `--extra-file <p>` (one flag per path). Poll and extract JSON as per the per-batch pattern.

3.5. **Step 3.5: ERROR-only-aggregate retry (no round consumed)**

   When the JSON envelope from step 3 has top-level `verdict: "ERROR"` (or, equivalently, every entry in `reviews[]` has `verdict: "ERROR"`), skip steps 4 and 5 entirely and immediately re-run:

   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-bg.py" \
     --slug review-code-holistic-retry-r<H> -- \
     "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-review-code.py" \
       [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then extract the JSON summary line from the log.

   The round counter `H` is **not** consumed — the round produced no reviewable output. On the **second** consecutive run that still has top-level `verdict: "ERROR"`, halt with `BLOCKED: holistic code review ERROR-only round {H}` and surface each entry's `error` string from `reviews[]` to the user. Do NOT auto-retry beyond the second pass. The two-pass cap mirrors mill-plan's existing step 4.5.

4. On `APPROVE`: `_status.append_phase(status_path, "holistic-approved", _timestamp.now_utc_iso())`. Commit status. Proceed to Handoff.

5. On `REQUEST_CHANGES`: **Load `mill-receiving-review` before reading any finding.** Dispatch:
   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-implement-holistic.py" \
     --review-file <abs-path-to-holistic-review-file> --round {H}
   ```
   Parse stdout JSON (same last-`{"status":...}`-line pattern as per-batch). The CLI handles `holistic-fixing` phase + commit + push itself.
   - `stuck_type: transient`: one-retry policy (re-invoke once). If still transient: surface to user — retry fresh / skip holistic / block task.
   - `stuck_type: verify` or `logic`: surface to user — edit plan and retry / skip holistic and proceed to Handoff / block task.
   - On success: increment H and loop.

6. On `NEED_CONTEXT`: apply the same extra-files / notify path as per-batch.

7. **Rounds exhausted** (`H > max_holistic_rounds`, `REQUEST_CHANGES` still returned): If the deep-merged config has `pipeline.autonomous_mode: true`: `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`; `_status.update_field(status_path, "blocked_reason", f"holistic review exhausted {max_holistic_rounds} round(s) (autonomous-mode)")`; commit `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: blocked on holistic review (autonomous-mode)"` and push; halt with "Autonomous mode: holistic review exhausted. Task left as [active]." surface to user with a **blocked-task halt** (not blocked-batch):
   > Holistic review exhausted {max_holistic_rounds} round(s). Task is blocked.
   > 1) Rethink — revise discussion and re-run mill-plan.
   > 2) Skip holistic — accept remaining findings and proceed to Handoff.
   > 3) Block — halt and leave for manual resolution.
   Wait for user choice before proceeding.

## Handoff

1. `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-go: done {slug}"`.
2. Flip Home.md's task line to `[ready-to-merge]` — the new intermediate state signalling 'mill-go done, mill-merge pending':
   ```python
   home_path = wiki_path / "Home.md"
   with _wiki.wiki_lock(wiki_path, slug):
       _tasks_md.set_phase_at(home_path, slug, "ready-to-merge")
       _wiki.write_commit_push(wiki_path, ["Home.md"], f"task: ready-to-merge {slug}", slug=slug)
   ```
   `signature: _tasks_md.set_phase_at(path: Path, slug: str, phase: str | None) -> None`
   `signature: _wiki.wiki_lock(wiki_path: Path, slug: str) -> ContextManager[None]`
   `signature: _wiki.write_commit_push(wiki_path: Path, paths: list[str], msg: str, *, slug: str) -> None`
   The lock-context wraps the read-modify-write atomically; `set_phase_at` does the read+transform+write itself; `write_commit_push` acquires the lock internally but the counter from `wiki_lock` makes that a no-op.
3. `_notify.notify("mill-go.done", f"task {slug} complete", slug=slug)`.
4. **Release the builder lock immediately:**
   ```bash
   PYTHONPATH="${PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
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

- `status_path`, `reviews_dir/<file>`, and `plan_dir/<file>` writes are committed on the **task branch** via `git -C <worktree> add ... && git -C <worktree> commit`. `millpy-implement.py` pushes its own task-branch state commits (batch-start, fix-cycle) to `origin/<task-branch>` immediately after each `git commit`. The Builder's own state commits (Prepare, Approve, blocked, done) and per-card implementer commits do not push — mill-merge pushes the full task branch at task end. Adding push to the Builder's own commits is a follow-up task; this PR scopes the push policy to CLI commits only.
- Home.md writes (the Handoff `[done]` flip) go through `_wiki.write_commit_push(..., slug=...)` inside a `with _wiki.wiki_lock(wiki_path, slug):` block. The wiki helpers acquire the lock internally; the context manager makes the read-modify-write atomic.
- Phase transitions via `_status.append_phase`; batch-state mutations via `_status.set_batch_field`. Hand-editing either yaml block is banned.
- The path-invariant rule from CLAUDE.md is load-bearing: working state never goes to the wiki — only Home.md / _Sidebar.md do.
