# Batch: mill-merge-in-parent-and-baseline

```yaml
task: "mill-merge-in/mill-finalize/codeguide-update: cleanup-ordering and path-resolution bugs"
batch: "mill-merge-in-parent-and-baseline"
number: 1
cards: 4
verify: null
depends-on: []
```

## Batch Scope

Fixes three bugs that all live in the `mill-merge` -> `mill-merge-in` call chain: #977 (mill-merge invokes mill-merge-in bare, crashing on closed-PR re-entry once status.md is already gone), #946 (mill-merge-in's inline-mode codeguide docs get staged but never committed), and #945 (mill-merge-in's `--recompute-baseline` step has no timeout-ceiling protection). All three are grouped into one batch because #977's fix, #946's fix, and #945's fix each touch a distinct, non-overlapping section of `plugins/mill/skills/mill-merge-in/SKILL.md` (Entry, Step 5.5, Step 3.5 respectively) plus one small edit to `plugins/mill/skills/mill-merge/SKILL.md` for #977's caller side — grouping avoids a DAG file-overlap conflict without an artificial dependency edge to batch 2 or 3. This batch's external interface: `mill-merge-in`'s Entry now accepts and honors a positional `<branch>` argument by skipping its own `status.md` read when one is supplied — batch 2 and batch 3 do not depend on this and are unaffected. `verify: null` per the overview's "SKILL.md procedure edits carry `verify: null`" Shared Decision — these are pure orchestration-doc changes.

## Cards

### Card 1: mill-merge Step 2 — pass parent_branch explicitly to mill-merge-in

- **Context:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `### 2. Invoke mill-merge-in` (currently: "Call the `mill-merge-in` skill (no arguments — it picks up the parent from status.md the same way). If it reports failure → release the merge lock and halt. Capture the checkpoint branch name it prints; you may need it on rollback."), change the invocation so it passes the `parent_branch` value already resolved and bound at Entry Step 4 (including that step's `status_path`-absent fallback and its liveness-check rebind) as `mill-merge-in`'s optional positional `<branch>` argument (documented in `mill-merge-in/SKILL.md` Entry step 3 as "for ad-hoc syncing from some other branch than the task's declared parent"). This is Step 2 itself, not route-specific — apply the change once so both the `done` fresh-merge route and the `closed` PR-state-gate route (the only two routes that reach Step 2 via `## Entry`'s "In-place mode bypass" / PR-state-gate routing) pass the argument. State explicitly in the rewritten step text that `<parent_branch>` is passed as the positional override, not a bare invocation, and note (one sentence) that this is what lets `mill-merge-in` skip its own independent `status.md` read — see Card 2 in this same batch for the corresponding `mill-merge-in`-side change this depends on. Leave the "release the merge lock and halt" and "Capture the checkpoint branch name" sentences unchanged.
- **Commit:** `docs(mill-merge): pass resolved parent_branch explicitly to mill-merge-in (#977)`

### Card 2: mill-merge-in Entry — skip status.md resolve() when a positional branch override is supplied

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Reorder `## Entry` steps 2 and 3. Today `status_path` is computed inline only as part of step 2's `resolve(...)` call ("call `_parent_branch.resolve(status_path, interactive=..., expected_slug=slug)` where `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`"), and step 3 separately documents an optional positional `<branch>` argument with no stated interaction between the two. First, hoist the `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")` assignment so it runs unconditionally at the top of Entry, before the branch check below — the existing "Liveness check (#817)" paragraph's dead-parent rebind (`_status.update_field(status_path, "parent", resolved_branch)`) needs `status_path` bound regardless of which of the two paths below is taken, and today it is described as "already bound at the top of this Entry step," which is only true once this hoist is made explicit. Then rewrite so Entry checks whether the caller supplied the positional `<branch>` argument: if supplied, bind `parent_branch` to that value directly and skip the `resolve(...)` call entirely — this is the change that actually closes #977, since `_parent_branch.resolve` (function `resolve` in `_parent_branch.py`, lines 190-230) takes no branch-override parameter and raises `ParentBranchError` unconditionally whenever `status_path` is absent and `interactive=False`, so leaving the `resolve(...)` call unconditional would mean #977's crash still reproduces even after Card 1 passes the branch explicitly. When the positional argument is NOT supplied, fall through to the existing `resolve(status_path, ...)` call exactly as today (interactive/non-interactive/`expected_slug` behavior all unchanged), now reading the hoisted `status_path` instead of computing it inline. In both branches, the existing "Liveness check (#817)" paragraph immediately after (which calls `_parent_branch.check_liveness(parent_branch, git_root)`) still runs against whichever `parent_branch` value was bound — its own logic is unaffected by which of the two paths produced the value, so only its position relative to the reordered steps needs updating, not its content.
- **Commit:** `fix(mill-merge-in): skip status.md resolve() when caller supplies an explicit parent branch (#977)`

### Card 3: mill-merge-in Step 5.5 — commit codeguide docs alongside briefs

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `### 5.5. Commit dispatch briefs` (current guard: `if [ -d <worktree>/_mill/briefs ] && [ -n "$(git -C <worktree> status --porcelain -- _mill/briefs)" ]; then git -C <worktree> add _mill/briefs/ && git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"; fi`), rewrite so `[ -d _mill/briefs ]` no longer gates the whole block. New shape: (1) if `_mill/briefs` exists, run `git -C <worktree> add _mill/briefs/`; (2) independent of whether step 1 ran, if `git -C <worktree> status --porcelain` (unrestricted — no `-- _mill/briefs` pathspec) is non-empty, run `git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"`. Add one sentence noting this now also picks up Step 5's inline-mode codeguide docs — already `git add`-staged by `codeguide_commit.py --mode inline` back in Step 5, before this step runs — which the prior `_mill/briefs`-scoped guard silently dropped whenever `_mill/briefs/` did not exist (#946). Add a second sentence explaining why the unrestricted porcelain check is safe here rather than a risk of sweeping in unrelated dirty state: by this point in the skill, every earlier step that could leave the tree dirty (Step 2's checkpoint, Step 3's merge, Step 3.5's baseline recompute, Step 4's verify-fix, Step 5's codeguide-update) has already committed or rolled back its own changes per this file's own `## Rollback` section, so the only things that can legitimately still be unstaged/staged at Step 5.5 are dispatch briefs and/or codeguide docs — there is no other step between Step 1 and Step 5.5 that leaves working-tree state uncommitted on the success path. Update the two explanatory sentences immediately following the code block ("This step runs on the success path only..." and "Clean merges (no conflicts, no verify failures) skip steps 3 and 4 entirely, so this step gracefully handles the case where no briefs were written") so they also cover the new "no codeguide docs were staged either" no-op case.
- **Commit:** `fix(mill-merge-in): commit staged codeguide docs alongside dispatch briefs (#946)`

### Card 4: mill-merge-in Step 3.5 — background-dispatch the baseline recompute

- **Context:**
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Replace `### 3.5. Baseline recompute`'s synchronous foreground call (`PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --recompute-baseline`) with the same `millpy-bg.py --slug <name> -- ...` background-dispatch-and-poll pattern `mill-go-base/SKILL.md`'s `### 0.5. Baseline pre-flight` section uses for its invocation shape, and its `### 0.6. Per-batch baseline recapture` section's `"dead"`-handling wording for failure tolerance: background the same `millpy-merge-in-subagent.py --recompute-baseline` command via `millpy-bg.py --slug merge-in-baseline-recompute -- ...`; poll `cat <log-path>` until `[mill-bg] EXIT`, running the same `_bg.check_bg_status` liveness-check loop 0.5 uses (branch `"running"` -> keep polling, `"exit"` -> proceed, `"dead"` -> log the reason (ASCII-only) and continue — never halt, matching this step's own already-documented "It never blocks or fails the merge" contract, which the conversion must preserve verbatim); once `[mill-bg] EXIT` appears, extract the result via `grep '^{' <log-path>` exactly as 0.5 does. Keep the existing "It never blocks or fails the merge: on any internal error it prints a `baseline: \"error\"` result and returns exit 0 (fail-safe)" and "If step 1's no-op check already exited early..." explanatory sentences as-is; the `Rationale` paragraph quoting `_mill/discussion.md`'s baseline-aware Decision is unaffected and stays unchanged. Add the same "**Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree..." cwd-guard callout, matching the wording the callout carries at `mill-go-base/SKILL.md`'s 0.5/0.6 sections (this is the first `millpy-bg` call site in `mill-merge-in/SKILL.md` or `mill-merge/SKILL.md` — neither file has any other `millpy-bg` invocation today, so the callout's wording should reference `mill-go-base/SKILL.md`'s 0.5/0.6 as its precedent, not other sites "in this file family"), immediately before the background-dispatch command.
- **Commit:** `fix(mill-merge-in): background-dispatch --recompute-baseline to remove the timeout ceiling (#945)`

## Batch Tests

`verify: null`. All four cards are pure `SKILL.md` orchestration-procedure edits — no executable Python surface changes and no automated test to run. Verification is re-reading each rendered section after editing for internal consistency (cross-references between Card 1/Card 2's coupled change, the updated explanatory prose in Card 3, and the preserved rationale text in Card 4), matching the discussion.md Testing section's stated approach for these four bugs and mill-plan's own self-review convention for doc/procedure changes.
