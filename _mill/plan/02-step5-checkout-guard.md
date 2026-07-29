# Batch: step5-checkout-guard

```yaml
task: mill-merge misjudges worktree topology and mishandles Step 5 squash-restore checkout
batch: step5-checkout-guard
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py
depends-on: []
```

## Batch Scope

This batch delivers issue #736's fix: `mill-merge/SKILL.md` Step 5's restore-checkout currently exits 1 with a pathspec error in the common worktree-mode case (parent tracks nothing at `task_dir`), despite prose documenting it as a clean no-op. The fix guards the checkout with `2>/dev/null || true`, per the `step5-checkout-guard` Shared Decision, and corrects the prose that made the false no-op claim. The batch also adds integration coverage proving the guard actually fixes the halt — no existing `test-merge.py` scenario exercises this case (the existing true-worktree-mode scenario deliberately seeds a hub-side `_mill/status.md` specifically to dodge this exact bug). Independent of batch `is-inplace-topology-fix` — no shared files, no dependency either direction.

## Cards

### Card 6: Guard Step 5's restore-checkout in `mill-merge/SKILL.md`

- **Context:**
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - In Step 5's "Direct squash" bash block (lines 175-181), change line 178 from `git -C <parent-path> checkout -- "$TASK_DIR_REL"` to `git -C <parent-path> checkout -- "$TASK_DIR_REL" 2>/dev/null || true`, matching the existing swallow-idiom at `mill-merge-in/SKILL.md:37` (`OLD_CHK_SHA=$(git rev-parse --verify --quiet "$CHK" || true)`).
  - Update the `Why:` paragraph at line 185 — replace the sentence "This is a clean no-op when the parent tracks nothing at `task_dir`." with prose stating that a bare `git checkout -- <pathspec>` against a pathspec absent from `HEAD`'s tree exits 1 with `error: pathspec '...' did not match any file(s) known to git` (not a no-op), and that the `2>/dev/null || true` guard swallows exactly that narrow, expected failure mode. Keep the rest of the `Why:` paragraph (the #497 bug-2 corruption rationale) unchanged.
  - Do not modify line 177 (`git -C <parent-path> reset -q HEAD -- "$TASK_DIR_REL"`) — `git reset` against an absent pathspec already exits 0 (verified: no pathspec-match error the way `checkout` produces one), so it needs no guard.
  - Do not modify any other Step in this file.
- **Commit:** `fix(mill-merge): guard Step 5 restore-checkout against absent task_dir pathspec`

### Card 7: Add integration coverage for the Step 5 guard

- **Context:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Edits:**
  - `plugins/mill/integration_tests/test-merge.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
  - Insert a new scenario in `main()` immediately after the `print("PASS -- mill-merge end-to-end (flat-hub scenario)")` line (currently line 827) and before the `# === Phase-gate slug-mismatch fallback sub-scenario` comment (currently line 829). Use a fresh, self-contained fixture — do not reuse `hub`/`worktree`/`container` from `_setup_trio` (that fixture's hub already has a seeded `_mill/status.md` on `main` by this point in `main()`, from the true-worktree-mode #648 scenario earlier in the same function).
  - Mirror the lightweight single-repo fixture pattern already used for the dirty-parent-worktree preflight scenarios (lines 624-630): `git init -b main` at a new path `SCRATCH / f"merge-test-step5-guard-{uuid.uuid4().hex[:8]}"`, configure `user.email`/`user.name`, commit an initial `README.md`.
  - Create and check out a new branch (e.g. `task/guard-test`) off `main`, add a `_mill/status.md` file, commit it, then check back out to `main`. `main` now has no `_mill/` anywhere in its tree — the exact #736 case ("parent tracks nothing at `task_dir`").
  - Run `git -C <repo> merge --squash task/guard-test` on `main` (mirrors line 712's `merge --squash` call).
  - **Repro:** run a bare, unguarded `git -C <repo> checkout -- "_mill"` (`check=False`); assert `returncode != 0` and that combined stdout+stderr contains `did not match any file` — proves this fixture reproduces #736 before proving the fix, mirroring the `#648` repro sub-step's own structure (lines 714-745). This bare checkout touches neither the index nor the working tree on failure (same reasoning as the existing `#648` repro comment at lines 719-720), so no cleanup step is needed before the next assertion.
  - **Fix:** run `git -C <repo> reset -q HEAD -- "_mill"` (assert `returncode == 0` — a true no-op per the `step5-checkout-guard` Shared Decision's verified reset behavior), then run the corrected guarded form exactly as Card 6 writes it in the skill — invoke it via `subprocess.run("git checkout -- _mill 2>/dev/null || true", shell=True, cwd=str(repo), capture_output=True, text=True)` (the `||` guard is shell syntax, so this one call needs `shell=True` unlike every other `_run()` call in this file, which passes an argv list) — and assert `returncode == 0`.
  - Commit the result: `git -C <repo> commit -m "Demo guarded merge"`; assert the commit succeeds (mirrors line 757's commit step for the `#648` scenario).
  - Print `"PASS: Step 5 guarded checkout no longer halts when parent tracks nothing at task_dir (#736)"` on success.
  - This scenario is independent of the `hub`/`worktree`/`slug`/`child_branch`/`container` variables used throughout the rest of `main()` — it introduces no new module-level fixtures and does not require touching `_setup_trio`, `_setup_nested_hub_scenario`, or `_setup_nested_verify_plan`.
- **Commit:** `test(merge): add Step 5 guard coverage for parent-tracks-nothing-at-task_dir (#736)`

## Batch Tests

`verify:` runs the full `test-merge.py` integration test (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/test-merge.py`), unscoped, because this is the file's only test entry point — it has no `--only`-style file-set narrowing (integration tests run as standalone scripts, not through `run-all.py`'s unit-test harness), and Card 7's new scenario lives inside the same `main()` this command already executes end-to-end.
