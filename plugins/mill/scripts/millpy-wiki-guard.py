"""Claude Code PreToolUse hook: deny Bash commands that touch the wiki junction.

Reads the hook JSON from stdin; prints a deny payload only when the command is blocked.
"""
from __future__ import annotations

import sys

import _wiki_guard


# Installed as a PreToolUse hook by mill-setup; not a user-invocable skill.
def main() -> int:
    result = _wiki_guard.hook_main(sys.stdin.read())
    if result:
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
