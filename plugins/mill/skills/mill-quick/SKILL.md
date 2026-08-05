---
name: mill-quick
description: "single-pass fix+verify+done skill for simple tasks -- invoked immediately after mill-spawn in place of mill-start, with no discussion round, no plan, and no reviewer of any kind"
---

# mill-quick

The full mill pipeline (discussion + review rounds, plan + plan-review rounds, implement + code-review + fixer loops) pays a fixed review-and-orchestration cost regardless of task size.
For genuinely simple or mechanical tasks — small doc fixes, one-line config changes, renames — that cost is pure overhead. `mill-quick` collapses the entire pipeline into a single pass: this session reads the task, makes the fix inline, commits, runs `pipeline.done_gate`, and marks the task done — with zero discussion round, zero plan, and no reviewer of any kind.

## Entry

Every check below is a precondition: if any of them fails, halt immediately with the stated message and do not proceed to a later step.
No tracked `_mill/` file may be edited before step 6 — the one exception is step 5's builder-lock acquire, which writes the gitignored `.millhouse/builder.lock` file on a successful acquire.

1. **Resolve paths, config, and slug.**
   Mirrors `mill-start`'s own Entry step 1 / Path Setup pattern — `mill-quick` writes neither `discussion.md` nor any `_mill/reviews/` file, so it resolves no `discussion_path` / `reviews_dir`.

   - `git_root = _paths.resolve_git_root()`
   - `wiki_path = _paths.resolve_wiki_path(git_root)`
   - `worktree_root = _paths.resolve_hub_path()`
   - `cfg = _config.load_config(worktree_root, git_root)` — signature `_config.load_config(hub_root: Path, worktree_root: Path) -> dict`;
     called with this exact `(hub_root, git_root)` argument shape for consistency with the established call pattern used elsewhere in the codebase, e.g. `mill-go/SKILL.md`'s "0.55" block.
   - `slug = _marker.slug_from_branch(git_root, wiki_path, cfg)` — on `_marker.MarkerError`, halt: "this worktree was not created by mill-spawn" (identical wording to `mill-start`'s Entry step 3 halt).
   - `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`

2. **`done_gate`-null hard precondition.**
   The cheapest check — no wiki round-trip — so it runs first among the precondition checks.

   - `gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')`
   - If `gate_cmd` is falsy (`None` or empty string): halt with `"BLOCKED: mill-quick requires pipeline.done_gate to be configured in mill-config.yaml before use -- configure a repo-wide test command and retry."` Do not touch any file.
     This is the `verify-mechanism` Decision's hard precondition from `_mill/discussion.md` — `mill-quick` never proceeds with unverified work.

3. **Entry-phase gate.**

   - `status_data = _status.read(status_path)`
   - If `status_data.get('phase') != 'discussing'`: halt with `f"mill-quick only runs immediately after mill-spawn, before mill-start. Current phase: {status_data.get('phase')!r}. Run /mill-start instead."`
   - If `status_data.get('plan') is not None`: halt with the same message shape, substituting a note that `plan:` is already set (belt-and-suspenders per the `entry-phase-gate` Decision).

4. **Wiki task fetch + status precondition.**
   Use the exact same `PYTHONIOENCODING=utf-8`-prefixed invocation shape as `mill-start`'s Phase: Select (same reasoning: avoid the cp1252 `UnicodeEncodeError` on non-ASCII body/brief content on Windows):

   ```bash
   PYTHONIOENCODING=utf-8 PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   from pathlib import Path
   from wiki import _client
   import _paths
   wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
   task = _client.get_task(wiki_path, '<slug>')
   if task is None:
       raise SystemExit('[mill-quick] slug not found in wiki -- was this worktree created by mill-spawn?')
   print('STATUS:', task.get('status', ''))
   print('--- BRIEF ---')
   print(task.get('brief', ''))
   print('--- BODY ---')
   print(task.get('body', ''))
   "
   ```

   Unlike `mill-start`, `mill-quick` makes this call only once — there is no separate later re-fetch, since the printed `BRIEF`/`BODY` output is already in this session's context and stays valid for the rest of this same linear flow (no long gap like `mill-start`'s Select-then-Explore split).
   Parse only the first output line (the `STATUS:` line);
   if it is not `STATUS: active`, halt: `f"task status is {status!r}, expected 'active'."` (same gate `mill-start` Phase: Select uses).

5. **Acquire the builder lock** — only after every check in steps 2-4 has passed:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" acquire <slug>
   ```

   On exit 1 (a *different* slug holds a non-stale lock in this worktree — see `_builder_lock.py`'s `LockBusy`), surface stderr and halt.
   **Corrected scope of the `concurrency-guard` Decision:** this only guards cross-slug contention and self-heals across a crash/resume of the *same* slug (idempotent re-acquire) — it does **not** exclude two concurrent `mill-quick` invocations against the same slug;
   that risk is accepted under the operator-trust model.

6. **Write the intermediate phase** — the first point any file may be touched:

   - `_status.append_phase(status_path, "implementing", _timestamp.now_utc_iso())`
   - Commit via raw git (not the `git-commit` skill — this is state bookkeeping, not a code change): `git -C <worktree> add
     <status_path> && git -C <worktree> commit -m "mill-quick: start
     implementing {slug}"`. Do **not** push — deferred, mirroring `mill-go`'s Builder-role state commits (see Board discipline below).

## Fix

`mill-quick` is a single-inline-agent skill: **this session itself** performs the entire fix — exploration, editing, committing — with no `Agent`/`Task` tool call and no `mill-implementer-*` dispatch.
Whatever model the operator started this session with is the model that does the work;
`mill-quick` has no tier/model-selection parameter.

- Explore and edit using whatever tool calls the fix requires (Read, Grep, Glob, Edit, Write, Bash) — no fixed algorithm;
  the task body/ brief already read in Entry step 4 is the scope.
- Commit the fix by invoking the `git-commit` skill with a summary of the change as the argument — do **not** call raw `git commit`.
  The skill runs language-appropriate lint on staged files and triggers `codeguide-update` when `_codeguide/Overview.md` exists.
  This commit pushes immediately as part of `git-commit`'s own unconditional-push contract — this is harmless here because nothing downstream (`mill-merge`, `mill-finalize`) acts on a task before `phase: done`.

## Verify & Complete

1. **Run the done gate.** `gate_cmd` was already resolved and validated non-null in Entry step 2 — reuse that same value here (do not re-read config).
   Invoke:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
   import json
   import _paths, _config, _done_gate
   git_root = _paths.resolve_git_root()
   hub_root = _paths.resolve_hub_path()
   cfg = _config.load_config(hub_root, git_root)
   gate_cmd = (cfg.get('pipeline') or {}).get('done_gate')
   result = _done_gate.run_preflight(gate_cmd, git_root)
   print(json.dumps(result))
   "
   ```

   `gate_cmd` is re-derived inside the subprocess rather than passed from Entry's in-session value across a fresh `Bash` subprocess boundary — this is safe because Entry step 2 already proved it is non-null and it cannot have changed mid-flow.
   Give this Bash-tool call an extended 600000ms (10-minute) timeout, same justification as `mill-go`'s "0.55" step: `gate_cmd` is an arbitrary, potentially slow project command with no bound on runtime.

2. **Parse the JSON result** and branch on `result["result"]`:
   - `"ok"` → success path (below).
   - `"blocked"` → failure path (below), using `result["reason"]`.
   - `"skipped"` → treat identically to `"blocked"` with reason `"done_gate unexpectedly empty at verify time"` — this branch should be unreachable given Entry step 2's precondition;
     it is a defensive-only fallback, not an expected path.

3. **Success path:**

   - `_status.append_phase(status_path, "done", _timestamp.now_utc_iso())`.
     Commit via raw git (deferred push, same as Entry step 6): `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-quick: done {slug}"`.
   - Flip the wiki phase — required, not optional (mirrors `mill-go` Handoff step 2 exactly):

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
     from pathlib import Path; import _paths
     from wiki import _client
     wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())
     _client.set_phase(wiki_path, '<slug>', 'ready-to-merge')
     "
     ```
   - Release the builder lock:

     ```bash
     PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-builder-lock.py" release
     ```
   - Report to the user: `"Task complete via mill-quick. Run /mill-finalize to finalize the task (creates a PR or squashes directly, depending on config)."` Do **not** auto-invoke `/mill-finalize` — `pipeline.auto_merge`/`auto_report` auto-continuation (which `mill-go`'s own Handoff steps 5-6 perform) is intentionally out of scope here: it is not decided anywhere in `_mill/discussion.md`, and `mill-quick` matches `mill-start`'s own Handoff precedent of a plain informational report with no auto-invocation of the next skill.

4. **Failure path:**

   - `_status.set_blocked(status_path, f"done gate failed: {result['reason']}", timestamp=_timestamp.now_utc_iso())`.
   - Commit via raw git **and push immediately** — the one exception to the deferred-push rule, mirroring `mill-start`'s `--auto`-mode blocked-halt precedent (a blocked task never reaches `mill-merge` and would otherwise be invisible remotely): `git -C <worktree> add
     <status_path> && git -C <worktree> commit -m "mill-quick: blocked
     (done gate failed) for {slug}" && git -C <worktree> push`.
   - Release the builder lock (same command as the success path).
   - Halt, reporting to the user: `f"BLOCKED: done gate failed for {slug} -- {result['reason']}"`.

## Known limitations

**Orphaned `phase: implementing`.**
If this session crashes or is interrupted between writing `phase: implementing` and reaching the done-gate check, the task is left stuck at `implementing` with no automatic recovery — no fixer/retry loop exists by design. `mill-quick`'s own entry gate cannot resume it (requires `phase: discussing`), and `mill-go`'s resume path assumes a `plan.md` file with a `## Batches` section, a structure `mill-quick` never creates.
The escape hatch is manual: `mill-cleanup`/`mill-abandon`, or a manual `_status.set_blocked` call.

## Board discipline

`mill-quick` makes three kinds of commit, each with its own mechanism and push rule — they must not be conflated:

- **The fix commit** (the actual code change): via the `git-commit` skill, pushes immediately, harmless — nothing downstream acts on the task before `phase: done`.
- **The `implementing`/`done` phase commits**: raw git, deferred — not pushed here;
  pushed later by `mill-finalize`/`mill-merge`, mirroring `mill-go`'s own Builder-role state commits.
- **The `blocked` phase commit**: raw git, pushed immediately — the one exception, since a blocked task never reaches `mill-merge` and would otherwise be invisible remotely.
- On the success path, the wiki phase mutation `_client.set_phase(wiki_path, slug, "ready-to-merge")` mirrors `mill-go`'s Board discipline bullet for its own Handoff `[ready-to-merge]` flip.
- Hand-editing `status.md`'s yaml block is banned outside the documented `_status.py` calls above, matching every other mill skill's Board discipline section.
