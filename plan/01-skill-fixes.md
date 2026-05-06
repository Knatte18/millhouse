# Batch: 01-skill-fixes

```yaml
task: 21 (A) — mill-go cleanliness gate fixes
batch: 01-skill-fixes
cards: 4
verify: null
depends-on: []
```

## Batch Scope

This batch fixes three SKILL.md instruction bugs — all in `mill-go/SKILL.md` and
`mill-plan/SKILL.md` — that cause mill-go's cleanliness gate to fire as a false positive
on clean worktrees. No Python helper changes. The four cards correspond to four discrete
text edits: one to the gate command, one to the APPROVE commit in mill-go, and two to the
plan-review commit instructions in mill-plan.

## Cards

### Card 1: Fix cleanliness gate to ignore untracked files

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the "2b. Cleanliness gate" section of `mill-go/SKILL.md`, change the git command from `git -C <worktree> status --porcelain` to `git -C <worktree> status --porcelain --untracked-files=no`. Update the parenthetical description from "(uncommitted files present)" to "(uncommitted changes to tracked files present)" so the intent is clear. No other changes to the gate logic.
- **Commit:** `fix(mill-go): ignore untracked files in cleanliness gate (#166)`

### Card 2: Fix APPROVE commit to stage the review file

- **Reads:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the "3. Code Review loop" section, step 4, APPROVE bullet of `mill-go/SKILL.md`, update the commit instruction so it stages the review file alongside `status.md`. The review file path is available from the JSON summary's `reviews[0]["file"]` field (normal path) or from the crash-recovery scan path (crash-recovery path) — in both cases the implementer has the path at hand by this step. The new commit command must be: `git -C <worktree> add status.md <review_file_path> && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"`. Add a sentence before the commit command identifying where to obtain `<review_file_path>`: "Use the `file` field from `reviews[0]` in the JSON summary (or the crash-recovery scan path)." No changes to any other bullet in step 4.
- **Commit:** `fix(mill-go): stage review file in APPROVE commit (#165)`

### Card 3: Fix mill-plan 4a APPROVE commit to include reviews/

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the "Phase: Plan Review" section, step 4a of `mill-plan/SKILL.md`, replace the vague "commit+push both" with an explicit commit command. The current step 4a reads: "set overview frontmatter `approved: true` via direct Edit, append `plan-review-r{N}` to status timeline, commit+push both, break loop → Handoff." Replace it with the following expanded text (preserving the 4a label and keeping it as a single-sentence enumeration): "On `APPROVE` (verdict from JSON): set overview frontmatter `approved: true` via direct Edit. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`. Commit on the task branch: `git -C <worktree> add plan/ reviews/ status.md && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"`. Push. Break loop → Handoff." The phrase `reviews/` must be present in the git add command — this is the fix. `iso_ts` is `_timestamp.now_utc_iso()`.
- **Commit:** `fix(mill-plan): stage reviews/ in APPROVE commit (#170)`

### Card 4: Fix mill-plan 4c plan-fix commit to use reviews/ not reviews/<filename>

- **Reads:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In the "Phase: Plan Review" section, step 4c of `mill-plan/SKILL.md`, the final bullet currently reads: "Commit on the task branch: `git -C <worktree> add plan/ reviews/<filename> status.md && git commit -m "mill-plan: plan-fix round {N} for {slug}"`.". Change `reviews/<filename>` to `reviews/` so all review files (both the `millpy-review-plan.py` output and the fixer report) are staged. The corrected bullet: "Commit on the task branch: `git -C <worktree> add plan/ reviews/ status.md && git commit -m "mill-plan: plan-fix round {N} for {slug}"`.". No other changes to step 4c.
- **Commit:** `fix(mill-plan): stage all reviews in plan-fix commit (#170)`

## Batch Tests

`verify: null` — all changes are SKILL.md text edits with no runnable test surface. Correctness is confirmed by reading the final diff: each of the four git commit commands must stage `reviews/` (or the specific review file path) in addition to `status.md` or `plan/`. Run `python plugins/mill/unit_tests/run-all.py` as a smoke check to confirm no Python helper regressions (no helpers were modified).
