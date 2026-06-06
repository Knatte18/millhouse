# Batch: cache-preflight

```yaml
task: "Fix infrastructure bugs across merge, wiki-daemon, config, plan, and cleanup"
batch: cache-preflight
number: 7
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-preflight.py
depends-on: []
```

## Batch Scope

Turns the cryptic `ModuleNotFoundError` from a stale plugin cache (a
helper module missing from the installed cache, e.g. `_archive_tag.py`)
into an actionable "refresh your cache" message (#403). Adds a new
`_preflight.py` helper and wires a check into mill-merge before the step
that imports the at-risk helper.

## Cards

### Card 21: `_preflight` helper to detect missing cache helpers

- **Context:**
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_archive_tag.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_preflight.py`
- **Deletes:** none
- **Requirements:** Create `_preflight.py` exposing a pure function
  `missing_helpers(required: list[str], scripts_dir: Path) -> list[str]`
  that returns the names from `required` for which `<scripts_dir>/<name>.py`
  does not exist, and a `check_helpers(required: list[str]) -> int` that
  resolves the active scripts dir from `CLAUDE_PLUGIN_ROOT`
  (`<CLAUDE_PLUGIN_ROOT>/scripts`, falling back to this file's own dir),
  and on any missing helper prints an ASCII, actionable message to stderr
  naming the missing module(s) and instructing the operator to
  reinstall/refresh the plugin cache, returning a non-zero exit code; zero
  when all present. Provide a `__main__` entry so it can be invoked as a
  CLI with helper names as args. ASCII-only output.
- **Commit:** `feat(preflight): detect missing cache helper modules with actionable message`

### Card 22: Wire preflight into mill-merge + test

- **Context:**
  - `plugins/mill/scripts/_preflight.py`
  - `plugins/mill/unit_tests/run-all.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:**
  - `plugins/mill/unit_tests/test-preflight.py`
- **Deletes:** none
- **Requirements:** In `mill-merge/SKILL.md`, before the step that imports
  `_archive_tag` (Step 6 archive-tag), add a preflight check invoking
  `_preflight.check_helpers(["_archive_tag"])` (cache-form invocation,
  consistent with other SKILL script calls) and halt with the actionable
  message if it reports missing -- so the operator gets "refresh your
  cache" instead of a raw `ModuleNotFoundError`. Create `test-preflight.py`
  asserting: `missing_helpers` returns the missing names for a temp
  scripts dir lacking a file and `[]` when present; `check_helpers` returns
  non-zero + prints an ASCII actionable message when a helper is missing
  (capture stderr) and zero when present; and a fallback case: with
  `CLAUDE_PLUGIN_ROOT` unset, `check_helpers(["_preflight"])` returns 0
  without raising (it falls back to `_preflight.py`'s own `__file__` parent
  dir, where `_preflight.py` itself exists). ASCII-only.
- **Commit:** `feat(mill-merge): preflight-check _archive_tag presence before use`

## Batch Tests

`verify:` runs the new `test-preflight.py`. It exercises `missing_helpers`
/ `check_helpers` against temp directories and a patched
`CLAUDE_PLUGIN_ROOT`; the SKILL.md wiring is documentation and is covered
by inspection.

Ordering: Card 22 Creates `test-preflight.py`, which the `verify:` `--only`
flag requires on disk. mill-go runs `verify:` once at batch end after both
cards are implemented and committed, so the file exists when verify runs.
