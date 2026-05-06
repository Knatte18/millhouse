# Batch: helpers

```yaml
task: '4 (A) — mill-setup: --from-url for separate wiki repo'
batch: helpers
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch delivers two new helpers plus their unit tests. After this batch:

- `_wiki.clone_or_init(url, branch, dest)` encapsulates the clone-with-branch / clone-default-HEAD / init-orphan / pull-existing decision tree, and surfaces mismatch errors via a new `WikiSetupError` exception.
- `_config.set_local_wiki_overrides(cfg_path, repo_url, branch)` writes / updates the nested `wiki:` block in `.millhouse/config.local.yaml`, idempotently.

Both helpers are pure (no global state) and are unit-tested in isolation by mocking `_subprocess_util.run` and using `tempfile.TemporaryDirectory()` for filesystem paths. The mill-setup SKILL.md (next batch) calls these helpers from inline Python — the helpers' external interface (signatures, return types, raised exceptions) is the contract this batch publishes.

Batch-local decision: Card 1 introduces `WikiSetupError` (new exception class). Existing `WikiPushError` is reserved for push/rebase failures and stays untouched.

## Cards

### Card 1: Add `_wiki.clone_or_init` helper

- **Reads:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add a new exception class `WikiSetupError(Exception)` near the top of `_wiki.py`, alongside the existing `WikiPushError` class. Use it for all clone/init/mismatch failures introduced in this card.

  Add `clone_or_init(url: str, branch: str | None, dest: Path) -> dict` to `_wiki.py`. The helper covers four code paths and raises `WikiSetupError` for the unrecoverable cases.

  Path A — `dest` already exists and `dest / ".git"` exists:
  - Run `git -C <dest> remote get-url origin`. On non-zero return: raise `WikiSetupError(f"git -C {dest} remote get-url origin failed: {stderr}")`. On success, parse stdout (strip trailing whitespace) as `actual_url`. If `actual_url != url`: raise `WikiSetupError(f"wiki at {dest} has origin {actual_url!r}, expected {url!r}; remove or fix the wiki dir manually")`.
  - If `branch is not None`: run `git -C <dest> branch --show-current`. Parse stdout as `actual_branch` (strip whitespace). If `actual_branch != branch`: raise `WikiSetupError(f"wiki at {dest} is on branch {actual_branch!r}, expected {branch!r}; remove or fix the wiki dir manually")`. (When `branch is None`, skip the branch check — the caller did not pin a branch.)
  - Run `git -C <dest> pull --ff-only`. On non-zero: raise `WikiPushError(f"git pull --ff-only failed: {stderr}")` (existing exception used for fetch/push failures).
  - Return `{"action": "pulled", "branch_existed_on_remote": None}`.

  Path B — `dest` exists but is not a git repo (`dest / ".git"` missing):
  - Raise `WikiSetupError(f"{dest} exists but is not a git repository; move or remove it and re-run")`.

  Path C — `dest` does not exist, `branch is None`:
  - Run `git clone <url> <dest>`. On non-zero: raise `WikiSetupError(f"git clone {url} {dest} failed: {stderr}")`.
  - Return `{"action": "cloned", "branch_existed_on_remote": None}`.

  Path D — `dest` does not exist, `branch is not None`:
  - Run `git ls-remote --heads <url> <branch>`. On non-zero: raise `WikiSetupError(f"git ls-remote --heads {url} {branch} failed: {stderr}")`. The caller (Phase 2 in mill-setup) is responsible for translating this to a user-facing reachability message.
  - If stdout (stripped) is non-empty: branch exists on remote.
    - Run `git clone -b <branch> --single-branch <url> <dest>`. On non-zero: raise `WikiSetupError(f"git clone -b {branch} --single-branch {url} {dest} failed: {stderr}")`.
    - Return `{"action": "cloned", "branch_existed_on_remote": True}`.
  - If stdout is empty: branch missing on remote, init orphan path.
    - `git init <dest>` (run with `<dest>` as a positional arg, not `-C`). On non-zero: raise `WikiSetupError`.
    - `git -C <dest> remote add origin <url>`. On non-zero: raise.
    - `git -C <dest> checkout --orphan <branch>`. On non-zero: raise.
    - `git -C <dest> config branch.<branch>.remote origin`. On non-zero: raise.
    - `git -C <dest> config branch.<branch>.merge refs/heads/<branch>`. On non-zero: raise.
    - Return `{"action": "initialized", "branch_existed_on_remote": False}`.

  Every subprocess call goes through `_subprocess_util.run(argv)` (the existing pattern in `_wiki.py`). Argv lists are explicit (no shell). Paths are passed as `str(path)`.

  The helper does NOT log or print to stderr — that is the caller's job. (Compare with `sync_pull` / `write_commit_push` which do print: those existing helpers' logging stays unchanged in this card; the new helper is silent so callers can shape the user-facing message in mill-setup's Phase 2 / Phase 3 prose.)

  Add a clear module-level docstring entry / function docstring summarising the four paths, the return-dict shape, and the two exception types.

- **Commit:** `feat(wiki): add clone_or_init helper for --from-url/--branch`

### Card 2: Unit tests for `_wiki.clone_or_init`

- **Reads:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/unit_tests/test-wiki.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-wiki.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add new test functions to `test-wiki.py`, registered in the `main()` runner block alongside the existing tests. Reuse the file's `_ok_result(...)` helper.

  Each test patches `_wiki._subprocess_util.run` with a callable that records `(argv, kwargs)` calls and returns `_ok_result(...)` instances scripted per scenario. Use `tempfile.TemporaryDirectory()` for `dest` paths — never hit a real remote, never run real git.

  Required tests:

  1. `test_clone_with_explicit_branch_exists` — `dest` does not exist; the patched `run` returns non-empty stdout for `git ls-remote --heads <url> <branch>` and rc=0 for the clone. Assert: the recorded call sequence is `git ls-remote --heads <url> <branch>` followed by `git clone -b <branch> --single-branch <url> <dest>` (and only those two). Assert returned dict equals `{"action": "cloned", "branch_existed_on_remote": True}`.
  2. `test_init_orphan_when_branch_missing` — `dest` does not exist; `ls-remote` returns empty stdout (rc=0). Assert call sequence: `ls-remote --heads`, `git init <dest>`, `git -C <dest> remote add origin <url>`, `git -C <dest> checkout --orphan <branch>`, `git -C <dest> config branch.<branch>.remote origin`, `git -C <dest> config branch.<branch>.merge refs/heads/<branch>`. Assert returned dict equals `{"action": "initialized", "branch_existed_on_remote": False}`.
  3. `test_clone_without_branch` — `dest` does not exist; `branch` argument is `None`. Assert: NO `ls-remote` call is made (the helper short-circuits to `git clone`). The only call is `git clone <url> <dest>`. Returned dict equals `{"action": "cloned", "branch_existed_on_remote": None}`.
  4. `test_pull_existing_repo_match` — `dest` exists, `dest/.git` exists, `git -C <dest> remote get-url origin` returns the matching url, `git -C <dest> branch --show-current` returns the matching branch, `pull --ff-only` succeeds. Assert: `pull --ff-only` is the final call. Returned dict equals `{"action": "pulled", "branch_existed_on_remote": None}`.
  5. `test_halt_dest_exists_not_git_repo` — `dest` exists but `dest/.git` does not. Assert: raises `WikiSetupError`; the exception message contains `str(dest)` and the phrase "not a git repository".
  6. `test_halt_origin_url_mismatch` — `dest` exists with `.git`, `remote get-url origin` returns a URL different from the argument. Assert: raises `WikiSetupError`; both URLs appear in the message; no further git calls happen after the mismatch is detected.
  7. `test_halt_branch_mismatch` — `dest` exists with `.git`, origin URL matches, `branch --show-current` returns a different branch. Assert: raises `WikiSetupError`; both branches in the message; no `pull` call happens.
  8. `test_reachability_failure_ls_remote` — `dest` does not exist, `branch is not None`, `ls-remote` returns rc!=0 with network-style stderr. Assert: raises `WikiSetupError` (the caller translates to user-facing message in mill-setup's Phase 2).

  Use `pathlib.Path(tmp.name)` and child paths derived from it. The `dest` "does not exist" cases use a path inside the tempdir that is never created. The "dest exists" cases use `dest.mkdir()` plus optionally `(dest / ".git").mkdir()` to simulate a git repo.

  Each test wires its own `unittest.mock.patch` over `_wiki._subprocess_util.run` (mirroring the existing tests in this file). Register every new test in the `main()` runner.

- **Commit:** `test(wiki): unit tests for clone_or_init`

### Card 3: Add `_config.set_local_wiki_overrides` helper

- **Reads:**
  - `plugins/mill/scripts/_config.py`
  - `discussion.md`
- **Modifies:**
  - `plugins/mill/scripts/_config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add `set_local_wiki_overrides(cfg_path: Path, repo_url: str | None, branch: str | None) -> bool` to `_config.py`. Returns `True` if the file was created or modified, `False` if no-op.

  Logic:

  - If both `repo_url is None` and `branch is None`: return `False` immediately (no-op contract — caller passed no overrides to apply).
  - Load existing data: if `cfg_path.exists()`, parse via `yaml.safe_load(cfg_path.read_text(encoding="utf-8"))` into `data`; if the file did not exist or yaml returned `None`, set `data = {}`.
  - Look up `existing_wiki = (data.get("wiki") or {})`. Make a fresh dict `new_wiki = dict(existing_wiki)` so partial-update semantics are preserved (a missing-from-args key is not removed from the file).
  - If `repo_url is not None`: `new_wiki["repo_url"] = repo_url`.
  - If `branch is not None`: `new_wiki["branch"] = branch`.
  - Set `data["wiki"] = new_wiki` and serialise via `new_text = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)`.
  - Idempotency: if `cfg_path.exists()` AND the existing file text equals `new_text` byte-for-byte: return `False`.
  - Otherwise: ensure `cfg_path.parent` exists (`cfg_path.parent.mkdir(parents=True, exist_ok=True)`), write `new_text` (utf-8), return `True`.

  Notes:
  - The helper deliberately does NOT seed any template content. When `cfg_path` did not exist, the resulting file contains only the `wiki:` block (and any subsequent yaml dump output for the empty-elsewhere data dict — which is just the wiki block). Phase 5 of mill-setup remains responsible for the verbatim-template seed in the no-flags path; in the override path Phase 3.2 takes over file creation and Phase 5 sees the file already exists and skips (existing behavior).
  - Comments in `cfg_path` are not preserved across rewrites — this is the documented trade-off (Decision: yaml load+dump for config persistence). The file is gitignored and per-machine.
  - The helper uses `yaml` from the standard lookup the rest of `_config.py` already does (PyYAML — already a transitive dep via `_config.load_config`'s `import yaml`).
  - Add a function docstring summarising the contract, the return value, and the comment-loss caveat.

- **Commit:** `feat(config): add set_local_wiki_overrides for mill-setup persistence`

### Card 4: Unit tests for `_config.set_local_wiki_overrides`

- **Reads:**
  - `plugins/mill/scripts/_config.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Modifies:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Add new test functions to `test-config.py`, registered in the `main()` runner block. Use `tempfile.TemporaryDirectory()` for the `cfg_path` parent.

  Required tests:

  1. `test_no_op_when_both_args_none` — call with `repo_url=None`, `branch=None`. Assert: returns `False`. Assert: `cfg_path` does not exist after the call (no file created).
  2. `test_creates_file_when_missing` — call with `repo_url="https://example.com/x.git"`, `branch=None`, on a path that does not exist. Assert: returns `True`. Assert: file now exists; `yaml.safe_load(...)["wiki"]["repo_url"] == "https://example.com/x.git"`; `"branch"` key is absent from the wiki block.
  3. `test_updates_existing_value` — pre-write a file with `wiki: { repo_url: "https://old.git" }` (via `yaml.safe_dump`). Call with `repo_url="https://new.git"`. Assert: returns `True`. Assert: file now has `repo_url == "https://new.git"`.
  4. `test_idempotent_when_already_correct` — pre-write a file with the exact yaml-dumped `wiki: {repo_url: X, branch: B}`. Call with the same `repo_url=X`, `branch=B`. Assert: returns `False`. Assert: file mtime / contents unchanged (compare `read_text` before and after).
  5. `test_partial_update_branch_only_preserves_repo_url` — pre-write a file with `wiki: {repo_url: "https://x.git", branch: "old"}`. Call with `repo_url=None`, `branch="new"`. Assert: returns `True`. Assert: yaml-loaded result has `repo_url == "https://x.git"` AND `branch == "new"`.
  6. `test_preserves_other_top_level_keys` — pre-write a file containing `hub_relative_path: .` (no `wiki:` block). Call with `repo_url="https://x.git"`. Assert: returns `True`. Assert: yaml-loaded result still contains `hub_relative_path == "."` AND a `wiki: {repo_url: ...}` block.

  Each test creates a fresh `tempfile.TemporaryDirectory()`, computes `cfg_path = Path(tmp.name) / "config.local.yaml"`. Tests that pre-write the file use `yaml.safe_dump(data, sort_keys=False, allow_unicode=True)` to produce the same canonical form the helper will emit on no-op detection. Register every new test in the `main()` runner.

- **Commit:** `test(config): unit tests for set_local_wiki_overrides`

## Batch Tests

The frontmatter `verify:` field runs `python plugins/mill/unit_tests/run-all.py`, which globs every `test-*.py` in that directory. Cards 2 and 4 add tests to `test-wiki.py` and `test-config.py` respectively; both files are already picked up by the runner. The runner exits 0 on full pass; mill-go interprets non-zero as a batch verify failure. No additional integration tests are added (per discussion: unit-test coverage of the helpers is sufficient — `clone_or_init`'s end-to-end behaviour is exercised live by mill-setup itself in batch 02's docs and by manual `/mill-setup --from-url ...` invocations once that batch is approved).
