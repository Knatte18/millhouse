# Plan: millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts

```yaml
task: 'millpy-implement --stage baseline: Windows verify-baseline worktree teardown fails (WinError 145 / long paths), leaves orphaned artifacts'
slug: mill-go-windows-baseline-teardown-winerror145
approved: false
started: 20260820-175134
parent: main
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to schedule batches.
Every batch lives at `NN-<batch-slug>.md` in this directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: long-path-helper
    file: 01-long-path-helper.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-long-path.py
  - number: 2
    name: worktree-removal-longpaths
    file: 02-worktree-removal-longpaths.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-worktree.py
  - number: 3
    name: junction-walker-long-path-safety
    file: 03-junction-walker-long-path-safety.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-junction.py
  - number: 4
    name: safe-rmtree-long-path-safety
    file: 04-safe-rmtree-long-path-safety.md
    depends-on: [1]
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-safe-rmtree.py
```

## Shared Decisions

_Cross-cutting decisions every batch inherits: naming conventions, error-handling posture, test frameworks, style/lint constraints.
One subsection per decision.
Batch-local decisions live in each batch file._

### Decision: proactive-extended-path-prefix

- **Decision:** Every call site touched by this plan that opens or removes a path prone to Windows `MAX_PATH` failures (`os.scandir`, `shutil.rmtree`'s root argument, `os.path.lexists`/`os.lstat`/`os.rmdir`/`os.unlink`/`os.path.islink`/`os.path.isjunction`) passes the path through `_long_path.to_extended()` proactively, before the OS call is made — never as a retry inside an `except` block.
- **Rationale:** A proactive prefix prevents the failure outright with one code path per call site; a catch-then-retry shape would duplicate try/except-retry logic at every site (rejected in `_mill/discussion.md`'s `long-path-safe-walkers` decision).
- **Applies to:** 03-junction-walker-long-path-safety, 04-safe-rmtree-long-path-safety

### Decision: preserve-genuine-vanished-handling

- **Decision:** The existing "genuinely vanished" `FileNotFoundError` skip-and-log handling in both walkers is unchanged. It now fires on a `FileNotFoundError` raised from the extended-path-prefixed call instead of the raw-path call, but the handling itself (log a warning, skip, never propagate) is untouched.
- **Rationale:** Genuine concurrent-deletion races (sibling deletion, concurrent teardown) are a real, previously-fixed scenario that must keep being handled gracefully — the long-path fix is additive, not a replacement.
- **Applies to:** 03-junction-walker-long-path-safety, 04-safe-rmtree-long-path-safety

### Decision: core-longpaths-argv-placement

- **Decision:** `-c core.longpaths=true` is inserted as an adjacent `-c`/value pair immediately after `-C <cwd>` and before the `worktree` subcommand token, in both the `git worktree remove` and `git worktree prune` argv lists built by `_worktree.remove_safe`.
- **Rationale:** Mirrors `_verify_baseline.py:106`'s existing creation-side placement exactly, so the two call shapes (creation, removal) stay visually and structurally consistent.
- **Applies to:** 02-worktree-removal-longpaths

## All Files Touched

_Full union of every `Creates:` / `Edits:` / `Moves:` **target** path across every batch, sorted alphabetically (Move **source** paths are excluded — they disappear, like `Deletes:` tokens).
Cards are the source of truth;
this section is the input `_plan_validate.py`'s `all-files-touched-mismatch` check cross-references against the derived union of every card's `Edits:`/`Creates:`/Move-target paths, to catch drift between the hand/agent-maintained list here and that derived union._

- `plugins/mill/scripts/_junction.py`
- `plugins/mill/scripts/_long_path.py`
- `plugins/mill/scripts/_safe_rmtree.py`
- `plugins/mill/scripts/_worktree.py`
- `plugins/mill/unit_tests/test-junction.py`
- `plugins/mill/unit_tests/test-long-path.py`
- `plugins/mill/unit_tests/test-safe-rmtree.py`
- `plugins/mill/unit_tests/test-worktree.py`
