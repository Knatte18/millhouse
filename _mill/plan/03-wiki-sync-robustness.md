# Batch: wiki-sync-robustness

```yaml
task: "Fix wiki push upstream, cleanliness gate, mojibake, container config, and stacked-branch finalize"
batch: "wiki-sync-robustness"
number: 3
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-wiki-sync.py
depends-on: []
```

## Batch Scope

Fixes GitHub issues #469 and #462, merged because both edit
`wiki/_sync.py`'s `commit_push`. #469: the bare `git push` fails with "no
upstream branch" when the wiki clone's default branch lacks tracking — replace
it with an explicit-refspec push and configure tracking in `_setup.py`'s
plain-clone paths. #462: when the wiki directory is not a git repo, the `git
add` raises an opaque `WikiPushError` carrying raw git stderr — detect the
not-a-git-repo condition early and raise a clear, actionable `WikiPushError`.
A regression test also locks the already-correct error mapping (push failure
surfaces as `WikiPushError`, never `WikiNotFoundError`). All git tests use the
existing tempfile bare-repo + clone pattern in `test-wiki-sync.py`.

## Cards

### Card 4: explicit-refspec push in commit_push

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_sync.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `wiki/_sync.py` `commit_push`, replace the bare
  `["git", "-C", str(wiki_path), "push"]` invocation (inside the 2-attempt
  retry loop) with an explicit-refspec push: first resolve the current branch
  via `git -C <wiki_path> rev-parse --abbrev-ref HEAD`, then push
  `["git", "-C", str(wiki_path), "push", "origin", f"HEAD:{branch}"]`. Keep the
  existing non-fast-forward retry/rebase behaviour and the
  `WIKI_DAEMON_SKIP_PUSH` short-circuit unchanged. The refspec form must not
  depend on `push.default` or `branch.*.remote` config. If the resolved branch is
  empty or the literal `HEAD` (detached HEAD), raise `WikiPushError` with an
  ASCII message rather than pushing the malformed `HEAD:HEAD` refspec.
- **Commit:** `fix(wiki): push with explicit refspec so untracked clones succeed (#469)`

### Card 5: detect non-git-repo wiki dir early

- **Context:**
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_sync.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `wiki/_sync.py` `commit_push`, before the `git add`
  step, detect when `wiki_path` is not a git repository (e.g. no `.git`
  entry, or `git -C <wiki_path> rev-parse --git-dir` fails) and raise
  `WikiPushError` with an ASCII message that names the path and states it is not
  a git repository — instead of letting the raw `fatal: not a git repository`
  stderr leak through. Do not add a new error class or change the
  `ERR_PUSH_FAILED` mapping in `wiki/_server.py` / `wiki/_client.py`; the
  existing `WikiPushError -> ERR_PUSH_FAILED -> WikiPushError` chain is correct
  and must be preserved (this card reads those files only to confirm the mapping
  is unchanged).
- **Commit:** `fix(wiki): clear error when wiki dir is not a git repo (#462)`

### Card 6: configure upstream tracking on wiki clone

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_setup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_setup.py` `clone_or_init`, in the plain-clone paths
  (Path C `git clone <url> <dest>` and Path D `git clone -b <branch>
  --single-branch <url> <dest>`), after a successful clone set upstream tracking
  using the `git config branch.<b>.remote origin` + `git config
  branch.<b>.merge refs/heads/<b>` form — matching the existing orphan-init
  path's convention — so freshly created clones configure tracking
  deterministically. Resolve `<b>` from the clone's current branch when
  `branch` is `None` (Path C). Keep the existing return-dict shapes and error
  handling.
- **Commit:** `fix(setup): configure upstream tracking on plain wiki clones (#469)`

### Card 7: wiki-sync robustness tests

- **Context:**
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/_setup.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-sync.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `test-wiki-sync.py`, add tests using the existing
  tempfile bare-repo + clone helpers: (1) a clone whose default branch has NO
  upstream tracking (`branch.<b>.remote`/`branch.<b>.merge` unset, `push.default`
  unset) — `commit_push` succeeds via the refspec path and the commit lands on
  the bare remote; (2) `commit_push` against a directory that is not a git repo
  raises `WikiPushError` whose message names the path / states "not a git
  repository" (and is NOT a different exception); (3) `_setup.clone_or_init`'s
  plain-clone path leaves `branch.<b>.remote`/`branch.<b>.merge` configured.
  Match the file's existing pass/fail harness.
- **Commit:** `test(wiki): cover refspec push, non-git dir, and clone tracking (#469, #462)`

## Batch Tests

`verify:` runs `test-wiki-sync.py` directly (not via `run-all.py`, which lists
it in its SKIP set). The file uses a real tempfile bare-repo + clone and is the
established home for `wiki/_sync.py` `commit_push` coverage; the new cases for
refspec push, non-git-repo detection, and `_setup` tracking belong here.
