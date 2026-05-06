# Batch: config-and-subprocess

```yaml
task: '11 (B) — Review-code: configurable holistic effort + diff-scoping via start_sha'
batch: config-and-subprocess
cards: 2
verify: null
depends-on: []
```

## Batch Scope

Add two new config keys (`holistic_effort`, `diff_scope_threshold`) to both the live wiki config and the installation template that seeds fresh setups. Add `CREATE_NO_WINDOW` to the single subprocess spawn site to suppress console windows on Windows. These are independent of all Python logic changes and can be written first. No tests are added here — config edits have no runnable unit-test surface, and the subprocess flag is a platform-level behaviour that cannot be unit-tested without a real Windows subprocess.

## Cards

### Card 1: Add holistic_effort and diff_scope_threshold config keys

- **Reads:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Modifies:**
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Under `review.code` in `plugins/mill/templates/wiki-config.yaml`, add two new keys immediately after `self_fix_rounds` (place them at the end of the `code:` block):

  ```yaml
  holistic_effort: max        # effort passed to holistic review call; set to medium/low to reduce rate-limit risk on large tasks
  diff_scope_threshold: 0.25  # per-batch diff/file char ratio below which git diff is used instead of full file content
  ```

  **Also update `wiki/config.yaml` in the wiki repo** (this is a live operational config in a separate git repo, not tracked by the code reviewer, but must stay in sync with the template). Locate `wiki/config.yaml` at `c:/Code/millhouse/wiki/config.yaml` (or via `.millhouse/wiki` junction). Add the same two keys to its `review.code` block. The downstream `_review_code.py` changes use `.get("holistic_effort", "max")` and `.get("diff_scope_threshold", 0.25)` as safe defaults, so the plan works without this update, but the config should be kept current. Commit and push the wiki change separately (`git -C <wiki_path> add config.yaml && git -C <wiki_path> commit --message "feat: add holistic_effort and diff_scope_threshold to review.code" && git -C <wiki_path> push`).
- **Commit:** `feat(config): add holistic_effort and diff_scope_threshold to review.code config`

### Card 2: Add CREATE_NO_WINDOW to _subprocess_util.py

- **Reads:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Modifies:**
  - `plugins/mill/scripts/_subprocess_util.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_subprocess_util.run`, add `creationflags=subprocess.CREATE_NO_WINDOW` to `popen_kwargs` when `os.name == "nt"`. Place this block just before the `subprocess.Popen(argv, **popen_kwargs)` call, adjacent to the existing `if os.name != "nt": popen_kwargs["start_new_session"] = True` block so both Windows and POSIX paths are visually grouped. The `subprocess` module is already imported. Add a brief comment explaining the flag suppresses the CMD console window that would otherwise flash on-screen when spawning `cmd /c claude` or `git` on Windows.
- **Commit:** `fix(subprocess): suppress console window on Windows with CREATE_NO_WINDOW`

## Batch Tests

`verify: null` — config edits are verified by downstream batches that read from config, and the `CREATE_NO_WINDOW` flag is a platform-level behaviour not covered by unit tests. The existing unit suite should still pass after this batch (no logic was changed).
