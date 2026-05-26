#!/usr/bin/env python3
"""Force a wiki re-render: re-emit Home.md, _Sidebar.md, and proposal-*.md from tasks.json.

Commits and pushes only if the rendered output differs from on-disk content.
Useful after redeploying changes to wiki/_render.py without modifying any task state.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import _paths
from wiki import _client


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    t = time.perf_counter()
    _client.rerender(wiki_path)
    elapsed_ms = (time.perf_counter() - t) * 1000
    print(f"rerender ok ({elapsed_ms:.0f} ms)")


if __name__ == "__main__":
    main()
