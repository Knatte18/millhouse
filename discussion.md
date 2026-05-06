# Discussion: 21 (A) — mill-go cleanliness gate fixes

```yaml
task: 21 (A) — mill-go cleanliness gate fixes
slug: mill-cleanliness-gate-fixes
status: discussing
parent: main
```

## Problem

mill-go's cleanliness gate (step 2b) is supposed to catch an implementer that left
uncommitted changes after reporting success. Three related defects make it fire as a
false positive on clean worktrees:

1. **Bug A (#166)**: `git status --porcelain` with its default `--untracked-files=normal`
   emits `?? reviews/` for any untracked directory, including the `reviews/` directory
   that mill-go itself creates for code review output. The gate treats this as dirt.

2. **Bug B (#165)**: The mill-go APPROVE commit (`git add status.md`) does not stage the
   code review file just written by `millpy-review-code.py`. That file sits untracked in
   `reviews/` and trips the cleanliness gate when the next batch starts.

3. **Bug C (#170)**: mill-plan's plan review commits leave the `millpy-review-plan.py`
   output file untracked. Step 4a ("commit+push both") stages only `plan/00-overview.md`
   and `status.md`. Step 4c stages the fixer report but not the review file. By the time
   mill-go starts, `reviews/` contains untracked plan review files.

All three bugs result in mill-go blocking a task that is actually clean, with the message
"uncommitted working tree after implementer report".

## Scope

**In:**
- mill-go SKILL.md: change the cleanliness gate to use `--untracked-files=no`
- mill-go SKILL.md: change the per-batch APPROVE commit to also stage the specific review
  file returned in the `millpy-review-code.py` JSON
- mill-plan SKILL.md: change step 4a APPROVE commit to stage `reviews/`
- mill-plan SKILL.md: change step 4c REQUEST_CHANGES+blocking commit to use `reviews/`
  instead of only the fixer report filename

**Out:**
- No changes to any Python helper scripts
- No changes to `millpy-review-code.py`, `millpy-review-plan.py`, or `millpy-implement.py`
- Holistic code review APPROVE path (mill-go) does not commit `reviews/`; this is a
  separate issue — holistic leaves no next cleanliness gate to trip and is out of scope
- No new unit tests; all three bugs live in SKILL.md orchestrator instructions, not in
  testable Python helpers

## Decisions

### cleanliness-gate-untracked-filter

- **Decision:** Change the cleanliness gate from `git status --porcelain` to
  `git status --porcelain --untracked-files=no`.
- **Rationale:** The gate's intent is "did the implementer leave staged or in-place
  changes uncommitted?" Untracked files are irrelevant to that question — the implementer
  is expected to `git add` new files before committing. `--untracked-files=no` maps
  directly to the intended check and requires no string post-processing.
- **Rejected:** Filtering `??` lines in a post-processing step — same outcome but more
  code with no advantage.

### approve-commit-review-file

- **Decision:** The per-batch APPROVE commit in mill-go's code review loop stages
  `status.md` and the specific review file path extracted from the `reviews[].file` field
  of the `millpy-review-code.py` JSON, i.e.
  `git add status.md <review_file_path> && git commit -m "mill-go: approve batch <name>"`.
- **Rationale:** We already have the exact file path from the JSON we just parsed. Using
  the precise path is self-documenting and avoids staging anything unexpected from
  `reviews/`.
- **Rejected:** `git add status.md reviews/` — simpler wording but stages everything
  currently in `reviews/`, which could include unrelated files from a prior partial run.

### mill-plan-review-commit-scope

- **Decision:** Both mill-plan plan-review commit sites use `reviews/` to sweep the whole
  directory:
  - Step 4a (APPROVE): `git add plan/ reviews/ status.md`
  - Step 4c (REQUEST_CHANGES+blocking): `git add plan/ reviews/ status.md`
- **Rationale:** At both points `reviews/` exists (at least one review file was just
  written by `millpy-review-plan.py`). The precise review file path is not as readily
  available in the 4c commit context (the fixer report is a separate new file, and the
  review file path is in the JSON from the previous CLI call). Using `reviews/` covers
  both files (review output + fixer report) in a single, readable `git add` command.
- **Rejected:** Tracking the exact review file path through 4c — more bookkeeping for no
  practical benefit; `reviews/` is always correct here.

## Technical context

All three bugs are in SKILL.md files that describe orchestrator behavior. The Python
helpers are correct; the fix is purely instructional:

- `plugins/mill/skills/mill-go/SKILL.md` — contains the cleanliness gate (step 2b) and
  the APPROVE branch of the code review loop (step 4).
- `plugins/mill/skills/mill-plan/SKILL.md` — contains plan review steps 4a and 4c.

**Cleanliness gate location** (mill-go SKILL.md, section "2b. Cleanliness gate"):

```
run `git -C <worktree> status --porcelain`
```

Change to:

```
run `git -C <worktree> status --porcelain --untracked-files=no`
```

**APPROVE commit location** (mill-go SKILL.md, section "3. Code Review loop", step 4, APPROVE bullet):

Current text:
```
Commit on the task branch: `git -C <worktree> add status.md && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"`.
```

The JSON summary from `millpy-review-code.py` has the shape:
```json
{"type":"code","round":N,"verdict":"APPROVE","reviews":[{"scope":"...","verdict":"...","file":"<abs-path>","session_id":"..."}]}
```
The review file path is `reviews[0].file` (for holistic, scope is "holistic"; for per-batch, scope is the batch name). Use the first entry's `file` field as `<review_file>`.

New commit instruction:
```
git -C <worktree> add status.md <review_file> && git -C <worktree> commit -m "mill-go: approve batch {batch_name}"
```

**mill-plan 4a location** (mill-plan SKILL.md, section "Phase: Plan Review", step 4a):

Current text (vague):
```
set overview frontmatter `approved: true` via direct Edit, append `plan-review-r{N}` to status timeline, commit+push both, break loop → Handoff.
```

The "commit+push both" needs to be explicit and include `reviews/`. mill-plan should:
1. Edit `plan/00-overview.md` to set `approved: true`
2. `_status.append_phase(status_path, f"plan-review-r{N}", iso_ts)`
3. `git -C <worktree> add plan/ reviews/ status.md && git -C <worktree> commit -m "mill-plan: approve plan for {slug}"`
4. Push, break loop → Handoff

**mill-plan 4c location** (mill-plan SKILL.md, section "Phase: Plan Review", step 4c, last bullet):

Current:
```
git -C <worktree> add plan/ reviews/<filename> status.md && git commit -m "mill-plan: plan-fix round {N} for {slug}"
```

Change to:
```
git -C <worktree> add plan/ reviews/ status.md && git commit -m "mill-plan: plan-fix round {N} for {slug}"
```

## Constraints

No CONSTRAINTS.md present. Discovered constraints:

- SKILL.md instructions are consumed verbatim by an orchestrator with no additional
  context. Every commit instruction must be fully specified (no "and so on").
- `git add reviews/` is safe only when `reviews/` exists. At mill-plan 4a and 4c this is
  guaranteed (the CLI just wrote at least one file there). At mill-go's APPROVE, we use
  the specific file path (from JSON) to avoid the non-existent-directory edge case.
- No Python script changes: the fixes must be self-contained in SKILL.md text to avoid
  touching the shared plugin that other repos depend on.

## Testing

These bugs live in SKILL.md orchestration instructions, not in Python helpers. No unit
tests can cover SKILL.md text directly. Correctness is verified by:

- Reading the final SKILL.md text in review and confirming each commit command stages the
  right files.
- Running `python plugins/mill/unit_tests/run-all.py` to confirm no regression in the
  Python helpers (none are changed, so this is a smoke check).

No new test files are created as part of this task.

## Q&A log

- **Q:** Bug A fix — `--untracked-files=no` or filter `??` lines? **A:** `--untracked-files=no`; simpler, no post-processing.
- **Q:** Bug B fix — stage specific review file or `reviews/`? **A:** Specific file from the JSON `reviews[].file` field; precise and we already have the path.
- **Q:** Bug C fix — how to expand the 4a and 4c commits? **A:** Both use `git add plan/ reviews/ status.md`; sweeping `reviews/` is safe at these points and covers both the review output and fixer report.
- **Q:** Should the holistic APPROVE path also be fixed to commit `reviews/`? **A:** Out of scope; holistic has no subsequent cleanliness gate to trip. Leave for a follow-up.
