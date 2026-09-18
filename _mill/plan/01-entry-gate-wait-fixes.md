# Batch: entry-gate-wait-fixes

```yaml
task: 'mill-plan: entry-gate wait for upstream mill-start misses discussion-gap-fix-r{N} and races the pinning commit'
batch: entry-gate-wait-fixes
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-phase-wait.py
depends-on: []
```

## Batch Scope

This batch delivers both fixes from `_mill/discussion.md` in one pass: mill-plan's Entry-gate wait trigger list is widened to match `discussion-gap-fix-r{N}` (closing #1041/#1028), and `_phase_wait.build_wait_command` gains an opt-in clean-git-tree gate that mill-plan's own wait call site now uses (closing #1029). It is one batch because all three changes are small, sequentially dependent edits to the same narrow subsystem — the extended `build_wait_command` signature (card 1) must exist before the call site that passes the new keyword arguments (card 2) can be written, and the widened trigger list plus the new keyword arguments both need to exist before the tests exercising them (card 3) can be written. There is no external interface for a later batch to consume — this plan has only one batch.

Batch-local decisions beyond the overview's Shared Decisions: none.

## Cards

### Card 1: Extend `build_wait_command` with opt-in clean-tree gating

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_phase_wait.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend `build_wait_command`'s signature to accept two new keyword-only parameters, inserted after the existing `giveup_s: int` parameter: `clean_tree_root: Path | None = None` and `clean_tree_paths: list[Path] | None = None`.
  At the top of the function body, before the existing `quoted_path = f'"{status_path}"'` line, add a guard: raise `ValueError("build_wait_command: clean_tree_root and clean_tree_paths must both be provided together, or both omitted")` when exactly one of `clean_tree_root` / `clean_tree_paths` is not `None` while the other is `None` (i.e. `(clean_tree_root is None) != (clean_tree_paths is None)`).
  When both `clean_tree_root` and `clean_tree_paths` are non-`None`, the rendered script's `READY` branch must additionally require a clean git tree for `clean_tree_paths` before echoing `READY`: wrap the existing `echo "READY"` / `exit 0` pair in a nested `if [ -z "$(git -C "<clean_tree_root>" status --porcelain -- "<path1>" "<path2>" ...)" ]; then ... fi` block, where `<clean_tree_root>` is `clean_tree_root` rendered double-quoted exactly like `quoted_path` already double-quotes `status_path` (i.e. `f'"{clean_tree_root}"'`), and `<path1> <path2> ...` is every entry of `clean_tree_paths`, each individually rendered double-quoted the same way and space-joined, appended after the `--` pathspec separator already shown in the `git status --porcelain --` shape above. When the phase-value grep matches but this git-status check is non-empty (dirty tree), do not echo `READY` and do not exit — fall through to the existing `elapsed`/`giveup_s` timeout-and-sleep logic unchanged, exactly as a non-matching phase value already does today; do not add a second, separate elapsed-increment code path for the dirty-tree case, since the existing per-iteration accounting already runs once regardless of which branch was taken.
  When `clean_tree_root` and `clean_tree_paths` are both omitted (the default, `None`/`None`), the function must render byte-identical output to today's — the plain unwrapped `echo "READY"` / `exit 0` pair, no nested `if`.
  Update the function's docstring: add `clean_tree_root` and `clean_tree_paths` entries to the `Args:` section, in the same style as the existing `status_path`/`ready_phase`/`poll_interval_s`/`giveup_s` entries, stating that `READY` is additionally withheld while `git -C clean_tree_root status --porcelain -- <clean_tree_paths>` reports any output, and that omitting both parameters (the default) reproduces today's behavior exactly. Add one sentence to the docstring's opening summary paragraph mentioning this optional clean-tree gating. Update the module-level docstring's `Public API` listing for `build_wait_command` with the same one-sentence addition.
- **Commit:** `feat(phase-wait): add opt-in clean-tree gate to build_wait_command`

### Card 2: Widen mill-plan's Entry-gate wait trigger and wire in clean-tree gating

- **Context:**
  - `plugins/mill/scripts/_phase_wait.py`
  - `plugins/mill/skills/mill-go-base/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Apply four edits to the `### Entry-gate wait for upstream mill-start` section of `mill-plan/SKILL.md`. Do not touch `mill-go-base/SKILL.md`'s own, already-correct copy of this pattern (its trigger list already includes `discussion-gap-fix-r{N}`, and its own wait is explicitly out of scope for this task per `_mill/discussion.md`).
  1. In the Entry step-4 phase table, the row whose condition column reads `` `phase: discussing`, or matching `^discussion-fix-r\d+$` ``: append `` / `^discussion-gap-fix-r\d+$` `` to the condition column (so it reads `` `phase: discussing`, or matching `^discussion-fix-r\d+$` / `^discussion-gap-fix-r\d+$` ``), leaving the action column unchanged.
  2. The line `` matched = _phase_wait.matches_wait_trigger(phase, {"discussing"}, [r"^discussion-fix-r\d+$"]) ``: change the `regex_patterns` list argument to `[r"^discussion-fix-r\d+$", r"^discussion-gap-fix-r\d+$"]`.
  3. The paragraph immediately below that call, beginning "The trigger is now widened to also match `discussion-fix-r{N}`.": reword its first sentence to "The trigger is now widened to also match `discussion-fix-r{N}` and `discussion-gap-fix-r{N}`." Keep the rest of that paragraph (the #821/commit-`ab1786d6` explanation) unchanged, and append one new sentence after it citing `mill-start/SKILL.md`'s Phase: Discussion Review step 5 (the plain-interactive gap-resolution path — under `--auto`/`--orch`, step 5 is skipped entirely, so `discussion-gap-fix-r{N}` never appears in that mode) as the site that writes, commits, and pushes `discussion-gap-fix-r{N}` as its own standalone phase when the final batch of a review round's gap answers is applied, before the loop continues to round N+1 — mirroring the `discussion-fix-r{N}` gap this same paragraph already describes for issue #821.
  4. The bullet `` - Build the command: `cmd = _phase_wait.build_wait_command(status_path, "discussed", 10, giveup_s)`. ``: first, insert a new sibling bullet immediately before it, at the same indentation level, inside the same `` - **If `matched` is `True` and `entry_wait` is `True`:** `` block: `` - Derive `discussion_path = _paths.resolve_task_path(worktree_root, cfg['paths']['discussion_file'])` (the same `resolve_task_path` pattern `Path Setup` already uses for `status_path`; `discussion_path` is not otherwise bound this early in mill-plan's Entry section). `` Then change the `Build the command:` bullet's call itself to pass the two new keyword arguments: `` cmd = _phase_wait.build_wait_command(status_path, "discussed", 10, giveup_s, clean_tree_root=git_root, clean_tree_paths=[status_path, discussion_path]) `` — `git_root` is already bound at Entry step 1 of this same file. Append one sentence to this bullet's prose, after its existing sentence, stating that passing `clean_tree_root`/`clean_tree_paths` makes the wait's `READY` condition additionally require a clean git tree for `status_path` and `discussion_path`, so `READY` fires only once mill-start's own commit for the corresponding phase transition has actually landed, not merely once the phase value is written to the working tree — closing the pinning race described in `_mill/discussion.md`'s "Gate `READY` on a clean tree, not just phase value" Decision (GitHub issue #1029).
- **Commit:** `fix(mill-plan): widen entry-gate wait trigger and gate READY on a clean tree`

### Card 3: Unit test coverage for both fixes

- **Context:**
  - `plugins/mill/scripts/_phase_wait.py`
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Edits:**
  - `plugins/mill/unit_tests/test-phase-wait.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Add five new cases to `plugins/mill/unit_tests/test-phase-wait.py`'s `main()`, inserted after the existing "Case 15" block and before the `print("All _phase_wait unit tests passed.")` line, numbered Case 16 through Case 20, following this file's existing style exactly (a `# Case N: ...` comment, `assert` statements, then a `print("PASS: ...")` line reporting what passed; wrap any exception-raising case in `try`/`except` per the pattern already used elsewhere in this repo's unit tests, e.g. `plugins/mill/unit_tests/test-sibling.py`'s Case 1 — `try: <call that should raise>; raise AssertionError("expected ValueError for ...") except ValueError as exc: assert "<message substring>" in str(exc)`).
  Case 16 — `matches_wait_trigger` against mill-plan's own (now-widened) 2-pattern trigger list, mirroring Case 15's shape but scoped to the list `mill-plan/SKILL.md`'s Entry-gate wait now uses (`exact={"discussing"}`, `regexes=[r"^discussion-fix-r\d+$", r"^discussion-gap-fix-r\d+$"]`): assert `matches_wait_trigger("discussion-gap-fix-r12", {"discussing"}, [r"^discussion-fix-r\d+$", r"^discussion-gap-fix-r\d+$"])` is true, assert the same call with `"discussion-fix-r3"` is true, and assert the same call with the near-miss `"discussion-fixed-r3"` is false.
  Case 17 — `build_wait_command` regression: assert the module-level `cmd` variable already built at the top of `main()` (`build_wait_command(Path("/tmp/status.md"), "planned", 10, 7200)`, no keyword arguments) equals this exact hardcoded golden string, so the assertion discriminates a real regression instead of merely comparing two identical calls to a pure function against each other:
  ```python
  expected = (
      "elapsed=0\n"
      "while true; do\n"
      "  if tr -d '\\r' < \"/tmp/status.md\" | grep -q \"^phase: planned$\"; then\n"
      "    echo \"READY\"\n"
      "    exit 0\n"
      "  fi\n"
      "  if [ \"$elapsed\" -ge 7200 ]; then\n"
      "    echo \"TIMEOUT after ${elapsed}s waiting for phase: planned\"\n"
      "    exit 2\n"
      "  fi\n"
      "  sleep 10\n"
      "  elapsed=$((elapsed + 10))\n"
      "done\n"
  )
  assert cmd == expected
  ```
  confirming that omitting the two new keyword arguments reproduces today's exact output, byte-for-byte, against a fixed baseline rather than a second live call.
  Case 18 — `build_wait_command` with `clean_tree_root`/`clean_tree_paths` supplied: call `build_wait_command(Path("/tmp/status.md"), "planned", 10, 7200, clean_tree_root=Path("/tmp/repo"), clean_tree_paths=[Path("/tmp/status.md"), Path("/tmp/discussion.md")])` and assert the rendered string contains `git -C "/tmp/repo" status --porcelain -- "/tmp/status.md" "/tmp/discussion.md"`, and that this git-status guard line appears before the `echo "READY"` line, and that `echo "READY"` is still nested inside an `if` whose condition references that same `git -C "/tmp/repo" status --porcelain` invocation (assert by string content only — this test file never executes rendered bash outside Case 13/20's dedicated tempdir-git subprocess pattern).
  Case 19 — `build_wait_command` raises `ValueError` when exactly one of `clean_tree_root`/`clean_tree_paths` is supplied: one sub-case with `clean_tree_root=Path("/tmp/repo")` and `clean_tree_paths=None` (default), one sub-case with `clean_tree_root=None` (default) and `clean_tree_paths=[Path("/tmp/status.md")]`; both must raise `ValueError` whose message contains the substring `"must both be provided together"`.
  Case 20 — end-to-end dirty-then-clean execution, required (not optional) per `_mill/discussion.md`'s Testing section, mirroring Case 13's real `subprocess.run(["bash", "-c", ...])` pattern inside a `tempfile.TemporaryDirectory()`: initialize a git repo in the tempdir (`subprocess.run(["git", "init", ...], cwd=tmp, ...)`, then set a throwaway `user.email`/`user.name` via `git -C <tmp> config` so the later commit succeeds non-interactively), write `status.md` there with `phase: planned\n` and commit it, then build `dirty_cmd = build_wait_command(status_path, "planned", 1, 5, clean_tree_root=Path(tmp), clean_tree_paths=[status_path])`; before making any further change, run `dirty_cmd` via `subprocess.run(["bash", "-c", dirty_cmd], ..., timeout=10)` and assert it returns exit code 2 (`TIMEOUT after ...`) because the phase already matches but nothing is dirty yet is the wrong state to assert READY-withheld from — instead, immediately after the initial commit, append an uncommitted change to `status.md` (rewrite its content, still `phase: planned\n`, so the working tree shows a modification against the committed blob) and run `dirty_cmd` again with the same short `giveup_s=5`/`poll_interval_s=1` budget, asserting exit code 2 (timeout) because the tree is dirty for the whole budget and `READY` must never fire. Then `git -C <tmp> add status.md && git -C <tmp> commit` the pending change (clean the tree) and run `dirty_cmd` a third time, asserting exit code 0 and stdout `"READY"`, confirming `READY` fires once the tree is clean. Wrap the whole case in the same `try: ... except FileNotFoundError: print("SKIP: ...")` fallback Case 13 already uses, for a host with no `git`/`bash` on `PATH`.
- **Commit:** `test(phase-wait): cover mill-plan's widened trigger list and clean-tree gating`

## Batch Tests

`verify:` runs `plugins/mill/unit_tests/test-phase-wait.py` directly — the sole file this batch's tests live in, and the only test file touched. This is a full run of that one file (not `run-all.py`), consistent with the "Single test file" pattern in `mill-plan/SKILL.md`'s "Verify command scope" guidance; no `--only` scoping is needed since the command already targets exactly one file.
