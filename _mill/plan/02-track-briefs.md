# Batch: track-briefs

```yaml
task: "Track _mill/briefs/ instead of gitignoring them"
batch: track-briefs
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-gitignore-phase.py
depends-on: []
```

## Batch Scope

Make agent briefs and responses part of the committed task record. Two orchestrator
SKILLs (mill-go, mill-plan) gain `_mill/briefs/` in the pathspec of the task-branch state
commits they already make, so briefs accumulate on the branch and are preserved under the
`archive/<slug>` tag (mill-merge's existing `git rm -r _mill/` sweeps them from the squash
diff). The agent-response filename is renamed `<brief>.md.out` → `<brief>.out.md` so it is
a readable Markdown file. A unit test locks in that briefs are never re-added to the
managed `.gitignore` block. These are mostly Markdown SKILL edits with no runnable surface
(verified by review); only the gitignore test is executable. The SKILL edits take effect
after merge + cache refresh, not in this task's own run (see Shared Decisions).

## Cards

### Card 6: Rename the response file to .out.md and commit mill-go briefs

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the `## Agent-mode dispatch` section: (a) Step 4 ("Capture output")
  and Step 5 (`--agent-output`) currently use `<brief_path>.out`. Change the response-file
  path to the brief path with its trailing `.md` replaced by `.out.md` (for a brief
  `foo-r1.md` the response is `foo-r1.out.md`). State the rule explicitly in both steps so
  any SKILL that references this pattern (mill-plan, mill-start) inherits it. (b) Add
  `_mill/briefs/` to the `git -C <worktree> add` pathspec of the task-branch commits that
  finalize a unit of work, leaving their commit messages unchanged: the per-batch approve
  commit (`mill-go: approve batch {batch_name}`), the per-batch review-disabled approve
  commit (`mill-go: approve batch {batch_name} (per-batch review disabled)`), the
  holistic-approve commit (`mill-go: holistic approve {slug}`), and the done commit
  (`mill-go: done {slug}`). Do NOT add `_mill/briefs/` to prepare, blocked, or
  holistic-reviewing commits.
- **Commit:** `feat(mill-go): track briefs and rename response file to .out.md`

### Card 7: Commit plan-review briefs in mill-plan

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `_mill/briefs/` to the `git -C <worktree> add` pathspec of the
  plan-review terminus commits that already stage `<plan_dir> <reviews_dir> <status_path>`:
  the approve commit in step 4a (`mill-plan: approve plan for {slug}`), the NIT/approve
  fix commit in steps 4b and 4c, and the blocking plan-fix commit in step 4d
  (`mill-plan: plan-fix round {N} for {slug}`). Leave commit messages unchanged. Do NOT add
  it to the write-plan commit (step at line ~90 — no briefs exist yet) or the validator-fix
  commit (no LLM brief produced).
- **Commit:** `feat(mill-plan): track plan-review briefs on the task branch`

### Card 8: Lock that briefs stay out of the managed .gitignore block

- **Context:**
  - `plugins/mill/scripts/_gitignore.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-gitignore-phase.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a test (e.g. `test_glob_entries_excludes_briefs`) asserting that no
  entry in `_gitignore.GLOB_ENTRIES` contains the substring `_mill/briefs` — locking in
  that a future managed-block regeneration cannot silently re-ignore briefs. Follow the
  file's existing test style (it imports `GLOB_ENTRIES` and returns an int error count).
- **Commit:** `test(gitignore): assert briefs are not in the managed ignore block`

## Batch Tests

`verify` runs only `test-gitignore-phase.py` (Card 8) — the single executable surface in
this batch. Cards 6 and 7 edit orchestrator `SKILL.md` files, which have no unit-test
surface; they are verified by code review against the cited commit-message strings and the
`## Agent-mode dispatch` step references. `verify` is intentionally narrow (one file) per
the per-batch scoping rule.
