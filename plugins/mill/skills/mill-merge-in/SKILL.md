---
name: mill-merge-in
description: Sync the parent branch into the current branch. Checkpoint + conflict policy + verify + codeguide-update. Safe to call standalone or as mill-merge's first step.
---

# mill-merge-in

Merge the parent branch into the current branch.
Creates a rollback checkpoint first, resolves conflicts conservatively, replays the same batch verifies mill-go ran during implementation, and runs codeguide-update when applicable.
This skill does not acquire the merge lock — only the calling `mill-merge` (or the user running it standalone) touches state outside the current branch.

## Entry

1. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
   On `MarkerError` → halt with "this worktree was not created by mill-spawn".
2. Resolve the parent branch.
   **Source of truth is `_mill/status.md`'s `parent:` row** — call `_parent_branch.resolve(status_path, interactive=True, expected_slug=slug)` where `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")` and `slug` is already resolved in Entry step 1 via `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
   Config does not carry a parent-branch override (YAGNI as of v2.0).
   If `mill-merge-in` is being called from `mill-merge`'s auto-merge path, pass `interactive=False` and propagate the raised `ParentBranchError` -- `expected_slug=slug` applies in both the interactive and non-interactive forms of the call.

   **Liveness check (#817):** after `resolve(...)` above returns a `parent_branch` successfully, first run the preflight guard `` import _preflight; exit(_preflight.check_helpers(['_parent_branch:check_liveness'])) `` , then verify it is still live: `_parent_branch.check_liveness(parent_branch, git_root)` (same call `mill-merge/SKILL.md` Entry Step 4 makes — see that step's own "Liveness check (#817)" paragraph for the exact bash invocation and the JSON shape returned).
   If alive, continue as before.
   If dead, call `_parent_branch.resolve_dead_parent(parent_branch, git_root, cfg)` and apply the identical halt/report/confirm/rebind behavior documented in `mill-merge/SKILL.md` Entry Step 4's "Liveness check (#817)" paragraph: report the `resolved` or `fallback` outcome and require operator confirmation before continuing (the `cycle` outcome always halts outright, no confirmation prompt), then on confirmation rebind `status.md`'s `parent:` row via `_status.update_field(status_path, "parent", resolved_branch)`, commit, push, and use `resolved_branch` as `parent_branch` for the remainder of this run.
   "Identical" above describes the operator-facing halt/report/confirm/rebind protocol, not the `status_path` derivation mechanism: this rebind reuses the same `status_path` already bound at the top of this Entry step (`_paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`) rather than deriving a fresh one, and that is safe here even though `mill-merge/SKILL.md` Entry Step 4 warns against the same `resolve_hub_path()` + literal-path pattern for its own rebind — that warning exists because `mill-merge` must reconcile cwd against a separately-tracked worktree location (its `mode == 'inplace'` vs `'worktree'` disambiguation, where cwd can legitimately be the main hub while the active slug's tracked worktree lives elsewhere).
   `mill-merge-in` has no such ambiguity: it always operates on "the current branch" from within that branch's own worktree (it is never dispatched against a different slug's worktree from some other cwd), so `resolve_hub_path()`'s cwd-walk necessarily lands on the same hub a slug-driven `resolve_active_hub()` lookup would return for that slug.
   This mirrors the identical `resolve_hub_path()`-based derivation this file's own Step 4 (Verify) already uses (`hub_root = _paths.resolve_hub_path()`), so Card 7's rebind is consistent with the rest of this file, not a one-off exception to it.
   This check runs identically whether `mill-merge-in` is invoked standalone or dispatched from `mill-merge`'s Step 2 — `mill-merge-in` reads the same `status_path` independently via its own `resolve()` call, and must not skip this check just because `mill-merge`'s own Entry Step 4 may have already performed it moments earlier for its own call site. The redundancy is harmless: `check_liveness` is a single read-only `git ls-remote`.
3. Optional positional argument: `<branch>` from the user's invocation overrides both status.md and the prompt.
   This is for ad-hoc syncing from some other branch than the task's declared parent.

## Steps

### 1. No-op check

```bash
git fetch origin "<parent-branch>" 2>/dev/null
if git rev-parse --verify --quiet "refs/remotes/origin/<parent-branch>" >/dev/null 2>&1 \
   && git merge-base --is-ancestor "<parent-branch>" "origin/<parent-branch>"; then
  MERGE_REF="origin/<parent-branch>"
else
  MERGE_REF="<parent-branch>"
fi
git log HEAD.."$MERGE_REF" --oneline
```

If output is empty → report "Nothing to merge — already up to date." and exit 0 immediately.
No checkpoint, no verify, no codeguide-update.
This is the fast-path contract that lets `mill-merge` call this skill cheaply as a first step.

### 2. Create checkpoint

```bash
CHK="mill-checkpoint-$(git rev-parse --abbrev-ref HEAD | tr '/' '-')"
OLD_CHK_SHA=$(git rev-parse --verify --quiet "$CHK" || true)
git branch -f "$CHK"
if [ -n "$OLD_CHK_SHA" ]; then
  NEW_CHK_SHA=$(git rev-parse "$CHK")
  echo "[mill-merge-in] note: existing checkpoint $CHK moved from $OLD_CHK_SHA -> $NEW_CHK_SHA (current pre-merge HEAD)"
fi
```

The checkpoint is force-refreshed to the current (true pre-merge) HEAD on every run.
This is safe because step 1's no-op check has already confirmed we are at a clean pre-merge HEAD: if there were no new commits on the parent, the skill would have exited in step 1 before reaching here.
On a re-run (the common case when a checkpoint branch from a prior run is still present), `git branch -f` moves the checkpoint to the actual pre-merge HEAD rather than failing silently with "already exists".

If a checkpoint branch already existed from a prior run, the informational note above records the move — this is non-blocking.
The move is intentional: the prior checkpoint may have pointed at a stale HEAD.

Record the checkpoint branch name.
On any failure after this point, roll back via `git reset --hard "$CHK"` and **preserve** the checkpoint branch (do not delete on failure — the user may need to investigate).

### 3. Merge parent into current

```bash
git fetch origin "<parent-branch>" 2>/dev/null
if git rev-parse --verify --quiet "refs/remotes/origin/<parent-branch>" >/dev/null 2>&1 \
   && git merge-base --is-ancestor "<parent-branch>" "origin/<parent-branch>"; then
  MERGE_REF="origin/<parent-branch>"
else
  MERGE_REF="<parent-branch>"
fi
git merge "$MERGE_REF"
```

Re-running the resolution here (rather than reusing step 1's value) is required, not optional: each fenced bash block in this skill runs as a separate tool call, so no shell variable survives from step 1.
Re-deriving from `refs/remotes/origin/<parent-branch>` is safe because that ref is durable on disk after step 1's fetch — exactly like the existing `$CHK` checkpoint ref — so it reproduces the identical `MERGE_REF` deterministically.

**On conflicts** — iterate `git diff --name-only --diff-filter=U`:

| File category | Policy |
|---|---|
| Whitespace- / formatting-only differences | Accept current branch version. |
| Package lock files (`package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `poetry.lock`, `Cargo.lock`) | Accept current branch version, then regenerate via the project's install command (`npm install`, `yarn`, `pnpm install`, `poetry lock --no-update`, `cargo build`, etc.). Commit the regenerated file. |
| Build artefacts (dist/, build/, *.min.*) | Accept current branch version. |
| Real code conflicts | Enumerate unresolved files via `git diff --name-only --diff-filter=U`. **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`. If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go-base/SKILL.md`) with `<cli> = millpy-merge-in-subagent.py` and `<args> = --mode conflicts --files <file1> <file2> ...`. On `{"status":"success"}`: read the optional `discarded` field from the JSON envelope. If `discarded` is non-empty, **surface each discarded item to the operator before continuing**, and recommend an operator action based on that entry's own description text: for a drop-shaped entry (anything other than the ambiguous-move description below), recommend a manual diff against the parent branch (`git diff <parent-branch>..HEAD`) to verify nothing load-bearing was lost; for a kept-both/ambiguous-shaped entry — identifiable by its `"kept both sides of a conflict, ambiguous move-vs-duplicate"` description text — nothing was lost, so instead recommend checking the resolved file itself for duplication or self-contradiction between the two kept occurrences. Only after the operator acknowledges (or `discarded` is empty/absent): run `git -c core.editor=true merge --continue` to create the merge commit. `-c core.editor=true` scopes the editor suppression to this one command -- no env-var leak into subsequent operations. An empty or absent `discarded` keeps the existing silent-continue behavior. On `{"status":"stuck"}`: roll back → `git reset --hard "$CHK"` — preserve checkpoint, report to caller. If `subprocess` or `psmux`: use the subprocess/psmux branch — `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --mode conflicts --files <file1> <file2> ...` — same success/stuck handling as agent mode. |

On `{"status":"stuck"}` from the sub-agent → roll back to checkpoint (`git reset --hard "$CHK"`), preserve the checkpoint, report to the caller.

### 3.5. Baseline recompute

Runs unconditionally after step 3 completes successfully (including after any conflict-resolution sub-dispatch in step 3's table), before step 4's verify replay begins:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --recompute-baseline
```

- This call is synchronous and does not go through Agent-mode dispatch.
  Unlike steps 3/4's conflict/verify-fix sub-agent dispatches, `--recompute-baseline` runs the same deterministic computation `millpy-implement.py --stage baseline` uses, with no LLM session involved — it needs no `<cli>`/`<args>` Agent-mode dispatch pattern reference.
- It never blocks or fails the merge: on any internal error it prints a `baseline: "error"` result and returns exit 0 (fail-safe).
  This step never triggers the Rollback section.
- If step 1's no-op check already exited early ("Nothing to merge"), this step never runs at all — the "## No-op guarantee" section's promise ("this skill touches nothing" when there was nothing to merge) continues to hold.

Rationale (`_mill/discussion.md`'s `baseline-aware module-wide verify gate (#590)` Decision, merge-in paragraph): "Whenever `mill-merge-in` pulls new parent commits into the task branch, it must recompute the baseline eagerly at its own clean post-sync boundary — immediately after the sync completes and before control returns to any further batch work — by resetting `module_verify_baseline` to `null` and then immediately invoking `millpy-merge-in-subagent.py`'s own call to the same `millpy-implement.py --stage baseline` computation...
This mirrors the batch-1 pre-flight rule exactly: the parent's dependency manifests just changed as of the merge-in, and recomputing eagerly at that boundary — rather than lazily inside a later batch's finalize, after that batch's implementer may have already touched manifests again — keeps the baseline computation on the correct side of the 'no implementer has touched manifests since this snapshot' invariant established for batch 1."

### 4. Verify

Replay exactly the tests that ran during implementation.
Resolve `hub_root = _paths.resolve_hub_path()` and `status_path = _paths.resolve_task_path(hub_root, "_mill/status.md")` (the same resolution Entry step 2 already uses).
Call `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root, status_path=status_path)` where `plan_dir = _paths.resolve_task_path(hub_root, "_mill/plan/")`.
That yields `(batch_name, verify_cmd, cwd)` triples in DAG order, skipping batches with `verify: null`, batches that have not reached `"approved"` state yet, and batches whose verify target a later-approved batch's `Deletes:`/`Moves:` declares removed.

Immediately after that call, attribute and report every batch this filtering silently dropped, per the "visible, counted skips" Shared Decision (a verify that never ran must never look identical, in the report, to one that ran and passed).
Independently recompute the raw, unfiltered batch-with-verify set: call `_plan_dag.extract_batch_index()` on the overview text and `_plan_dag.topo_order()` on the result, then for each batch in that order read its frontmatter via `_plan_dag._read_batch_frontmatter()` and normalize its `verify:` via `_plan_dag.parse_verify_field()`, collecting the names of every batch whose command is non-`None`.
Diff that raw set against the names actually present in the `iter_batch_verifies(...)` return value above -- every name in the raw set but absent from the actual return was dropped.
For each dropped batch, attribute its reason via one cached `_status.read_batches(status_path)` lookup (call it once, reused across every dropped batch, never once per batch): if the batch's own state isn't `"approved"`, increment `skipped_not_approved`;
otherwise (the batch IS approved but still missing) increment `skipped_target_removed`.

`signature: _plan_dag._read_batch_frontmatter(batch_path: Path) -> dict`
`signature: _plan_dag.parse_verify_field(frontmatter: dict, hub_root: Path, git_root: Path) -> tuple[str | None, Path | None]`

Before the loop, load config and read the allowlist: call `cfg = _config.load_config(_paths.resolve_hub_path(), git_root)`, then read `skip_list = (cfg.get("verify") or {}).get("skip_known_broken") or []`. `skip_list` is the empty list when the key is absent (the default for all existing hubs).
Initialise counters `ran = 0`, `skipped = 0`, `skipped_not_approved = 0`, and `skipped_target_removed = 0` -- the last two are seeded once, up front, from the diff-and-reclassify attribution above;
the first two are incremented by the loop below.

For each `(name, cmd, cwd)`:
- Plugin-root substitution: compute `local_plugin_root = str(git_root / "plugins" / "mill")`;
  if `(git_root / "plugins" / "mill").is_dir()`, rewrite `cmd = cmd.replace("${PLUGIN_ROOT}", local_plugin_root)`.
  If `plugins/mill` does not exist in the current git root (non-millhouse repos), this is a no-op.
- Allowlist pre-check: iterate `skip_list`;
  on the first entry `p` where `p in cmd` is true, print `[verify] skipped {p} (allowlisted as known-broken)` to stdout (where `{p}` is the literal matched entry), increment `skipped`, and `continue` to the next `(name, cmd, cwd)` triple without running the command and without invoking the verify-fix sub-agent.
  If no entry in `skip_list` matches, fall through to the next bullet.
- Resolve the run cwd: `hub_root` when `cwd == hub_root`, `git_root` when `cwd == git_root`, and `git_root` when `cwd is None` (the string-form default — matching `_implementer_common._run_verify_gate`'s actual live-dispatch behavior: mill-go's own batch verify calls always pass `git_root=git_root` to `_run_verify_gate`, which resolves a plain-string `verify:` command's cwd to `git_root` whenever `git_root` is not `None`, per that function's own docstring — "When None, falls back to project_root" — so `git_root` is what a plain-string `verify:` command was actually exercised against during implementation, and this replay step must match that, not `hub_root`).
  Run the command from that resolved cwd.
  On success: increment `ran` and continue to the next triple.
- On failure → **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`.
  If `agent` (Claude provider only): follow the Agent-mode dispatch pattern (see "## Agent-mode dispatch" in `plugins/mill/skills/mill-go-base/SKILL.md`) with `<cli> = millpy-merge-in-subagent.py` and `<args> = --mode verify-fix --cmd "<cmd>" --checkpoint "$CHK"`.
  Special handling: when the prepare stage reports `dispatch_needed: false` in its JSON output (verify already passed), skip the Agent tool invocation and finalize call, and use the embedded success envelope directly.
  On `{"status":"success"}`: increment `ran`, continue to next batch verify.
  On `{"status":"stuck"}`: roll back → `git reset --hard "$CHK"` — preserve checkpoint, escalate to the caller.
  If `subprocess` or `psmux`: use the subprocess/psmux branch — `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --mode verify-fix --cmd "<cmd>" --checkpoint "$CHK"` — same success/stuck handling as agent mode.

If `iter_batch_verifies` returns `[]` (no plan,
or every batch had null verify) → skip verify entirely.
This covers tasks that were entirely docs or config.

### 5. Codeguide update

If `_codeguide/Overview.md` exists anywhere in the repo, invoke the `codeguide-update` skill scoped to the checkpoint diff:

- Resolve `hub_root = _paths.resolve_hub_path()`.
- Run `cd <hub_root>` via the Bash tool.
- Use the Skill tool with name `codeguide:codeguide-update` (namespace matches `plugins/codeguide/settings.json`).
- Pass argument `"$CHK..HEAD"` so the update sees everything the merge introduced, including your conflict resolutions.
- Immediately after the Skill tool call returns, run `cd <worktree>` via the Bash tool to restore cwd for the remaining steps in this file (Step 5.5, Step 6).

**Why the explicit `cd`:** `codeguide/scripts/resolve.py`'s inline walk only searches from cwd *upward* to the git toplevel — it has no mechanism to find a `_codeguide/` directory that lives in a descendant directory below cwd (i.e. the hub, nested under `git_root`). `codeguide-update/SKILL.md`'s own Step 1 (`resolve.py --json`) and Step 2 (`resolve_scope.py $ARGUMENTS`) take no cwd/root argument at all — the CLI has no `--cwd` flag — so the ambient shell cwd at invocation time is the only lever available. Pinning it to `hub_root` here matches the confirmed repro (running from the hub root resolves correctly; running from git_root in a nested layout does not) without changing `resolve.py`'s shared upward-only walk algorithm, which other flat-layout call sites depend on. This `cd` is intra-worktree (`hub_root` is a subdirectory of the current worktree, not a different worktree), so it does not conflict with the cross-worktree `cd`-to-parent prohibition.

If `_codeguide/Overview.md` is absent → skip silently.
This is the documented convention in `plugins/mill/skills/git-commit/SKILL.md` step 2 and we follow it here for symmetry.

### 5.5. Commit dispatch briefs

If any dispatch briefs exist and have changes (both the `merge/conflicts` brief written in step 3 and the `merge/verify-fix` brief written in step 4 after the `git merge --continue`), stage and commit them.
Use a guarded `git status --porcelain` check to avoid an empty commit:

```bash
if [ -d <worktree>/_mill/briefs ] && [ -n "$(git -C <worktree> status --porcelain -- _mill/briefs)" ]; then
  git -C <worktree> add _mill/briefs/ && git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"
fi
```

This step runs on the success path only: any failure in steps 2-5 triggers the Rollback (`git reset --hard "$CHK"`) before reaching this point, so the brief commit is intentionally outside rollback scope and captures successful state.
Clean merges (no conflicts, no verify failures) skip steps 3 and 4 entirely, so this step gracefully handles the case where no briefs were written (the `git status --porcelain` guard returns empty).

### 6. Report

```
Merged <parent-branch> into <current-branch>. <N> commits integrated.
Verify: <ran> batch tests ran.
Checkpoint: <CHK> (delete manually once you are confident the merge is stable).
```

Build the `Verify:` line by starting with `Verify: <ran> batch tests ran` and appending one clause per nonzero skip counter, in this fixed order -- allowlisted, not-approved, target-removed -- each included only when its own count is nonzero: `, <skipped> skipped (allowlisted as known-broken)` when `skipped >= 1`;
`, <skipped_not_approved> skipped (batch not approved)` when `skipped_not_approved >= 1`;
`, <skipped_target_removed> skipped (target removed by later batch)` when `skipped_target_removed >= 1`.
Terminate with a single trailing period regardless of how many clauses were appended.
When all three counters are zero the line is exactly `Verify: <ran> batch tests ran.`;
when only `skipped` is nonzero the line is exactly `Verify: <ran> batch tests ran, <skipped> skipped (allowlisted as known-broken).` -- preserving today's exact wording for that one case.

Leave the checkpoint branch in place on success.
The user decides when to delete it — typically after mill-merge's squash lands on parent without follow-up fixes.

## Rollback

If any step between 2 and 5 fails:

```bash
git reset --hard "$CHK"
```

Do **not** delete the checkpoint.
Surface the failure to the caller.
If called from `mill-merge`, the caller releases its merge lock and aborts;
if standalone, the user investigates.

## No-op guarantee

When step 1 returns empty, this skill touches no task state: no checkpoint, no verify, no codeguide-update, no output side effects.
Step 1 always performs a network fetch (`git fetch origin <parent-branch>`) even when the result is a no-op;
this is a deliberate cost of correctly detecting a stale local ref and is the only exception to the "touches no task state" guarantee. `mill-merge` depends on this — it calls `mill-merge-in` first every time, expecting a cheap exit when there is nothing to sync.
