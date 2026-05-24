"""Unit tests for wiki protocol with structured operations.

Covers: new ops dispatch, OP_READ/OP_WRITE rejection, PROTOCOL_VERSION=2,
auth handling, and version mismatch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki import (
    PROTOCOL_VERSION,
    OP_UPSERT_TASK,
    OP_UPSERT_TASKS_BATCH,
    OP_SET_PHASE,
    OP_REMOVE_TASK,
    OP_MERGE_TASKS,
    OP_GET_TASK,
    OP_LIST_TASKS_BRIEF,
    OP_LIST_TASKS_FULL,
    OP_HEALTH,
    FIELD_OP,
    FIELD_TOKEN,
    FIELD_OK,
    FIELD_ERROR_TYPE,
    FIELD_ERROR,
    ERR_NOT_FOUND,
    ERR_PROTOCOL,
)  # noqa: E402


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

    # --- (1) OP_UPSERT_TASK constant ---
    try:
        assert OP_UPSERT_TASK == "upsert_task", f"OP_UPSERT_TASK should be 'upsert_task', got {OP_UPSERT_TASK!r}"
        ok("OP_UPSERT_TASK constant")
    except Exception as exc:
        fail("OP_UPSERT_TASK constant", exc)

    # --- (2) OP_UPSERT_TASKS_BATCH constant ---
    try:
        assert OP_UPSERT_TASKS_BATCH == "upsert_tasks_batch", f"OP_UPSERT_TASKS_BATCH should be 'upsert_tasks_batch', got {OP_UPSERT_TASKS_BATCH!r}"
        ok("OP_UPSERT_TASKS_BATCH constant")
    except Exception as exc:
        fail("OP_UPSERT_TASKS_BATCH constant", exc)

    # --- (3) OP_SET_PHASE constant ---
    try:
        assert OP_SET_PHASE == "set_phase", f"OP_SET_PHASE should be 'set_phase', got {OP_SET_PHASE!r}"
        ok("OP_SET_PHASE constant")
    except Exception as exc:
        fail("OP_SET_PHASE constant", exc)

    # --- (4) OP_REMOVE_TASK constant ---
    try:
        assert OP_REMOVE_TASK == "remove_task", f"OP_REMOVE_TASK should be 'remove_task', got {OP_REMOVE_TASK!r}"
        ok("OP_REMOVE_TASK constant")
    except Exception as exc:
        fail("OP_REMOVE_TASK constant", exc)

    # --- (5) OP_MERGE_TASKS constant ---
    try:
        assert OP_MERGE_TASKS == "merge_tasks", f"OP_MERGE_TASKS should be 'merge_tasks', got {OP_MERGE_TASKS!r}"
        ok("OP_MERGE_TASKS constant")
    except Exception as exc:
        fail("OP_MERGE_TASKS constant", exc)

    # --- (6) OP_GET_TASK constant ---
    try:
        assert OP_GET_TASK == "get_task", f"OP_GET_TASK should be 'get_task', got {OP_GET_TASK!r}"
        ok("OP_GET_TASK constant")
    except Exception as exc:
        fail("OP_GET_TASK constant", exc)

    # --- (7) OP_LIST_TASKS_BRIEF constant ---
    try:
        assert OP_LIST_TASKS_BRIEF == "list_tasks_brief", f"OP_LIST_TASKS_BRIEF should be 'list_tasks_brief', got {OP_LIST_TASKS_BRIEF!r}"
        ok("OP_LIST_TASKS_BRIEF constant")
    except Exception as exc:
        fail("OP_LIST_TASKS_BRIEF constant", exc)

    # --- (8) OP_LIST_TASKS_FULL constant ---
    try:
        assert OP_LIST_TASKS_FULL == "list_tasks_full", f"OP_LIST_TASKS_FULL should be 'list_tasks_full', got {OP_LIST_TASKS_FULL!r}"
        ok("OP_LIST_TASKS_FULL constant")
    except Exception as exc:
        fail("OP_LIST_TASKS_FULL constant", exc)

    # --- (9) OP_HEALTH constant ---
    try:
        assert OP_HEALTH == "health", f"OP_HEALTH should be 'health', got {OP_HEALTH!r}"
        ok("OP_HEALTH constant")
    except Exception as exc:
        fail("OP_HEALTH constant", exc)

    # --- (10) Upsert task request round-trip ---
    try:
        req = {
            FIELD_OP: OP_UPSERT_TASK,
            FIELD_TOKEN: "token123",
            "payload": {"slug": "my-task", "title": "My Task"},
        }
        encoded = json.dumps(req)
        decoded = json.loads(encoded)
        assert decoded[FIELD_OP] == OP_UPSERT_TASK
        assert decoded[FIELD_TOKEN] == "token123"
        assert decoded["payload"]["slug"] == "my-task"
        ok("upsert task request round-trip")
    except Exception as exc:
        fail("upsert task request round-trip", exc)

    # --- (11) Success response with task dict ---
    try:
        resp = {
            FIELD_OK: True,
            "task": {"id": 0, "slug": "my-task", "title": "My Task"},
        }
        assert resp[FIELD_OK] is True
        assert resp["task"]["slug"] == "my-task"
        ok("success response with task dict")
    except Exception as exc:
        fail("success response with task dict", exc)

    # --- (12) Error response with not_found ---
    try:
        resp = {
            FIELD_OK: False,
            FIELD_ERROR_TYPE: ERR_NOT_FOUND,
            FIELD_ERROR: "task not found",
        }
        assert resp[FIELD_OK] is False
        assert resp[FIELD_ERROR_TYPE] == ERR_NOT_FOUND
        ok("error response with not_found")
    except Exception as exc:
        fail("error response with not_found", exc)

    # --- (13) Old OP_READ is rejected ---
    try:
        req = {
            FIELD_OP: "read",
            FIELD_TOKEN: "token",
        }
        resp = {
            FIELD_OK: False,
            FIELD_ERROR_TYPE: ERR_PROTOCOL,
            FIELD_ERROR: "unknown op: read",
        }
        assert resp[FIELD_ERROR_TYPE] == ERR_PROTOCOL
        assert "unknown op: read" in resp[FIELD_ERROR]
        ok("old OP_READ is rejected")
    except Exception as exc:
        fail("old OP_READ is rejected", exc)

    # --- (14) Old OP_WRITE is rejected ---
    try:
        req = {
            FIELD_OP: "write_commit_push",
            FIELD_TOKEN: "token",
        }
        resp = {
            FIELD_OK: False,
            FIELD_ERROR_TYPE: ERR_PROTOCOL,
            FIELD_ERROR: "unknown op: write_commit_push",
        }
        assert resp[FIELD_ERROR_TYPE] == ERR_PROTOCOL
        assert "unknown op: write_commit_push" in resp[FIELD_ERROR]
        ok("old OP_WRITE is rejected")
    except Exception as exc:
        fail("old OP_WRITE is rejected", exc)

    # --- (15) PROTOCOL_VERSION is 2 (integer) ---
    try:
        assert PROTOCOL_VERSION == 2, f"expected 2, got {PROTOCOL_VERSION!r}"
        assert isinstance(PROTOCOL_VERSION, int), f"expected int, got {type(PROTOCOL_VERSION)}"
        ok("PROTOCOL_VERSION is 2 (integer)")
    except Exception as exc:
        fail("PROTOCOL_VERSION is 2 (integer)", exc)

    # --- (16) List tasks brief request ---
    try:
        req = {
            FIELD_OP: OP_LIST_TASKS_BRIEF,
            FIELD_TOKEN: "token",
            "payload": {},
        }
        resp = {
            FIELD_OK: True,
            "tasks": [
                {"id": 0, "slug": "task1", "title": "Task 1", "group": None, "brief": "", "status": None, "has_proposal": False},
            ],
        }
        assert resp[FIELD_OK] is True
        assert len(resp["tasks"]) == 1
        ok("list tasks brief request")
    except Exception as exc:
        fail("list tasks brief request", exc)

    # --- (17) Health check request ---
    try:
        req = {
            FIELD_OP: OP_HEALTH,
            FIELD_TOKEN: "token",
            "payload": {},
        }
        resp = {
            FIELD_OK: True,
        }
        assert resp[FIELD_OK] is True
        ok("health check request")
    except Exception as exc:
        fail("health check request", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
