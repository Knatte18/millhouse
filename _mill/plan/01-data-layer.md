# Batch: Data Layer

```yaml
task: Migrate wiki task store to TinyDB
batch: Data Layer
number: 1
cards: 4
verify: null
depends-on: []
```

## Batch Scope

This batch delivers the three pure data-layer modules and the dependency addition. `wiki/_parse.py` parses raw Home.md markdown into task dicts. `wiki/_render.py` renders task dicts back into `Home.md`, `_Sidebar.md`, and `proposal-<slug>.md` files. `wiki/_store.py` replaces the existing in-memory dict with a TinyDB-backed Store that delegates to parse and render internally. `pyproject.toml` gains the `tinydb>=4.8` dependency. None of these modules import from `wiki/_server.py` or `wiki/_client.py`. The external interface consumed by batch 2 is the `Store` class from `wiki/_store.py`.

## Cards

### Card 1: Add tinydb dependency

- **Context:**
  - `plugins/mill/pyproject.toml`
- **Edits:**
  - `plugins/mill/pyproject.toml`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add `"tinydb>=4.8"` to the `dependencies` list in `[project]`. The existing entries are `"pyyaml>=6.0"` and `"pygit2>=1.14.0"`. Preserve the existing list order; append tinydb as the third entry.
- **Commit:** `feat(wiki): add tinydb dependency`

### Card 2: Create wiki/_render.py

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_store.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/wiki/_render.py`
- **Deletes:** none
- **Requirements:**
  Define module-level function `render(tasks: list[dict]) -> dict[str, str]`.

  Return value: a dict mapping `rel_path -> content` for every file to commit. Always includes `"Home.md"` and `"_Sidebar.md"`. Also includes `"proposal-<slug>.md"` for every task whose `"body"` field is a non-empty string.

  `Home.md` structure (exact):
  - First line: `# Tasks\n`
  - Blank line after header.
  - Tasks with `group=None` listed first, no section header.
  - Then each group present in tasks, in order `A`, `B`, `C`, `D`, `Z`. For each non-None group that has at least one task: emit `# Layer <letter>\n\n` header, then the tasks in that group.
  - Each task entry (two lines + body):
    - `## <title>\n`
    - Slug line: `[<slug>]` followed by ` [<status>]` if status is one of `active`, `done`, `pr-pending`, `ready-to-merge`; no marker for `None` or `blocked`.
    - Blank line.
    - `brief` text (may be empty string — if empty, omit the blank+brief line entirely).
    - Blank line before the next entry (or before the next group header).

  `_Sidebar.md` structure:
  - Same group ordering as `Home.md`.
  - Each task: `[[<title>]](proposal-<slug>.md)` if `body != ""`, else plaintext `<title>`.
  - Tasks within a group on consecutive lines; groups separated by a blank line.

  `proposal-<slug>.md`: `body` field content verbatim (no wrapping or modification). Only emitted if `body != ""`.

  The function is pure (no I/O, no side effects). Import nothing from `wiki/_server.py`, `wiki/_client.py`, or `wiki/_store.py`.
- **Commit:** `feat(wiki): add _render.py -- render tasks to Home.md, _Sidebar.md, proposal files`

### Card 3: Create wiki/_parse.py

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/wiki/_parse.py`
- **Deletes:** none
- **Requirements:**
  Define module-level function `parse_home_md(content: str) -> list[dict]`.

  The function walks `content` line by line and returns a list of task dicts. Each dict has the keys: `slug`, `title`, `group`, `brief`, `status`. (Fields `id`, `body` are not extractable from Home.md and are omitted from the returned dicts — callers that call `upsert_task` with this output must supply or preserve those fields separately.)

  Parsing rules:
  - Track the current group by scanning for lines matching `^# Layer ([A-Z])` — capture the letter as the group. Reset to `None` on `^# ` lines that don't match this pattern.
  - Detect a task heading on a line matching `^## `. Title is everything after `## `.
  - The line immediately following the heading is the slug line. Match `^\[(?P<slug>[a-z][a-z0-9-]*)\]( \[(?P<status>s|active|ready-to-merge|pr-pending|done|abandoned)\])?`. Extract `slug` and `status`; map `abandoned` -> `None`, `s` -> `None`.
  - Collect `brief`: scan lines after the slug line up to the next `^## ` or `^# ` or EOF. Brief is the first non-empty paragraph (lines joined until a blank line terminates it). If no non-empty paragraph exists, `brief = ""`.
  - Skip any lines that are part of the leading preamble (before the first `## ` heading).

  The function is pure (no I/O). Import nothing from `wiki/_server.py`, `wiki/_client.py`, or `wiki/_store.py`.
- **Commit:** `feat(wiki): add _parse.py -- parse Home.md into task dicts`

### Card 4: Replace wiki/_store.py with TinyDB Store

- **Context:**
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/wiki/_render.py`
- **Edits:**
  - `plugins/mill/scripts/wiki/_store.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  Completely replace the existing `Store` class. The new `Store` must satisfy all of the following.

  **Constructor:** `Store(db_path: Path)`. Opens a `TinyDB(str(db_path))` instance. Initialises a separate `_file_cache: dict[str, tuple[str, str]]` for non-Home.md paths. Initialises `_initialized: bool = False` to track whether TinyDB has been populated.

  **`content_hash(content: str) -> str` (static method):** SHA-256 hex digest of content encoded as UTF-8. Identical to the method in the old Store.

  **`set(rel_path: str, content: str) -> None`:**
  - If `rel_path == "Home.md"`: call `parse_home_md(content)` from `wiki._parse`. For each returned task dict, call `upsert_task` (merging, not replacing — see below). Set `_initialized = True`.
  - Else: store `(content, content_hash(content))` in `_file_cache[rel_path]`.

  **`get(rel_path: str) -> tuple[str, str] | None`:**
  - If `rel_path == "Home.md"`: if `not _initialized`, return `None`. Else call `render(all_tasks())` from `wiki._render`, return `(rendered["Home.md"], content_hash(rendered["Home.md"]))`.
  - Else: return `_file_cache.get(rel_path)`.

  **`invalidate(rel_path: str) -> None`:**
  - If `rel_path == "Home.md"`: set `_initialized = False`.
  - Else: remove `rel_path` from `_file_cache` (no-op if absent).

  **`upsert_task(task: dict) -> None`:** Merge `task` into the existing TinyDB document for `task["slug"]`. Merge means: load existing document, update only keys present in `task`, write back. Keys absent from `task` (e.g., `body`, `id`) are preserved from the existing document. If no document exists for this slug: assign `id` = `max(existing ids) + 1` (or `1` if table is empty), then insert the full dict (filling missing keys with defaults: `group=None`, `brief=""`, `body=""`, `status=None`).

  **`all_tasks() -> list[dict]`:** Return all documents from the TinyDB table as a list of dicts, in insertion order.

  **`get_by_slug(slug: str) -> dict | None`:** Return the TinyDB document for `slug`, or `None` if absent.

  Remove the old `invalidate_all()` method entirely — it is not called anywhere after batch 2's server changes.
- **Commit:** `feat(wiki): replace _store.py with TinyDB-backed Store`

## Batch Tests

verify is null — unit tests for this batch are written in batch 3. To smoke-test during implementation: `python -c "from wiki._store import Store; from pathlib import Path; import tempfile, os; d=tempfile.mkdtemp(); s=Store(Path(d)/'tasks.json'); print('import OK')"`.
