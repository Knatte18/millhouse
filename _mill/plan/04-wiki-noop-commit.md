# Batch: wiki-noop-commit

```yaml
task: '66 (A) -- Review sandbox follow-up: guard exceptions + bare-exit + sandbox argv'
batch: wiki-noop-commit
number: 4
cards: 2
verify: python plugins/mill/unit_tests/test-wiki-noop-commit.py
depends-on: []
```

## Batch Scope

Replace `_wiki._write_commit_push_body`'s English-locale `"nothing to commit"` stdout-substring fallback with a positive check via `git diff --cached --quiet` (#337). The new check runs immediately after `git add --` and detects "nothing staged" deterministically and locale-independently. The fallback branch at the existing `git commit` failure path is removed. The `WikiPushError` message for an actual `git commit` failure is upgraded to include both stdout and stderr so non-empty-stdout failures stay debuggable. Add a unit test that exercises the no-op path against a fixture wiki where the staged file is rewritten with identical content.

External interface: `write_commit_push` signature unchanged. Callers that relied on a clean return for the no-op case continue to work; the new behaviour is strictly more reliable.

## Cards

### Card 12: rewrite `_write_commit_push_body` to detect no-op staging via `git diff --cached --quiet`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_wiki._write_commit_push_body` (currently lines 465-506 of `_wiki.py`):

  1. Immediately after the `git add` call (lines 472-476), run `_subprocess_util.run(["git", "-C", str(wiki_path), "diff", "--cached", "--quiet"])`. If `returncode == 0`, log `[wiki] write_commit_push: no changes staged, skipping commit` to stderr (use `print(..., file=sys.stderr)` matching existing log style) and `return` cleanly (do not commit, do not push). If `returncode == 1`, proceed to the existing `git commit` path. If `returncode != 0 and != 1` (real git error), raise `WikiPushError(f"git diff --cached --quiet failed: {result.stderr.strip()!r}")`.
  2. Remove the `combined = (commit.stdout or "") + (commit.stderr or ""); if "nothing to commit" in combined: ... return` fallback branch (currently lines 482-485). The positive check upstream supersedes it.
  3. Update the `WikiPushError` message at the remaining `git commit` failure line (currently line 486) from `f"git commit failed: {commit.stderr.strip()!r}"` to `f"git commit failed: stderr={commit.stderr.strip()!r} stdout={commit.stdout.strip()!r}"`. This keeps stderr-only failures readable while making stdout-only failures actionable.

  Do not touch the rebase-retry loop (lines 488-506) or the `clone_or_init`, `health_check`, `sync_pull`, `_acquire`, `_release`, `wiki_lock` functions in the same file. The only public-API behaviour change is that callers no longer see a `WikiPushError("git commit failed: ''")` for legitimately-no-op commits -- they now get a clean return.
- **Commit:** `fix(wiki): detect no-op staging via git diff --cached --quiet, capture full commit stderr+stdout`

### Card 13: unit test for the no-op commit path against a temp wiki fixture

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/_test_helpers.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-noop-commit.py`
- **Deletes:** none
- **Requirements:** Create a `unittest.TestCase` test file covering three cases against a temporary git repo set up as a "wiki" (one initial commit so HEAD has a SHA; configure user.name/user.email). The test calls `_wiki.write_commit_push(wiki_path, relative_paths, commit_msg, slug="test")` directly -- the wiki-lock is real but uses the temp dir so it is isolated.

  1. `test_noop_unchanged_file` -- arrange a tracked file `Home.md` with known content. Call `write_commit_push(wiki, ["Home.md"], "msg", slug="test")`. Expect: no exception, no new commit on HEAD (assert `git rev-parse HEAD` is unchanged), no remote push attempted. Use `unittest.mock.patch` on `_subprocess_util.run` to ASSERT the sequence of git commands invoked is `[git add, git diff --cached --quiet]` AND `git commit` is NOT invoked AND `git push` is NOT invoked. Alternatively (if mocking is too invasive), set up a temp bare repo as remote, observe that HEAD is unchanged and the remote's HEAD is unchanged.
  2. `test_noop_rewrite_identical_content` -- arrange the tracked file. Inside the test, rewrite `Home.md` with the EXACT SAME content it already has (so the file mtime changes but content does not). Call `write_commit_push`. Expect: same as case 1 (no commit, no push). This is the regression for #337's original symptom.
  3. `test_real_change_commits_normally` -- arrange the tracked file. Modify it to have different content. Call `write_commit_push`. Expect: HEAD advances by one commit; the commit message matches what was passed. Push is attempted (mock the push command if no remote is configured) and treated as success.

  Do not test the rebase-retry path -- that is existing behaviour and out of this batch's scope.

  Standalone-runnable (`python plugins/mill/unit_tests/test-wiki-noop-commit.py`) and via `run-all.py`.
- **Commit:** `test(wiki): cover no-op commit path including identical-content rewrite (#337)`

## Batch Tests

`verify:` runs `test-wiki-noop-commit.py`. The three cases (unchanged file, identical-content rewrite, real change) cover every branch of the new check. No other test file is affected by this batch's change.
