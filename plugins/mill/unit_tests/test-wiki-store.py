"""Unit tests for wiki._store.Store in-process cache logic.

Covers: empty store returns None; set+get round-trip with hash;
invalidate removes entries and is idempotent; invalidate_all clears all;
hash is SHA-256 of UTF-8 content; independent stores are isolated;
non-ASCII content survives round-trip with correct hash.
"""
from __future__ import annotations

import hashlib
import sys
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

    # --- (a) empty store returns None ---
    try:
        store = Store()
        result = store.get("nonexistent.md")
        assert result is None, "expected None on empty store"
        ok("empty store returns None")
    except Exception as exc:
        fail("empty store returns None", exc)

    # --- (b) set then get returns (content, hash) with correct hash ---
    try:
        store = Store()
        content = "hello world"
        store.set("test.md", content)
        result = store.get("test.md")
        assert result is not None, "expected non-None after set"
        actual_content, actual_hash = result
        assert actual_content == content, f"content mismatch: {actual_content!r} != {content!r}"
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert actual_hash == expected_hash, f"hash mismatch: {actual_hash!r} != {expected_hash!r}"
        ok("set then get returns (content, hash) with correct hash")
    except Exception as exc:
        fail("set then get returns (content, hash) with correct hash", exc)

    # --- (c) invalidate removes entry (subsequent get returns None) ---
    try:
        store = Store()
        store.set("test.md", "content")
        store.invalidate("test.md")
        result = store.get("test.md")
        assert result is None, "expected None after invalidate"
        ok("invalidate removes entry")
    except Exception as exc:
        fail("invalidate removes entry", exc)

    # --- (d) invalidate on absent key is no-op (no exception) ---
    try:
        store = Store()
        store.invalidate("nonexistent.md")
        ok("invalidate on absent key is no-op")
    except Exception as exc:
        fail("invalidate on absent key is no-op", exc)

    # --- (e) invalidate_all clears all entries ---
    try:
        store = Store()
        store.set("a.md", "content a")
        store.set("b.md", "content b")
        store.set("c.md", "content c")
        store.invalidate_all()
        assert store.get("a.md") is None
        assert store.get("b.md") is None
        assert store.get("c.md") is None
        ok("invalidate_all clears all entries")
    except Exception as exc:
        fail("invalidate_all clears all entries", exc)

    # --- (f) content_hash is SHA-256 of UTF-8 content ---
    try:
        test_content = "hello"
        expected = hashlib.sha256("hello".encode()).hexdigest()
        actual = Store.content_hash(test_content)
        assert actual == expected, f"hash mismatch: {actual!r} != {expected!r}"
        ok("content_hash is SHA-256 of UTF-8 content")
    except Exception as exc:
        fail("content_hash is SHA-256 of UTF-8 content", exc)

    # --- (g) two stores are independent instances ---
    try:
        store1 = Store()
        store2 = Store()
        store1.set("test.md", "content1")
        result2 = store2.get("test.md")
        assert result2 is None, "store2 should not have store1's entry"
        ok("two stores are independent instances")
    except Exception as exc:
        fail("two stores are independent instances", exc)

    # --- (h) non-ASCII content survives set+get round-trip with correct hash ---
    try:
        content = "Nær"
        store = Store()
        store.set("norwegian.md", content)
        result = store.get("norwegian.md")
        assert result is not None
        actual_content, actual_hash = result
        assert actual_content == content, f"non-ASCII content mismatch: {actual_content!r} != {content!r}"
        expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        assert actual_hash == expected_hash, f"hash mismatch for non-ASCII: {actual_hash!r} != {expected_hash!r}"
        ok("non-ASCII content survives round-trip with correct hash")
    except Exception as exc:
        fail("non-ASCII content survives round-trip with correct hash", exc)

    print("", file=sys.stderr)
    if failed:
        print(f"FAIL -- {failed} of {passed + failed}", file=sys.stderr)
        return 1
    print(f"PASS -- all {passed} tests", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
