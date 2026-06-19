# Batch: brief-commit-uniformity

```yaml
task: "Fix config unknown-key warning on git namespace and commit _mill/briefs/ after dispatch"
batch: brief-commit-uniformity
number: 2
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py test-gitignore-phase.py
depends-on: []
```

## Batch Scope

Make dispatch-brief committing uniform across all orchestrators so `_mill/briefs/` files (agent prompts + `.out.md` responses) reach branch history instead of being lost on `/mill-cleanup`. mill-go and mill-plan already stage `_mill/briefs/`; this batch fixes the two orchestrators that do not — **mill-start** (discussion-review brief) and **mill-merge-in** (merge-conflict + verify-fix briefs) — by editing their SKILL.md commit steps, then adds a content regression-lock test (idiomatic in this repo per `test-skill-helper-drift.py`). Pure SKILL prose plus one new test file; independent of batch 1 (no shared files). External interface: none.

## Cards

### Card 3: Commit _mill/briefs/ in mill-start's discussion-review commit steps

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `_mill/briefs/` to mill-start's commit pathspecs, mirroring the mill-go/mill-plan pattern (`git add ... _mill/briefs/`), at these sites:
  1. **Phase: Discussion Review, step 4b (interactive)** — the commit described as "Single git commit covering exactly three pathspecs — `<discussion_path>`, `<reviews_dir>/`, `<status_path>`": add `_mill/briefs/` so it covers four pathspecs. Unguarded (a brief always exists after a review round).
  2. **`## Auto mode`, step 4b (`--auto` variant)** — the commit "single commit covering `<discussion_path>` + `<reviews_dir>/` + `<status_path>`": add `_mill/briefs/`. Unguarded.
  3. **Phase: Discussion Review, step 5 (GAPS_FOUND)** — the command `git -C <worktree> add <discussion_path> <reviews_dir>/ && git commit -m "mill-start: discussion-gap-fix round {N} for {slug}"`: add `_mill/briefs/`. Unguarded.
  4. **Phase: Handoff** — the command `git -C <worktree> add <status_path> <reviews_dir> && git commit -m "mill-start: handoff {slug}"`: add `_mill/briefs/` **guarded**, because Handoff is reachable via the review-skip path (`rounds: 0` or `reviewer: null`) where no brief exists. Use the guard form `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi` immediately before the commit (keep `_mill/briefs/` out of the unconditional `git add`).
  5. **`## Auto mode` halt-commits (audit completeness)** — before the ERROR-only blocked commit (`... "mill-start: blocked (auto: discussion review ERROR) for <slug>"`) and the gaps-unresolved blocked commit, add the same guarded `if [ -d <worktree>/_mill/briefs ]; then git -C <worktree> add _mill/briefs/; fi` stage so an in-flight brief is preserved.
  Do not add a brief stage to the pre-review "Phase: Discussion File" commit (no brief exists yet). Do not touch mill-go or mill-plan.
- **Commit:** `fix(mill-start): commit _mill/briefs/ in discussion-review commit steps`

### Card 4: Add a trailing brief-commit step to mill-merge-in

- **Context:**
  - `plugins/mill/scripts/millpy-merge-in-subagent.py`
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Insert a new step between `### 5. Codeguide update` and `### 6. Report` — a `### 5.5 Commit dispatch briefs` step — that stages and commits any `_mill/briefs/` files, guarded for absence: `if [ -d <worktree>/_mill/briefs ] && [ -n "$(git -C <worktree> status --porcelain -- _mill/briefs)" ]; then git -C <worktree> add _mill/briefs/ && git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"; fi`. State that this captures **both** the `merge/conflicts` brief (written in step 3, `millpy-merge-in-subagent.py` line ~243) and the `merge/verify-fix` brief (written in step 4, line ~324, *after* the step-3 `git merge --continue` — which is why staging before `merge --continue` cannot capture it, and clean merges skip `merge --continue` entirely). The `git status --porcelain -- _mill/briefs` guard also covers the already-committed case: if a brief was somehow committed earlier in the run the porcelain output is empty and the step is skipped — no empty commit. Note it runs on the success path only: any failure in steps 2-5 triggers the Rollback (`git reset --hard "$CHK"`) before reaching this point, so the brief commit is intentionally outside rollback (it captures successful state). Do not renumber step 6 (Report); do not alter the no-op fast-path (step 1 returns early before any brief is written).
- **Commit:** `fix(mill-merge-in): commit dispatch briefs after verify`

### Card 5: Regression-lock the brief-commit steps

- **Context:**
  - `plugins/mill/skills/mill-start/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
  - `plugins/mill/unit_tests/test-skill-helper-drift.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-brief-commit.py`
- **Deletes:** none
- **Requirements:** Create a new unit test modeled on `test-skill-helper-drift.py`'s structure: resolve `HUB = Path(__file__).resolve().parent.parent.parent.parent` and `SKILLS = HUB / "plugins" / "mill" / "skills"`, read the SKILL.md files with `read_text`, and assert (robust substring/section checks, not exact-line matches, to limit brittleness):
  1. `mill-start/SKILL.md` references `_mill/briefs/` in its Handoff commit and in the discussion-gap-fix (step 5) and discussion-fix (step 4b) commit steps. **Primary form (preferred):** assert the substrings `mill-start: handoff`, `mill-start: discussion-gap-fix`, and `mill-start: discussion-fix` each have `_mill/briefs/` within a small window (e.g. +/- 300 chars of the commit-message marker). As a coarse backstop only, the total `_mill/briefs/` occurrence count in the file must be `>= 4` (5 add-sites land in mill-start: 4b interactive, 4b `--auto`, gap-fix, handoff guard, plus the `--auto` halt sites — `>= 4` tolerates wording drift while still catching a dropped site). Note `mill-start: discussion-fix` legitimately appears twice (interactive 4b ~line 181 and `--auto` 4b ~line 37), so do not assert single-occurrence.
  2. `mill-merge-in/SKILL.md` contains a `git ... add _mill/briefs/` step (assert the substring `_mill/briefs/` is present and appears in an `add` context).
  Provide a `main()` that runs a `tests = [...]` list, prints `PASS`/`FAIL` per test, returns 1 on any failure, with `if __name__ == "__main__": sys.exit(main())` — matching the convention used by `run-all.py` (which runs each `test-*.py` as a subprocess).
- **Commit:** `test(briefs): lock _mill/briefs commit steps in orchestrator SKILLs`

## Batch Tests

`verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-brief-commit.py test-skill-helper-drift.py test-gitignore-phase.py`. The new `test-brief-commit.py` locks the SKILL.md commit-step edits from cards 3-4. `test-skill-helper-drift.py` is included because it scans the same SKILL.md files for helper-reference drift — confirming the prose edits introduce no broken `_<module>.<fn>(` references. `test-gitignore-phase.py` confirms its existing `test_glob_entries_excludes_briefs` lock still holds (briefs remain un-ignored — the precondition that makes committing them meaningful). The SKILL.md changes have no Python code path of their own; the content-lock test is the automated gate, matching the regression-lock idiom already present in `test-skill-helper-drift.py`.
