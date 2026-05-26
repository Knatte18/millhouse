#!/usr/bin/env python3
"""Cleanly shut down the wiki daemon. The next wiki request will respawn it with the latest code.

Useful after redeploying wiki module code (no protocol-version bump) so the running daemon
picks up the new behavior.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import _paths
from wiki import _client


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()

    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)

    if _client.shutdown(wiki_path):
        print("daemon shutdown requested")
    else:
        print("no daemon running")


if __name__ == "__main__":
    main()
