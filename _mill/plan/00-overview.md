# Plan: Port mill to POSIX, not just Windows

```yaml
task: "Port mill to POSIX, not just Windows"
slug: "posix-cross-platform-port"
approved: false
started: "20260713-083239"
parent: "hanf/linux-port-more"
root: ""
verify: null
```

## Batch Index

_The fenced yaml block below is the authoritative DAG mill-go reads to
schedule batches. Every batch lives at `NN-<batch-slug>.md` in this
directory and is mirrored as one entry here._

```yaml
batches:
  - number: 1
    name: posix-portability-fixes
    file: 01-posix-portability-fixes.md
    depends-on: []
    verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py
  - number: 2
    name: bootstrap-posix-test
    file: 02-bootstrap-posix-test.md
    depends-on: []
    verify: PYTHONPATH= bash -n plugins/mill/integration_tests/test-bootstrap.sh
```

## Shared Decisions

### Decision: dual-support-never-replace

- **Decision:** Every change adds a POSIX path beside the existing Windows path;
  no Windows path is ever deleted. Where a runtime OS branch is involved, follow
  the established `if os.name == "nt": ... else: ...` convention already used in
  `_junction.py`, `_subprocess_util.py`, and `wiki/_client.py`. In shell/doc
  snippets, prefer the file-existence probe idiom (`.venv/bin/python` vs
  `.venv/Scripts/python.exe`) over branching on `uname`/`$OS`, matching
  `mill-setup/SKILL.md:74`.
- **Rationale:** the task is dual support (Linux/macOS alongside Windows), not a
  Windows-to-POSIX migration.
- **Applies to:** all batches

### Decision: ascii-only-output

- **Decision:** Any `print()`/`_log()`/shell `echo`/comment text added or edited
  stays ASCII-only — em dash becomes ` -- `, arrows become ` -> `. This is
  enforced tree-wide by `test-guards.py`'s `no_unicode_arrow` check for
  `test-*.py` and is a hard project convention everywhere else (Windows cp1252
  crashes on non-ASCII stdout).
- **Rationale:** cross-platform stdout safety; also keeps the guard suite green.
- **Applies to:** all batches

### Decision: no-tmp-use-scratch

- **Decision:** Ephemeral test fixtures go under `.scratch/` (gitignored), never
  `/tmp`, `$env:TEMP`, or any system temp dir.
- **Rationale:** `conversation/SKILL.md` File Writing rule; avoids Windows
  permission prompts and matches the `.millhouse/` isolation model.
- **Applies to:** bootstrap-posix-test

### Decision: python-verify-isolation-prefix

- **Decision:** Every non-null `verify:` command begins with the literal
  `PYTHONPATH= ` (empty value, single space) so the test subprocess does not
  inherit the mill-cache `PYTHONPATH` and loads worktree modules. This is a
  Python/mill project (`pyproject.toml` present), so the `verify-not-isolated`
  validator enforces the prefix for all verify commands, including the
  `bash -n` syntax check.
- **Rationale:** project convention (CLAUDE.md "Verify command shape").
- **Applies to:** all batches

## All Files Touched

- `.claude/settings.json`
- `plugins/mill/integration_tests/test-bootstrap.sh`
- `plugins/mill/scripts/_vscode.py`
- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-wiki-push/SKILL.md`
- `plugins/mill/unit_tests/test-guards.py`
