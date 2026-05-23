"""Unit tests for wiki protocol JSON envelope and field mapping.

Covers: read request round-trip; write request with FIELD_FILES;
success and error response envelopes; CONFLICT, AUTH error types;
PROTOCOL_VERSION is 1 (integer).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from wiki import (
    PROTOCOL_VERSION,
    OP_READ,
    OP_WRITE,
    FIELD_OP,
    FIELD_TOKEN,
    FIELD_PATH,
    FIELD_OK,
    FIELD_CONTENT,
    FIELD_HASH,
    FIELD_ERROR_TYPE,
    FIELD_ERROR,
    FIELD_FILES,
    FIELD_BASE_HASH,
    FIELD_NEW_CONTENT,
    FIELD_MESSAGE,
    ERR_NOT_FOUND,
    ERR_CONFLICT,
    ERR_AUTH,
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

    # --- (a) read request round-trip ---
    try:
        req = {
            FIELD_OP: OP_READ,
            FIELD_TOKEN: "t",
            FIELD_PATH: "Home.md",
        }
        encoded = json.dumps(req)
        decoded = json.loads(encoded)
        assert decoded[FIELD_OP] == OP_READ
        assert decoded[FIELD_TOKEN] == "t"
        assert decoded[FIELD_PATH] == "Home.md"
        ok("read request round-trip")
    except Exception as exc:
        fail("read request round-trip", exc)

    # --- (b) write request with FIELD_FILES ---
    try:
        req = {
            FIELD_OP: OP_WRITE,
            FIELD_TOKEN: "t",
            FIELD_MESSAGE: "commit message",
            FIELD_FILES: {
                "Home.md": {
                    FIELD_BASE_HASH: "abc123",
                    FIELD_NEW_CONTENT: "new content",
                },
            },
        }
        encoded = json.dumps(req)
        decoded = json.loads(encoded)
        assert decoded[FIELD_OP] == OP_WRITE
        assert FIELD_FILES in decoded
        files = decoded[FIELD_FILES]
        assert "Home.md" in files
        file_entry = files["Home.md"]
        assert file_entry[FIELD_BASE_HASH] == "abc123"
        assert file_entry[FIELD_NEW_CONTENT] == "new content"
        ok("write request with FIELD_FILES")
    except Exception as exc:
        fail("write request with FIELD_FILES", exc)

    # --- (c) success response envelope ---
    try:
        resp = {
            FIELD_OK: True,
            FIELD_CONTENT: "file content",
            FIELD_HASH: "hash123",
        }
        assert resp[FIELD_OK] is True
        ok("success response envelope")
    except Exception as exc:
        fail("success response envelope", exc)

    # --- (d) error response envelope with ERR_NOT_FOUND ---
    try:
        resp = {
            FIELD_OK: False,
            FIELD_ERROR_TYPE: ERR_NOT_FOUND,
            FIELD_ERROR: "Home.md",
        }
        assert resp[FIELD_OK] is False
        assert resp[FIELD_ERROR_TYPE] == ERR_NOT_FOUND
        ok("error response envelope with ERR_NOT_FOUND")
    except Exception as exc:
        fail("error response envelope with ERR_NOT_FOUND", exc)

    # --- (e) CONFLICT error envelope ---
    try:
        resp = {
            FIELD_OK: False,
            FIELD_ERROR_TYPE: ERR_CONFLICT,
            FIELD_ERROR: "conflict detected",
        }
        assert resp[FIELD_ERROR_TYPE] == ERR_CONFLICT
        ok("CONFLICT error envelope")
    except Exception as exc:
        fail("CONFLICT error envelope", exc)

    # --- (f) AUTH error envelope ---
    try:
        resp = {
            FIELD_OK: False,
            FIELD_ERROR_TYPE: ERR_AUTH,
            FIELD_ERROR: "bad token",
        }
        assert resp[FIELD_ERROR_TYPE] == ERR_AUTH
        ok("AUTH error envelope")
    except Exception as exc:
        fail("AUTH error envelope", exc)

    # --- (g) PROTOCOL_VERSION is 1 (integer) ---
    try:
        assert PROTOCOL_VERSION == 1, f"expected 1, got {PROTOCOL_VERSION!r}"
        assert isinstance(PROTOCOL_VERSION, int), f"expected int, got {type(PROTOCOL_VERSION)}"
        ok("PROTOCOL_VERSION is 1 (integer)")
    except Exception as exc:
        fail("PROTOCOL_VERSION is 1 (integer)", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
