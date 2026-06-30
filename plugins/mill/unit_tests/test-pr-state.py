"""Unit tests for _pr_state.resolve_pr_state."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add the scripts directory to sys.path so _pr_state (and its dependency
# _subprocess_util) can be imported without a package install.
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import _pr_state  # noqa: E402


def _make_run_mock(returncode: int, stdout: str, stderr: str = "") -> MagicMock:
    """Return a MagicMock that looks like a CompletedProcess from _subprocess_util.run."""
    mock = MagicMock()
    mock.returncode = returncode
    mock.stdout = stdout
    mock.stderr = stderr
    return mock


def test_single_merged_pr() -> None:
    """A single MERGED PR object -> state='merged' with number, url, merge_commit populated."""
    payload = '[{"state":"MERGED","mergeCommit":{"oid":"abc123"},"number":42,"url":"https://example.com/1"}]'
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, payload)):
        result = _pr_state.resolve_pr_state("my-branch", cwd="/repo")

    assert result["state"] == "merged", f"expected 'merged', got {result['state']!r}"
    assert result["number"] == 42, f"expected 42, got {result['number']!r}"
    assert result["url"] == "https://example.com/1", f"expected url, got {result['url']!r}"
    assert result["merge_commit"] == {"oid": "abc123"}, f"expected merge_commit obj, got {result['merge_commit']!r}"
    print("PASS resolve_pr_state -- single MERGED -> merged with number/url/merge_commit")


def test_single_open_pr() -> None:
    """A single OPEN PR object -> state='open'."""
    payload = '[{"state":"OPEN","mergeCommit":null,"number":7,"url":"https://example.com/7"}]'
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, payload)):
        result = _pr_state.resolve_pr_state("open-branch", cwd="/repo")

    assert result["state"] == "open", f"expected 'open', got {result['state']!r}"
    assert result["number"] == 7
    print("PASS resolve_pr_state -- single OPEN -> open")


def test_single_closed_pr() -> None:
    """A single CLOSED PR object -> state='closed'."""
    payload = '[{"state":"CLOSED","mergeCommit":null,"number":3,"url":"https://example.com/3"}]'
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, payload)):
        result = _pr_state.resolve_pr_state("closed-branch", cwd="/repo")

    assert result["state"] == "closed", f"expected 'closed', got {result['state']!r}"
    assert result["number"] == 3
    print("PASS resolve_pr_state -- single CLOSED -> closed")


def test_empty_array() -> None:
    """An empty JSON array [] -> state='none'."""
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, "[]")):
        result = _pr_state.resolve_pr_state("no-pr-branch", cwd="/repo")

    assert result == {"state": "none", "number": None, "url": None, "merge_commit": None}, (
        f"expected none-dict, got {result!r}"
    )
    print("PASS resolve_pr_state -- empty array [] -> none")


def test_empty_stdout() -> None:
    """Empty stdout (gh returned nothing) -> state='none'."""
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, "")):
        result = _pr_state.resolve_pr_state("quiet-branch", cwd="/repo")

    assert result["state"] == "none"
    print("PASS resolve_pr_state -- empty stdout -> none")


def test_nonzero_returncode() -> None:
    """Non-zero exit code from gh -> state='none'."""
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(1, "", "gh error")):
        result = _pr_state.resolve_pr_state("error-branch", cwd="/repo")

    assert result["state"] == "none"
    print("PASS resolve_pr_state -- returncode != 0 -> none")


def test_gh_missing_no_exception_returns_none() -> None:
    """When _subprocess_util.run raises FileNotFoundError (gh absent) -> none, no exception."""
    with patch.object(_pr_state._subprocess_util, "run", side_effect=FileNotFoundError("gh not found")):
        # Must not propagate any exception.
        result = _pr_state.resolve_pr_state("any-branch", cwd="/repo")

    assert result["state"] == "none", f"expected 'none', got {result['state']!r}"
    print("PASS resolve_pr_state -- gh missing (FileNotFoundError) -> none, no exception propagated")


def test_multi_pr_closed_then_merged_returns_merged() -> None:
    """[CLOSED, MERGED] -> state='merged'; stale CLOSED must not mask MERGED."""
    payload = (
        '['
        '{"state":"CLOSED","mergeCommit":null,"number":1,"url":"https://example.com/1"},'
        '{"state":"MERGED","mergeCommit":{"oid":"def456"},"number":2,"url":"https://example.com/2"}'
        ']'
    )
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, payload)):
        result = _pr_state.resolve_pr_state("multi-branch", cwd="/repo")

    assert result["state"] == "merged", f"expected 'merged', got {result['state']!r}"
    # The winning object is the MERGED PR (number=2).
    assert result["number"] == 2, f"expected number 2 (MERGED PR), got {result['number']!r}"
    assert result["merge_commit"] == {"oid": "def456"}
    print("PASS resolve_pr_state -- [CLOSED, MERGED] -> merged (precedence MERGED > CLOSED)")


def test_multi_pr_closed_then_open_returns_open() -> None:
    """[CLOSED, OPEN] -> state='open'; superseded CLOSED must not mask OPEN."""
    payload = (
        '['
        '{"state":"CLOSED","mergeCommit":null,"number":10,"url":"https://example.com/10"},'
        '{"state":"OPEN","mergeCommit":null,"number":11,"url":"https://example.com/11"}'
        ']'
    )
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, payload)):
        result = _pr_state.resolve_pr_state("reopen-branch", cwd="/repo")

    assert result["state"] == "open", f"expected 'open', got {result['state']!r}"
    assert result["number"] == 11, f"expected number 11 (OPEN PR), got {result['number']!r}"
    print("PASS resolve_pr_state -- [CLOSED, OPEN] -> open (precedence OPEN > CLOSED)")


def test_malformed_json() -> None:
    """Malformed JSON stdout -> state='none', no exception."""
    with patch.object(_pr_state._subprocess_util, "run", return_value=_make_run_mock(0, "{not json")):
        result = _pr_state.resolve_pr_state("bad-json-branch", cwd="/repo")

    assert result["state"] == "none", f"expected 'none', got {result['state']!r}"
    print("PASS resolve_pr_state -- malformed JSON stdout -> none, no exception")


if __name__ == "__main__":
    test_single_merged_pr()
    test_single_open_pr()
    test_single_closed_pr()
    test_empty_array()
    test_empty_stdout()
    test_nonzero_returncode()
    test_gh_missing_no_exception_returns_none()
    test_multi_pr_closed_then_merged_returns_merged()
    test_multi_pr_closed_then_open_returns_open()
    test_malformed_json()
    print("All test-pr-state.py tests passed.")
