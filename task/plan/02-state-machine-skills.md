# Batch: state-machine-skills

```yaml
task: "46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup"
batch: state-machine-skills
number: 2
cards: 4
verify: null
depends-on: [1]
```

## Batch Scope

This batch lands the SKILL.md text changes that move the Home.md state machine from `[active] → [done]` to `[active] → [ready-to-merge] → ([pr-pending] →)? [done]`. Two SKILL.md files are edited: `mill-go` (Handoff step 2 flips to `[ready-to-merge]` instead of `[done]`) and `mill-merge` (teardown Steps 8–10 removed; `[pr-pending]` Home.md flip added to BOTH PR-creation paths in Step 5; PR-path re-entry prose updated; Step 12 final report updated). No Python code changes here; the helper changes from batch 1 make the new phase strings valid in `_tasks_md.set_phase`. Cards are split per logical edit so the reviewer can verify each independently. Card numbering continues at 7 (cards 1–6 were batch 1).

## Cards

### Card 7: mill-go Handoff — flip to `[ready-to-merge]`

- **Context:**
  - `plugins/mill/scripts/_tasks_md.py`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-go/SKILL.md`, locate the Handoff section (heading `## Handoff`, ~line 277). In Step 2's Python snippet, change `_tasks_md.set_phase_at(home_path, slug, "done")` to `_tasks_md.set_phase_at(home_path, slug, "ready-to-merge")`. Update the surrounding sentence: replace "Flip Home.md's task line to `[done]`" with "Flip Home.md's task line to `[ready-to-merge]` — the new intermediate state signalling 'mill-go done, mill-merge pending'". Update the `write_commit_push` commit message argument on the following line from `f"task: complete {slug}"` to `f"task: ready-to-merge {slug}"`. Step 1 (the `_status.append_phase(status_path, "done", ...)` call) is UNCHANGED — status.md still records `done` as the implementation-complete phase. Update Step 5's auto-merge prose: where it reads "Task complete. Run `/mill-merge` to merge the task branch back to parent." leave it as-is; the user-facing message remains accurate.
- **Commit:** `feat(mill-go): handoff flips Home.md to [ready-to-merge] instead of [done]`

### Card 8: mill-merge — remove Steps 8–10 (worktree, portal, wiki-active teardown)

- **Context:**
  - `plugins/mill/scripts/_worktree.py`
  - `plugins/mill/scripts/_junction.py`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-merge/SKILL.md`, delete three sections from the Teardown sequence: `### 8. Drop the worktree + branch` (currently lines ~192–222, including the `WorktreeLockedError` exception table and "In-place mode:" sub-section), `### 9. Remove portal entry` (~lines 224–230), and `### 10. Remove wiki active directory` (~lines 232–239). Renumber subsequent step headings: `### 11. Regenerate sidebar + release merge lock` becomes `### 8. Regenerate sidebar + release merge lock`, and `### 12. Notify + report` becomes `### 9. Notify + report`. Update every "Step 11" / "Step 12" reference elsewhere in the file (e.g. the PR-path bullet `Skip to Step 11 (Release lock)`, the rollback-after-Step-5 note "Post-Step-5 failures (archive tag, Home.md, sidebar, worktree/branch/portal removal)") to "Step 8" / "Step 9" — and remove "worktree/branch/portal removal" from any enumeration of post-Step-5 failures since those are no longer mill-merge's concern. In the section `## Teardown sequence`, update the intro paragraph from "Steps 4–10 implement the canonical teardown" to "Steps 4–7 implement the canonical merge sequence; worktree, portal, and wiki active-dir teardown is handled by `/mill-cleanup`." Update the "Recovery note" if it mentions worktree removal. **Update frontmatter `description:` field (line 3):** the current text "Finalize a completed task. Cleanup commit on task branch, squash-merge to parent, archive tag, Home.md flip, worktree+branch+portal removal, optional legacy wiki cleanup. PR-path honoured via git.require-pr-to-base. Runs from the child worktree." must change to "Finalize a completed task. Cleanup commit on task branch, squash-merge to parent, archive tag, Home.md flip. Worktree, branch, portal, and legacy wiki cleanup are handled by /mill-cleanup. PR-path honoured via git.require-pr-to-base. Runs from the child worktree." **Update Entry Step 1's MarkerError handling (currently line ~21):** the parenthetical "On `_marker.MarkerError` (detached HEAD, prefix mismatch, slug absent from Home.md, or not [active])" must drop "or not [active]" because batch 1 card 3 removed that check from `slug_from_branch`. Replace the halt message "This worktree has no active task branch — `mill-merge` needs `status.md` to know the parent branch." with "This worktree has no registered task branch — `mill-merge` needs `status.md` to know the parent branch."
- **Commit:** `refactor(mill-merge): drop Steps 8-10 teardown — moved to mill-cleanup`

### Card 9: mill-merge — flip Home.md to `[pr-pending]` in BOTH PR-creation paths

- **Context:**
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_wiki.py`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-merge/SKILL.md`, add a Home.md flip to both PR-creation paths in `### 5. PR path or direct squash?`. (a) **Primary PR path** (the bullet `**PR path** — activate when git.require-pr-to-base: true AND parent-branch == base-branch`, currently lines ~90–98): after the `gh pr create` block and BEFORE the `_status.append_phase(status_path, "pr-pending", ...)` line, insert a Python snippet flipping Home.md to `[pr-pending]`:
  ```python
  with _wiki.wiki_lock(<WIKI_PATH>, slug):
      home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")
      new_text = _tasks_md.set_phase(home_text, slug, "pr-pending")
      (wiki_path / "Home.md").write_text(new_text, encoding="utf-8")
      _wiki.write_commit_push(<WIKI_PATH>, ["Home.md"], f"task: pr-pending {slug}", slug=slug)
  ```
  (b) **Branch-protection fallback** (the numbered sub-steps within `**On push failure — branch-protection fallback:**`, lines ~108–164): insert the same Home.md flip block as a new sub-step between current sub-step 6 (which writes `pr-pending` to status.md) and current sub-step 7 (the user-facing report). Renumber sub-step 7 → 8 and sub-step 8 → 9. Add a sentence to the section's intro paragraph: "Both PR-creation paths flip Home.md to `[pr-pending]` before halting at Step 8 so the coordination state is visible." (Step number 8 references the renumbered "Release lock" step from card 8.) Do not touch the rollback (Steps 1–5) section.
- **Commit:** `feat(mill-merge): flip Home.md to [pr-pending] in both PR-creation paths`

### Card 10: mill-merge — update PR-path re-entry and Step 9 report

- **Context:**
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/skills/mill-merge/SKILL.md`, update two sections that reference the now-removed teardown steps. (a) `## PR-path re-entry` (currently lines ~261–270), MERGED sub-bullet: replace the prose "continue to Step 6 (archive tag). Skip Steps 1–5 (merge lock no longer needed; squash has already landed via the external PR). The rest of the teardown (tag, Home.md flip, worktree/branch/portal removal, legacy wiki cleanup) runs as normal." with "continue to Step 6 (archive tag). Skip Steps 1–5 (merge lock no longer needed; squash has already landed via the external PR). Steps 6–7 run (archive tag + Home.md `[done]` flip). Worktree, branch, portal, and legacy wiki active-dir teardown are now handled by `/mill-cleanup --apply` — direct the operator to run it after Step 9 reports." (b) `### 9. Notify + report` (the renumbered Step 12 from card 8): change the user-facing report message from "Merge complete for `<slug>`. Worktree and branch removed. Archive tag `archive/<slug>` created. Home.md updated." to "Merge complete for `<slug>`. Worktree intact — run `/mill-cleanup --apply` to remove worktree, branch, portal, and legacy wiki active-dir. Archive tag `archive/<slug>` created. Home.md updated to `[done]`." Update the "Verify after teardown" bullet list: remove the entries asserting `<container>/wts/<slug>` is gone, `$CHILD_BRANCH` is gone, and `<container>/portals/<slug>` is gone — those are mill-cleanup's responsibility. Keep the "git tag -l archive/<slug>" and "Home.md shows [done]" assertions.
- **Commit:** `docs(mill-merge): update PR-path re-entry + Step 9 report for teardown split`

## Batch Tests

`verify: null`. No automated tests cover SKILL.md text. The plan reviewer reads these changes end-to-end; the integration test `test-merge.py` (modified in batch 4) verifies the runtime behavior implied by these SKILL.md edits — that the worktree is intact post-merge — but the integration test is operator-invoked, not part of the unit suite. Markdown linting is not wired in this codebase.
