r"""
Convert a .ipynb notebook to a compact text digest.

The digest contains markdown-cell text and code-cell source with execution
outputs stripped. This helper uses pure stdlib (json, sys, pathlib, argparse)
and parses nbformat JSON directly without importing nbformat or jupyter.

Truncation: code cells over MAX_CODE_CELL_LINES are truncated to
CODE_CELL_HEAD_LINES + marker + CODE_CELL_TAIL_LINES.

Public API
----------
CLI: ``python nb_digest.py <path>``
    stdout  — the notebook digest (UTF-8)
    stderr  — error messages (ASCII only)
    exit    — 0 on success, 2 on error (malformed/missing file/invalid notebook)

Function: ``build_digest(nb: dict, source_name: str) -> str``
    ``nb``          — notebook dict (nbformat shape)
    ``source_name`` — filename or identifier for the header
    Returns         — the digest string (markdown with fenced code blocks)
"""

import argparse
import json
import pathlib
import sys

# Truncation constants for oversized code cells
MAX_CODE_CELL_LINES = 150
CODE_CELL_HEAD_LINES = 100
CODE_CELL_TAIL_LINES = 20


def cell_source_text(cell: dict) -> str:
    """Return the cell's source joined into one string.

    Handles both list[str] (line-by-line) and str representations.
    """
    source = cell.get("source", "")
    if isinstance(source, list):
        return "".join(source)
    return source


def notebook_language(nb: dict) -> str:
    """Return the notebook's kernel language.

    Checks kernelspec.language, falls back to language_info.name,
    defaults to "text" if neither is present.
    """
    try:
        metadata = nb.get("metadata", {})
        kernelspec = metadata.get("kernelspec", {})
        if "language" in kernelspec:
            return kernelspec["language"]

        language_info = metadata.get("language_info", {})
        if "name" in language_info:
            return language_info["name"]
    except (KeyError, TypeError):
        pass

    return "text"


def build_digest(nb: dict, source_name: str) -> str:
    """Build a digest from a notebook dict.

    Emits:
    - Header block with metadata
    - For each cell: type marker, content (code in fence, markdown verbatim)
    - Truncation marker for oversized code cells
    - Output count marker (outputs never included, only count)
    """
    cells = nb.get("cells", [])
    lang = notebook_language(nb)

    lines = []
    lines.append(f"# notebook digest: {source_name}")
    lines.append(f"# language: {lang}")
    lines.append(f"# cells: {len(cells)}")

    for idx, cell in enumerate(cells, start=1):
        cell_type = cell.get("cell_type", "raw")

        if cell_type == "markdown":
            lines.append(f"# [markdown cell {idx}]")
            lines.append(cell_source_text(cell))

        elif cell_type == "code":
            lines.append(f"# [code cell {idx}]")
            source = cell_source_text(cell)
            source_lines = source.splitlines(keepends=True)

            # Check if truncation is needed
            if len(source_lines) > MAX_CODE_CELL_LINES:
                # Keep head + tail, add truncation marker
                head = source_lines[:CODE_CELL_HEAD_LINES]
                tail = source_lines[-CODE_CELL_TAIL_LINES:]
                omitted = len(source_lines) - CODE_CELL_HEAD_LINES - CODE_CELL_TAIL_LINES

                lines.append(f"```{lang}")
                lines.extend("".join(head).rstrip('\n').split('\n'))
                lines.append(f"# [code cell truncated: {omitted} lines omitted]")
                lines.extend("".join(tail).rstrip('\n').split('\n'))
                lines.append("```")
            else:
                # Normal code cell, emit in full
                lines.append(f"```{lang}")
                lines.append(source.rstrip('\n'))
                lines.append("```")

            # Add output marker if outputs exist
            outputs = cell.get("outputs", [])
            if outputs:
                lines.append(f"# [{len(outputs)} output(s) omitted]")

        else:
            # raw or unknown cell type
            lines.append(f"# [raw cell {idx}]")
            lines.append(cell_source_text(cell))

    return "\n".join(lines)


def load_notebook(path) -> dict:
    """Load a notebook from a file.

    Raises ValueError if the file is not valid JSON or not a notebook dict.
    Raises json.JSONDecodeError if JSON is malformed.
    """
    try:
        text = pathlib.Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"Cannot read file: {e}")

    try:
        nb = json.loads(text)
    except json.JSONDecodeError:
        raise

    if not isinstance(nb, dict):
        raise ValueError("Not a JSON object")

    if "cells" not in nb or not isinstance(nb["cells"], list):
        raise ValueError("Not a notebook (missing or invalid 'cells')")

    return nb


def main(argv: list[str]) -> int:
    """CLI entry point.

    Returns 0 on success, 2 on error.
    """
    # Reconfigure stdout to handle non-ASCII gracefully on cp1252 console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(prog="nb_digest.py")
    parser.add_argument("path", help="Path to the .ipynb notebook")

    try:
        args = parser.parse_args(argv[1:])
    except SystemExit:
        return 2

    try:
        nb = load_notebook(args.path)
        source_name = pathlib.Path(args.path).name
        digest = build_digest(nb, source_name)
        print(digest)
        return 0
    except (ValueError, json.JSONDecodeError, OSError, KeyError) as e:
        print(f"nb_digest: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
