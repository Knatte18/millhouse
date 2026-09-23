"""
Unit test for `plugins/mill/scripts/_verify_baseline.py`.

Case 1 regresses the no-checkout design (`_mill/discussion.md`'s `remove-all-three-checkouts` /
`algorithm-simplification` Decisions): a table-driven exercise of `compute_baseline`'s 2-run
flakiness-guard algorithm against its `tuple[str, list[str]]` return, using a call-counting fake for
`_run_verify_in`.
Asserts the run count explicitly (not just the returned verdict) -- deleting the third control run
is a behavioral change a bare outcome assertion would not catch.
Also asserts the signature half: the returned list equals the deduplicated, order-preserving union of
`_extract_failure_signatures(output)` across every run actually performed in each case.

Case 2 is the regression guard against the checkout mechanism creeping back in: `compute_baseline`
performs no git operation of any kind.
`_verify_baseline._subprocess_util.run` is patched with a fake that raises `AssertionError` if called
with any argv containing "git";
`compute_baseline` is called with a fake `cwd` and a benign command and must still return
successfully, with `_subprocess_util.run` never invoked at all.

Follows the monkeypatch/in-memory fixture style of `test-worktree.py`: no real git is invoked.

Cases (b)/(c) cover `compute_batch_baselines`'s basic multi-command computation directly against a
mocked `cwd`: (b) confirms two distinct commands each get their own, independent (non-aliased)
signature list keyed by name;
(c) confirms a command with zero recognized FAIL-marker lines on both runs maps to `[]` (present,
not an absent dict key).

Case (d) covers `compute_batch_baselines`'s union-of-two-runs corroboration: a signature that only
reproduces on one of the two runs still ends up in the union (neither run's set silently overwrites
the other's).

Cases (f)-(i) regress #1098, where `compute_batch_baselines` ran every verify command twice
unconditionally and keyed its loop on the batch name, so a plan whose last batch verifies the union
of the earlier batches executed each suite four times instead of once: (f) two names sharing one
`(command, effective_cwd)` pair evaluate it once and each still get a non-aliased list;
(g) a command exiting 0 with zero signatures runs once, not twice;
(h) the skip is gated on the zero exit code, so a non-zero exit with no recognized signatures is
still re-run;
(i) dedup is keyed on the pair, so one command string at two distinct cwds stays two units of work.

Cases (j)-(m) regress #1101, where that dedup could never fire in production because the only caller
drives one batch per call (to keep its per-batch try/except isolation), re-creating the call-local
cache empty every time, and where no verify run had any timeout at all: (j) a caller-owned
`pair_cache` makes the dedup span calls while still handing back independent list objects;
(k) omitting it keeps the old call-local behaviour, so the shared cache is opt-in;
(l) `timeout_seconds` reaches `subprocess.run` and a `TimeoutExpired` propagates to the caller's
"leave the baseline unset" fail-safe instead of being swallowed into a bogus baseline;
(m) omitting it imposes no ceiling.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _implementer_common import _extract_failure_signatures
from _verify_baseline import compute_baseline, compute_batch_baselines


def _run_one_compute_baseline_case(
    label: str, exit_codes: tuple[int, ...]
) -> tuple[str, list[str], list[str], list[str]]:
    """
    Run `compute_baseline` against a call-counting fake for `_run_verify_in` that returns
    `exit_codes[i]` on its i-th invocation, and a matching output line per non-zero exit.

    Returns `(verdict, signatures, run_calls, outputs)`.
    """
    outputs = [
        f"--- FAIL: Test{label}{i} (0.01s)\n" if rc != 0 else "ok\n"
        for i, rc in enumerate(exit_codes)
    ]
    run_calls: list[str] = []

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del command, run_cwd, timeout_seconds
        index = len(run_calls)
        run_calls.append(label)
        return exit_codes[index], outputs[index]

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        verdict, signatures = compute_baseline(Path("/fake/cwd"), "echo ok")

    return verdict, signatures, run_calls, outputs


def _case_1_two_run_algorithm_against_return_tuple() -> None:
    """
    Case 1: `compute_baseline`'s new 2-run algorithm, table-driven against its
    `tuple[str, list[str]]` return, using a call-counting fake for `_run_verify_in`.
    """
    cases = [
        ("all-pass", (0,), "clean", 1),
        ("fail-then-pass", (1, 0), "clean", 2),
        ("both-fail", (1, 1), "pre-existing-failures", 2),
    ]

    for label, exit_codes, expected_verdict, expected_run_count in cases:
        verdict, signatures, run_calls, outputs = _run_one_compute_baseline_case(label, exit_codes)

        assert verdict == expected_verdict, (
            f"case {label}: expected verdict {expected_verdict!r}, got {verdict!r}"
        )
        assert len(run_calls) == expected_run_count, (
            f"case {label}: expected {expected_run_count} run(s), got {len(run_calls)}"
        )

        expected_signatures: list[str] = []
        seen: set[str] = set()
        for output in outputs:
            for line in _extract_failure_signatures(output):
                if line not in seen:
                    seen.add(line)
                    expected_signatures.append(line)
        assert signatures == expected_signatures, (
            f"case {label}: expected signatures {expected_signatures!r}, got {signatures!r}"
        )

    print(
        "PASS: compute_baseline's 2-run algorithm returns the correct verdict, "
        "run count, and signature union for all-pass/fail-then-pass/both-fail"
    )


def _case_2_no_git_subprocess_call() -> None:
    """
    Case 2: regression guard against the checkout mechanism creeping back in -- `compute_baseline`
    performs no git operation of any kind.
    """

    def _fail_on_git(argv: list[str], **kwargs) -> None:
        if any("git" in str(token) for token in argv):
            raise AssertionError(f"unexpected git invocation: {argv!r}")
        raise AssertionError(f"unexpected _subprocess_util.run call: {argv!r}")

    with (
        patch("_verify_baseline._subprocess_util.run", side_effect=_fail_on_git) as fake_run,
        patch("_verify_baseline._run_verify_in", return_value=(0, "ok\n")),
    ):
        verdict, signatures = compute_baseline(Path("/fake/cwd"), "echo ok")

    assert verdict == "clean", f"expected 'clean', got {verdict!r}"
    assert signatures == [], f"expected no signatures, got {signatures!r}"
    fake_run.assert_not_called()

    print(
        "PASS: compute_baseline performs no git subprocess call of any kind"
    )


def _case_b_independent_signature_lists() -> None:
    """
    Case (b): two distinct commands each get their own, independent (non-aliased) signature list
    keyed by name.
    """
    cwd = Path("/fake/cwd")

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del run_cwd, timeout_seconds
        if command == "cmd-a":
            return 1, "--- FAIL: TestA (0.01s)\n"
        if command == "cmd-b":
            return 1, "--- FAIL: TestB (0.02s)\n"
        raise AssertionError(f"unexpected command: {command!r}")

    commands = [("batchA", "cmd-a", None), ("batchB", "cmd-b", None)]
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(commands, cwd)

    assert len(result) == 2, f"expected 2 entries, got {len(result)}: {result!r}"
    assert result["batchA"] == ["--- FAIL: TestA (0.01s)"], result["batchA"]
    assert result["batchB"] == ["--- FAIL: TestB (0.02s)"], result["batchB"]
    assert result["batchA"] is not result["batchB"], (
        "expected independent (non-aliased) list objects per command"
    )

    print(
        "PASS: compute_batch_baselines returns independent signature lists "
        "keyed by name for distinct commands"
    )


def _case_c_zero_failures_returns_empty_list() -> None:
    """
    Case (c): a command with zero recognized FAIL-marker lines on both runs maps to [] (present, not
    an absent dict key).
    """
    cwd = Path("/fake/cwd")

    with patch("_verify_baseline._run_verify_in", return_value=(0, "ok, nothing failed\n")):
        result = compute_batch_baselines([("clean-batch", "cmd-clean", None)], cwd)

    assert "clean-batch" in result, f"expected 'clean-batch' key present, got {result!r}"
    assert result["clean-batch"] == [], (
        f"expected empty list for zero-failure command, got {result['clean-batch']!r}"
    )

    print(
        "PASS: compute_batch_baselines maps a zero-failure command to a "
        "present-but-empty signature list"
    )


def _case_d_union_of_two_runs() -> None:
    """
    Case (d): a signature that only reproduces on one of the two runs still ends up in the union --
    neither run's set silently overwrites the other's.
    """
    cwd = Path("/fake/cwd")
    call_count = {"n": 0}

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del run_cwd, timeout_seconds
        assert command == "cmd-flaky"
        call_count["n"] += 1
        if call_count["n"] == 1:
            return 1, "--- FAIL: TestFlakyA (0.01s)\n"
        return 1, "--- FAIL: TestFlakyB (0.02s)\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines([("flaky-batch", "cmd-flaky", None)], cwd)

    assert result["flaky-batch"] == [
        "--- FAIL: TestFlakyA (0.01s)",
        "--- FAIL: TestFlakyB (0.02s)",
    ], f"expected union of both runs' signatures, got {result['flaky-batch']!r}"

    print(
        "PASS: compute_batch_baselines unions signatures from both runs "
        "instead of one run's set overwriting the other"
    )


def _case_e_mixed_cwd_dedup() -> None:
    """
    Case (e): `compute_batch_baselines` with commands resolving to two distinct `cwd_override`
    paths against one shared `cwd` -- confirming each command runs at its own cwd and dedup stays
    per-cwd.
    """
    with tempfile.TemporaryDirectory() as tmp:
        cwd = Path(tmp) / "checkout"
        cwd.mkdir()
        target_git_root = cwd
        target_hub = cwd / "hub"
        target_hub.mkdir()

        seen_cwds: list[tuple[str, Path]] = []

        def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
            del timeout_seconds
            seen_cwds.append((command, run_cwd))
            return 0, "ok\n"

        commands = [
            ("root-batch", "cmd-root", target_git_root),
            ("hub-batch", "cmd-hub", target_hub),
        ]
        with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
            result = compute_batch_baselines(commands, cwd)

        assert result == {"root-batch": [], "hub-batch": []}, result

        # One run each, not two: both commands exit 0 with no signatures, so the corroboration
        # re-run is skipped (#1098).
        root_cwds = [c for command, c in seen_cwds if command == "cmd-root"]
        hub_cwds = [c for command, c in seen_cwds if command == "cmd-hub"]
        assert root_cwds == [target_git_root], root_cwds
        assert hub_cwds == [target_hub], hub_cwds

        print(
            "PASS: compute_batch_baselines runs each command at its own "
            "resolved cwd_override, deduping per (command, cwd) pair"
        )


def _case_f_identical_command_and_cwd_runs_once() -> None:
    """
    Case (f) regresses #1098: two batch names sharing one `(command, effective_cwd)` pair run the
    command once, not once per name -- and each still gets its own, non-aliased list object.

    Uses a failing command so the corroboration re-run is not itself skipped;
    the assertion is about the pair being evaluated once (2 runs total), not four times.
    """
    cwd = Path("/fake/cwd")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del run_cwd, timeout_seconds
        runs.append(command)
        return 1, "--- FAIL: TestShared (0.01s)\n"

    commands = [
        ("batch1", "dotnet test Suite", None),
        ("batch3", "dotnet test Suite", None),
    ]
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(commands, cwd)

    assert runs == ["dotnet test Suite", "dotnet test Suite"], (
        f"expected the shared command evaluated once (2 runs), got {len(runs)} runs: {runs!r}"
    )
    assert result["batch1"] == ["--- FAIL: TestShared (0.01s)"], result["batch1"]
    assert result["batch3"] == result["batch1"], result["batch3"]
    assert result["batch1"] is not result["batch3"], (
        "expected independent (non-aliased) list objects even for a shared command"
    )

    print(
        "PASS: compute_batch_baselines evaluates an identical (command, cwd) pair "
        "once and fans independent copies out to every batch name"
    )


def _case_g_green_run_skips_corroboration_rerun() -> None:
    """
    Case (g) regresses #1098: a command that exits 0 with zero extracted signatures is run once, not
    twice -- there is nothing for the second run to corroborate.
    """
    cwd = Path("/fake/cwd")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del run_cwd, timeout_seconds
        runs.append(command)
        return 0, "Passed!  - Failed: 0, Passed: 412\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines([("green-batch", "cmd-green", None)], cwd)

    assert len(runs) == 1, f"expected a single run for a green command, got {runs!r}"
    assert result == {"green-batch": []}, result

    print(
        "PASS: compute_batch_baselines skips the corroboration re-run when "
        "run 1 exits 0 with zero failure signatures"
    )


def _case_h_nonzero_exit_without_signatures_still_reruns() -> None:
    """
    Case (h): the run-2 skip is gated on a ZERO exit code, not on the signature list alone.

    A command that fails without emitting any line `_extract_failure_signatures` recognizes (a build
    break, a crashed runner) is still re-run, so a signature that only surfaces on the second
    attempt reaches the baseline.
    """
    cwd = Path("/fake/cwd")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del run_cwd, timeout_seconds
        runs.append(command)
        if len(runs) == 1:
            return 1, "error CS0246: the type or namespace could not be found\n"
        return 1, "--- FAIL: TestLate (0.03s)\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines([("broken-batch", "cmd-broken", None)], cwd)

    assert len(runs) == 2, (
        f"expected a re-run after a non-zero exit with no signatures, got {runs!r}"
    )
    assert result["broken-batch"] == ["--- FAIL: TestLate (0.03s)"], result["broken-batch"]

    print(
        "PASS: compute_batch_baselines still re-runs a non-zero-exit command "
        "that emitted no recognized failure signatures"
    )


def _case_i_same_command_distinct_cwds_not_deduped() -> None:
    """
    Case (i): dedup is keyed on the `(command, effective_cwd)` pair -- one command string run at two
    distinct cwds is two distinct units of work, not one.
    """
    cwd = Path("/fake/cwd")
    seen_cwds: list[Path] = []

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del command, timeout_seconds
        seen_cwds.append(run_cwd)
        return 1, f"--- FAIL: Test{run_cwd.name} (0.01s)\n"

    commands = [
        ("root-batch", "make test", Path("/fake/cwd")),
        ("sub-batch", "make test", Path("/fake/cwd/sub")),
    ]
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        result = compute_batch_baselines(commands, cwd)

    assert seen_cwds == [
        Path("/fake/cwd"),
        Path("/fake/cwd"),
        Path("/fake/cwd/sub"),
        Path("/fake/cwd/sub"),
    ], seen_cwds
    assert result["root-batch"] == ["--- FAIL: Testcwd (0.01s)"], result["root-batch"]
    assert result["sub-batch"] == ["--- FAIL: Testsub (0.01s)"], result["sub-batch"]

    print(
        "PASS: compute_batch_baselines keys dedup on (command, cwd), so one "
        "command string at two distinct cwds stays two units of work"
    )


def _case_j_caller_owned_pair_cache_spans_calls() -> None:
    """
    Case (j) regresses #1101: a caller-owned `pair_cache` makes the dedup span calls.

    The production call site drives one batch per call (single-element list) to keep its per-batch
    try/except isolation, so a call-local cache is re-created empty every time and can never fire.
    With a shared `pair_cache`, the second call's identical pair is served from the cache instead of
    re-running the command -- and still hands back an independent list object.
    """
    cwd = Path("/fake/cwd")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del run_cwd, timeout_seconds
        runs.append(command)
        return 1, "--- FAIL: TestShared (0.01s)\n"

    pair_cache: dict = {}
    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        first = compute_batch_baselines(
            [("batch1", "dotnet test Suite", None)],
            cwd,
            pair_cache=pair_cache,
        )
        second = compute_batch_baselines(
            [("batch3", "dotnet test Suite", None)],
            cwd,
            pair_cache=pair_cache,
        )

    assert len(runs) == 2, (
        f"expected the shared pair evaluated once across both calls (2 runs), got {runs!r}"
    )
    assert second["batch3"] == ["--- FAIL: TestShared (0.01s)"], second["batch3"]
    assert second["batch3"] is not first["batch1"], (
        "expected an independent list object per name, not the cached list itself"
    )
    assert second["batch3"] is not pair_cache[("dotnet test Suite", cwd)], (
        "expected a copy, not the cache's own list object"
    )

    print(
        "PASS: compute_batch_baselines dedups across calls when the caller "
        "owns and threads a pair_cache"
    )


def _case_k_omitted_pair_cache_stays_call_local() -> None:
    """
    Case (k): omitting `pair_cache` keeps the old call-local behaviour -- two separate calls with
    the same pair each evaluate it, so the shared cache is genuinely opt-in.
    """
    cwd = Path("/fake/cwd")
    runs: list[str] = []

    def _fake_run_verify_in(command: str, run_cwd: Path, timeout_seconds=None) -> tuple[int, str]:
        del run_cwd, timeout_seconds
        runs.append(command)
        return 1, "--- FAIL: TestShared (0.01s)\n"

    with patch("_verify_baseline._run_verify_in", side_effect=_fake_run_verify_in):
        compute_batch_baselines([("batch1", "cmd", None)], cwd)
        compute_batch_baselines([("batch3", "cmd", None)], cwd)

    assert len(runs) == 4, f"expected 2 runs per independent call (4 total), got {runs!r}"

    print(
        "PASS: compute_batch_baselines without a pair_cache stays call-local, "
        "so the shared cache is opt-in"
    )


def _case_l_timeout_propagates() -> None:
    """
    Case (l) regresses #1101: `timeout_seconds` reaches `subprocess.run`, and a `TimeoutExpired`
    propagates to the caller rather than being swallowed into a fabricated non-zero exit.

    A swallowed timeout would feed truncated output into the signature extractor and cache a bogus
    baseline;
    propagating lets the caller apply its existing "leave the baseline unset" fail-safe.
    Also asserts nothing is written to `pair_cache` for the pair that raised, so a later call can
    retry it.
    """
    cwd = Path("/fake/cwd")
    seen_timeouts: list[float | None] = []

    def _fake_subprocess_run(*args, **kwargs):
        seen_timeouts.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(cmd="cmd-hang", timeout=kwargs.get("timeout"))

    pair_cache: dict = {}
    with patch("_verify_baseline.subprocess.run", side_effect=_fake_subprocess_run):
        try:
            compute_batch_baselines(
                [("hung-batch", "cmd-hang", None)],
                cwd,
                pair_cache=pair_cache,
                timeout_seconds=90.0,
            )
        except subprocess.TimeoutExpired:
            pass
        else:
            raise AssertionError("expected TimeoutExpired to propagate to the caller")

    assert seen_timeouts == [90.0], (
        f"expected timeout_seconds forwarded to subprocess.run, got {seen_timeouts!r}"
    )
    assert pair_cache == {}, (
        f"expected nothing cached for a pair whose evaluation raised, got {pair_cache!r}"
    )

    print(
        "PASS: compute_batch_baselines forwards timeout_seconds to subprocess.run "
        "and lets TimeoutExpired propagate without caching the failed pair"
    )


def _case_m_no_timeout_by_default() -> None:
    """
    Case (m): omitting `timeout_seconds` passes `timeout=None` to `subprocess.run` -- no ceiling is
    imposed on repos that have not configured one.
    """
    cwd = Path("/fake/cwd")
    seen_timeouts: list[float | None] = []

    def _fake_subprocess_run(*args, **kwargs):
        seen_timeouts.append(kwargs.get("timeout"))
        return MagicMock(returncode=0, stdout="ok\n", stderr="")

    with patch("_verify_baseline.subprocess.run", side_effect=_fake_subprocess_run):
        result = compute_batch_baselines([("plain-batch", "cmd-plain", None)], cwd)

    assert result == {"plain-batch": []}, result
    assert seen_timeouts == [None], (
        f"expected timeout=None when no ceiling is configured, got {seen_timeouts!r}"
    )

    print("PASS: compute_batch_baselines imposes no subprocess timeout by default")


def main() -> int:
    try:
        _case_1_two_run_algorithm_against_return_tuple()
        _case_2_no_git_subprocess_call()
        _case_b_independent_signature_lists()
        _case_c_zero_failures_returns_empty_list()
        _case_d_union_of_two_runs()
        _case_e_mixed_cwd_dedup()
        _case_f_identical_command_and_cwd_runs_once()
        _case_g_green_run_skips_corroboration_rerun()
        _case_h_nonzero_exit_without_signatures_still_reruns()
        _case_i_same_command_distinct_cwds_not_deduped()
        _case_j_caller_owned_pair_cache_spans_calls()
        _case_k_omitted_pair_cache_stays_call_local()
        _case_l_timeout_propagates()
        _case_m_no_timeout_by_default()

        print("All _verify_baseline unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
