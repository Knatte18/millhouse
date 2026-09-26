"""Token-based detection of shell commands that touch the wiki junction.

Stdlib-only so the PreToolUse hook starts fast and never depends on the mill
package layout. The check parses the command instead of substring-matching, so
prose that merely mentions the junction name (a grep pattern, an echo argument,
a heredoc body) is not a false positive.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys

DENY_REASON = (
    "Mill wiki files are daemon-owned (CLAUDE.md: Mill wiki -- never touched directly). "
    "Use the wiki._client API instead of raw shell commands on the wiki junction."
)

_WIKI_COMPONENT = ".wiki"
_HEREDOC_START = re.compile(r"(?<!<)<<(?!<)(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2")
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WRAPPER_WORDS = {"sudo", "env", "command"}
_SHELL_WORDS = {"bash", "sh", "zsh"}
_TEXT_WORDS = {"echo", "printf"}
_GREP_WORDS = {"grep", "egrep", "fgrep", "rg", "ag", "awk"}
_PATTERN_FLAGS = {"-e", "--regexp", "-f", "--file"}
_SEPARATORS = {";", "&&", "||", "|", "&", ";;", "|&", "(", ")"}
_PUNCT = set("();<>|&")
_PLACEHOLDER = "SUBST"


def _strip_heredocs(text: str) -> str:
    """Drop heredoc bodies that have a matching terminator line; keep everything else."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        match = _HEREDOC_START.search(line)
        if match:
            dash, tag = match.group(1), match.group(3)
            for j in range(i + 1, len(lines)):
                candidate = lines[j].lstrip("\t") if dash else lines[j]
                if candidate == tag:
                    out.append(line[: match.start()] + line[match.end():])
                    i = j + 1
                    break
            else:
                out.append(line)
                i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)


def _extract_substitutions(text: str) -> tuple[str, list[str]]:
    """Replace ``$(...)`` and backtick spans with a placeholder; return the new text and inner strings."""
    out: list[str] = []
    inner: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("$(", i):
            depth = 1
            j = i + 2
            while j < n and depth:
                if text[j] == "(":
                    depth += 1
                elif text[j] == ")":
                    depth -= 1
                j += 1
            end = j - 1 if depth == 0 else j
            inner.append(text[i + 2 : end])
            out.append(_PLACEHOLDER)
            i = j
        elif text[i] == "`":
            j = text.find("`", i + 1)
            if j == -1:
                inner.append(text[i + 1 :])
                i = n
            else:
                inner.append(text[i + 1 : j])
                i = j + 1
            out.append(_PLACEHOLDER)
        else:
            out.append(text[i])
            i += 1
    return "".join(out), inner


def _is_wiki_path(token: str) -> bool:
    """Return True when a whitespace-free token has a path component exactly equal to the junction name."""
    if any(ch.isspace() for ch in token):
        return False
    candidates = [token]
    if "=" in token:
        candidates.append(token.split("=", 1)[1])
    return any(_WIKI_COMPONENT in re.split(r"[/\\]", c) for c in candidates)


def _is_punct_token(token: str) -> bool:
    return bool(token) and all(ch in _PUNCT for ch in token)


def _split_commands(tokens: list[str]) -> list[list[str]]:
    commands: list[list[str]] = [[]]
    for token in tokens:
        if token in _SEPARATORS:
            commands.append([])
        else:
            commands[-1].append(token)
    return [c for c in commands if c]


def _split_redirects(words: list[str]) -> tuple[list[str], list[str]]:
    """Separate redirect-target tokens from plain words; drop the operators themselves."""
    plain: list[str] = []
    targets: list[str] = []
    after_redirect = False
    for word in words:
        if _is_punct_token(word) and ("<" in word or ">" in word):
            after_redirect = True
            continue
        if after_redirect:
            targets.append(word)
            after_redirect = False
        else:
            plain.append(word)
    return plain, targets


def _command_word_index(words: list[str]) -> int:
    for idx, word in enumerate(words):
        if _ASSIGNMENT.match(word) or word in _WRAPPER_WORDS:
            continue
        return idx
    return len(words)


def _grep_tested_args(args: list[str]) -> list[str]:
    """Return every argument except the single pattern/program argument."""
    tested: list[str] = []
    pattern_seen = False
    flags_done = False
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if not flags_done and arg == "--":
            flags_done = True
            continue
        if not flags_done and arg.startswith("-") and arg != "-":
            if arg in _PATTERN_FLAGS:
                pattern_seen = True
                skip_next = True
                continue
            if arg.startswith(("--regexp=", "--file=")):
                pattern_seen = True
                continue
            tested.append(arg)
            continue
        if not pattern_seen:
            pattern_seen = True
            continue
        tested.append(arg)
    return tested


def _simple_command_touches_wiki(words: list[str]) -> bool:
    plain, targets = _split_redirects(words)
    if any(_is_wiki_path(t) for t in targets):
        return True
    start = _command_word_index(plain)
    for word in plain[:start]:
        if _is_wiki_path(word):
            return True
    if start >= len(plain):
        return False
    command_token = plain[start]
    args = plain[start + 1 :]
    name = os.path.basename(command_token)
    if _is_wiki_path(command_token):
        return True
    if name in _SHELL_WORDS:
        if "-c" in args:
            idx = args.index("-c")
            if idx + 1 < len(args) and command_touches_wiki(args[idx + 1]):
                return True
    elif name == "eval":
        if args and command_touches_wiki(" ".join(args)):
            return True
    elif name in _TEXT_WORDS:
        return False
    elif name in _GREP_WORDS:
        return any(_is_wiki_path(a) for a in _grep_tested_args(args))
    return any(_is_wiki_path(a) for a in args)


def command_touches_wiki(command: str) -> bool:
    """Return True when the shell command references the wiki junction as a path."""
    text = _strip_heredocs(command)
    text, inner = _extract_substitutions(text)
    if any(command_touches_wiki(sub) for sub in inner):
        return True
    try:
        lex = shlex.shlex(text.replace("\n", " ; "), posix=True, punctuation_chars=True)
        lex.whitespace_split = True
        tokens = list(lex)
    except ValueError:
        return re.search(r"\.wiki\b", command) is not None
    return any(_simple_command_touches_wiki(c) for c in _split_commands(tokens))


def deny_json(command: str) -> str:
    """Return the PreToolUse deny payload, or an empty string when the command is allowed."""
    if not command_touches_wiki(command):
        return ""
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": DENY_REASON,
            }
        }
    )


def hook_main(stdin_text: str) -> str:
    """Parse hook stdin JSON and return the deny payload; empty string on any error or allow."""
    try:
        command = json.loads(stdin_text)["tool_input"]["command"]
    except (ValueError, KeyError, TypeError):
        return ""
    if not isinstance(command, str):
        return ""
    try:
        return deny_json(command)
    except Exception:  # noqa: BLE001 -- a guard bug must never block a tool call
        print("wiki-guard: internal error", file=sys.stderr)
        return ""
