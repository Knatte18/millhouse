"""Unit tests for plugins/mill/scripts/_render.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _render import render  # noqa: E402


def main() -> int:
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write("hello <NAME>, today is <DATE>\n")
            tmp_path = Path(tmp.name)
        try:
            out = render(tmp_path, {"NAME": "world", "DATE": "2026-04-19"})
            assert out == "hello world, today is 2026-04-19\n", f"unexpected: {out!r}"
            print(f"PASS: render substitutes tokens -- {out.strip()}")
        finally:
            tmp_path.unlink()

        # Unresolved token raises KeyError.
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write("hello <NAME> and <MISSING>\n")
            tmp_path = Path(tmp.name)
        try:
            try:
                render(tmp_path, {"NAME": "world"})
            except KeyError as exc:
                assert "MISSING" in str(exc), str(exc)
                print(f"PASS: render raises KeyError on unresolved token -- {exc}")
            else:
                raise AssertionError("expected KeyError")
        finally:
            tmp_path.unlink()

        # (a) Leading comment is stripped before render.
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write("<!-- doc comment -->\n# Hello <NAME>\n")
            tmp_path = Path(tmp.name)
        try:
            out = render(tmp_path, {"NAME": "world"})
            assert out == "# Hello world\n", f"unexpected: {out!r}"
            assert "doc comment" not in out
            print("PASS: render strips leading HTML comment before substitution")
        finally:
            tmp_path.unlink()

        # (b) Mid-template comment is preserved verbatim.
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write("# Hello\n<!-- inline -->\n<NAME>\n")
            tmp_path = Path(tmp.name)
        try:
            out = render(tmp_path, {"NAME": "world"})
            assert "<!-- inline -->" in out, f"mid-template comment missing: {out!r}"
            assert "world" in out
            print("PASS: render preserves mid-template comment verbatim")
        finally:
            tmp_path.unlink()

        # (c) Template that is only a comment renders to empty string.
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write("<!-- only a comment -->")
            tmp_path = Path(tmp.name)
        try:
            out = render(tmp_path, {})
            assert out == "", f"expected empty string, got {out!r}"
            print("PASS: render returns empty string for comment-only template")
        finally:
            tmp_path.unlink()

        # (d) Tokens inside leading comment are NOT substituted (no KeyError).
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write("<!-- <MISSING_TOKEN> -->\n# Hello <NAME>\n")
            tmp_path = Path(tmp.name)
        try:
            out = render(tmp_path, {"NAME": "world"})
            assert out == "# Hello world\n", f"unexpected: {out!r}"
            print("PASS: tokens inside leading comment are not checked (no KeyError)")
        finally:
            tmp_path.unlink()

        # (e) Tokens after leading comment ARE substituted.
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as tmp:
            tmp.write("<!-- doc -->\n<GREETING> <TARGET>\n")
            tmp_path = Path(tmp.name)
        try:
            out = render(tmp_path, {"GREETING": "Hello", "TARGET": "world"})
            assert out == "Hello world\n", f"unexpected: {out!r}"
            print("PASS: tokens after leading comment are substituted normally")
        finally:
            tmp_path.unlink()

        print("All _render unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
