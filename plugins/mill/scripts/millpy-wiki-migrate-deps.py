#!/usr/bin/env python3
"""Runner to migrate old 'group' field to new 'depends_on/isolated/deferred' fields."""
from __future__ import annotations

import sys
from pathlib import Path

import _paths
from wiki import _client as wiki


def main() -> int:
    """Migrate wiki task store from group-based schema to depends_on/isolated/deferred.

    Resolves git_root and wiki_path automatically; calls wiki.migrate_deps to
    perform the migration. The migration is idempotent — running twice is safe.

    Returns:
        0 on success.

    Raises:
        SystemExit: On git discovery or migration errors.
    """
    git_root = _paths.resolve_git_root()
    wiki_path = _paths.resolve_wiki_path(git_root)
    wiki.migrate_deps(wiki_path)
    print("Migration complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
