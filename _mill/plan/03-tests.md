# Batch: Tests

```yaml
task: Migrate wiki task store to TinyDB
batch: Tests
number: 3
cards: 3
verify: "python plugins/mill/unit_tests/test-wiki-store.py && python plugins/mill/unit_tests/test-wiki-render.py && python plugins/mill/integration_tests/test-wiki-daemon-tinydb.py"
depends-on: [2]
```

## Batch Scope

This batch adds all tests for the new data layer and server integration. Card 7 tests `render()` in isolation. Card 8 tests the `Store` class — TinyDB CRUD, the `set`/`get` lifecycle, and the `invalidate` semantics. Card 9 is an integration test that starts a real daemon process against a fixture wiki repo and exercises the full read/write cycle. All test fixtures use `.scratch/` subdirectories, never system temp dirs.

## Cards

### Card 7: Unit tests for wiki/_render.py

- **Context:**
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-render.py`
- **Deletes:** none
- **Requirements:**
  Follow the existing test file structure: `HUB = Path(__file__).resolve().parent.parent.parent.parent`, `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`, `def main() -> int`, `if __name__ == "__main__": sys.exit(main())`.

  Test cases (each prints `PASS: <description>` on success):

  1. **Empty task list:** `render([])` returns dict with `"Home.md"` key containing `"# Tasks\n"` (only the header), `"_Sidebar.md"` key present, no `proposal-*.md` keys.

  2. **Ungrouped tasks appear before grouped:** given one task with `group=None` and one with `group="A"`, the ungrouped task's `## heading` appears before the `# Layer A` section header in `Home.md`.

  3. **Group order A->B->C->D->Z:** given tasks in groups Z, A, D in that order in the list, rendered `Home.md` has `# Layer A` before `# Layer D` before `# Layer Z`.

  4. **Status markers:** `status="active"` emits `[active]`, `status="done"` emits `[done]`, `status=None` emits no marker, `status="blocked"` emits no marker.

  5. **proposal file generated for non-empty body:** a task with `body="some content"` produces `"proposal-<slug>.md": "some content"` in the returned dict, and the sidebar entry uses `[[Title]](proposal-<slug>.md)` form.

  6. **No proposal file for empty body:** a task with `body=""` produces no `proposal-*.md` key, sidebar entry is plaintext title.

  7. **brief appears in Home.md body:** a task with `brief="Short summary."` has that text on the line after the blank line following the slug line.

  8. **Task with empty brief:** a task with `brief=""` has no blank-line+brief block after the slug line (the entry ends with the slug line, then a blank before the next entry).

  Register `test-wiki-render.py` in `run-all.py` by adding it to the test list in that file.
- **Commit:** `test(wiki): unit tests for _render.py`

### Card 8: Unit tests for wiki/_store.py

- **Context:**
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_parse.py`
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/unit_tests/run-all.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-wiki-store.py`
- **Deletes:** none
- **Requirements:**
  Use a `tempfile.mkdtemp()` call (not `tempfile.TemporaryDirectory`) to create a throwaway directory for `tasks.json`. Clean up manually at test end or let OS clean it (acceptable for unit tests).

  Test cases (each prints `PASS: <description>` on success):

  1. **content_hash is deterministic:** `Store.content_hash("hello") == Store.content_hash("hello")` and differs from `Store.content_hash("world")`.

  2. **get("Home.md") returns None before first set:** `Store(path).get("Home.md") is None`.

  3. **set("Home.md") with valid markdown populates TinyDB:** construct a minimal Home.md string with one `## Title\n[my-slug]` entry. Call `store.set("Home.md", content)`. Assert `store.get_by_slug("my-slug") is not None` and `store.get_by_slug("my-slug")["title"] == "Title"`.

  4. **get("Home.md") after set returns rendered content:** `store.get("Home.md")` returns a tuple; the first element is a string containing `## Title`. The second element equals `Store.content_hash(first_element)`.

  5. **upsert_task assigns auto-increment id:** insert two tasks with slugs `"a"` and `"b"`. Their ids are 1 and 2 (or both non-zero integers that differ).

  6. **upsert_task merge preserves body:** insert task `{"slug": "t", "body": "existing body"}`. Then call `upsert_task({"slug": "t", "title": "New Title"})`. Assert `store.get_by_slug("t")["body"] == "existing body"`.

  7. **all_tasks returns all documents:** insert three tasks; `len(store.all_tasks()) == 3`.

  8. **invalidate("Home.md") marks uninitialized:** after a `set("Home.md", ...)`, call `store.invalidate("Home.md")`. Assert `store.get("Home.md") is None`.

  9. **invalidate("other.md") clears file cache:** `store.set("other.md", "content")` then `store.invalidate("other.md")`. Assert `store.get("other.md") is None`.

  10. **Store loads existing tasks.json on init:** create a `Store`, insert a task, close it (let it go out of scope), create a new `Store` with the same path. Assert the task is visible via `get_by_slug`.

  Register `test-wiki-store.py` in `run-all.py`.
- **Commit:** `test(wiki): unit tests for _store.py`

### Card 9: Integration test for daemon with TinyDB

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/wiki/_server.py`
  - `plugins/mill/scripts/wiki/_store.py`
  - `plugins/mill/scripts/wiki/_render.py`
  - `plugins/mill/scripts/wiki/_sync.py`
  - `plugins/mill/scripts/wiki/__init__.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/integration_tests/test-wiki-daemon-tinydb.py`
- **Deletes:** none
- **Requirements:**
  Follow the structure of existing integration tests if any exist. If the `plugins/mill/integration_tests/` directory does not have an `__init__.py`, do not add one.

  The test creates a real git repo in `.scratch/test-wiki-daemon-tinydb/` (create the subdirectory; clean up on test exit). Initialize it with `git init`, `git config user.email`, `git config user.name`, commit an initial `Home.md` with at least one `## Task\n[my-task]` entry and a `config.yaml` stub, and push to a bare remote also in `.scratch/`. The daemon connects to this wiki repo.

  Use `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts"` when spawning any subprocess (inherit from env in the test process).

  Test cases:

  1. **Read Home.md via client:** call `wiki._client.read(wiki_path, "Home.md")`. Assert the returned content contains `## Task`.

  2. **Write Home.md and verify tasks.json committed:** read current `(content, base_hash)`. Modify content to add a phase marker (e.g., `[my-task] [active]`). Call `wiki._client.write_commit_push(wiki_path, {"Home.md": (modified, base_hash)}, "test write")`. Assert `(wiki_path / "tasks.json").exists()`. Assert the last git commit in the wiki repo includes `tasks.json` (run `git -C <wiki_path> show --name-only HEAD` and check output).

  3. **Phase marker round-trip:** after test case 2, call `wiki._client.read(wiki_path, "Home.md")` again. Assert the returned content contains `[active]`.

  4. **Daemon restart preserves task state:** kill the daemon by deleting `.wiki-daemon.json` and sending SIGTERM (or on Windows, use taskkill). Re-read `Home.md` via a fresh `wiki._client.read` call (forces daemon restart). Assert the `[active]` marker is still present in the returned content (TinyDB reloaded from `tasks.json`).

  The integration test is a standalone script (`if __name__ == "__main__": main()`). It prints `PASS: <description>` per test case. Exit 0 on all pass, exit 1 on first failure with a descriptive error message.
- **Commit:** `test(wiki): integration test for daemon TinyDB persistence`

## Batch Tests

All test files are the deliverable. Run via:
```
python plugins/mill/unit_tests/test-wiki-store.py
python plugins/mill/unit_tests/test-wiki-render.py
python plugins/mill/integration_tests/test-wiki-daemon-tinydb.py
```
