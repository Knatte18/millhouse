"""Unit tests for wiki._store.Store TinyDB-backed implementation.

Covers: content_hash, set/get for Home.md with parsing, set/get for other files,
invalidate semantics, upsert_task, all_tasks, get_by_slug, and persistence.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki._store import Store  # noqa: E402


def main() -> int:
    passed = 0
    failed = 0

    def ok(name: str) -> None:
        nonlocal passed
        passed += 1
        print(f"PASS: {name}")

    def fail(name: str, exc: Exception) -> None:
        nonlocal failed
        failed += 1
        print(f"FAIL: {name}: {exc}", file=sys.stderr)

    # --- (1) content_hash is deterministic ---
    try:
        h1 = Store.content_hash("hello")
        h2 = Store.content_hash("hello")
        h3 = Store.content_hash("world")
        assert h1 == h2, "Same content should have same hash"
        assert h1 != h3, "Different content should have different hash"
        ok("content_hash is deterministic")
    except Exception as exc:
        fail("content_hash is deterministic", exc)

    # --- (2) get returns None before first set ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            result = store.get("Home.md")
            assert result is None, "get should return None before set"
            ok("get returns None before first set")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("get returns None before first set", exc)

    # --- (3) set Home.md with valid markdown populates TinyDB ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            home_content = "# Tasks\n\n## Title\n[my-slug]\n\n"
            store.set("Home.md", home_content)
            task = store.get_by_slug("my-slug")
            assert task is not None, "Task should be retrieved by slug"
            assert task["title"] == "Title", f"Title mismatch: {task.get('title')!r}"
            ok("set Home.md populates TinyDB")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("set Home.md populates TinyDB", exc)

    # --- (4) get Home.md after set returns rendered content ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            home_content = "# Tasks\n\n## Title\n[my-slug]\n\n"
            store.set("Home.md", home_content)
            result = store.get("Home.md")
            assert result is not None, "get should return tuple after set"
            rendered_content, content_hash = result
            assert isinstance(rendered_content, str), "First element should be string"
            assert isinstance(content_hash, str), "Second element should be hash string"
            assert "## Title" in rendered_content, "Title should be in rendered content"
            expected_hash = Store.content_hash(rendered_content)
            assert content_hash == expected_hash, "Hash should match rendered content"
            ok("get Home.md returns rendered content")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("get Home.md returns rendered content", exc)

    # --- (5) upsert_task assigns auto-increment id ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.upsert_task({"slug": "a", "title": "Task A"})
            store.upsert_task({"slug": "b", "title": "Task B"})
            task_a = store.get_by_slug("a")
            task_b = store.get_by_slug("b")
            assert task_a is not None and task_a.get("id") is not None, "Task A should have id"
            assert task_b is not None and task_b.get("id") is not None, "Task B should have id"
            id_a = task_a["id"]
            id_b = task_b["id"]
            assert isinstance(id_a, int) and isinstance(id_b, int), "IDs should be integers"
            assert id_a != id_b, "IDs should be different"
            ok("upsert_task assigns auto-increment id")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("upsert_task assigns auto-increment id", exc)

    # --- (6) upsert_task merge preserves body ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.upsert_task({"slug": "t", "title": "Original", "body": "existing body"})
            store.upsert_task({"slug": "t", "title": "New Title"})
            task = store.get_by_slug("t")
            assert task is not None, "Task should exist"
            assert task["body"] == "existing body", f"Body should be preserved, got {task.get('body')!r}"
            assert task["title"] == "New Title", f"Title should be updated, got {task.get('title')!r}"
            ok("upsert_task merge preserves body")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("upsert_task merge preserves body", exc)

    # --- (7) all_tasks returns all documents ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.upsert_task({"slug": "a", "title": "A"})
            store.upsert_task({"slug": "b", "title": "B"})
            store.upsert_task({"slug": "c", "title": "C"})
            tasks = store.all_tasks()
            assert len(tasks) == 3, f"Should have 3 tasks, got {len(tasks)}"
            ok("all_tasks returns all documents")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("all_tasks returns all documents", exc)

    # --- (8) invalidate Home.md marks uninitialized ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            home_content = "# Tasks\n\n## Title\n[my-slug]\n\n"
            store.set("Home.md", home_content)
            assert store.get("Home.md") is not None, "Should be initialized after set"
            store.invalidate("Home.md")
            result = store.get("Home.md")
            assert result is None, "Should be None after invalidate"
            ok("invalidate Home.md marks uninitialized")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("invalidate Home.md marks uninitialized", exc)

    # --- (9) invalidate other.md clears file cache ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.set("other.md", "content")
            assert store.get("other.md") is not None, "Should be cached after set"
            store.invalidate("other.md")
            result = store.get("other.md")
            assert result is None, "Should be None after invalidate"
            ok("invalidate other.md clears file cache")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("invalidate other.md clears file cache", exc)

    # --- (10) Store loads existing tasks.json on init ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"

            store1 = Store(db_path)
            store1.upsert_task({"slug": "persistent", "title": "Persistent Task"})
            del store1

            store2 = Store(db_path)
            task = store2.get_by_slug("persistent")
            assert task is not None, "Task should be loaded from disk on new Store init"
            assert task["title"] == "Persistent Task", "Task data should be preserved"
            ok("Store loads existing tasks.json on init")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("Store loads existing tasks.json on init", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
