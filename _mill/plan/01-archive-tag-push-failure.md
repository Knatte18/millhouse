# Batch: archive-tag-push-failure

```yaml
task: 'Self-discovered mill pipeline bugs: silent archive-tag push failure, ignored --max-rounds override, dead test-registry helper, truncated commit_sha in implementer reports'
batch: archive-tag-push-failure
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-archive-tag-conflict.py
depends-on: []
```

## Batch Scope

Adds push-failure visibility to `_archive_tag.create_or_resolve`'s four best-effort `git push` call sites (`created`, `noop`, `force_update`, `moved_aside`), threads the new `push_failed`/`push_error` fields through mill-merge Step 6 as a non-halting operator warning, and extends the existing local-git test file with a bare-remote fixture covering both successful and rejected pushes for every action. One batch: the producer (`_archive_tag.py`), its sole caller (`mill-merge/SKILL.md` Step 6), and the test file that exercises the new fields form one indivisible change — Step 6 cannot read a field `_archive_tag.py` doesn't yet emit, and the new test assertions need Card 1's dict shape to exist first. No batch-local decisions differ from `## Shared Decisions` in the overview.

## Cards

### Card 1: Add push_failed/push_error reporting to `_archive_tag.create_or_resolve`

- **Context:** none
- **Edits:**
  - `plugins/mill/scripts/_archive_tag.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `create_or_resolve` (`plugins/mill/scripts/_archive_tag.py`), capture the `CompletedProcess` returned by every `_subprocess_util.run([..., "push", ...], check=False)` call instead of discarding it, and add `push_failed: bool` and `push_error: str | None` keys to every returned dict:
  - `created` branch (~lines 60-74): capture the `git push origin <tag_name>` call's result into a variable (e.g. `push_result`); set `push_failed = push_result.returncode != 0` and `push_error = push_result.stderr.strip() if push_failed else None`; include both keys in the returned dict alongside the existing `action`/`tag`/`moved_aside_to`.
  - `noop` branch (~lines 83-90): no push is attempted here — return `push_failed: False, push_error: None` unconditionally, so the key is never absent regardless of action.
  - `force_update` branch (~lines 98-114): same capture-and-report pattern as `created`, applied to the `git push --force-with-lease origin <tag_name>` call.
  - `moved_aside` branch (~lines 116-171): capture both push results — the `moved_aside_tag` push and the primary `tag_name` `--force-with-lease` push. Set `push_failed = moved_aside_push.returncode != 0 or primary_push.returncode != 0` (OR of both). Build `push_error` as a combined string naming which push(es) failed: `"moved-aside tag push failed: <stderr>"` when only the moved-aside push failed, `"primary tag push failed: <stderr>"` when only the primary push failed, and both messages joined with `" | "` when both fail; `None` when neither fails.
  - Update the function's docstring `Returns:` section to document the two new keys (`push_failed`, `push_error`) alongside the existing three.
  - The underlying `git push` calls stay `check=False` — only the returncode/stderr inspection and the returned dict shape change.
- **Commit:** `fix(archive-tag): surface push failures via push_failed/push_error`

### Card 2: Read push_failed in mill-merge Step 6 and warn without halting

- **Context:**
  - `plugins/mill/scripts/_archive_tag.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `plugins/mill/skills/mill-merge/SKILL.md`'s "### 6. Archive tag" section, inside the inline Python snippet, after the existing `if result['moved_aside_to']:` block (which prints the moved-aside message), add a new conditional block reading the Card 1 fields: `if result.get('push_failed'): print(f'[mill-merge] WARNING: archive tag push failed -- reconcile {result["tag"]} with remote manually: {result.get("push_error")}')`. Use `.get()` (not direct subscript) for both `push_failed` and `push_error` reads — unlike the existing `result["action"]`/`result['moved_aside_to']` direct-subscript reads in this snippet, `.get()` is required here specifically because both fields are new and a not-yet-upgraded `_archive_tag.py` (or an older cached copy) would otherwise raise `KeyError` instead of just skipping the warning. Do not halt Step 6 or block any subsequent step (Home.md flip, lock release, notify) when `push_failed` is true — this is a warning only.
- **Commit:** `docs(mill-merge): warn on archive-tag push failure without halting`

### Card 3: Extend test-archive-tag-conflict.py with push-outcome coverage

- **Context:**
  - `plugins/mill/scripts/_archive_tag.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-archive-tag-conflict.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** Extend the `TestArchiveTagConflict` class in `plugins/mill/unit_tests/test-archive-tag-conflict.py` (do not create a new file — this file already provides `_init_repo`/`_make_commit`/`_get_head_sha` fixture helpers) with a bare-remote fixture and new test methods covering the `push_failed`/`push_error` fields added by Card 1:
  - Add a new fixture helper `_init_bare_remote(self, worktree: Path, tmp: Path, reject_ref_names: set[str] | None = None) -> Path` that: creates a bare repo at `tmp / "remote.git"` via `git init --bare <path>`; when `reject_ref_names` is given, writes an executable (`chmod 0o755`) `hooks/pre-receive` shell script (`#!/bin/sh` shebang) inside the bare repo that reads each `<old> <new> <refname>` line from stdin and exits non-zero (after printing a `rejected: <refname>` line to stderr) if any line's `refname` is in `reject_ref_names`, else exits 0; adds the bare repo as `origin` via `git -C <worktree> remote add origin <bare-path>`; returns the bare repo path. This decouples the test from `--force-with-lease`'s remote-tracking-ref semantics (this fixture never runs `git fetch`, so relying on real lease-conflict detection would be git-version-dependent) — the hook gives deterministic, per-push accept/reject control instead.
  - `test_created_push_success_reports_no_failure`: fresh worktree (`_init_repo`), bare remote with no rejections (`_init_bare_remote(worktree, tmp_path)`), call `create_or_resolve(worktree, "test-slug", "HEAD")`; assert `result["action"] == "created"`, `result["push_failed"] is False`, `result["push_error"] is None`.
  - `test_noop_reports_no_push_attempted`: fresh worktree with the tag pre-created at `HEAD` (no bare remote needed — `noop` never pushes); call `create_or_resolve`; assert `result["action"] == "noop"`, `result["push_failed"] is False`, `result["push_error"] is None`.
  - `test_created_push_rejected_reports_push_failed_true`: fresh worktree, bare remote with `reject_ref_names={"refs/tags/archive/test-slug"}`; call `create_or_resolve`; assert `result["action"] == "created"`, `result["push_failed"] is True`, `result["push_error"]` is a non-empty string.
  - `test_force_update_push_rejected_reports_push_failed_true`: worktree with the tag pre-created at the ancestor commit, a new commit made afterward (mirrors `test_ancestor_sha_force_updates`'s setup), bare remote created with `reject_ref_names={"refs/tags/archive/test-slug"}` immediately before calling `create_or_resolve`; assert `result["action"] == "force_update"`, `result["push_failed"] is True`, `result["push_error"]` is a non-empty string.
  - `test_moved_aside_partial_push_failure_names_which_tag`: worktree diverged via an orphan branch (mirrors `test_divergent_sha_moves_aside_to_01`'s setup), bare remote created with `reject_ref_names={"refs/tags/archive/test-slug"}` (rejects only the primary tag, allows the moved-aside tag) immediately before calling `create_or_resolve`; assert `result["action"] == "moved_aside"`, `result["moved_aside_to"] == "archive/test-slug-01"`, `result["push_failed"] is True`, `"primary"` is present in `result["push_error"]`, `"moved-aside"` is absent from it.
  - `test_moved_aside_both_pushes_rejected_combines_errors`: same divergent setup, bare remote created with `reject_ref_names={"refs/tags/archive/test-slug", "refs/tags/archive/test-slug-01"}`; assert `result["push_failed"] is True` and both `"primary"` and `"moved-aside"` are present in `result["push_error"]`.
  - Every new test creates its own `tempfile.TemporaryDirectory()` container and passes a fresh subdirectory (e.g. `Path(tmp) / "work"`) to `_init_repo`, so the worktree and the bare "remote" live as sibling directories inside the same temp container (matching the existing `_init_repo(self, tmp: Path)` signature, which calls `git init <tmp>` directly on the path it is given).
- **Commit:** `test(archive-tag): cover push_failed/push_error across all four actions`

## Batch Tests

`verify:` runs `test-archive-tag-conflict.py` directly (a `unittest.TestCase`-based file invoked via its own `if __name__ == "__main__": unittest.main()`), covering both the five pre-existing tests and the six new ones added by Card 3. Scoped to this one file since `_archive_tag.py`'s only production caller is `mill-merge/SKILL.md`'s inline Python snippet (Card 2), which has no dedicated automated test in this repo (mill-merge's SKILL.md scripts are exercised via the `integration_tests/` merge flow, out of scope for this batch's unit-level fix).
