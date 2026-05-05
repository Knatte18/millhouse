"""Unit tests for plugins/mill/scripts/_review_cli.py.

# TODO: CLI subprocess-level tests (running millpy-review-*.py against a tempfile
# fixture and asserting ERROR: on stderr) are deferred to integration_tests/.
"""
from __future__ import annotations

import contextlib
import io
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _review_cli import print_error  # noqa: E402
from _review_common import ReviewError  # noqa: E402


def main() -> int:
    failures = 0

    # (a) plain message — ERROR: prefix present, hint absent, trailing newline present
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        print_error(ReviewError("plain message"))
    captured = buf.getvalue()
    if not captured.startswith("ERROR: plain message"):
        print(f"FAIL (a) prefix: {captured!r}", file=sys.stderr)
        failures += 1
    if not captured.endswith("\n"):
        print(f"FAIL (a) trailing newline: {captured!r}", file=sys.stderr)
        failures += 1
    if "Hint: check the plan card" in captured:
        print(f"FAIL (a) hint must be absent: {captured!r}", file=sys.stderr)
        failures += 1

    # (b) [resolve_ref_paths] prefix — ERROR: line + hint both present
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        print_error(ReviewError("[resolve_ref_paths] referenced path not found: 'foo.py'"))
    captured = buf.getvalue()
    if "ERROR: [resolve_ref_paths] referenced path not found: 'foo.py'" not in captured:
        print(f"FAIL (b) error line: {captured!r}", file=sys.stderr)
        failures += 1
    if "Hint: check the plan card" not in captured:
        print(f"FAIL (b) hint missing: {captured!r}", file=sys.stderr)
        failures += 1
    if "list it under Deletes:" not in captured:
        print(f"FAIL (b) deletes mention missing: {captured!r}", file=sys.stderr)
        failures += 1

    # (c) [resolve_ref_paths] internal (not at start) — hint must NOT be added
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        print_error(ReviewError("some prefix [resolve_ref_paths] inner"))
    captured = buf.getvalue()
    if "Hint: check the plan card" in captured:
        print(f"FAIL (c) hint must be absent for internal occurrence: {captured!r}", file=sys.stderr)
        failures += 1

    if failures == 0:
        print("test-review-cli: all tests passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
