# Batch: mill-merge-skill-fixes

```yaml
task: 'mill-merge/merge-in: squash non-ff rejection, stale-worktree logic, parent-branch detection, conflict resolution'
batch: mill-merge-skill-fixes
number: 2
cards: 4
verify: null
depends-on: [1]
```

## Rename mechanic

Not applicable — this batch has no `Moves:` entries.

## Batch Scope

Applies all four `mill-merge/SKILL.md` prose/logic fixes that live in this one file: #824's pre-squash parent fast-forward (Card 3), #824's rollback-target fix plus the matching rollback-exemption extension (Card 4), #819's narrowed stale-worktree entry gate (Card 5), and #817's liveness-check wiring at the Entry Step 4 parent-resolution call site (Card 6, depends on batch 1's `_parent_branch.check_liveness` / `resolve_dead_parent`). All four land in one batch because they all edit the same file and a Sonnet implementer needs the whole file in context regardless of which fix it is applying — splitting by issue number would mean four batches all listing the same `Context:`/`Edits:` target. `verify: null` — this batch is SKILL.md prose with no directly runnable surface; #824's and #817's actual git-sequence behavior is exercised by batch 4's integration tests (which test the prescribed git sequence directly, not the prose), and #819 is verified by review per `_mill/discussion.md`'s `testing-approach` Decision ("no automated test; verified by re-reading the narrowed entry gate").

## Cards

### Card 3: #824 — pre-squash parent fast-forward

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In `### 5. Direct squash`, immediately after the existing "Pre-squash dirty-parent-worktree check" block's halt-message paragraph and its "Rollback exemption" note (the paragraph beginning "**Rollback exemption:** this halt is exempt from `## Rollback (Steps 1-5 only)` below") and before the `git -C <parent-path> merge --squash "$CHILD_BRANCH"` bash block, insert a new subsection:

    ```markdown
    **Pre-squash parent fast-forward (`mode == 'worktree'` only):** immediately after the dirty-parent-worktree check above confirms the parent worktree is clean, fast-forward the parent worktree's local branch to `origin/<parent_branch>`:

    ```bash
    git -C <parent-path> fetch origin "<parent_branch>"
    git -C <parent-path> merge --ff-only "origin/<parent_branch>"
    ```

    This step also applies only when `mode == 'worktree'` — skip it entirely in in-place mode, same gate as the dirty-parent-worktree check immediately above it.

    **Why:** `mill-merge-in` only advances the *child* branch to `origin/<parent_branch>`; it never touches the parent worktree's own local ref. Whenever `origin/<parent_branch>` has moved since the parent worktree last synced (a race, not specifically "non-linear history" — a plain fast-forward advance on origin triggers it just as easily as a merge commit), Step 5's squash-then-push below would otherwise run against a stale parent ref and get rejected as a non-fast-forward push.

    `merge --ff-only` fails only when the parent worktree's local branch and `origin/<parent_branch>` have genuinely diverged — the parent has local commits not present on `origin/<parent_branch>` AND `origin/<parent_branch>` has independently advanced past the parent's own last-synced point (neither ref is a fast-forward of the other). A parent with local-only commits whose `origin/<parent_branch>` has NOT independently moved is not a failure case — `--ff-only` reports "Already up to date" and exits 0 in that case, since a fast-forward trivially exists. If `merge --ff-only` fails (a genuine two-sided divergence — an out-of-band state this task does not otherwise expect), halt Step 5 — do NOT run `merge --squash` below — and report to the operator:

    > "The parent worktree's local branch has diverged from `origin/<parent_branch>` — it has local commits not present on the remote. Reconcile manually (commit/push, or investigate the divergence), then re-run `/mill-merge`."

    **Rollback exemption:** this halt is exempt from `## Rollback (Steps 1-5 only)` below, for the same reason as the dirty-parent-worktree halt immediately above it — nothing has been mutated at this halt point. See that section's "Dirty-parent-worktree halt (Step 5)" paragraph — at this card's own commit that is still its title verbatim; Card 4 of this batch (which must land in the same session, before this plan's implementation is considered complete) renames it to "Dirty-parent-worktree halt and parent-fast-forward-failure halt (Step 5)" and extends it to cover this new halt too.

    `reset --hard origin/<parent_branch>` is deliberately never used as the fast-forward mechanism here — it would silently discard any local-only commits on the parent worktree's branch, exactly the class of silent parent-state destruction the sibling rollback-target fix (Card 4) treats as a bug. `merge --ff-only` fails loudly instead.
    ```
  - The inserted subsection must sit strictly between the existing dirty-parent-worktree check's content and the `git -C <parent-path> merge --squash "$CHILD_BRANCH"` bash block — the squash bash block itself is unchanged by this card.
- **Commit:** `fix(mill): fast-forward parent worktree to origin before squash (#824)`

### Card 4: #824 — rollback target fix + exemption extension

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Replace the `## Rollback (Steps 1–5 only)` section's opening paragraph and bash block — currently "Any failure between lock acquisition (Step 1) and the squash landing on parent (Step 5) rolls back via the checkpoint `mill-merge-in` created:" followed by `` ```bash\ngit -C <parent-path> reset --hard mill-checkpoint-<name>\n``` `` — with:
    ```markdown
    Any failure between lock acquisition (Step 1) and the squash landing on parent (Step 5) rolls back the parent worktree to `origin/<parent_branch>`:

    ```bash
    git -C <parent-path> reset --hard origin/<parent_branch>
    ```
    ```
  - Immediately after that bash block and its existing "Release the merge lock. Preserve the checkpoint branch. Report the failure with the step name." paragraph, insert a new explanatory paragraph:
    ```markdown
    **Why `origin/<parent_branch>`, not the checkpoint:** `mill-checkpoint-<name>` is created in the *child* worktree by `mill-merge-in` and points at the child's own pre-merge-in history — resetting the parent worktree to it checks the parent out to unrelated child commits, regardless of which Steps 1-5 failure triggered the rollback. `origin/<parent_branch>` is the correct rollback target for the parent worktree in every case.
    ```
  - Rewrite the existing "**Dirty-parent-worktree halt (Step 5):**" paragraph to cover both halts and use the new reset target. Replace its current text (both sentences) with:
    ```markdown
    **Dirty-parent-worktree halt and parent-fast-forward-failure halt (Step 5):** the pre-squash dirty-parent-worktree check and the pre-squash parent-fast-forward check (both `mode == 'worktree'` only) that halt Step 5 before `merge --squash` runs are exempt from this rollback — no reset applies, and there is no `git reset --hard` at all.
    Nothing has been mutated yet at either halt point: running `git -C <parent-path> reset --hard origin/<parent_branch>` there would destroy exactly the independent uncommitted (or unpushed local-commit) parent-worktree work each halt message tells the operator to reconcile manually.
    ```
  - The `## Rollback (Steps 1–5 only)` section's "**Cleanup-commit rollback (Step 4):**" paragraph (the `git reset --hard HEAD` block) is unchanged by this card.
- **Commit:** `fix(mill): rollback resets parent worktree to origin, not child checkpoint (#824)`

### Card 5: #819 — narrow stale-worktree entry gate

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Replace the entire "Stale-worktree edge: ..." paragraph block in Entry Step 1 (from "Stale-worktree edge: if `active_data` is not None AND the corresponding..." through "...and that the run is stopping rather than guessing.") with:
    ```markdown
    Stale-worktree edge: this disambiguation procedure — including its `status.md` write/commit/push side effects below — fires only when a genuine ambiguity exists.
    Run `git worktree list --porcelain` unconditionally first (cheap, read-only, no side effects) and inspect the entry for `<worktrees-dir>/<slug>/`.
    If that entry is present, current, and its branch matches the active task branch: no ambiguity — the `mode` already set above (from `_inplace.is_inplace()`) is trustworthy as-is.
    Skip the rest of this Stale-worktree edge block and continue to Step 1.5.
    If that entry is absent from the output, or its recorded branch no longer matches the active task branch (a stale registration): genuine ambiguity — treat the directory as in-place cruft, `mode = 'inplace'`, and run the disambiguation procedure below.
    Before appending the timeline row below, derive the path variables inline (Path Setup in Step 1.5 has not run yet at this point): `worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` and `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`.
    Capture `original_phase = _status.read_full(status_path)["yaml"].get("phase")` before mutating anything, then `_status.append_phase(status_path, f"self-resolved-stale-worktree-{mode}", _timestamp.now_utc_iso())`. `append_phase` overwrites the top-level `phase:` field as well as appending the timeline row — since Step 5 immediately below reads that same `phase:` field and expects exactly `done` or `pr-pending`, restore it before continuing: `_status.append_phase(status_path, original_phase, _timestamp.now_utc_iso())`.
    Commit both mutations together: `git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-merge: self-resolved stale-worktree ambiguity ({mode})"` and push before continuing.
    If the entry is present but its state does not cleanly resolve to either "current and matching" or "stale/absent/mismatched" above (an inconclusive `git worktree list --porcelain` read), fall back to the existing safe default and halt: report to the operator that the branch matches the current cwd AND `<worktree_path>` exists, that `git worktree list --porcelain` output was inconclusive, and that the run is stopping rather than guessing.
    ```
  - The defect being fixed: today's gate fires the side-effecting disambiguation procedure on essentially every normal worktree-mode invocation (the old trigger condition — `active_data is not None AND directory exists AND branch matches` — is true on nearly every normal run, not just edge cases). The rewrite moves the actual `git worktree list --porcelain` staleness/absence/branch-mismatch check to be the trigger itself, so the common case (worktree registration is fine) takes the new fast no-op path and performs zero side effects, while genuine staleness/absence/mismatch still runs the full procedure exactly as before.
  - Do not reintroduce any notion of an `_inplace.is_inplace()` result being "suspect" — that trigger does not exist anywhere else in the codebase and is not part of the rewritten gate.
- **Commit:** `fix(mill): narrow stale-worktree entry gate to actual porcelain staleness (#819)`

### Card 6: #817 — liveness check wiring in mill-merge Entry Step 4

- **Context:**
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In Entry Step 4, immediately after the sentence "If `status_path.exists()` is `True`: call `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)` exactly as before." and before the existing "On `_parent_branch.ParentBranchError` ..." paragraph, insert:
    ```markdown
    **Liveness check (#817):** when `_parent_branch.resolve(...)` above returns successfully, verify the returned `parent_branch` is still live:

    ```bash
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
    import json
    import _parent_branch, _paths
    git_root = _paths.resolve_git_root()
    print(json.dumps({'alive': _parent_branch.check_liveness('<parent_branch>', git_root)}))
    "
    ```

    If `alive` is `true`, continue as before — no further action.

    If `alive` is `false`, resolve a successor:

    ```bash
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
    import json
    import _parent_branch, _paths, _config
    git_root = _paths.resolve_git_root()
    cfg = _config.load_config(_paths.resolve_hub_path(), git_root)
    print(json.dumps(_parent_branch.resolve_dead_parent('<parent_branch>', git_root, cfg)))
    "
    ```

    Report the result to the operator and require confirmation before mill-merge proceeds, except in the `cycle` case, which always halts outright with no confirmation prompt (there is no candidate branch to confirm):
    - `outcome: "resolved"` — "Parent branch `<parent_branch>` no longer exists on origin. It appears to have been merged and archived (chain: `<hops, joined by ' -> '>`). The resolved successor parent is `<branch>`. Confirm before mill-merge proceeds against `<branch>`."
    - `outcome: "fallback"` — "Parent branch `<parent_branch>` no longer exists on origin. No archive-tag chain could resolve a successor (`<reason>`). Falling back to the repo's base branch `<branch>`. Confirm before mill-merge proceeds against `<branch>`."
    - `outcome: "cycle"` — halt outright, no confirmation prompt: "Archive-tag chain walk for `<parent_branch>` hit its 10-hop cap without resolving a live parent (chain: `<hops, joined by ' -> '>`). Investigate manually."

    On operator confirmation (the `resolved` and `fallback` cases only), rebind `status.md`'s `parent:` row to the new branch and use it for the remainder of this run. Derive `status_path` the same way the rest of this Entry Step 4 already does (Path Setup 1.5's `worktree_root = _paths.resolve_active_hub(container_path, slug, cfg=cfg, git_root=git_root)` then `status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])`) — never a fresh `_paths.resolve_hub_path()` + literal `'_mill/status.md'` derivation, which walks from cwd instead of the already-resolved `worktree_root` and bypasses the config-driven `cfg['paths']['status_md']` the rest of the file always reads:

    ```bash
    PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
    import _status, _paths, _config
    git_root = _paths.resolve_git_root()
    container_path = _paths.resolve_container_path(git_root)
    cfg = _config.load_config(_paths.resolve_hub_path(), git_root)
    worktree_root = _paths.resolve_active_hub(container_path, '<slug>', cfg=cfg, git_root=git_root)
    status_path = _paths.resolve_task_path(worktree_root, cfg['paths']['status_md'])
    _status.update_field(status_path, 'parent', '<resolved_branch>')
    "
    git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-merge: rebind dead parent branch for {slug}"
    git -C <worktree> push
    ```

    `parent_branch` for the remainder of this run is now `<resolved_branch>`.
    ```
  - This liveness check applies only to the `status_path.exists()` True branch (the actual `_parent_branch.resolve(...)` call) — it does not apply to the `status_path.exists()` False fallback branch above it, which already sets `parent_branch = cfg.git.base_branch` directly and has its own separate operator-facing notice.
- **Commit:** `feat(mill): wire dead-parent-branch liveness check into mill-merge Entry Step 4 (#817)`

## Batch Tests

`verify: null` — pure SKILL.md prose/logic edits with no directly runnable surface in this batch. #824's fast-forward/rollback behavior and #817's liveness-check/chain-walk behavior are covered by batch 4's integration tests (which exercise the exact git sequences and `_parent_branch` calls this batch's prose describes, per `test-merge.py`'s existing convention of testing backing helpers and prescribed git sequences rather than the prose itself). #819's narrowed gate has no automated test per `_mill/discussion.md`'s `testing-approach` Decision — verified by re-reading Card 5's rewritten gate against the single `git worktree list --porcelain` staleness/absence/branch-mismatch condition it is now defined by.
