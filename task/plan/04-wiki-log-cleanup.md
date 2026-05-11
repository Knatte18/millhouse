# Batch: wiki-log-cleanup

```yaml
task: 49 (A) — Defensive guards mot cwd-inni-wiki kjedereaksjoner
batch: wiki-log-cleanup
number: 4
cards: 1
verify: null
depends-on: []
```

## Batch Scope

One-time cleanup of the orphan log file the 2026-05-11 incident left in the wiki repo. The file `.scratch/bg-20260511-103712-review-discussion-r1.log` was committed to wiki origin at commit `2abb004` because `millpy-bg` ran with a wiki cwd and `wiki/.gitignore` has no `.scratch/` entry. The discussion explicitly chose to remove the file going forward (`git rm` + commit + push) rather than rewriting wiki history or adding the `.scratch/` exclusion. The guards in batch 1 prevent the same file ever being written to wiki again, so a forward-only fix is sufficient.

This batch does not modify the task worktree. The only commit it produces lives on the wiki repo's branch. Because the action is operational rather than code, `verify: null` and no automated test gates it. A post-batch smoke check confirms the file is gone from `<wiki_path>/.scratch/`.

Batch-local decision: the implementer marks the work done on the task branch via one empty commit (`git commit --allow-empty -m "chore(wiki-cleanup): rm orphan bg-log"`) so mill-go's per-batch commit tracking has a stable handle. The empty commit is harmless and survives mill-merge's squash.

## Cards

### Card 10: `git rm` orphan bg-log from wiki repo

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Requirements:** Perform a one-time cleanup of the orphan log in the wiki repo. Execute the following steps from the task worktree (so `_paths.resolve_git_root()` succeeds and is NOT inside the wiki):
    1. Resolve the wiki path: `wiki_path = _paths.resolve_wiki_path(_paths.resolve_git_root())`.
    2. Open a `_wiki.wiki_lock(wiki_path, slug="wiki-cleanup")` context.
    3. Inside the lock, call `_wiki.sync_pull(wiki_path, slug="wiki-cleanup")` to fast-forward the local wiki clone.
    4. Run `git -C <wiki_path> rm .scratch/bg-20260511-103712-review-discussion-r1.log` via `_subprocess_util.run`. Verify `returncode == 0`; on non-zero, raise `SystemExit` with the stderr text — do NOT swallow.
    5. Run `git -C <wiki_path> commit -m "wiki: rm orphan bg-log (.scratch/bg-20260511-103712-review-discussion-r1.log)"`. Verify `returncode == 0`.
    6. Run `git -C <wiki_path> push`. Verify `returncode == 0`.
    7. After exiting the lock, assert the file is gone: `not (wiki_path / ".scratch" / "bg-20260511-103712-review-discussion-r1.log").exists()`. Raise `SystemExit` if it still exists.
    8. Make ONE empty commit on the task worktree to mark the batch done: `git commit --allow-empty -m "chore(wiki-cleanup): rm orphan bg-log"`. This is required so mill-go's per-batch tracking sees a task-branch commit. Do NOT add `task/` changes here; the empty commit is the only task-branch artefact this batch produces.
  The implementer may execute steps 1–7 by writing a short inline `python -c "..."` block invoked via the `Bash` tool (with `PYTHONPATH="plugins/mill/scripts"` and the existing `uv run --project plugins/mill` invocation pattern used elsewhere in this repo), or by running raw `git -C` commands directly inside a `wiki_lock` context they enter explicitly via a `python -c` block. Either approach is acceptable; the helper-based path (`wiki_lock` + `sync_pull`) is preferred because the lockfile is honoured automatically. The implementer MUST NOT `cd` into the wiki directory at any point — the same anti-pattern this whole task exists to prevent.
- **Commit:** `chore(wiki-cleanup): rm orphan bg-log`

## Batch Tests

`verify: null`. The cleanup is an operational task on a different repo; there is no unit-test surface. The card's own assertion in step 7 (file no longer exists after push) is the verification, plus the `wiki` repo's HEAD on origin showing the new commit. After the batch lands, a manual `ls C:/Code/millhouse/wiki/.scratch/` (or the platform equivalent) shows zero files matching `bg-*-review-discussion-r1.log`.
