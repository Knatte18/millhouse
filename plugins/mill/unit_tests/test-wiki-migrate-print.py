"""Unit tests for millpy-wiki-migrate.py's _ensure_utf8_stdout() stdout guard.

Loads millpy-wiki-migrate.py via importlib.util.spec_from_file_location (the
file has a hyphenated name and cannot be `import`ed directly -- same pattern
as test-abandon.py's trampoline loader). Uses the ok()/fail() harness pattern
from test-wiki-client-retry.py.

Covers: #588 -- printing externally-authored wiki content (task titles,
briefs) containing non-ASCII characters must not crash with
UnicodeEncodeError on a Windows cp1252 console. _ensure_utf8_stdout()
reconfigures sys.stdout to UTF-8 before any such content is printed.
"""
from __future__ import annotations

import importlib.util
import io
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"

_spec = importlib.util.spec_from_file_location(
    "mill_wiki_migrate", str(SCRIPTS / "millpy-wiki-migrate.py")
)
_wiki_migrate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_wiki_migrate)


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

    # --- non-ASCII print survives on a simulated cp1252 stdout ---
    try:
        original_stdout = sys.stdout
        try:
            # Simulate a Windows cp1252 console -- the precondition that
            # triggered #588's UnicodeEncodeError crash.
            sys.stdout = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")

            _wiki_migrate._ensure_utf8_stdout()

            assert sys.stdout.encoding.lower() == "utf-8", (
                f"expected stdout encoding 'utf-8' after guard, got {sys.stdout.encoding!r}"
            )

            try:
                print("test: →")
            except UnicodeEncodeError as exc:
                fail(
                    "non-ASCII print survives on a simulated cp1252 stdout",
                    exc,
                )
            else:
                ok("non-ASCII print survives on a simulated cp1252 stdout")
        finally:
            sys.stdout = original_stdout
    except Exception as exc:
        fail("non-ASCII print survives on a simulated cp1252 stdout", exc)

    print(f"\n{passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
