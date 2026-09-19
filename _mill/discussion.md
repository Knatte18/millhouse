# Discussion: mill-merge / mill-merge-in: brief-staging path bug and easy-to-miss caching instruction

```yaml
task: mill-merge / mill-merge-in: brief-staging path bug and easy-to-miss caching instruction
slug: mill-merge-family-doc-gaps
status: discussing
parent: main
```

## Problem

Two doc-only gaps in the `mill-merge` / `mill-merge-in` SKILL.md pair, consolidated from GitHub issues #996 and #987:

1. **#996 — `mill-merge-in/SKILL.md` Step 5.5 brief-staging.** A past merge introduced `git -C <worktree> add <worktree>/_mill/briefs/` in Step 5.5's commit block, diverging from the relative-path convention (`git -C <worktree> add _mill/briefs/`) used everywhere else, and broke `test-brief-commit.py`'s `add _mill/briefs/` substring regression lock. **This bug itself was already fixed** on 2026-09-04 in commit `7a972fbf` ("mill-merge-in: fix Step 5.5 git add command to match brief-commit test convention") — verified by reading the current `plugins/mill/skills/mill-merge-in/SKILL.md` Step 5.5, which already reads `git -C <worktree> add _mill/briefs/`. What remains is the doc gap that let it happen: nothing in Step 5.5 explains *why* the path must stay relative, so a future edit (e.g. another merge-in conflict resolution) can silently reintroduce the same `-C <dir> add <dir>/<path>` mistake, since that pattern looks equally plausible to someone unfamiliar with the convention.

2. **#987 — `mill-merge/SKILL.md` caching instruction.** Entry's phase-gate table caches `cached_task` / `cached_task_description` from `_mill/status.md` while phase is `done` (Entry, ~line 164), specifically because Step 4's cleanup commit (`### 4. Cleanup commit`, ~line 279) runs `git rm -r <task_dir>` and commits it, deleting `status.md` before Step 5 (`### 5. Direct squash`, ~line 307) needs `<cached_task>` for the squash commit message and Step 6 needs it for the PR title. The caching instruction sits roughly 115 lines away from Step 4's deletion and over 140 lines from Step 5's use — in a live `mill-go -> mill-finalize -> mill-merge` run, an orchestrator skipped it, and the values were only recovered via an undocumented fallback (`git show HEAD~1:_mill/status.md`, reading the deleted file's content from the cleanup commit's parent) improvised on the spot. There is one existing precedent for a documented recovery path in this same file — the `closed` PR-state route (`### PR-state gate`, ~line 216) already documents a fallback for when `cached_task`/`cached_task_description` are undefined, using `_client.get_task(wiki_path, slug)` — but that fallback is scoped to the `closed` route (where `status.md` is typically already gone via `mill-finalize`'s earlier cleanup) and does not cover the ordinary `done`-phase direct-squash flow, which is the flow that actually failed.

Both are documentation-only fixes: no script or runtime-code changes, no behavior change to a correctly-run merge. The goal is to make the already-correct behavior harder to break silently, and to give the actually-failed flow the same kind of documented recovery path the `closed` route already has.

## Scope

**In:**
- `plugins/mill/skills/mill-merge-in/SKILL.md`, Step 5.5: add a short explanatory note next to the `git -C <worktree> add _mill/briefs/` line, in the file's existing "Why X, not Y" callout style (e.g. the adjacent "Why staged-only, not unscoped porcelain" paragraph), stating the relative-path convention and citing the #996 regression it exists to prevent.
- `plugins/mill/skills/mill-merge/SKILL.md`, `### 5. Direct squash` (or immediately adjacent to it): document a recovery-path fallback for `cached_task` / `cached_task_description` when they are undefined at the point of use in the ordinary `done`-phase flow — via `git show HEAD~1:<status_path>` against the cleanup commit written by Step 4, parsing `task:` / `task_description:` the same way `_status.read_full` would, falling back to `slug` if the `task:` field itself is absent. This is option (c) from #987's suggested fixes.

**Out:**
- No change to Step 5.5's actual bash commands in `mill-merge-in/SKILL.md` — they are already correct; only a doc note is added.
- No change to Entry's existing caching instruction location in `mill-merge/SKILL.md` (rejecting #987's option (a), moving the instruction to sit next to Step 4 — see Decisions below) and no change to Step 4's own text (rejecting option (b), restating the reminder inline at Step 4).
- No change to the existing `closed`-route fallback (`### PR-state gate`, ~line 216) — it is already correct for its own narrower case and is left as-is; the new fallback is additive, for the `done`-phase direct-squash flow specifically.
- No test changes. `test-brief-commit.py` already asserts the exact substring the current Step 5.5 code contains; adding a doc note nearby does not touch that substring. No new regression-lock test is added for #987 since the fix is a documented manual-recovery procedure, not a scripted behavior — there is nothing script-level to regression-lock.
- No changes to any other SKILL.md, script, or helper.

## Decisions

### doc-note-placement-996

- Decision: Add the explanatory note in `mill-merge-in/SKILL.md` immediately after Step 5.5's bash block, in the same paragraph position as the existing "Why staged-only, not unscoped porcelain" note (i.e. as a second "Why relative, not absolute" callout in that same step).
- Rationale: Matches this file's own established convention of placing a "Why" explanation directly under the bash block it justifies, rather than as a separate section or a top-of-file caveat that a future editor might not associate with the specific line they're changing.
- Rejected: A top-of-file or Entry-level general warning about path conventions — too far from the line an editor would actually be touching, defeating the point of a preventive note.

### recovery-path-987

- Decision: Implement #987's suggested option (c) — document the `git show HEAD~1:<status_path>` recovery path as a fallback for the ordinary `done`-phase direct-squash flow, placed at `### 5. Direct squash` right before the `git -C <parent-path> commit -m "<cached_task>"` line that consumes it — rather than option (a) (move the caching instruction next to Step 4) or option (b) (restate the reminder inline at Step 4).
- Rationale: Option (c) is the minimal, lowest-risk change — it adds a safety net at the actual point of failure without restructuring Entry's existing phase-gate table (which several other paragraphs in this file already reference by its current position and content — e.g. the `closed`-route fallback at ~line 216 explicitly contrasts itself against "the `done` branch caching block"). It's also the option this file already has a working precedent for: the `closed`-route fallback at ~line 216 does exactly this pattern (recover `cached_task`/`cached_task_description` when undefined, right before they're needed) for a narrower case. Extending the same pattern to the general `done`-phase flow is consistent with the file's existing style and doesn't require reasoning about whether moving or restating the Entry instruction could desync it from the `closed`-route's own already-cross-referencing prose.
- Rejected: Option (a) — moving the caching instruction to sit immediately before Step 4's `git rm -r` reads as the more "root-cause" fix (closing the actual distance problem), but it requires rewriting the Entry phase-gate table's structure and every cross-reference to "Entry Step 5" / "the `done` branch caching block" elsewhere in the same file (at minimum the `closed`-route paragraph at ~line 216 and its own line 219 back-reference) — a larger, more error-prone diff for a doc-only task, and it still would not by itself give a recovery path for a run where the (relocated) instruction is skipped anyway; a documented fallback is needed regardless of where the instruction lives. Option (b) — restating the reminder inline at Step 4 — is weaker than (a) (a restated reminder can be skipped exactly as easily as the original) and doesn't add a fallback either; it only adds a second easy-to-miss reminder next to the first.

## Technical context

- `plugins/mill/skills/mill-merge-in/SKILL.md` Step 5.5 ("Commit dispatch briefs") currently reads (already fixed, no code change needed):
  ```bash
  if [ -d <worktree>/_mill/briefs ]; then
    git -C <worktree> add _mill/briefs/
  fi
  if [ -n "$(git -C <worktree> diff --cached --name-only)" ]; then
    git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"
  fi
  ```
  followed by an existing "**Why staged-only, not unscoped porcelain:**" paragraph — the new note is added as a sibling paragraph immediately after that one.
- `plugins/mill/unit_tests/test-brief-commit.py::test_mill_merge_in_brief_commits` is the regression lock #996 broke and commit `7a972fbf` re-fixed. It asserts (substring match, not line-scoped) that `mill-merge-in/SKILL.md` contains `"add _mill/briefs/"` or `"add _mill/briefs"`. A doc note that keeps that exact substring intact (which this change does — it only adds prose after the existing bash block) cannot regress this test; no test change is needed, and none should be made, since the assertion's job is exactly to keep locking the code line, independent of surrounding prose.
- `plugins/mill/skills/mill-merge/SKILL.md`:
  - Entry's caching block (~line 164-170): `cached_task = _status.read_full(status_path)["yaml"].get("task", slug)`, `cached_task_description = _status.read_full(status_path)["yaml"].get("task_description", cached_task)`. Stays exactly as-is.
  - `### 4. Cleanup commit` (~line 279-291): `git -C <worktree> rm -r <task_dir>` then `git commit -m "chore: pre-merge cleanup"`. This is the commit whose *parent* (`HEAD~1` at the moment Step 5 runs, since no other commit intervenes between Step 4 and Step 5 in the direct-squash flow) still has `status.md` in its tree — the basis for the new fallback.
  - `### 5. Direct squash` (~line 307 onward): the direct-path bash block ends with `git -C <parent-path> commit -m "<cached_task>"` — this is the exact consumption point where an undefined `cached_task` previously caused the live incident, and where the new fallback note is added, immediately before that bash block.
  - `### PR-state gate`, `closed` route (~line 206-227): existing, unmodified precedent for a documented recovery fallback (reads from `_client.get_task(wiki_path, slug)` instead of git history, since in that route `status.md` is typically already gone by the time `mill-merge` is reached at all — `mill-finalize` deleted it earlier). The new fallback for the `done`-phase flow uses `git show HEAD~1:<status_path>` instead, since in that flow `status.md`'s last content is in the cleanup commit's parent, not recoverable from the wiki (the wiki task has no `task_description` field, only `title`, per the existing `closed`-route fallback's own comment at ~line 222-223 — `git show HEAD~1` recovers the *actual* status.md fields losslessly, which is why it is preferred here over reusing the wiki-based fallback).
  - `_status.read_full(status_path)` signature (used by the existing caching block) reads the YAML block and returns a dict with a `"yaml"` key; the new fallback note parses the `git show` output the same way — read the raw YAML text, extract `task:` / `task_description:` — since `_status.read_full` itself takes a `Path` and cannot be pointed at a `git show` string directly; the note documents the field names to extract, not a new helper call.

## Testing

Doc-only change — no new automated test is added or expected:
- `test-brief-commit.py` (existing) continues to pass unmodified; verified by inspection above that the substring it locks is untouched by the #996 doc note.
- No script-level behavior exists for #987's recovery path to lock — it is an operator/orchestrator-facing manual procedure documented in prose, exercised only in the rare case where Entry's caching step was skipped. Adding a regression-lock test for prose content in `mill-merge/SKILL.md` would only duplicate `test-skill-helper-drift.py`-style textual assertions for a fallback path that has no code to drift out of sync with; skipped as out of proportion for a doc-only task.
- Verify command for the plan: re-run the existing full unit-test suite (`plugins/mill/unit_tests/run-all.py`) to confirm no existing lock (particularly `test-brief-commit.py` and `test-skill-helper-drift.py`) regresses from either doc edit.

## Q&A log

- **Q:** For #987, which of the issue's three suggested fixes (a: move the caching instruction next to Step 4; b: restate the reminder inline at Step 4; c: document the `git show HEAD~1` recovery path as a fallback) should this task implement?
  1) Document the `git show HEAD~1:<status_path>` recovery-path fallback at Step 5's point of use (Recommended) — matches the existing `closed`-route precedent in the same file, smallest diff, adds a safety net that survives a skipped Entry step regardless of where that step lives.
  2) Move the caching instruction to sit immediately before Step 4's `git rm -r`.
  3) Restate the reminder inline at Step 4, in addition to Entry's existing instruction.
  **A:** [auto-pick] Document the `git show HEAD~1:<status_path>` recovery-path fallback at Step 5's point of use. **Why:** it is the only option of the three that still helps when the caching step is skipped regardless of where that step is later relocated to, it mirrors a pattern this file already uses successfully (the `closed`-route fallback), and it is the smallest, lowest-risk diff for a doc-only task — options (a)/(b) touch Entry's phase-gate table and its several existing cross-references elsewhere in the file, for no guaranteed reduction in the "skipped instruction" risk that caused the live incident in the first place.
- **Q:** #996's underlying bug (`git -C <worktree> add <worktree>/_mill/briefs/`) is already fixed in the current codebase (commit `7a972fbf`, 2026-09-04). Should this task still touch `mill-merge-in/SKILL.md` at all, or is #996 fully resolved with no further action?
  1) Add a preventive "why relative path" doc note at Step 5.5 so the fix doesn't silently regress again (Recommended) — the wiki task's own title and brief describe this as a "family: doc gaps" task, and the fold-in comment on #996 explicitly consolidated it into this task rather than closing it as already-fixed, indicating the intended deliverable is the preventive doc note, not the (already-shipped) code fix.
  2) Take no action on #996 — treat it as already resolved by commit `7a972fbf` and close out that half of the task with no doc change.
  **A:** [auto-pick] Add a preventive "why relative path" doc note at Step 5.5. **Why:** the task was folded in (not closed as duplicate/already-fixed) specifically into a "doc gaps" family task, which only makes sense if a doc gap — not the code bug itself — is the remaining deliverable; leaving Step 5.5 without an explanation of the convention it depends on leaves the exact same class of regression free to recur on the next unrelated merge-in edit.
