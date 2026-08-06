#!/usr/bin/env python3
"""
Mechanical verifier for pydocreflow.py's output on a pair of (old, new) source files.
Checks:

1. `new` still parses as valid Python (ast.parse doesn't raise).
2. The concatenated text of every docstring plus every standalone comment, with all whitespace collapsed to single spaces, is identical between `old` and `new` -- proving the reflow only moved words onto different lines, never added, dropped, or changed one.

Usage:
    python verify.py <old_file> <new_file>
"""

import ast
import io
import re
import sys
import tokenize


def _docstring_texts(src):
    tree = ast.parse(src)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body:
                continue
            first = node.body[0]
            if (isinstance(first, ast.Expr)
                    and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                out.append(first.value.value)
    return out


def _comment_texts(src):
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                out.append(tok.string.lstrip("#"))
    except tokenize.TokenizeError:
        pass
    return out


def _collapsed(parts):
    return re.sub(r"\s+", " ", " ".join(parts)).strip()


def verify_pair(old_src, new_src):
    ast.parse(new_src)  # raises on syntax error
    old_text = _collapsed(_docstring_texts(old_src) + _comment_texts(old_src))
    new_text = _collapsed(_docstring_texts(new_src) + _comment_texts(new_src))
    return old_text == new_text, old_text, new_text


def main(argv):
    if len(argv) != 2:
        print("usage: verify.py <old_file> <new_file>", file=sys.stderr)
        return 2
    old_src = open(argv[0], encoding="utf-8").read()
    new_src = open(argv[1], encoding="utf-8").read()
    ok, old_text, new_text = verify_pair(old_src, new_src)
    if ok:
        print("OK")
        return 0
    print("MISMATCH", file=sys.stderr)
    for i in range(min(len(old_text), len(new_text))):
        if old_text[i] != new_text[i]:
            print("first diff at", i, file=sys.stderr)
            print("old:", repr(old_text[max(0, i - 40):i + 40]), file=sys.stderr)
            print("new:", repr(new_text[max(0, i - 40):i + 40]), file=sys.stderr)
            break
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
