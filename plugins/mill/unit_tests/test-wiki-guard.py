"""Unit tests for the token-based wiki-guard module and its PreToolUse hook CLI."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _wiki_guard

J = "." + "wiki"
HOME = J + "/Home.md"


def _yes(command: str) -> None:
    assert _wiki_guard.command_touches_wiki(command), command


def _no(command: str) -> None:
    assert not _wiki_guard.command_touches_wiki(command), command


def test_true_grep_file() -> None:
    _yes("grep foo " + HOME)


def test_true_grep_recursive_dir() -> None:
    _yes("grep -r foo " + J)


def test_true_cat() -> None:
    _yes("cat " + HOME)


def test_true_git_dash_c() -> None:
    _yes("git -C " + J + " status")


def test_true_cd_and_ls() -> None:
    _yes("cd " + J + " && ls")


def test_true_ls_parent_relative() -> None:
    _yes("ls ../" + J + "/x")


def test_true_bash_c() -> None:
    _yes('bash -c "cat ' + HOME + '"')


def test_true_echo_substitution() -> None:
    _yes("echo $(cat " + HOME + ")")


def test_true_unbalanced_quote_fail_closed() -> None:
    _yes('echo "unterminated ' + J + "/x")


def test_false_grep_bare_pattern() -> None:
    _no("grep -rn " + J + " plugins")


def test_false_grep_quoted_pattern() -> None:
    _no('grep -rn "' + J + '" plugins')


def test_false_grep_escaped_pattern() -> None:
    _no("grep -rn \\" + J + " plugins")


def test_false_grep_dash_e() -> None:
    _no("grep -e " + J + " plugins")


def test_false_echo_bare() -> None:
    _no("echo " + J)


def test_false_echo_hub_suffix() -> None:
    _no('echo "path/hub' + J + '"')


def test_false_gh_body_suffix() -> None:
    _no('gh issue create --body "error at /x/hub' + J + '"')


def test_false_gh_body_prose_with_spaces() -> None:
    _no('gh issue create --body "the path ' + HOME + ' is daemon-owned"')


def test_false_heredoc_body() -> None:
    _no("cat > .scratch/x.md <<'EOF'\nsee " + HOME + "\nEOF\n")


def test_false_plain_grep() -> None:
    _no("grep foo file.txt")


def test_true_echo_redirect_write() -> None:
    _yes("echo x > " + HOME)


def test_true_echo_redirect_append() -> None:
    _yes("echo x >> " + HOME)


def test_true_here_string_word() -> None:
    _yes("cat <<< " + HOME)


def test_true_unterminated_heredoc() -> None:
    _yes("cat <<EOF\ncat " + HOME + "\n")


def test_true_quoted_whitespace_free_path() -> None:
    _yes('cp x "' + HOME + '"')


def test_true_single_quoted_substitution() -> None:
    _yes("cat '$(cat " + HOME + ")'")


def test_hook_main_deny() -> None:
    out = _wiki_guard.hook_main(json.dumps({"tool_input": {"command": "cat " + HOME}}))
    payload = json.loads(out)["hookSpecificOutput"]
    assert payload["permissionDecision"] == "deny"
    assert payload["permissionDecisionReason"] == _wiki_guard.DENY_REASON


def test_hook_main_benign() -> None:
    assert _wiki_guard.hook_main(json.dumps({"tool_input": {"command": "ls"}})) == ""


def test_hook_main_bad_input() -> None:
    assert _wiki_guard.hook_main("not json") == ""
    assert _wiki_guard.hook_main(json.dumps({"other": 1})) == ""
    assert _wiki_guard.hook_main(json.dumps({"tool_input": {"command": 5}})) == ""


def test_cli_subprocess() -> None:
    script = str(SCRIPTS / "millpy-wiki-guard.py")
    deny = json.dumps({"tool_input": {"command": "cat " + HOME}})
    ok = json.dumps({"tool_input": {"command": "ls"}})
    proc = subprocess.run([sys.executable, script], input=deny, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert proc.stdout.strip() == _wiki_guard.hook_main(deny)
    assert json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"
    proc = subprocess.run([sys.executable, script], input=ok, capture_output=True, text=True, check=False)
    assert proc.returncode == 0
    assert proc.stdout == ""


def main() -> int:
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
            except AssertionError as exc:
                failures += 1
                print(f"FAIL {name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
