# Batch: mill-merge-status-absent-fallback

```yaml
task: 'mill-go/mill-plan/mill-merge: dispatch-classification, watchdog, entry-gate, and implementer-compliance gaps (round 2)'
batch: mill-merge-status-absent-fallback
number: 7
cards: 2
verify: null
depends-on: []
```

## Batch Scope

`#782`: two independent crash fixes in `mill-merge/SKILL.md`'s closed-PR re-entry path, where `_mill/status.md` is typically absent (mill-finalize/this file's own Step 4 cleanup commit already removed `task_dir`).
Card 18 fixes Entry Step 4, which calls `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)` unconditionally today — `_read_parent_from_status` (in `_parent_branch.py`) treats "file missing" identically to "file present but no `parent:` row," so `resolve()` raises `ParentBranchError` in non-interactive mode either way, even though the "file entirely absent" case has a semantically different, resolvable fallback (`cfg.git.base_branch`) that the "file exists but the row is missing" case does not.
Card 19 fixes `## Steps` Step 5's branch-protection fallback sub-step 6, which calls `_status.append_phase(status_path, "pr-pending", ...)` unconditionally *after* Step 4's own cleanup commit (`git -C <worktree> rm -r <task_dir>`) has already deleted `status_path` earlier in the same invocation — this call always raises against an already-gone file.
Both fixes touch the same file (`mill-merge/SKILL.md`) in disjoint sections (Entry Step 4 vs. `## Steps` Step 5) with no logical dependency between them; kept as one batch (rather than two) purely because both are the same GitHub issue (`#782`) and the same small file.
No batch-local decisions differ from `## Shared Decisions` in the overview — this batch is governed by `doc-batches-preserve-file-conventions`: `## Entry`'s numbering is mixed, not uniformly bold-led — steps 1, 1.5, and 5 use a bold lead-in (`N. **Bold lead-in.**`) but steps 2, 3, and 4 (Card 18's target) are plain numbered sentences with no bold lead-in — so Card 18's edit stays within Step 4's existing plain-numbered-sentence style, adding no bold lead-in of its own.
Step 5's edit (Card 19) stays within its existing plain ordered-list-numeral sub-step style (`1.` ... `9.`) inside the `### 5. Direct squash` heading (this file's `## Steps` convention) — do not convert either card's target into the other file-section's style.

## Cards

### Card 18: Add `status_path.exists()` fallback to `cfg.git.base_branch` in Entry Step 4

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  Entry Step 4 currently reads: "4. Resolve parent branch via `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)`. ... On `_parent_branch.ParentBranchError` (status.md is missing the `parent:` row): `_status.set_blocked(...)`, commit ... and push, then halt with `BLOCKED: status.md is missing the parent: row for <slug> -- mill-spawn should have written it; set it manually and re-run /mill-merge.`"
  Restructure this step to branch on `status_path.exists()` **before** calling `resolve()`: if `status_path.exists()` is `False`, skip the `_parent_branch.resolve(...)` call entirely for this run, set `parent_branch = cfg.git.base_branch` directly (already loaded in Entry Step 1, "Config keys to read," with its own documented `"main"` fallback when absent), and report a one-line operator-facing notice at that point: "status.md absent; assuming parent branch is `<base_branch>` (config `base_branch`) -- if this task's true parent differs (e.g. a stacked branch merging into something other than `base_branch`), abort and resolve manually."
  If `status_path.exists()` is `True`, call `_parent_branch.resolve(status_path, interactive=False, expected_slug=slug)` exactly as today, including the existing `ParentBranchError` handling (`_status.set_blocked` + commit + push + halt message) for the "file exists but no `parent:` row" case, completely unchanged.
  Do not reorder Entry Step 4 relative to Entry Step 5 (the phase gate) — this fix is entirely local to Step 4's own body.
  Do not touch `_parent_branch.py` itself — `_read_parent_from_status`'s "missing file / absent row / malformed block -> `None`" tolerance is documented as intentional in its own docstring; this fix belongs in the caller (this Step 4 edit), not the helper.
- **Commit:** `docs(mill-merge): fall back to base_branch when status.md is absent in Entry Step 4`

### Card 19: Remove the doomed `_status.append_phase` call in Step 5's branch-protection fallback sub-step 6

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  In `### 5. Direct squash`'s "On push failure — branch-protection fallback" nested numbered list (sub-steps `1.` through `9.`), sub-step `6` currently reads in full: "Append the `pr-pending` phase and commit+push `<status_path>` on the task branch:" followed by a ` ```python ` fence containing `_status.append_phase(status_path, "pr-pending", _timestamp.now_utc_iso())` and a ` ```bash ` fence containing `git add <status_path> && git commit -m "chore: pr-pending after branch-protection fallback" && git push`.
  This call always raises because Step 4's own cleanup commit (`git -C <worktree> rm -r <task_dir>`, which runs earlier in this same mill-merge invocation, before Step 5 is ever reached) has already deleted `<status_path>` from the working tree — there is no re-creation of the file in between.
  Delete sub-step `6` in its entirety (both fences and its lead-in sentence).
  Renumber the following sub-steps down by one: the current sub-step `7` ("Flip Home.md to `[pr-pending]`" via `_client.set_phase(wiki_path, '<slug>', 'pr-pending')`) becomes the new sub-step `6`; the current sub-step `8` becomes the new sub-step `7`; the current sub-step `9` becomes the new sub-step `8` — do not leave a numbering gap.
  Add one new sentence to the (renumbered) former-sub-step-7 — the `_client.set_phase(...)` wiki call — stating explicitly that this wiki call is now the sole durable record of the `pr-pending` transition for this fallback path, since `status.md` no longer exists to append a phase to at this point; this matches the wiki-fallback convention this file's own Entry Step 5 phase gate already documents for when `status_path` is absent.
  Search the rest of `mill-merge/SKILL.md` for any other cross-reference to "sub-step 6", "sub-step 7", "sub-step 8", or "sub-step 9" by number within this same branch-protection fallback context, and update any found to the renumbered values — do not leave a stale numeric cross-reference.
- **Commit:** `docs(mill-merge): remove doomed append_phase call from Step 5 branch-protection fallback`

## Batch Tests

`verify: null` — both cards are logic changes to `SKILL.md`-documented control flow (a conditional before a script call; removing a doomed call and renumbering), not new Python functions — there is no direct unit-testable surface, matching `_mill/discussion.md`'s Testing section for `#782` ("no direct unit test unless the fallback is factored into `_parent_branch.py` itself" — out of scope per this batch's own Decision above).
Verification is a careful re-read confirming: Card 18's `status_path.exists()` branch is evaluated strictly before any `resolve()` call and leaves the existing `ParentBranchError` handling untouched; and Card 19's renumbering leaves no gap and no stale cross-reference to the old sub-step numbers anywhere in the file.
