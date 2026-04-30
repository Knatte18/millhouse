# Discussion: 22 — par-A — mill-merge: auto-switch to PR path on branch-protection rejection

```yaml
task: 22 — par-A — mill-merge: auto-switch to PR path on branch-protection rejection
slug: mill-merge-pr-fallback
status: discussing
parent: main
```

## Problem

When `git.require-pr-to-base` is absent or false, mill-merge takes the direct path: squash-merge on the parent branch locally, then `git push`. If the remote enforces PRs via branch protection, the push fails with a rejection message. mill-merge currently halts fatally at that point, leaving the parent branch with an uncommitted squash (or a local commit that never reached origin). The user must manually soft-reset the parent, push the child branch, create a PR, update `status.md`, and release the merge lock.

The fix is a fallback: detect the branch-protection rejection in the push stderr, undo the local squash commit, and continue exactly via the PR path that mill-merge already implements. No new concepts; only a routing decision on failure.

A parallel documentation gap: the `wiki-config.yaml` template (which mill-setup seeds into new wikis) has no `git:` block, so there is no visible knob for operators to flip to opt into the PR path proactively. The template and the live millhouse wiki/config.yaml both need a commented-out `git:` section added.

## Scope

**In:**
- `plugins/mill/skills/mill-merge/SKILL.md` — add branch-protection fallback block inside the Step 5 direct path.
- `plugins/mill/templates/wiki-config.yaml` — add commented-out `git:` block.
- `c:/Code/millhouse/wiki/config.yaml` (live wiki) — add commented-out `git:` block.

**Out:**
- No new Python scripts; no new helpers; no changes to `_paths.py`, `_status.py`, or any other helper.
- No changes to `millpy-*.py` CLI scripts.
- No changes to the PR-path re-entry flow (already correct).
- No changes to how `git.require-pr-to-base: true` is handled (the planned PR path continues to work as before).
- No changes to mill-setup or mill-spawn.
- No unit tests — there is no Python code being added; the change is prose in a SKILL.md.

## Decisions

### reset-mechanism

- Decision: use `git -C <parent-path> reset --hard origin/<parent_branch>` to undo the local squash commit on the parent.
- Rationale: the squash commit never reached origin, so `origin/<parent_branch>` is the exact pre-squash state. `--hard` discards both the commit and any staged diff on the parent; the content is safe on the child branch and is going to become a PR anyway.
- Rejected: `--soft` — leaves the squash diff staged on the parent, which serves no purpose and could confuse a subsequent git operation in that worktree.

### detection-strings

- Decision: match any of four substrings in the stderr/stdout of the failed `git push`: `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`.
- Rationale: GitHub's push rejection for branch protection emits one or more of these strings. `GH006` is the machine-readable API-level prefix that appears consistently even when the human-readable message text varies across GitHub Enterprise versions. `protected branch` appears specifically as `protected branch hook declined` in the non-force push rejection; false-positive risk from force-push rejections is zero here because mill-merge's direct path never uses `--force`.
- Rejected: matching only the three human-readable strings — misses GHE environments where the prose differs.

### fallback-scope

- Decision: the fallback fires for any parent branch whose push is rejected with branch-protection language, not just when `parent == base-branch`.
- Rationale: GitHub allows branch protection on any branch, not only the default branch. Limiting to base-branch would silently fail for protected topic branches.
- Rejected: base-branch-only scope — too narrow given GitHub's capabilities.

### pr-body-content

- Decision: the auto-created PR body is: the task summary from `status.md` (same as the planned PR path), prefixed with a one-liner: "Auto-created: direct push was rejected by branch protection."
- Rationale: the reviewer has context that the PR was not author-initiated. Without the note, the PR looks identical to a manual PR.
- Rejected: task summary only — loses the auto-creation signal.

### user-output-after-fallback

- Decision: after the fallback PR is created and `pr-pending` is appended, print both the PR URL and the suggestion: "Direct push rejected by branch protection — switched to PR path. PR: <url>. Consider setting `git.require-pr-to-base: true` in wiki/config.yaml."
- Rationale: the user needs the PR URL to monitor or merge it. Without it, they must run `gh pr list` manually.
- Rejected: suggestion-only output — forces unnecessary follow-up command.

### git-config-block-fields

- Decision: both `require-pr-to-base` and `base-branch` are added as commented-out fields in the `git:` block.
- Rationale: `base-branch` is optional (mill-merge defaults to `main`), but making it visible reduces the time-to-understand for operators setting up a non-default base branch.
- Rejected: `require-pr-to-base` only — hides a commonly needed setting.

## Technical context

### mill-merge SKILL.md — Step 5 direct path (lines ~98–106)

The direct path currently does three git operations in sequence:
```
git -C <parent-path> merge --squash "$CHILD_BRANCH"
git -C <parent-path> commit -m "<task: field from status.md>"
git -C <parent-path> push
```
The fallback intercepts push failure. Capture stderr from `git push`. If exit code is non-zero and stderr contains any detection string → rollback then re-route. If exit code is non-zero but stderr contains none of the strings → existing error handling applies (fail the step, trigger rollback in Step 1–5 rollback block).

The rollback command:
```
git -C <parent-path> reset --hard origin/<parent_branch>
```
This must run before any attempt to push the child branch.

After rollback, the PR-path logic from Step 5 runs with one argument difference and one body addition:
- `--base` must be `<parent-branch>` (not `<base-branch>`). In the existing PR path, `parent == base-branch` is a prerequisite so the two values are identical; in the fallback they can differ (e.g., parent is `develop`, base is `main`).
- PR body is `"Auto-created: direct push was rejected by branch protection.\n\n<task_description>"` instead of just the task summary.

The skip target is Step 11 (Release lock) — same as the existing PR path.

### PR-path idempotency note

If the user re-runs `/mill-merge` after a partial fallback (e.g., PR was created but `pr-pending` was not appended before a crash), the entry-phase gate will see `phase: done` again and re-execute the direct path. The push will fail again with the same detection strings, the rollback will run (idempotent if already reset), and `gh pr create` will fail because a PR already exists for the branch. This edge case requires `gh pr create` to handle "already exists" gracefully: check `gh pr list --head "$CHILD_BRANCH"` first; if a PR exists, skip creation and continue with `_status.append_phase`.

### wiki-config.yaml template — location of `git:` block

Add the `git:` block between `spawn:` and `paths:` (logical grouping: repo-level git settings belong near spawn configuration). The block is fully commented out.

```yaml
# ---------------------------------------------------------------------------
# Git integration
# ---------------------------------------------------------------------------
# Uncomment if your remote enforces PRs to the base branch (branch protection).
# git:
#   require-pr-to-base: true   # create a PR instead of pushing directly
#   base-branch: main          # branch to target; defaults to main if absent
```

### live wiki/config.yaml — c:/Code/millhouse/wiki/config.yaml

Same `git:` block added in the same position (between `spawn:` and `paths:`). The live config does not have the `git:` key at all today.

## Testing

No new Python code → no unit tests. The change is to the SKILL.md (prose instructions). Verify correctness via inspection:

- **Skill prose review:** confirm the fallback block in Step 5 is unambiguous: correct command order (reset before PR creation), detection string list complete, skip target correct (Step 11).
- **Idempotency check:** confirm the "PR already exists" edge case is handled — `gh pr list` check before `gh pr create`.
- **Template diff:** confirm the `git:` block is present and correctly commented in both `wiki-config.yaml` template and `wiki/config.yaml`.
- **No regression on planned PR path:** confirm the existing `require-pr-to-base: true` branch is not affected by the new fallback block (fallback is inside the `else` branch of the existing `require-pr-to-base` check).

## Q&A log

- **Q:** `--hard` or `--soft` reset on parent? **A:** `--hard`; content is on child branch, no use for staged diff.
- **Q:** Which branch-protection strings to detect? **A:** `Changes must be made through a pull request`, `repository rule violations`, `protected branch`, `GH006`.
- **Q:** Fallback scope: any branch or base-branch only? **A:** Any parent branch; branch protection can apply to any branch.
- **Q:** PR body for auto-created PR? **A:** Prepend "Auto-created: direct push was rejected by branch protection." before the task summary.
- **Q:** What to print after fallback? **A:** PR URL + suggestion to set `git.require-pr-to-base: true`.
- **Q:** Template `git:` block fields? **A:** Both `require-pr-to-base` and `base-branch`, both commented out.
- **Q:** Live wiki/config.yaml? **A:** Also patched with the `git:` block (this is the dogfood repo).
- **Q:** `--base` arg in fallback PR creation — `<base-branch>` or `<parent-branch>`? **A:** `<parent-branch>`; the existing PR path can use `<base-branch>` because it gates on `parent == base-branch`, but the fallback fires for any protected branch, so `--base` must follow `<parent-branch>` exactly.
- **Q:** `protected branch` false-positive risk (appears in force-push rejections too)? **A:** Accepted; mill-merge's direct path never uses `--force`, so that error cannot occur in this code path.
