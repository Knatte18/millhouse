# Batch: keybindings

```yaml
task: "Auto-name task sessions <slug>:<phase>"
batch: "keybindings"
number: 2
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-vscode-keybindings.py
depends-on: [1]
```

## Batch Scope

Delivers `_vscode_keybindings`: locating the user-level VS Code `keybindings.json`, textually merging a marker-delimited block of six `alt+shift+N` bindings into that JSONC file, and reporting conflicts.
It is one batch because the parser, the merge and the writer share one small tokenizer and one test file.
It depends on batch 1 only for the task labels and their order (`_vscode_tasks.TASK_SPECS`, `_vscode_tasks.LABEL_PREFIX`).
Batch-local decision: the real user file is never touched by tests; every function that touches disk takes an explicit path.

## Cards

### Card 5: Add _vscode_keybindings helper

- **Context:**
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/scripts/_vscode.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_vscode_keybindings.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/scripts/_vscode_keybindings.py` with a module docstring in `_vscode.py`'s style.
  It imports `_vscode_tasks` and derives the bindings from `TASK_SPECS`: binding number N (1-based, in `TASK_SPECS` order: start, start-auto, start-orch, plan, go, quick) is `{"key": "alt+shift+N", "command": "workbench.action.tasks.runTask", "args": "<LABEL_PREFIX><task_key>"}`.
  Constants: `BLOCK_BEGIN = "// mill:begin"` and `BLOCK_END = "// mill:end"`.
  Functions:
  - `desired_bindings() -> list[dict]` returns those six dicts.
  - `keybindings_path(platform: str | None = None, *, env: dict | None = None, home: Path | None = None) -> Path` returns the stable-`Code` user file: `<home>/.config/Code/User/keybindings.json` for a platform starting with `linux`, `<env APPDATA>/Code/User/keybindings.json` for `win32` (raise `ValueError` when `APPDATA` is unset), `<home>/Library/Application Support/Code/User/keybindings.json` for `darwin`; `platform` defaults to `sys.platform`, `env` to `os.environ`, `home` to `Path.home()`; any other platform raises `ValueError`.
  - `strip_jsonc(text: str) -> str` removes `//` line comments and `/* */` block comments that lie outside string literals (a `//` inside a string value is not a comment; string escapes such as `\"` are honoured) and removes trailing commas before `]` or `}`; the result must be accepted by `json.loads`.
  Implement it with one small character-level scanner that tracks string and comment state; reuse that scanner to find the index of the top-level array's closing `]` and to find the last significant token before it.
  - `merge_bindings(text: str) -> tuple[str, list[str]]` returns `(new_text, warnings)`.
  Behaviour: empty or whitespace-only `text` is treated as a missing file and yields `[`, the mill block, `]`.
  Otherwise, first locate an existing block (the lines from `BLOCK_BEGIN` through `BLOCK_END`) and exclude it when parsing; parse the remainder with `strip_jsonc` + `json.loads`; a top-level value that is not a list, or text that does not parse, raises `KeybindingsParseError` (a `ValueError` subclass defined in the module).
  A desired binding whose `key` equals (case-insensitively, ignoring whitespace) the `key` of any entry outside the block is a conflict: it is left out of the block and one warning string is added naming the key, the existing entry's `command`, and the mill task label, e.g. `alt+shift+4 is already bound to <command>; skipped mill binding "mill: plan"`.
  The remaining bindings are rendered as the block: `BLOCK_BEGIN`, one 4-space-indented JSON object per line separated by commas, `BLOCK_END`.
  If a block already exists it is replaced in place (so re-running is idempotent and does not move it); if none exists it is inserted immediately before the closing `]`, adding a comma after the previous last entry when it lacks one (no comma when the array is empty) and never touching comments or other entries.
  If no bindings remain (all conflict), an existing block is removed and nothing is inserted.
  All text outside the block is preserved byte-for-byte.
  All warning text is ASCII.
  - `write_bindings(path: Path | None = None, *, platform: str | None = None) -> tuple[str, list[str]]` returns `(status, warnings)` with status one of `"created"`, `"updated"`, `"unchanged"`, `"skipped"`.
  `path` defaults to `keybindings_path(platform)`.
  When the file does not exist it is created with only the mill block, provided its parent directory exists; when the parent directory does not exist (VS Code not installed) nothing is written, the status is `"skipped"` and a warning says so.
  On `KeybindingsParseError` (or an OS error reading the file) the file is left untouched, the status is `"skipped"` and a warning states that all six bindings were skipped.
  The file is rewritten only when `merge_bindings` changed the text.
  Never prints; callers print the warnings.
- **Commit:** `feat(vscode): merge mill session shortcuts into user keybindings.json`

### Card 6: Unit tests for _vscode_keybindings

- **Context:**
  - `plugins/mill/scripts/_vscode_keybindings.py`
  - `plugins/mill/scripts/_vscode_tasks.py`
  - `plugins/mill/unit_tests/test-vscode.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-vscode-keybindings.py`
- **Deletes:** none
- **Moves:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-vscode-keybindings.py` in `test-vscode.py`'s structure; every disk test uses a tempdir path (never the real user file).
  Cover: `desired_bindings` returns six entries with keys `alt+shift+1` through `alt+shift+6` mapped in order to the labels `mill: start`, `mill: start-auto`, `mill: start-orch`, `mill: plan`, `mill: go`, `mill: quick`; `keybindings_path` for `linux`, `win32` (with an injected `env` holding `APPDATA`, and a `ValueError` when it is absent) and `darwin` using an injected `home`; `strip_jsonc` on comments outside strings, a `//` and a `/*` inside a string value left intact, escaped quotes, trailing commas before `]` and `}`, and comments containing brackets or quotes.
  `merge_bindings` on: empty text; an existing JSONC array containing comments and other entries (comments and entries preserved byte-for-byte, block inserted before the closing `]`, comma added after the previously last entry); an array whose last entry already has a trailing comma; an empty array `[]`; a second run producing identical text; a changed binding set replacing the block in place when a user entry was added after the block; a conflicting `Alt+Shift+4` entry outside the block (case and whitespace variants) skipped with a warning naming the key and the command while the other five bindings are written; all six conflicting, which removes an existing block; a top-level object and unparsable text each raising `KeybindingsParseError`.
  `write_bindings` on tempdir paths: `created` for a missing file whose parent exists; `skipped` with a warning for a missing parent directory; `unchanged` on re-run (file bytes and mtime preserved); `updated` after a stale block; `skipped` for unparsable content with the file bytes unchanged.
- **Commit:** `test(vscode): cover keybindings JSONC merge, conflicts and path resolution`

## Batch Tests

`verify:` runs only the new `test-vscode-keybindings.py`; it uses tempfile fixtures exclusively, so it never reads or writes a real VS Code user file.
