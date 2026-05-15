"""Unit tests for plugins/mill/scripts/_review_cli.py.

# TODO: CLI subprocess-level tests (running millpy-review-*.py against a tempfile
# fixture and asserting ERROR: on stderr) are deferred to integration_tests/.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
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

    # (d) validate_role_refs failure via millpy-review-discussion CLI
    # wiki/config.yaml references "missing_reviewer"; reviewers.yaml omits it.
    # main() should exit 1 and write the missing name to stderr.
    import importlib.util as _ilu
    _cli_path = HUB / "plugins" / "mill" / "scripts" / "millpy-review-discussion.py"
    _spec = _ilu.spec_from_file_location("millpy_review_discussion", str(_cli_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    with tempfile.TemporaryDirectory() as _tmpdir:
        _tmp = Path(_tmpdir)
        _wiki = _tmp / "wiki"
        _wiki.mkdir()
        (_wiki / "config.yaml").write_text(
            "roles:\n"
            "  discussion-review:\n"
            "    holistic:\n"
            "      rounds: 2\n"
            "      reviewer: missing_reviewer\n"
            "paths:\n"
            "  discussion_file: discussion.md\n"
            "  plan_dir: plan/\n"
            "  reviews_dir: reviews/\n",
            encoding="utf-8",
        )
        (_wiki / "agents.yaml").write_text(
            "sonnetmax:\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: claude-sonnet-4-6\n",
            encoding="utf-8",
        )
        _mill = _tmp / ".millhouse"
        _mill.mkdir()

        import unittest.mock as _mock
        import os as _os

        _orig_cwd = _os.getcwd()
        _os.chdir(_tmp)
        _err_buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(_err_buf):
                with _mock.patch("_paths.resolve_wiki_path", return_value=_wiki):
                    _rc = _mod.main([])
        finally:
            _os.chdir(_orig_cwd)

        _err_text = _err_buf.getvalue()
        if _rc != 1:
            print(f"FAIL (d) exit code: expected 1, got {_rc}", file=sys.stderr)
            failures += 1
        if "missing_reviewer" not in _err_text:
            print(f"FAIL (d) stderr missing reviewer name: {_err_text!r}", file=sys.stderr)
            failures += 1

    if failures == 0:
        print("test-review-cli: all tests passed")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
