# Discussion: 40 (B) — mill-finalize: lift PR decision out of mill-merge

```yaml
task: 40 (B) — mill-finalize: lift PR decision out of mill-merge
slug: mill-finalize
status: discussing
parent: main
```

## Problem

`mill-merge` currently conflates two concerns: merge mechanics (squash, teardown) and end-of-task orchestration (decide PR vs direct, create PR, halt for review, re-enter after review lands). The skill name promises a merge; it also does PR creation, `pr-pending` state management, and a re-entry path that only fires after an external GitHub action. This leaks orchestration concerns into a skill that should be a pure implementation step.

The consequence is that `mill-go`'s Handoff Step 5 must know about the PR mode — it passes through a `pr-pending` halt that belongs to an orchestration layer above it. Introducing `mill-finalize` moves the decision to the right layer: mill-go calls a finalization orchestrator; finalization decides the path; mill-merge becomes a pure squash-and-teardown primitive.

Folded-in: GitHub issue #268 — in PR mode, `task/` currently appears in the PR diff because the cleanup commit runs after `gh pr create`. The fix is to run cleanup before PR creation, which requires the updated ordering this task introduces.

## Scope

**In:**
- New `plugins/mill/skills/mill-finalize/SKILL.md` — orchestrator-callable end-of-task skill; decides PR vs direct; PR path: checks + mill-merge-in + status update + cleanup commit + push + /git-pr + Home.md pr-pending + halt; direct path: delegate to /mill-merge.
- Refactor `plugins/mill/skills/mill-merge/SKILL.md` — remove Step 5's PR-creation branch; keep direct path + branch-protection fallback intact; update phase-gate and re-entry detection to handle absent `task/status.md` (post-cleanup re-entry via Home.md).
- Update `plugins/mill/skills/mill-go/SKILL.md` Handoff Step 5 — replace `/mill-merge` with `/mill-finalize`.
- Update `SKILLS.md` — add mill-finalize row, update mill-merge description.
- Config-key rename: `git.require-pr-to-base` → `git.require_pr_to_base`, `git.base-branch` → `git.base_branch` across all files that reference these keys (see Technical context).
- Update `plugins/mill/templates/wiki-config.yaml` to document new snake_case keys.
- Unit tests: `plugins/mill/unit_tests/test-mill-finalize-dispatch.py` (PR-vs-direct dispatch logic); update `plugins/mill/unit_tests/test-mill-merge-inplace.py` to remove PR-path assertions that move to mill-finalize.

**Out:**
- No change to `mill-merge-in` internals (mill-finalize calls it the same way mill-merge does).
- No change to `/git-pr` internals (step 1.5 guard naturally doesn't fire — task/ is absent by the time /git-pr runs).
- No change to `pipeline.auto_merge` semantics (still means "auto-invoke finalization from mill-go").
- No mid-flight PR-mode override mechanism.
- No post-PR-conflict automation (future task).
- No rename of the `mill-merge` skill itself.
- No migration script for existing `wiki/config.yaml` files — operators update manually on first run.
- No changes to integration tests (mill-finalize is SKILL.md only; integration coverage is manual).
- No changes to `specs/roadmap/README.md`.

## Decisions

### mill-finalize is SKILL.md only, no Python CLI

- Decision: mill-finalize is implemented as a `SKILL.md` only. No `millpy-finalize.py` script.
- Rationale: The dispatch logic is two branches (PR or direct) driven by config + branch comparison. This is agent-driven orchestration, identical in pattern to mill-merge. A Python CLI would add no capability.
- Rejected: `millpy-finalize.py` — over-engineering; nothing in the flow requires a subprocess boundary.

### PR-mode step ordering: status update → cleanup commit → push → /git-pr

- Decision: In PR-mode, the steps are: (1) checks, (2) mill-merge-in, (3) update `task/status.md` to `pr-pending` + commit, (4) cleanup commit (`git rm -r task/`), (5) push, (6) /git-pr, (7) flip Home.md to `[pr-pending]`, (8) halt.
- Rationale: Satisfies issue #268 (task/ absent from PR diff). Git history preserves the pr-pending status record in the commit before cleanup. git-pr's step-1.5 guard checks for `task/status.md` — since cleanup already removed it, the guard doesn't fire; no changes to git-pr needed.
- Rejected: Skip cleanup in PR-mode — violates #268. Run cleanup before status update — loses the status audit trail in git history.

### Re-entry detection in refactored mill-merge

- Decision: Mill-merge phase gate first tries to read `task/status.md`. If the file is absent (cleanup commit already ran in PR-mode), it falls back to reading Home.md for the `[pr-pending]` marker for the slug. Both paths route to the same re-entry teardown (archive tag + Home.md [done] + notify).
- Rationale: Preserves existing behaviour when `task/status.md` exists (fresh runs, legacy worktrees). Handles the post-cleanup case cleanly. No second source of truth — Home.md is authoritative for cross-machine coordination already.
- Rejected: Require `task/status.md` — breaks re-entry after cleanup; Detect re-entry solely from Home.md — changes detection path even for existing status.md cases without benefit.

### config-key rename: breaking, no alias shim

- Decision: `git.require-pr-to-base` → `git.require_pr_to_base`, `git.base-branch` → `git.base_branch`. Code reads new keys only. Operators update their `wiki/config.yaml` manually. Template ships new keys. No backwards-compat shim.
- Rationale: 10+ keys in the config already use snake_case; most of the `git:` block used kebab-case. Consistent snake_case allows cleaner Python dict access. A shim prolongs the transition without benefit. Note: `git.parent-branch` is also kebab-case but is intentionally excluded (different purpose, lower usage, deferred scope — see Technical context).
- Rejected: Read both spellings with deprecation warning — the warning would be invisible in most runs; shims accumulate.

### Branch-protection fallback in mill-merge direct path: keep

- Decision: The direct-path branch-protection fallback in mill-merge Step 5 (which creates a PR when `git push` is rejected with a branch-protection error) is kept unchanged.
- Rationale: If an operator misconfigures `require_pr_to_base: false` but the remote enforces branch protection, the fallback prevents a dead-end. The fallback lives entirely within the direct path and does not duplicate mill-finalize's PR dispatch logic.
- Rejected: Remove — too harsh; imposes a hard dependency on correct config with no safety net.

### mill-go Handoff Step 5: replace /mill-merge with /mill-finalize

- Decision: `pipeline.auto_merge: true` invokes `/mill-finalize`. Mill-go's Handoff Step 5 is updated to say "invoke `/mill-finalize`". Mill-go has no awareness of PR vs direct.
- Rationale: Single source of truth for dispatch. Mill-go stays lean — it orchestrates, it doesn't decide the merge path.
- Rejected: Add conditional in mill-go — duplicates dispatch logic in two places.

## Technical context

### mill-merge current PR-path (to be removed from mill-merge Step 5)

`plugins/mill/skills/mill-merge/SKILL.md` Step 5 has two branches:
- **PR path** (activated when `git.require-pr-to-base: true` AND `parent == base-branch`): runs `gh pr create`, flips Home.md to `[pr-pending]`, appends `pr-pending` to status.md, pushes task branch, halts.
- **Direct path**: squash-merge, push, with branch-protection fallback.

After refactor, Step 5 becomes direct-path-only. The PR path moves to mill-finalize.

### mill-merge phase gate (to be updated)

Current gate: reads `task/status.md` `phase:` — `done` → fresh merge, `pr-pending` → re-entry, other → halt.

Updated gate: try `task/status.md`; if absent, check Home.md `[pr-pending]` for slug → re-entry, Home.md `[active]`/other → halt with explanation. If `task/status.md` exists, existing logic applies.

### mill-go Handoff Step 5 (to be updated)

Current text: `"If pipeline.auto_merge: true → invoke /mill-merge."` and later `"mill-merge may halt on pr-pending in PR mode (git.require-pr-to-base: true) — that is a skill-level halt and is expected."`

Updated text: `"If pipeline.auto_merge: true → invoke /mill-finalize."` — remove the parenthetical about pr-pending halt (mill-go doesn't know about PR mode anymore).

### Config keys affected by rename

Files to update (`git.require-pr-to-base` → `git.require_pr_to_base`, `git.base-branch` → `git.base_branch`):

- `plugins/mill/skills/mill-merge/SKILL.md` — Step 1 (config key read), Step 5 (condition comment)
- `plugins/mill/skills/git-pr/SKILL.md` — Step 2 reads `git.parent-branch` (a different key used as PR base override). This key is intentionally excluded from this rename: it serves a different purpose (ad-hoc base override for standalone PR creation), has separate per-user `.millhouse/config.yaml` placement, and is not part of the `wiki/config.yaml` schema being normalised. Deferring it keeps scope tight. Verify during implementation that no other git: kebab-case keys sneak in.
- `plugins/mill/templates/wiki-config.yaml` — config template, update commented-out example keys
- `plugins/codeguide/skills/codeguide-update/SKILL.md` — references `base-branch` for parent detection (verify usage)
- `plugins/codeguide/scripts/resolve_scope.py` — `_detect_base_branch` function (verify which key it reads)
- `plugins/codeguide/unit_tests/test-resolve-scope.py` — fixtures using old key names

Note: `resolve_scope.py`'s `_detect_base_branch` uses git native detection (`origin/HEAD`, `origin/main`, `origin/master`) — it does NOT read mill config keys. Verify before editing. The config-update-SKILL.md reference to `base_branch` may be a local variable, not a config key. Read before touching.

### git-pr step 1.5 guard interaction

git-pr's step 1.5 halts when `$GIT_ROOT/task/status.md` exists. In mill-finalize's PR-mode flow, the cleanup commit (Step 4) removes `task/` before `/git-pr` is called (Step 6). So the guard doesn't fire — no changes to git-pr needed.

### Unit test targets

- `plugins/mill/unit_tests/test-mill-merge-inplace.py` — currently tests mill-merge including PR-path scenarios. Remove PR-path tests; add test for updated phase-gate (absent status.md + Home.md fallback).
- New `plugins/mill/unit_tests/test-mill-finalize-dispatch.py` — test `require_pr_to_base` + `parent == base_branch` evaluation with config fixtures; test PR-path and direct-path routing; test config-key fallback for old kebab-case keys (expect failure, document breakage).

## Constraints

- Junctions and hardlinks are never used in scripts — always resolve real paths via `_paths.py`.
- Working state (`task/`) lives on the task branch only. Wiki holds only `Home.md` and `config.yaml`.
- Scripts never change cwd to wiki — all wiki writes go through `_wiki.write_commit_push` or `git -C <wiki_path>`.
- mill-merge always runs from the child worktree; `cd <parent-worktree>` is forbidden.
- NTFS junctions must be stripped before any recursive deletion (via `_junction.strip_all_in_worktree`). Mill-finalize's PR path does NOT delete the worktree — it halts for human review. So junction stripping is mill-merge's concern, unchanged.
- `${CLAUDE_PLUGIN_ROOT}` is used for all intra-plugin paths in SKILL.md instructions.
- mill-finalize PR-mode must run the cleanup commit BEFORE `gh pr create` (issue #268).
- Config-key rename is breaking — no shim. Operators update manually.

## Testing

### mill-finalize dispatch (new unit test)

File: `plugins/mill/unit_tests/test-mill-finalize-dispatch.py`

Scenarios:
- `require_pr_to_base: true` + `parent == base_branch` → PR path selected
- `require_pr_to_base: true` + `parent != base_branch` → direct path selected (PR only applies when merging to base)
- `require_pr_to_base: false` (or absent) → direct path selected regardless of branch
- Old kebab-case key `require-pr-to-base` → not recognised (returns false/absent) — documents the breaking change
- Config deep-merge: local override of `require_pr_to_base` wins over wiki config

### mill-merge phase gate (no removals needed)

File: `plugins/mill/unit_tests/test-mill-merge-inplace.py`

The existing file contains only `_inplace` module signature smoke tests (`is_inplace`, `prompt_stale_worktree`). There are no PR-path tests to remove.

The updated phase-gate (absent `task/status.md` → Home.md fallback) is SKILL.md agent logic with no backing Python helper — no unit test is needed for it. Leave `test-mill-merge-inplace.py` unchanged.

### No TDD candidates

Mill-finalize and the mill-merge phase-gate update are pure SKILL.md changes (no Python helper logic beyond what already exists). Unit tests cover the config-key evaluation logic only, which can be tested with simple dict fixtures.

## Q&A log

- **Q:** Should mill-finalize be SKILL.md only, no Python CLI? **A:** [auto-pick] 1) SKILL.md only. **Why:** dispatch is two branches (PR or direct); same pattern as mill-merge, which has no backing CLI.
- **Q:** In PR-mode, where does the cleanup commit go relative to /git-pr? **A:** [auto-pick] 1) Update status.md → pr-pending, commit; then cleanup commit (removes task/); then push; then /git-pr. **Why:** satisfies #268, preserves audit trail, git-pr guard doesn't fire naturally.
- **Q:** How should refactored mill-merge detect re-entry when task/status.md is absent? **A:** [auto-pick] 1) Try status.md first; if absent, fall back to Home.md [pr-pending] marker. **Why:** preserves existing behaviour; handles post-cleanup case cleanly.
- **Q:** How should the config-key rename roll out? **A:** [auto-pick] 1) Breaking rename, no alias. Code reads new snake_case only. Operators update wiki/config.yaml manually. **Why:** 10+ keys already use snake_case; shim prolongs inconsistency.
- **Q:** Keep branch-protection fallback in mill-merge direct path? **A:** [auto-pick] 1) Keep it. **Why:** prevents dead-end if require_pr_to_base misconfigured; doesn't duplicate dispatch logic.
- **Q:** Mill-go Handoff Step 5 update? **A:** [auto-pick] 1) Replace /mill-merge with /mill-finalize. **Why:** single source of truth for dispatch; mill-go stays mode-agnostic.
- **Q:** Testing approach? **A:** [auto-pick] 1) Unit tests for dispatch + update test-mill-merge-inplace.py. **Why:** dispatch is pure logic, testable with config fixtures; unit coverage is fast and reliable.
