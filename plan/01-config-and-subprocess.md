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
  - `wiki/config.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
- **Modifies:**
  - `wiki/config.yaml`
  - `plugins/mill/templates/wiki-config.yaml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Under `review.code` in both `wiki/config.yaml` and `plugins/mill/templates/wiki-config.yaml`, add two new keys immediately after `holistic: true` (or after `self_fix_rounds` — place them visually near the existing `code:` block keys so the section stays coherent):

  ```yaml
  holistic_effort: max        # effort passed to holistic review call; set to medium/low to reduce rate-limit risk on large tasks
  diff_scope_threshold: 0.25  # per-batch diff/file char ratio below which git diff is used instead of full file content
  ```

  Both files must receive identical additions. `wiki/config.yaml` is the live config used by the running mill instance; `plugins/mill/templates/wiki-config.yaml` seeds fresh `mill-setup` installations. Omitting either causes `KeyError` on `cfg["review"]["code"]["holistic_effort"]` for one of the two setups.
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
