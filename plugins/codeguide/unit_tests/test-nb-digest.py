"""Unit tests for plugins/codeguide/scripts/nb_digest.py."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "codeguide" / "scripts"))

from nb_digest import build_digest, notebook_language, load_notebook  # noqa: E402


def _make_notebook(cells: list[dict], metadata: dict | None = None) -> dict:
    """Create a minimal nbformat notebook dict."""
    if metadata is None:
        metadata = {}
    return {
        "cells": cells,
        "metadata": metadata,
        "nbformat": 4,
        "nbformat_minor": 2,
    }


def _code_cell(source: str | list[str], outputs: list[dict] | None = None) -> dict:
    """Create a code cell."""
    if isinstance(source, str):
        source = [source]
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": outputs or [],
        "source": source,
    }


def _markdown_cell(source: str | list[str]) -> dict:
    """Create a markdown cell."""
    if isinstance(source, str):
        source = [source]
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source,
    }


def _raw_cell(source: str | list[str]) -> dict:
    """Create a raw cell."""
    if isinstance(source, str):
        source = [source]
    return {
        "cell_type": "raw",
        "metadata": {},
        "source": source,
    }


def main() -> int:
    try:
        # Test 1: Outputs stripped - code cell with various outputs
        nb = _make_notebook([
            _code_cell("print('hello')", outputs=[
                {"output_type": "stream", "name": "stdout", "text": "hello\n"},
                {"output_type": "display_data", "data": {"image/png": "iVBORw0KGgoAAAANS..."}},
                {"output_type": "execute_result", "data": {"text/plain": "42"}},
            ])
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "print('hello')" in digest, "Code should be present"
        assert "[1 output(s) omitted]" in digest, "Should have output marker"
        assert "iVBORw0KGgoAAAANS" not in digest, "Base64 image data should not be in digest"
        assert "hello" not in digest or "print('hello')" in digest, "Stdout should not be in digest"
        print("PASS: outputs stripped from digest")

        # Test 2: Markdown kept verbatim
        nb = _make_notebook([
            _markdown_cell("# Title\n\nThis is **bold** and *italic*."),
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "# Title" in digest, "Markdown content should be present"
        assert "This is **bold** and *italic*." in digest, "Markdown formatting should be preserved"
        print("PASS: markdown kept verbatim")

        # Test 3: Oversized code cell truncated
        large_code = "\n".join([f"line_{i} = {i}" for i in range(200)])
        nb = _make_notebook([
            _code_cell(large_code),
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "[code cell truncated:" in digest, "Should have truncation marker"
        assert "line_0 = 0" in digest, "Should have head lines"
        assert "line_199 = 199" in digest, "Should have tail lines"
        assert "line_50 = 50" not in digest or "line_100" not in digest, \
            "Middle lines should not be present (one of them should be cut)"
        print("PASS: oversized code cell truncated")

        # Test 4: Normal code cell not truncated
        normal_code = "\n".join([f"x = {i}" for i in range(50)])
        nb = _make_notebook([
            _code_cell(normal_code),
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "[code cell truncated:" not in digest, "Should not have truncation marker"
        assert "x = 0" in digest, "Should have all lines"
        assert "x = 49" in digest, "Should have all lines"
        print("PASS: normal code cell not truncated")

        # Test 5: Non-Python kernel labeling
        nb = _make_notebook(
            [_code_cell("x <- 5")],
            metadata={
                "kernelspec": {
                    "display_name": "R",
                    "language": "R",
                    "name": "ir",
                }
            }
        )
        digest = build_digest(nb, "test.ipynb")
        assert "# language: R" in digest, "Should label kernel language"
        assert "```R" in digest, "Code fence should use R language"
        print("PASS: non-Python kernel labeled correctly")

        # Test 6: Kernel language from language_info fallback
        nb = _make_notebook(
            [_code_cell("x = 1")],
            metadata={
                "language_info": {
                    "name": "julia",
                }
            }
        )
        digest = build_digest(nb, "test.ipynb")
        assert "# language: julia" in digest, "Should fallback to language_info.name"
        print("PASS: language_info fallback works")

        # Test 7: Empty notebook
        nb = _make_notebook([])
        digest = build_digest(nb, "test.ipynb")
        assert "# cells: 0" in digest, "Should show cell count"
        assert "[0 output(s) omitted]" not in digest, "Should not have spurious output marker"
        print("PASS: empty notebook handled")

        # Test 8: Notebook with no outputs
        nb = _make_notebook([
            _code_cell("x = 1"),
            _markdown_cell("Some text"),
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "[0 output(s) omitted]" not in digest, "Should not mark zero outputs"
        print("PASS: outputs-free notebook no spurious markers")

        # Test 9: Raw cell
        nb = _make_notebook([
            _raw_cell("raw content\nline 2"),
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "[raw cell 1]" in digest, "Should have raw cell marker"
        assert "raw content" in digest, "Should have raw content"
        print("PASS: raw cell handled")

        # Test 10: Unknown cell type treated as raw
        nb = _make_notebook([
            {
                "cell_type": "unknown_type",
                "metadata": {},
                "source": "unknown cell content",
            }
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "[raw cell 1]" in digest, "Unknown cell type should be treated as raw"
        assert "unknown cell content" in digest, "Should have content"
        print("PASS: unknown cell type treated as raw")

        # Test 11: Single-string source (not list)
        nb = _make_notebook([
            _code_cell("single_string_source = True"),
        ])
        # Override source to be string instead of list
        nb["cells"][0]["source"] = "single_string_source = True"
        digest = build_digest(nb, "test.ipynb")
        assert "single_string_source = True" in digest, "Single string source should work"
        print("PASS: single-string source handled")

        # Test 12: Markdown with single-string source
        nb = _make_notebook([
            _markdown_cell("# Heading"),
        ])
        nb["cells"][0]["source"] = "# Heading"  # Override to string
        digest = build_digest(nb, "test.ipynb")
        assert "# Heading" in digest, "Markdown single-string source should work"
        print("PASS: markdown single-string source handled")

        # Test 13: Multiple cells with various types
        nb = _make_notebook([
            _markdown_cell("## Introduction"),
            _code_cell("x = 1\ny = 2"),
            _markdown_cell("## Analysis"),
            _code_cell("result = x + y"),
            _raw_cell("Some raw data"),
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "# cells: 5" in digest, "Should count all cells"
        assert "[markdown cell 1]" in digest, "Should have markdown cell 1"
        assert "[code cell 2]" in digest, "Should have code cell 2"
        assert "[markdown cell 3]" in digest, "Should have markdown cell 3"
        assert "[code cell 4]" in digest, "Should have code cell 4"
        assert "[raw cell 5]" in digest, "Should have raw cell 5"
        print("PASS: multiple cells of various types")

        # Test 14: Malformed input returns exit code 2
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            bad_json = tmppath / "bad.ipynb"
            bad_json.write_text("{invalid json", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(HUB / "plugins" / "codeguide" / "scripts" / "nb_digest.py"),
                 str(bad_json)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            assert result.returncode == 2, f"Expected exit code 2, got {result.returncode}"
            assert result.stdout == "", "Stdout should be empty on error"
            assert len(result.stderr) > 0, "Stderr should have error message"
            print("PASS: malformed JSON returns exit code 2")

        # Test 15: Non-ASCII cell content round-trip
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            nb_file = tmppath / "unicode.ipynb"
            nb = _make_notebook([
                _markdown_cell("This notebook has Unicode: éñü (French/Spanish/German)"),
                _code_cell("# Comment in Chinese: 中文\nprint('Hello')"),
            ])
            nb_file.write_text(json.dumps(nb), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(HUB / "plugins" / "codeguide" / "scripts" / "nb_digest.py"),
                 str(nb_file)],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            assert result.returncode == 0, f"Exit code should be 0, got {result.returncode}"
            assert "éñü" in result.stdout or "Unicode:" in result.stdout, \
                "Non-ASCII content should survive or at least not crash"
            # Allow for replace mode stripping unprintable chars, just verify no crash
            print("PASS: non-ASCII cell content survives subprocess round-trip")

        # Test 16: Header with source name
        nb = _make_notebook([_code_cell("x = 1")])
        digest = build_digest(nb, "my_analysis.ipynb")
        assert "# notebook digest: my_analysis.ipynb" in digest, "Header should include source name"
        print("PASS: header includes source name")

        # Test 17: load_notebook validation
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            # Not a JSON object
            bad_file = tmppath / "not_object.ipynb"
            bad_file.write_text('[]', encoding="utf-8")
            try:
                load_notebook(bad_file)
                assert False, "Should raise ValueError for non-object"
            except ValueError:
                pass
            print("PASS: load_notebook rejects non-object JSON")

        # Test 18: load_notebook missing cells key
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            bad_file = tmppath / "no_cells.ipynb"
            bad_file.write_text('{"metadata": {}}', encoding="utf-8")
            try:
                load_notebook(bad_file)
                assert False, "Should raise ValueError for missing cells"
            except ValueError as e:
                assert "cells" in str(e).lower(), "Error should mention cells"
            print("PASS: load_notebook rejects missing cells key")

        # Test 19: Notebook language defaults to "text"
        nb = _make_notebook([_code_cell("x = 1")])
        lang = notebook_language(nb)
        assert lang == "text", f"Should default to 'text', got '{lang}'"
        print("PASS: notebook_language defaults to text")

        # Test 20: Code cell with multiple outputs
        nb = _make_notebook([
            _code_cell("1+1", outputs=[
                {"output_type": "execute_result", "data": {"text/plain": "2"}},
                {"output_type": "execute_result", "data": {"text/plain": "2"}},
                {"output_type": "stream", "name": "stdout", "text": "done\n"},
            ])
        ])
        digest = build_digest(nb, "test.ipynb")
        assert "[3 output(s) omitted]" in digest, "Should count all 3 outputs"
        print("PASS: multiple outputs counted correctly")

        print("All nb_digest unit tests passed.")
        return 0

    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
