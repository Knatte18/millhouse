---
name: mill-go
description: In a spawned worktree with an approved plan, sequentially execute every batch in the plan's DAG. Per batch spawn one implementer Sonnet, run code review, loop with receive-review on REQUEST_CHANGES, halt on stuck. Hand off to mill-merge.
---

# mill-go

You are the **Builder** — a lean orchestrator. You coordinate per-batch implementation but never read card bodies or diffs yourself. The **Implementer** (spawned per batch) reads its own batch file, implements cards, runs `verify:`, and fixes on receive-review. You read only `status.md`, the Batch Index DAG in `00-overview.md`, and the fenced yaml verdict block of each code review. Keeping your context lean is the whole point — Builder cost is a rounding error next to the Implementer and code-reviewer calls.

## Entry

1. Read the task slug: `slug = _active.read_slug(Path(".millhouse"))`. Missing → halt with "this worktree was not created by mill-spawn".
   `signature: _active.read_slug(mill_dir: Path) -> str`
2. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root(Path.cwd()))`. Sync the wiki clone: `_wiki.sync_pull(wiki_path, slug=slug)`.
   `signature: _wiki.sync_pull(wiki_path: Path, *, slug: str) -> None`
3. Load config — deep-merge `<wiki_path>/config.yaml` with `.millhouse/config.local.yaml` via `_review_common.load_config(wiki_path, Path(".millhouse"))`. Read these keys:
   - `pipeline.auto_merge` — whether to invoke mill-merge after success.
   - `pipeline.auto_report` — whether to auto-fire mill-self-report at end-of-work.
   - `review.code.rounds` — max review rounds per batch.
   - `review.code.self_fix_rounds` — passed to the implementer brief.
   - `review.code.holistic` — if true, run one holistic code review after all batches approve.
4. Acquire the builder lock: `_builder_lock.acquire(Path(".millhouse"), slug)`. On `LockBusy`: surface the message and halt — a second mill-go will corrupt state.
   `signature: _builder_lock.acquire(mill_dir: Path, slug: str) -> LockInfo`
5. **Entry phase gate.** Set `status_path = Path("status.md").resolve()` and inspect the phase via `_status.read_full(status_path)`.
   `signature: _status.read_full(status_path: Path) -> dict`

   | phase | action |
   | --- | --- |
   | `planned` | fresh run — continue to Prepare |
   | `implementing` / `reviewing` / `fixing` | resume (see *Resume*) |
   | `blocked` | surface `blocked_reason` from status.md and halt |
   | `discussed` / `discussing` / `planning` | tell user to finish mill-plan and halt |
   | `done` | tell user the task is complete; suggest `/mill-merge` if auto-merge was off |
   | any other | surface + halt |

6. Read the plan overview: `overview_path = Path("plan/00-overview.md").resolve()`. Confirm `approved: true` in the frontmatter. Extract the Batch Index via `_plan_dag.extract_batch_index(overview_text)`, validate via `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`, then compute `order = _plan_dag.topo_order(batches)`.
   `signature: _plan_dag.extract_batch_index(overview_text: str) -> list[dict]`
   `signature: _plan_dag.validate(batches: list[dict], batch_files: list[str]) -> None`
   `signature: _plan_dag.topo_order(batches: list[dict]) -> list[str]`

## Prepare

On a fresh run only (no `## Batches` section in status.md):

- `_status.init_batches(status_path, order)` — seeds every batch at `state: pending`.
  `signature: _status.init_batches(status_path: Path, names: list[str]) -> None`
- `_status.append_phase(status_path, "implementing", _timestamp.now_utc_iso())`.
  `signature: _status.append_phase(status_path: Path, phase: str, timestamp: str) -> None`
  `signature: _timestamp.now_utc_iso() -> str`
- Commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: prepare for {slug}"`.

## Execute — sequential loop

For each batch in `order`:

### 1. Implement

- Invoke:
  ```bash
  uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name>
  ```
  The CLI atomically: resolves paths and config, renders the implementer brief, generates a `session_id`, sets batch state → `running`, records `start_sha` and `implementer_session` in status.md, commits and pushes on the task branch, spawns the implementer, and prints the implementer's JSON report on stdout. The Builder reads stdout JSON directly for the Parse step. Note: the CLI exits 0 when the implementer produced JSON (success or stuck). On exit code 1 the stdout still carries a `{"status":"stuck","stuck_type":"transient",...}` line if an LLM-layer failure (timeout, dead session, etc.) occurred — parse it the same way and route through Stuck escalation. Only treat exit 1 as an unrecoverable pre-launch error when stdout is empty.

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

### 3. Code Review loop

- Set batch state → `reviewing`, `review_round: 1`.
- `_status.append_phase(status_path, f"reviewing-{batch_name}-r1", _timestamp.now_utc_iso())`.
- `extra_files = []`.

For each round `N` from 1 to `review.code.rounds`:

1. **Crash-recovery check.** Before firing the CLI, scan `Path("reviews").resolve()` for a file matching `*-code-review-{batch_name}-r{N}.md`. If found, treat it as this round's review file — parse its verdict from the fenced yaml block via `_review_common.parse_verdict(file_content)` and skip to step 4 below. This covers the case where mill-go crashed after writing the review but before committing state.
   `signature: _review_common.parse_verdict(text: str) -> str`

2. Background via `millpy-bg`:

   ```bash
   uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
       --slug review-code-<batch_name>-r<N> -- \
       uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py" \
           --batch <batch_name> [--extra-file <p> ...]
   ```

   Returns immediately with `pid=<N> log=<abs-path>`. Do **not** use `run_in_background: true`. Poll `cat <log-path>` until `[mill-bg] EXIT` appears, then extract the JSON summary line (last non-empty, non-sentinel line). The CLI prints one JSON line `{"type":"code","round":N,"verdict":"...","reviews":[...]}`.

3. **Before reading any review file, load the `mill-receiving-review` skill.** Non-negotiable.

4. Branch on verdict:
   - `APPROVE` — batch state → `approved`, `review_file: <path>`. `_status.append_phase(status_path, f"approved-{batch_name}", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"`. Break out of the loop → next batch.
   - `NEED_CONTEXT` — read the `## Missing context` bullets from the review file. For each listed path, if it exists under the worktree, append to `extra_files` for the NEXT round. `_notify.notify("mill-go.review-need-context", f"batch {batch_name} round {N}", slug=slug, files=len(missing))`. Record this gap for mill-self-report (see Handoff). Increment round and continue the loop. If ALL the missing files are paths already in `extra_files` from a prior round (no new info), treat as a stuck-logic failure and break.
     `signature: _notify.notify(event: str, detail: str, **context) -> None`
   - `REQUEST_CHANGES` — invoke:
     ```bash
     uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-implement.py" <batch_name> --resume --round <N> --review-file <review-file-abs-path>
     ```
     The CLI atomically: reads `implementer_session` from status.md, sets batch state → `fixing`, calls `_status.append_phase` for `fixing-{batch_name}-r{N}`, commits and pushes (status.md plus the review file), and resumes the warm implementer session with the fix prompt (which instructs the implementer to load `mill-receiving-review` and apply findings). Parse the JSON report the same way as step 2 — including the exit-code-1-with-stuck-JSON behavior described under "1. Implement". On stuck → escalate.

5. **Max-rounds exhaustion.** After `review.code.rounds` rounds without APPROVE: `_notify.notify("mill-go.review-exhausted", f"batch {batch_name}", slug=slug, rounds=N)`, set batch state → `blocked`, `blocked_reason: "review rounds exhausted"`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: blocked on {batch_name} after {N} rounds"`. Go to *Blocked* below.

### Stuck escalation

- **CLI emits `stuck_type: transient`** (LLM-layer failure surfaced as the synthetic stuck JSON described in Implement step 2; the CLI exits 1 in that case but stdout carries the JSON) → apply the one-retry policy: re-invoke `millpy-implement.py <batch_name>` once with no `--resume` flag (a fresh session). If the second invocation also reports `stuck_type: transient`, escalate to user with the regular `transient` three-option prompt (retry fresh, edit plan and retry, block).
- `transient` (already retried once) → surface to user with three options: retry fresh, edit plan and retry, block. User picks.
- `verify` / `logic` → surface to user with three options: edit plan to clarify then retry fresh, skip this batch (block the task), block the task. User picks.
- On user-chosen block: set batch state → `blocked`, `blocked_reason: <reason>`, `_status.append_phase(status_path, "blocked", _timestamp.now_utc_iso())`, commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: blocked on {batch_name}"`. Go to *Blocked*.

### Blocked

- `_notify.notify("mill-go.blocked", f"batch {batch_name}: {blocked_reason}", slug=slug, batch=batch_name)`.
- Release the builder lock: `_builder_lock.release(mill_dir)`.
- Tell the user: "Batch X blocked with reason Y. Inspect reviews/ and status.md. Re-run `/mill-go` after resolving, or `/mill-abandon` to wind down." Do not proceed to Handoff.

## Holistic code review

After every batch in `order` has state `approved`, and only if `review.code.holistic: true`:

- Background via `millpy-bg`: `uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" --slug review-code-holistic-r<N> -- uv run --project "${CLAUDE_PLUGIN_ROOT}" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-review-code.py"` (no `--batch`). Poll and extract JSON as per the per-batch pattern above.
- On `REQUEST_CHANGES`: apply the same review-fix loop as per-batch — track holistic state via `_status.append_phase` with dedicated holistic phase names (`"holistic-reviewing"`, `"holistic-fixing"`, `"holistic-approved"`) rather than `_status.set_batch_field` (which would raise `ValueError: Batch 'holistic' not present` since 'holistic' is never initialized via `init_batches`). Spawn the implementer via `_implementer_sonnet.run(prompt_text, session_id=new_uuid, resume=False, cwd=worktree_path)` with the review file pointer (no resume — holistic review's findings span multiple batches; the implementer receives whole-worktree access).
  `signature: _implementer_sonnet.run(prompt_text: str, *, session_id: str | None = None, resume: bool = False, cwd: Path | str | None = None, timeout: int = 1800) -> tuple[str, str]`
  Run the same review-fix loop until APPROVE or rounds-exhausted. On rounds-exhausted only, surface to user with the same blocked-batch halt prompt as per-batch flow.
- On `NEED_CONTEXT` apply the same extra-files / notify path as per-batch.

## Handoff

1. `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())`. Commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: done {slug}"`.
2. Flip Home.md's task line to `[done]`:
   ```python
   home_path = wiki_path / "Home.md"
   with _wiki.wiki_lock(wiki_path, slug):
       _tasks_md.set_phase_at(home_path, slug, "done")
       _wiki.write_commit_push(wiki_path, ["Home.md"], f"task: complete {slug}", slug=slug)
   ```
   `signature: _tasks_md.set_phase_at(path: Path, slug: str, phase: str | None) -> None`
   `signature: _wiki.wiki_lock(wiki_path: Path, slug: str) -> ContextManager[None]`
   `signature: _wiki.write_commit_push(wiki_path: Path, paths: list[str], msg: str, *, slug: str) -> None`
   The lock-context wraps the read-modify-write atomically; `set_phase_at` does the read+transform+write itself; `write_commit_push` acquires the lock internally but the counter from `wiki_lock` makes that a no-op.
3. `_notify.notify("mill-go.done", f"task {slug} complete", slug=slug)`.
4. **Release the builder lock immediately:** `_builder_lock.release(Path(".millhouse"))`.
   `signature: _builder_lock.release(mill_dir: Path) -> None`
5. If `pipeline.auto_report: true` → invoke `/mill-self-report` directly with no argument. The skill checks `gh auth` itself and bails cleanly if absent. Wait for it to finish before continuing.
6. If `pipeline.auto_merge: true` → invoke `/mill-merge`. Otherwise tell the user: "Task complete. Run `/mill-merge` to merge the task branch back to parent."

## Principles

- **Lean Builder.** You never read card bodies, diffs, or source files unless responding to a stuck-logic event on a specific batch. Your context stays small by design — this is what lets Opus be a legitimate Builder choice.
- **Implementer owns receive-review.** On `REQUEST_CHANGES` the implementer (not Builder) loads `mill-receiving-review` and applies findings. Builder passes a pointer to the review file; the implementer's warm session already knows the code.
- **Commits go through `git-commit`.** `implementer-brief.md` already instructs this, but enforce it if the implementer asks for confirmation: every per-card commit invokes the `git-commit` skill so lint + `codeguide-update` run per-commit. Batch N+1's implementer then reads a codeguide that already reflects batch N's additions.
- **One task per worktree.** The builder lock enforces this at runtime. Do not attempt to relax it.
- **Never guess when stuck.** Surface to the user with concrete options; don't invent a recovery.
- **Review files are the ground truth.** Verdict parsing reads only the fenced yaml block; the `## Findings` body is the implementer's job to read, not yours.
- **Helper signatures are documented inline.** Every helper this skill names has an explicit one-line signature in the section that calls it. Never Read or Grep the helper source — the signature is here, and any failure surfaces as an exception. (See `mill:workflow` for the project-wide rule.)

## Board discipline

- Status.md, reviews/<file>, and plan/<file> writes are committed on the **task branch** via `git -C <worktree> add ... && git -C <worktree> commit`. `millpy-implement.py` pushes its own task-branch state commits (batch-start, fix-cycle) to `origin/<task-branch>` immediately after each `git commit`. The Builder's own state commits (Prepare, Approve, blocked, done) and per-card implementer commits do not push — mill-merge pushes the full task branch at task end. Adding push to the Builder's own commits is a follow-up task; this PR scopes the push policy to CLI commits only.
- Home.md writes (the Handoff `[done]` flip) go through `_wiki.write_commit_push(..., slug=...)` inside a `with _wiki.wiki_lock(wiki_path, slug):` block. The wiki helpers acquire the lock internally; the context manager makes the read-modify-write atomic.
- Phase transitions via `_status.append_phase`; batch-state mutations via `_status.set_batch_field`. Hand-editing either yaml block is banned.
- The path-invariant rule from CLAUDE.md is load-bearing: working state never goes to the wiki — only Home.md / _Sidebar.md do.
