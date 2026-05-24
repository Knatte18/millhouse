"""Unit tests for wiki._store.Store TinyDB-backed implementation.

Covers: id-from-0, identifier dispatch, get_task, remove_task, set_phase,
list_tasks_brief, list_tasks_full, upsert_tasks_batch, merge_tasks, reload.
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

    # --- (1) upsert_task on empty DB assigns id = 0 ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            task = store.upsert_task({"slug": "first"})
            assert task.get("id") == 0, f"First task should have id=0, got {task.get('id')}"
            ok("upsert_task on empty DB assigns id = 0")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("upsert_task on empty DB assigns id = 0", exc)

    # --- (2) upsert_task assigns next id = max + 1 ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.upsert_task({"slug": "a", "id": 0})
            store.upsert_task({"slug": "b", "id": 1})
            store.upsert_task({"slug": "d", "id": 3})
            task = store.upsert_task({"slug": "e"})
            assert task.get("id") == 4, f"Next id should be 4, got {task.get('id')}"
            ok("upsert_task with gaps assigns next id = max + 1")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("upsert_task with gaps assigns next id = max + 1", exc)

    # --- (3) upsert_task with existing slug updates and preserves id ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            task1 = store.upsert_task({"slug": "t", "title": "Original"})
            orig_id = task1.get("id")
            task2 = store.upsert_task({"slug": "t", "title": "Updated"})
            assert task2.get("id") == orig_id, "ID should be preserved on update"
            assert task2.get("title") == "Updated", "Title should be updated"
            ok("upsert_task with existing slug updates and preserves id")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("upsert_task with existing slug updates and preserves id", exc)

    # --- (4) get_task(slug) and get_task(id) return same record ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            task1 = store.upsert_task({"slug": "myslug", "title": "My Task"})
            task_id = task1.get("id")

            by_slug = store.get_task("myslug")
            by_id = store.get_task(task_id)

            assert by_slug == by_id, "get_task by slug and id should return same dict"
            ok("get_task(slug) and get_task(id) return same record")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("get_task(slug) and get_task(id) return same record", exc)

    # --- (5) get_task with missing identifier returns None ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            result_slug = store.get_task("nonexistent")
            result_id = store.get_task(999)
            assert result_slug is None, "Missing slug should return None"
            assert result_id is None, "Missing id should return None"
            ok("get_task with missing identifier returns None")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("get_task with missing identifier returns None", exc)

    # --- (6) remove_task(slug) and remove_task(id) both work ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            task1 = store.upsert_task({"slug": "r1"})
            task2 = store.upsert_task({"slug": "r2"})
            task_id = task1.get("id")

            store.remove_task("r1")
            assert store.get_task("r1") is None, "Task should be removed by slug"

            store.remove_task(task2.get("id"))
            assert store.get_task("r2") is None, "Task should be removed by id"
            ok("remove_task(slug) and remove_task(id) both work")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("remove_task(slug) and remove_task(id) both work", exc)

    # --- (7) remove_task with missing identifier returns silently ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.remove_task("nonexistent")
            store.remove_task(999)
            ok("remove_task with missing identifier returns silently")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("remove_task with missing identifier returns silently", exc)

    # --- (8) set_phase updates and clears status ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            task = store.upsert_task({"slug": "p"})

            store.set_phase("p", "active")
            updated = store.get_task("p")
            assert updated.get("status") == "active", "Status should be set"

            store.set_phase("p", None)
            cleared = store.get_task("p")
            assert cleared.get("status") is None, "Status should be cleared"
            ok("set_phase updates and clears status")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("set_phase updates and clears status", exc)

    # --- (9) list_tasks_brief returns correct key set and has_proposal ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.upsert_task({"slug": "with-body", "body": "content"})
            store.upsert_task({"slug": "without-body", "body": ""})

            brief_list = store.list_tasks_brief()
            assert len(brief_list) == 2, f"Should have 2 tasks, got {len(brief_list)}"

            for row in brief_list:
                key_set = set(row.keys())
                expected = {"id", "slug", "title", "group", "brief", "status", "has_proposal"}
                assert key_set == expected, f"Key set mismatch: {key_set} vs {expected}"
                assert "body" not in row, "body should not be in brief dict"

            by_slug = {r["slug"]: r for r in brief_list}
            assert by_slug["with-body"]["has_proposal"] == True, "has_proposal should be True for task with body"
            assert by_slug["without-body"]["has_proposal"] == False, "has_proposal should be False for task without body"
            ok("list_tasks_brief returns correct key set and has_proposal")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("list_tasks_brief returns correct key set and has_proposal", exc)

    # --- (10) list_tasks_full returns all fields including body ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.upsert_task({"slug": "full", "body": "proposal content"})

            full_list = store.list_tasks_full()
            assert len(full_list) == 1, f"Should have 1 task, got {len(full_list)}"
            task = full_list[0]
            assert "body" in task, "Full task should contain body field"
            assert task["body"] == "proposal content", "Body should be preserved"
            ok("list_tasks_full returns all fields including body")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("list_tasks_full returns all fields including body", exc)

    # --- (11) upsert_tasks_batch upserts multiple tasks ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            tasks = [
                {"slug": "batch1", "title": "Batch 1"},
                {"slug": "batch2", "title": "Batch 2"},
            ]
            store.upsert_tasks_batch(tasks)

            result = store.list_tasks_brief()
            assert len(result) == 2, f"Should have 2 tasks, got {len(result)}"
            ok("upsert_tasks_batch upserts multiple tasks")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("upsert_tasks_batch upserts multiple tasks", exc)

    # --- (12) merge_tasks performs atomic multi-step operation ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)

            store.upsert_task({"slug": "remove-a"})
            store.upsert_task({"slug": "remove-b"})
            upsert_task = store.upsert_task({"slug": "merge-c", "title": "C"})
            merge_c_id = upsert_task.get("id")

            result = store.merge_tasks(
                remove_slugs=["remove-a", "remove-b"],
                upsert={"slug": "merge-c", "title": "Updated C"},
                set_phase=(merge_c_id, "active"),
            )

            assert result.get("slug") == "merge-c", "Upserted task should be returned"
            assert store.get_task("remove-a") is None, "remove-a should be removed"
            assert store.get_task("remove-b") is None, "remove-b should be removed"

            c_task = store.get_task("merge-c")
            assert c_task.get("title") == "Updated C", "merge-c should be updated"
            assert c_task.get("status") == "active", "merge-c status should be set to active"
            ok("merge_tasks performs atomic multi-step operation")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("merge_tasks performs atomic multi-step operation", exc)

    # --- (13) reload discards in-memory state ---
    try:
        tmp_dir = tempfile.mkdtemp()
        try:
            db_path = Path(tmp_dir) / "tasks.json"
            store = Store(db_path)
            store.upsert_task({"slug": "reload-test"})

            # Manually mutate tasks.json file to add a new task (simulating external change)
            import json
            data = json.loads(db_path.read_text())
            data["_default"]["2"] = {
                "id": 1,
                "slug": "new-task",
                "group": None,
                "brief": "",
                "body": "",
                "status": None,
                "title": "New"
            }
            db_path.write_text(json.dumps(data))

            # Reload should re-read from disk and see the new task
            store.reload()
            brief_after = store.list_tasks_brief()
            assert len(brief_after) == 2, f"After reload, should see 2 tasks, got {len(brief_after)}"
            ok("reload discards in-memory state")
        finally:
            import shutil
            shutil.rmtree(tmp_dir, ignore_errors=True)
    except Exception as exc:
        fail("reload discards in-memory state", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
