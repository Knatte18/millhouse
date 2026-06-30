# Batch: mill-merge-skill

```yaml
task: "Handle pre-closed and pre-merged PRs gracefully in mill-merge"
batch: mill-merge-skill
number: 3
cards: 1
verify: null
depends-on: [1]
```

## Batch Scope

Rewrite `plugins/mill/skills/mill-merge/SKILL.md` so mill-merge queries PR state
at startup (via the batch-1 helper) and routes merged/open/closed/none for BOTH
the `done` and `pr-pending` phases through one unified gate, replacing the
`## PR-path re-entry` section that handled only `pr-pending`. This is a
documentation/instructions batch: SKILL.md is executed by the orchestrator LLM,
so there is no runnable test surface (`verify: null`). The behavioral logic it
relies on is the `_pr_state.resolve_pr_state` contract delivered and tested in
batch 1. Depends on batch 1 because the new gate invokes that helper.

## Cards

### Card 3: Unified PR-state startup gate in mill-merge SKILL.md

- **Context:**
  - `plugins/mill/scripts/_pr_state.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/skills/mill-finalize/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Add a new `### PR-state gate` subsection in `## Entry`, placed immediately
    after the Step 5 "Phase gate" block and before `## Steps`. It runs for BOTH
    resolved phases (`done` and `pr-pending`). It must:
    1. Capture the child branch up front:
       `CHILD_BRANCH=$(git branch --show-current)` (state that this is captured
       here, earlier than the existing Step 3 capture, because the gate needs it;
       Step 3's capture remains for the squash flow).
    2. Resolve PR state with an inline snippet (cwd = child git root, never wiki):
       ```bash
       PR_STATE_JSON=$(PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
       import json
       import _pr_state, _paths
       r = _pr_state.resolve_pr_state('$CHILD_BRANCH', _paths.resolve_git_root())
       print(json.dumps(r))
       ")
       ```
       Parse the JSON `state` / `number` fields from `PR_STATE_JSON`.
    3. Route on `state` (using the helper's lowercase values):
       - `merged` -> **cleanup-only teardown**: run Step 4 (cleanup commit) so
         the archive tag reflects a clean tip, then Step 6 (archive tag), Step 7
         (Home.md `[done]`), Step 8 (release lock -- no-op if never acquired),
         Step 9 (notify/report). SKIP Steps 1, 2, and 5. State explicitly that
         the local parent branch is intentionally NOT fast-forwarded here (it
         resyncs on the next parent-side fetch/pull) -- do not add a parent
         ff-sync step (discussion Decisions/merged-remote-cleanup-only,
         Local-parent staleness).
       - `open` -> **halt and report**, never auto-close:
         "PR #<number> is still open -- close or merge it on GitHub, then re-run
         `/mill-merge`." (discussion Decisions/open-pr-halt).
       - `closed` -> **proceed with the normal local squash** exactly as the
         `done` fresh-merge flow (continue to Step 1). **Commit-message source
         (required):** the `closed` route can be reached from a `pr-pending`
         re-entry, in which case `_mill/status.md` is typically absent (mill-finalize
         already `git rm -r`'d `task_dir`) so the Entry phase-gate `done` branch
         never cached `cached_task`/`cached_task_description` (SKILL.md L56-60) and
         Step 5's `git commit -m "<cached_task>"` would be undefined. The gate's
         `closed` route MUST therefore establish these values before continuing to
         Step 1: if `status_path.exists()`, read `cached_task` /
         `cached_task_description` from it exactly as the `done` branch does;
         otherwise derive them from the wiki via
         `task = _client.get_task(wiki_path, slug)` -> `cached_task =
         task["title"]`, `cached_task_description = task.get("title")` (title is the
         available field; there is no separate description in the wiki task).
         State that this fallback feeds Step 5's squash commit message.
         Add a caution note: in a branch-protected repo the Step 5 push may be
         rejected, triggering the existing Step 5 branch-protection fallback that
         auto-creates a NEW PR -- which contradicts the operator's deliberate
         close-without-merge. The fallback itself stays as-is, but the gate must
         note that CLOSED -> local-squash is not guaranteed terminal (discussion
         Decisions/closed-no-merge-proceeds, Branch-protection interaction).
       - `none` -> **silent fallback to phase-based behavior** (no new output):
         if `phase: done`, continue to Step 1 (today's direct squash); if
         `phase: pr-pending`, keep today's "status.md says pr-pending but no PR
         on this branch; inspect manually" halt (discussion
         Decisions/no-pr-silent-fallback).
  - Update the Entry Step 5 "Phase gate" table: the `done` row and the
    `pr-pending` row must both route into the new `### PR-state gate` (replace the
    `pr-pending` row action "see *PR-path re-entry* below" with "see *PR-state
    gate* below"; change the `done` row action so a fresh `done` merge also passes
    through the PR-state gate before Step 1, rather than going straight to Step 1).
  - Replace the existing `## PR-path re-entry` section: its merged/open/closed/
    none cases are now subsumed by the `### PR-state gate`. Either delete the
    `## PR-path re-entry` section and add a one-line pointer to the gate, or
    repoint it; do NOT leave two divergent PR routing tables. Critically, the old
    section's MERGED branch said "continue to Step 6 ... Skip Steps 1-5" (which
    also skipped Step 4) -- the unified gate's `merged` route MUST run Step 4
    before the archive tag (discussion Decisions/merged-remote-cleanup-only,
    "SKILL.md rewrite required").
  - Do NOT modify `### 5. Direct squash`, the branch-protection fallback, Steps
    6-9, or any mill-finalize / git-pr behavior -- only the Entry gate and the
    `## PR-path re-entry` section change (discussion Scope/Out).
  - Keep all prose ASCII-only (` -- `, ` -> `).
- **Commit:** `docs(mill): unified PR-state startup gate in mill-merge`

## Batch Tests

`verify: null` -- SKILL.md is orchestrator-executed instructions with no runnable
unit-test surface; the underlying `resolve_pr_state` logic is covered by batch
1's `test-pr-state.py`. Correctness of the prose routing is validated by the
plan/code reviewers, not by a test runner. No automated check applies to this
batch.
