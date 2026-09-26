"""
Global Claude Code settings.json permission-allowlist merge helper.

Background `mill-implementer`/`mill-reviewer` subagents run with a fixed `tools:` frontmatter (see
`plugins/mill/agents/mill-implementer.md` and `plugins/mill/agents/mill-reviewer.md`).
When the operator's global `~/.claude/settings.json` does not already allow those bare tool names, a
background agent-mode dispatch can block on an interactive tool-permission prompt with no way to
answer it -- from `TaskOutput` alone that stall looks identical to a genuinely running subagent
(#631).

`mill-setup` Phase 4.8 closes that gap by merging the mill subagent tool surface into the operator's
`permissions.allow` list at bootstrap time, the same phase that already writes `MILL_PYTHON` to that
file.

Public API:
    merge_permission_allowlist(settings_path, tool_names)
    Read settings_path (or start from {} if absent), add any of
    tool_names not already present to permissions.allow (preserving
    existing order and entries), write back only if the list
    actually changed, and return the resulting dict.

    reconcile_destructive_denylist(settings_path)
    Read settings_path (or start from {} if absent), retire any target-blind
    rm -rf deny rules (RETIRED_DENY) from permissions.deny, add any missing
    catastrophic-target rules (DESTRUCTIVE_DENY), write back only if the
    list actually changed, and return the resulting dict.

    build_wiki_guard_command(plugin_root)
    Return the PreToolUse hook command line that runs the wiki-guard script
    from plugin_root.

    reconcile_wiki_guard_hook(settings_path, hook_command)
    Read settings_path (or start from {} if absent), install hook_command as the
    single wiki-guard PreToolUse hook under the "Bash" matcher, replacing any
    older installed path or the legacy inline grep hook in place, write back
    only if something changed, and return the resulting dict.

Module-level constants:
    MILL_SUBAGENT_TOOLS The union of mill-implementer.md's and mill-reviewer.md's `tools:`
    frontmatter -- the single source of truth Phase 4.8 passes as tool_names, so the allowlist and
    the two agent definitions cannot silently drift apart.

    WIKI_GUARD_SCRIPT_NAME File name of the wiki-guard hook script, used both to build the hook
    command and to recognise a previously installed hook.
"""
from __future__ import annotations

import json
from pathlib import Path

# Union of mill-implementer.md's tools: (Read, Edit, Write, Bash, Grep, Glob, Skill) and mill-reviewer.md's tools: (Read, Grep, Glob, Write).
MILL_SUBAGENT_TOOLS = ["Bash", "Read", "Edit", "Write", "Grep", "Glob", "Skill"]

# Target-blind rm -rf deny rules being retired -- they block rm -rf against any target, including a
# throwaway scratch dir, exactly as hard as they block rm -rf against ~ (#1127).
RETIRED_DENY = ["Bash(rm -rf:*)", "Bash(rm -rf *)"]

# Scoped catastrophic-target rules replacing RETIRED_DENY. User-root entries (/, ~, ~/, $HOME, /home,
# /Users, /root) are exact-match only, so anything below those roots stays deletable. System-tree
# entries (/etc, /usr, /var, /boot, /opt, /bin, /lib) are prefix-matched with :*, since nothing under
# those roots is ever legitimately deleted recursively.
DESTRUCTIVE_DENY = [
    "Bash(rm -rf /)", "Bash(rm -rf /*)",
    "Bash(rm -rf ~)", "Bash(rm -rf ~/)", "Bash(rm -rf $HOME)",
    "Bash(rm -rf /home)", "Bash(rm -rf /Users)", "Bash(rm -rf /root)",
    "Bash(rm -rf /etc:*)", "Bash(rm -rf /usr:*)", "Bash(rm -rf /var:*)",
    "Bash(rm -rf /boot:*)", "Bash(rm -rf /opt:*)", "Bash(rm -rf /bin:*)",
    "Bash(rm -rf /lib:*)",
]

WIKI_GUARD_SCRIPT_NAME = "millpy-wiki-guard.py"


def build_wiki_guard_command(plugin_root: Path) -> str:
    """
    Build the PreToolUse hook command that runs the wiki-guard script from plugin_root.

    The command embeds the versioned plugin cache path, so it goes stale (and the guard fails
    open) after a plugin cache refresh until mill-setup Phase 4.8 is re-run.

    Args:
        plugin_root: The plugin root directory containing scripts/.

    Returns:
        The shell command string, with PYTHONPATH pointing at the scripts directory.
    """
    scripts_dir = f"{plugin_root.as_posix()}/scripts"
    return f'PYTHONPATH="{scripts_dir}" "$MILL_PYTHON" "{scripts_dir}/{WIKI_GUARD_SCRIPT_NAME}"'


def _is_wiki_guard_hook(hook: dict) -> bool:
    """Return True for a current/older installed wiki-guard hook or the legacy inline grep hook."""
    command = hook.get("command", "")
    if WIKI_GUARD_SCRIPT_NAME in command:
        return True
    return "daemon-owned" in command and "\\.wiki\\b" in command


def reconcile_wiki_guard_hook(settings_path: Path, hook_command: str) -> dict:
    """
    Ensure settings_path's PreToolUse "Bash" matcher carries exactly one wiki-guard hook, hook_command.

    Loads the existing settings.json (or starts from an empty dict), then finds every hook object
    under Bash-matcher entries that is either an installed wiki-guard script command (any path) or
    the legacy inline grep hook.
    The first match is replaced in place with hook_command and any further matches are removed;
    unrelated hooks sharing an entry survive, and an entry is dropped only when its hooks list
    becomes empty.
    When no match exists a new Bash entry is appended.
    The file is only rewritten when something changed.

    Args:
        settings_path: Path to the global ~/.claude/settings.json file.
        hook_command: The command from build_wiki_guard_command.

    Returns:
        The resulting settings dict (same shape as the file's JSON).
    """
    data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    entries = data.setdefault("hooks", {}).setdefault("PreToolUse", [])
    new_hook = {"type": "command", "command": hook_command}

    matches = [
        (entry, hook)
        for entry in entries
        if entry.get("matcher") == "Bash"
        for hook in entry.get("hooks", [])
        if _is_wiki_guard_hook(hook)
    ]

    if len(matches) == 1 and matches[0][1].get("command") == hook_command:
        return data

    if not matches:
        entries.append({"matcher": "Bash", "hooks": [new_hook]})
    else:
        first_entry, first_hook = matches[0]
        first_entry["hooks"][first_entry["hooks"].index(first_hook)] = new_hook
        for entry, hook in matches[1:]:
            entry["hooks"] = [candidate for candidate in entry["hooks"] if candidate is not hook]
        data["hooks"]["PreToolUse"] = [
            entry for entry in entries if entry.get("hooks") != [] or "hooks" not in entry
        ]

    settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def reconcile_destructive_denylist(settings_path: Path) -> dict:
    """
    Reconcile settings_path's permissions.deny list against RETIRED_DENY and DESTRUCTIVE_DENY.

    Loads the existing settings.json (or starts from an empty dict if the file does not exist yet),
    removes any entry present in RETIRED_DENY (target-blind rm -rf rules), then appends any entry
    from DESTRUCTIVE_DENY not already present -- preserving the existing order and every other
    pre-existing deny entry, and never touching permissions.allow,
    permissions.additionalDirectories, or any other top-level key (env, model, hooks, etc.).
    The file is only rewritten when the deny list actually changed, matching
    merge_permission_allowlist's own idempotent no-op pattern.

    Args:
        settings_path: Path to the global ~/.claude/settings.json file.

    Returns:
        The resulting settings dict (same shape as the file's JSON), reflecting any reconciliation
        performed.
    """
    data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    permissions = data.setdefault("permissions", {})
    deny = permissions.setdefault("deny", [])

    changed = False

    # Retire target-blind rm -rf rules -- they block rm -rf against any target as hard as against ~.
    for entry in RETIRED_DENY:
        if entry in deny:
            deny.remove(entry)
            changed = True

    # Append only the scoped catastrophic-target rules not already present, preserving order and
    # avoiding duplicates -- existing entries (including any not in DESTRUCTIVE_DENY) are left untouched.
    for entry in DESTRUCTIVE_DENY:
        if entry not in deny:
            deny.append(entry)
            changed = True

    # Skip the write entirely when nothing changed, so a repeated mill-setup run does not touch the file's mtime or reformat unrelated content.
    if changed:
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return data


def merge_permission_allowlist(settings_path: Path, tool_names: list[str]) -> dict:
    """
    Merge tool_names into settings_path's permissions.allow list.

    Loads the existing settings.json (or starts from an empty dict if the file does not exist yet),
    then appends any name in tool_names that is not already present in permissions.allow --
    preserving the existing order and entries, and never touching permissions.deny,
    permissions.additionalDirectories, or any other top-level key (env, model, hooks, etc.).
    The file is only rewritten when the allow list actually changed, matching Phase 4.8's existing
    MILL_PYTHON idempotent no-op pattern.

    Args:
        settings_path: Path to the global ~/.claude/settings.json file.
        tool_names: Bare tool names to ensure are present in permissions.allow, e.g.
            MILL_SUBAGENT_TOOLS.

    Returns:
        The resulting settings dict (same shape as the file's JSON), reflecting any merge performed.
    """
    data = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.exists() else {}
    permissions = data.setdefault("permissions", {})
    allow = permissions.setdefault("allow", [])

    # Append only the tool names not already present, preserving order and avoiding duplicates -- existing entries (including any not in tool_names) are left untouched.
    changed = False
    for name in tool_names:
        if name not in allow:
            allow.append(name)
            changed = True

    # Skip the write entirely when nothing changed, so a repeated mill-setup run does not touch the file's mtime or reformat unrelated content.
    if changed:
        settings_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    return data
