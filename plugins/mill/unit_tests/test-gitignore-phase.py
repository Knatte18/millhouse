"""Unit tests for plugins/mill/scripts/_gitignore.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _gitignore import END, STANDARD_ENTRIES, START, upsert  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors = 0

    # --- empty .gitignore + upsert(p, []) ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        changed = upsert(gi, [])
        content = _read(gi)
        if not changed:
            print("FAIL: empty .gitignore + upsert([]) should return True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: empty .gitignore + upsert([]) -> True")
        if START not in content:
            print("FAIL: START marker missing after upsert on empty file", file=sys.stderr)
            errors += 1
        else:
            print("PASS: START marker present")
        if END not in content:
            print("FAIL: END marker missing after upsert on empty file", file=sys.stderr)
            errors += 1
        else:
            print("PASS: END marker present")
        for entry in STANDARD_ENTRIES:
            if entry not in content:
                print(f"FAIL: standard entry missing: {entry}", file=sys.stderr)
                errors += 1
            else:
                print(f"PASS: standard entry present: {entry}")
        # No extra trailing whitespace beyond the final newline
        if content.rstrip("\n") != content.rstrip():
            print("FAIL: trailing whitespace beyond newline", file=sys.stderr)
            errors += 1
        else:
            print("PASS: no extra trailing whitespace")

    # --- empty .gitignore + upsert(p, ["tasks.md"]) ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        changed = upsert(gi, ["tasks.md"])
        content = _read(gi)
        if "/tasks.md" not in content:
            print("FAIL: /tasks.md not in block after upsert with hardlink entry", file=sys.stderr)
            errors += 1
        else:
            print("PASS: /tasks.md present in block")
        if not changed:
            print("FAIL: upsert with hardlink entry should return True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: upsert with hardlink entry -> True")
        # Entry must appear after the standard entries inside the block
        block_start = content.index(START)
        block_end = content.index(END)
        block_inner = content[block_start:block_end]
        last_std_pos = max(block_inner.find(e) for e in STANDARD_ENTRIES)
        hardlink_pos = block_inner.find("/tasks.md")
        if hardlink_pos < last_std_pos:
            print("FAIL: hardlink entry appears before standard entries", file=sys.stderr)
            errors += 1
        else:
            print("PASS: hardlink entry appears after standard entries")

    # --- existing user content + no marker → block appended after user content ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        user_content = "# user content\n*.log\n"
        gi.write_text(user_content, encoding="utf-8")
        changed = upsert(gi, [])
        content = _read(gi)
        if not changed:
            print("FAIL: user content + no marker should return True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: user content + no marker -> True")
        if not content.startswith(user_content.rstrip("\n")):
            print("FAIL: user content not preserved before block", file=sys.stderr)
            errors += 1
        else:
            print("PASS: user content preserved before block")
        start_pos = content.find(START)
        if start_pos <= 0:
            print("FAIL: block should appear after user content", file=sys.stderr)
            errors += 1
        else:
            # Check blank-line separator
            if "\n\n" not in content[content.find("*.log"):start_pos]:
                print("FAIL: no blank-line separator before block", file=sys.stderr)
                errors += 1
            else:
                print("PASS: blank-line separator before block")

    # --- re-run upsert with same input → returns False ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        upsert(gi, ["tasks.md"])
        first_content = _read(gi)
        changed = upsert(gi, ["tasks.md"])
        second_content = _read(gi)
        if changed:
            print("FAIL: re-run with same input should return False", file=sys.stderr)
            errors += 1
        else:
            print("PASS: re-run with same input -> False")
        if first_content != second_content:
            print("FAIL: file changed on idempotent re-run", file=sys.stderr)
            errors += 1
        else:
            print("PASS: file byte-equal on idempotent re-run")

    # --- stale marker block → block rewritten, outside-marker content unchanged ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        user_before = "# user entry\n*.bak\n"
        stale_block = f"{START}\n**/.old-path/\n{END}\n"
        gi.write_text(user_before + "\n" + stale_block, encoding="utf-8")
        changed = upsert(gi, [])
        content = _read(gi)
        if not changed:
            print("FAIL: stale block should return True", file=sys.stderr)
            errors += 1
        else:
            print("PASS: stale block -> True (rewritten)")
        if "**/.old-path/" in content:
            print("FAIL: stale entry still present after rewrite", file=sys.stderr)
            errors += 1
        else:
            print("PASS: stale entry removed")
        for entry in STANDARD_ENTRIES:
            if entry not in content:
                print(f"FAIL: standard entry missing after rewrite: {entry}", file=sys.stderr)
                errors += 1
        if "# user entry" not in content or "*.bak" not in content:
            print("FAIL: outside-marker user content was changed", file=sys.stderr)
            errors += 1
        else:
            print("PASS: outside-marker user content unchanged after rewrite")

    # --- START present but END missing → ValueError ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text(f"{START}\n**/.millhouse/\n", encoding="utf-8")
        try:
            upsert(gi, [])
            print("FAIL: expected ValueError for missing END marker", file=sys.stderr)
            errors += 1
        except ValueError as exc:
            print(f"PASS: ValueError raised for missing END marker: {exc}")

    # --- hardlink entry without leading / → normalised ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        upsert(gi, ["tasks.md"])
        content = _read(gi)
        if "tasks.md" in content and "/tasks.md" not in content:
            print("FAIL: entry not normalised to /tasks.md", file=sys.stderr)
            errors += 1
        elif "/tasks.md" in content:
            print("PASS: entry without / normalised to /tasks.md")
        else:
            print("FAIL: /tasks.md not found in output", file=sys.stderr)
            errors += 1

    # --- hardlink entry already /-prefixed → kept as-is (no double slash) ---
    with tempfile.TemporaryDirectory() as tmpdir:
        gi = Path(tmpdir) / ".gitignore"
        gi.write_text("", encoding="utf-8")
        upsert(gi, ["/tasks.md"])
        content = _read(gi)
        if "//tasks.md" in content:
            print("FAIL: double slash introduced for already-prefixed entry", file=sys.stderr)
            errors += 1
        elif "/tasks.md" in content:
            print("PASS: already-prefixed entry kept as-is (no double slash)")
        else:
            print("FAIL: /tasks.md not found in output for already-prefixed entry", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _gitignore unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
