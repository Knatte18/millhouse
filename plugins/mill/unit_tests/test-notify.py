"""Unit tests for _notify.py + _notify_stdout.py.

Verifies that ``notify()`` dispatches through the default stdout backend
without raising and that the backend prints its expected single-line
format to stderr.
"""
from __future__ import annotations

import io
import sys
from contextlib import redirect_stderr
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _notify  # noqa: E402
import _notify_stdout  # noqa: E402


def main() -> int:
    try:
        # stdout backend BACKEND name and send()
        assert _notify_stdout.BACKEND == "stdout"
        buf = io.StringIO()
        with redirect_stderr(buf):
            _notify_stdout.send("mill-go.test", "smoke", {"slug": "demo", "round": 2})
            _notify_stdout.send("mill-go.test", "no ctx", {})
        out = buf.getvalue()
        assert "[notify] mill-go.test  smoke" in out
        assert "slug=demo" in out
        assert "round=2" in out
        print("PASS: _notify_stdout.send writes single-line events")

        # notify() dispatcher — just verify it doesn't raise (delivery errors are swallowed)
        _notify._reset_cache_for_tests()
        buf = io.StringIO()
        with redirect_stderr(buf):
            _notify.notify("mill-go.test", "smoke check ok", slug="demo", batch="foundation")
        assert "[notify] mill-go.test" in buf.getvalue()
        print("PASS: _notify.notify() dispatches via stdout backend")

        print("All _notify unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
