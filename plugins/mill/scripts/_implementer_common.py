"""Shared helpers for millpy-implement.py and millpy-fix.py."""

import html
import json
import os
import re
import shutil
import subprocess
import sys
import _agent_dispatch
import _cleanliness
import _status
import _subprocess_util
import _timestamp
from pathlib import Path


def _is_only_start_batch_commit(project_root: Path, start_sha: str) -> bool:
    """Return True when the only commit since start_sha is the batch-start housekeeping commit.

    Detects Bug #557: prepare makes a "mill-go: start batch" commit, so HEAD != start_sha even when
    the implementer wrote zero code commits.
    A single-card retry has start_sha == the start-batch commit, so its real code commit message
    will NOT start with the prefix.
    Returns False on any subprocess failure so the guard is always safe to skip on error.
    """
    result = _subprocess_util.run(
        ["git", "log", "--pretty=%s", f"{start_sha}..HEAD"],
        cwd=project_root,
    )
    if result.returncode != 0:
        return False
    # Collect non-empty commit subject lines since start_sha.
    msgs = [m.strip() for m in result.stdout.strip().splitlines() if m.strip()]
    return len(msgs) == 1 and msgs[0].startswith("mill-go: start batch")


def _content_commit_count(project_root: Path, start_sha: str | None) -> int | None:
    """
    Count content commits since start_sha, excluding the batch-start housekeeping commit.

    The prepare stage always makes a "mill-go: start batch <name>" commit before the implementer
    runs.
    Because start_sha is captured BEFORE that commit, a raw `git rev-list --count start_sha..HEAD`
    over-counts by one whenever the housekeeping commit is present.
    This helper subtracts it so that callers see the true number of content commits the implementer
    made.

    Algorithm:
      1. Return None when start_sha is None (gate disabled).
      2. Run `git rev-list --count start_sha..HEAD` to get the raw range count.
          Return None on non-zero exit or non-numeric output.
      3. Run `git log --pretty=%s start_sha..HEAD` to get per-commit subjects.
          Git log returns newest-first, so the last non-empty subject is the oldest commit.
      4. Subtract the count of all in-range commit subjects that start with "mill-go: start batch"
          from the raw count (floored at 0).
          A resumed batch may contain more than one such housekeeping commit;
          all are excluded.
      5. Return the adjusted count.

    Returns None on any subprocess failure so callers can treat it as a gate no-op.

    Args:
        project_root: Path to the worktree root used as cwd for git subprocesses.
        start_sha: The SHA recorded at batch start.
        None disables the count (returns None).

    Returns:
        Content commit count (int >= 0),
        or None when inputs are absent or git fails.
    """
    if start_sha is None:
        return None

    # Get the raw commit count since start_sha.
    result = _subprocess_util.run(
        ["git", "rev-list", "--count", f"{start_sha}..HEAD"],
        cwd=project_root,
    )
    if result.returncode != 0:
        return None

    # Guard the parse: non-numeric stdout must not raise (e.g. mocked sha strings in tests).
    try:
        count = int(result.stdout.strip())
    except ValueError:
        return None

    # Inspect the oldest commit subject to detect the housekeeping commit.
    # git log returns newest-first;
    # the last non-empty line is the oldest commit.
    log_result = _subprocess_util.run(
        ["git", "log", "--pretty=%s", f"{start_sha}..HEAD"],
        cwd=project_root,
    )
    if log_result.returncode == 0:
        subjects = [s.strip() for s in log_result.stdout.strip().splitlines() if s.strip()]
        if subjects:
            # Subtract ALL housekeeping commits from the count.
            # A resumed batch may have more than one "mill-go: start batch" commit in range (e.g.
            # the original prepare commit plus a retry prepare commit).
            # Subtract all of them so that only implementer-authored content commits remain.
            count = max(0, count - sum(1 for s in subjects if s.startswith("mill-go: start batch")))

    return count


def _cards_done_all_commit_none(cards_done, commit_none_card_ids: set[int] | None) -> bool:
    """
    Return True when every self-reported done card is a ``Commit: none`` card.

    This is the code-derived no-content-commit-gate carve-out check (issue #664): a batch whose
    reported cards_done are all verification-only ``Commit: none`` cards is expected to make zero
    content commits, so the zero-commit gates must not demote it to stuck/logic.
    commit_none_card_ids itself is always computed by the caller from the batch plan file on disk,
    never trusted from the implementer's own self-report (see the plan's "code-derived, never
    self-reported" Shared Decision).

    Args:
        cards_done: The implementer's self-reported cards_done value straight
        from parsed JSON -- may be None, a list of ints, a list of numeric
        strings, or malformed; coerced the same way _cards_incomplete_reason
        coerces it.
        commit_none_card_ids: The set of card numbers whose Commit: field is the literal none,
            computed from the batch file on disk.
            None or empty means no carve-out applies.

    Returns:
        True only when cards_done is present, coercible, non-empty, and every coerced card number is
        a member of commit_none_card_ids.
    """
    if not commit_none_card_ids:
        return False
    if cards_done is None:
        return False
    try:
        coerced = {int(x) for x in cards_done}
    except (ValueError, TypeError):
        return False
    if not coerced:
        return False
    return coerced.issubset(commit_none_card_ids)


def _reclassify_verify_failure(
    verify_stuck: dict,
    project_root: Path,
    start_sha: str | None,
    card_ids: set[int] | None,
    session_id: str | None,
    *,
    cards_done=None,
    commit_none_card_ids: set[int] | None = None,
) -> dict:
    """
    Reclassify a verify-failure stuck dict based on how many content commits exist.

    Called only when the verify gate already fired (verify_stuck is non-None).
    A verify failure that happens mid-batch -- before the implementer finished all cards -- should
    be classified as incomplete (resume required) not verify (needs a fix).
    A failure with zero content commits likely means the agent stopped before producing any work and
    should be classified as logic (not retryable without human intervention).

    Classification rules (applied in order):
      - content is None OR card_ids is None OR card_ids is empty: return verify_stuck unchanged.
      - content == 0 and cards_done is not entirely covered by commit_none_card_ids: reclassify as
          stuck_type=logic "no content commit" (orthogonal to cards_done otherwise -- zero commits
          means zero work regardless of any self-report, unless every reported card is a
          verification-only Commit: none card).
      - Otherwise, delegate to _cards_incomplete_reason (the same helper _batch_completeness_stuck
          uses): a non-None reason reclassifies as stuck_type=incomplete with commits_made=content;
          None means the batch is complete (either content >= len(card_ids), or cards_done confirms
              every declared card is done) and verify_stuck is returned unchanged.

    Args:
        verify_stuck: The stuck dict produced by _run_verify_gates (stuck_type="verify").
        project_root: Path to the worktree root for _content_commit_count.
        start_sha: SHA recorded at batch start;
            None disables reclassification.
        card_ids: The set of Card numbers declared in the batch file;
            None or empty disables reclassification.
        session_id: Session identifier included in reclassified dicts.
        cards_done: The implementer's self-reported list of card numbers this commit set addresses;
            forwarded to _cards_incomplete_reason.
            None (the default) uses the absent-field fallback (raw commit-count check).
        commit_none_card_ids: card numbers whose Commit: field is the literal none, computed by the
            caller from the batch plan file (never self-reported);
            when the coerced cards_done is a non-empty subset of this set, the content==0
                reclassification below is skipped.

    Returns:
        Either verify_stuck unchanged,
        or a new dict with a different stuck_type.
    """
    content = _content_commit_count(project_root, start_sha)

    # Inputs absent or gate disabled -- preserve original verify classification.
    if content is None or card_ids is None or len(card_ids) <= 0:
        return verify_stuck

    if content == 0 and not _cards_done_all_commit_none(cards_done, commit_none_card_ids):
        # No content commits at all -- agent likely aborted before touching any files.
        # Unaffected by cards_done: zero commits is zero work regardless of self-report, unless every reported card is a verification-only Commit: none card.
        return {
            "status": "stuck",
            "stuck_type": "logic",
            "reason": (
                "success reported but no content commit"
                " (only batch-start commit since start_sha)"
            ),
            "session_id": session_id or "unknown",
        }

    reason = _cards_incomplete_reason(card_ids, cards_done, content)
    if reason is not None:
        # Partial batch -- implementer stopped after some cards (or self-reported fewer cards done than declared).
        # Reclassify as incomplete (not transient) so the orchestrator knows to resume rather than retry fresh.
        return {
            "status": "stuck",
            "stuck_type": "incomplete",
            "reason": reason,
            "session_id": session_id or "unknown",
            "commits_made": content,
        }

    # Batch is complete (raw count >= card count, or cards_done confirms every declared card is done): verify failure is a genuine test failure that needs to be fixed -- preserve the original classification.
    return verify_stuck


def _cards_incomplete_reason(
    card_ids: set[int],
    cards_done,
    content: int,
) -> str | None:
    """
    Decide whether a batch is incomplete, sharing the identical rule between
    _batch_completeness_stuck and _reclassify_verify_failure.

    Two independent bases of evidence are considered, in order:
      1. Absent or malformed cards_done: fall back to the pre-#660 heuristic -- compare the raw
          content-commit count against len(card_ids).
          This is the fail-open path for implementer sessions that never populate cards_done (old
              sessions, non-compliant models) -- behaves identically to the count-only gate this
              function replaces.
      2. Present and validly coercible cards_done: compare the declared card_ids against the
          implementer's self-reported set via set difference.
          This is what lets a batch that legitimately combined multiple cards into one commit (fewer
              commits than cards, per the brief's "one combined commit" allowance) still be
              recognized as complete -- the raw count check alone cannot distinguish that from a
              genuinely stopped-early batch.

    Args:
        card_ids: The set of Card numbers declared in the batch file (read verbatim from "### Card
        N:" headings, not assumed contiguous).
        cards_done: The implementer's self-reported cards_done value straight from parsed JSON --
        may be None, a list of ints, a list of numeric strings, or malformed (any type at all);
        this function is responsible for validating and coercing it.
        content: The content-commit count since start_sha (excluding the batch-start housekeeping
        commit).

    Returns:
        The "batch incomplete: ..."
        reason string when incomplete,
        or None when the batch is judged complete.
    """

    def _count_only_reason() -> str | None:
        # Raw commit-count heuristic: cannot see which specific cards were combined, so it only knows "fewer commits than declared cards".
        if content < len(card_ids):
            return (
                f"batch incomplete: {content} content commit(s) since start but"
                f" {len(card_ids)} card(s) in batch -- implementer stopped before finishing all cards"
            )
        return None

    if cards_done is None:
        return _count_only_reason()

    # Implementers may legitimately emit JSON string card numbers (e.g. ["7", "8"]) rather than integers;
    # coerce before comparing.
    # A malformed entry means the self-report is untrusted, not partially trusted -- fall back exactly as if cards_done had been absent.
    try:
        coerced = {int(x) for x in cards_done}
    except (ValueError, TypeError):
        return _count_only_reason()

    missing = card_ids - coerced
    if missing:
        return (
            f"batch incomplete: cards {sorted(missing)} not reported done"
            f" (cards_done={sorted(coerced)}, declared={sorted(card_ids)})"
        )
    return None


def _batch_completeness_stuck(
    project_root: Path,
    start_sha: str | None,
    card_ids: set[int] | None,
    session_id: str | None,
    *,
    verify_cmd: str | None = None,
    ignore_verify: bool = False,
    cards_done=None,
    already_complete: bool = False,
) -> dict | None:
    """
    Check whether the implementer's commits/self-report satisfy the declared card_ids.

    Returns None (gate disabled/satisfied) in any of these cases, checked in order:
      1. already_complete is True: the resume-idempotent-confirmation backstop -- an implementer
          re-dispatched via --resume-incomplete that independently re-verifies every card is already
          satisfied (and makes no new commit) reports this explicitly, bypassing every check below.
      2. verify_cmd is not None and ignore_verify is False: a passing verify command is conclusive
          evidence of batch completeness on the explicit-success path, so the heuristic checks below
          are unnecessary.
          Pass ignore_verify=True on the no-JSON inference paths to force the completeness check
              even when a verify command is present (the implementer never reported success, so a
              passing verify command does not make the batch complete).
      3. start_sha is None, card_ids is None, or card_ids is empty: the gate has nothing to check
          against (e.g.
          a docs-only batch with zero cards).

    Otherwise counts content commits via _content_commit_count and delegates the incomplete-or-not
    decision to _cards_incomplete_reason (shared with _reclassify_verify_failure): an absent or
    malformed cards_done falls back to comparing the raw commit count against len(card_ids);
    a present, validly coercible cards_done instead compares card_ids against the self-reported set.

    Args:
        project_root: Path to the worktree root.
        start_sha: The SHA recorded at batch start;
            None disables the gate.
        card_ids: The set of Card numbers declared in the batch file;
            None or empty disables the gate.
        session_id: Session identifier included in the returned dict when non-None.
        verify_cmd: When not None and ignore_verify is False, the gate is disabled (verify is
            conclusive on the explicit-success path).
        ignore_verify: When True, run the check even when verify_cmd is not None.
            Used on the no-JSON inference paths where a partial batch is not made complete just
                because verify passes.
            Default False.
        cards_done: The implementer's self-reported list of card numbers this commit set addresses.
            None (the default) uses the absent-field fallback so old/non-compliant implementer
                sessions never regress.
        already_complete: When True, short-circuits the gate to "complete" regardless of every other
            argument -- the resume backstop.

    Returns:
        A stuck dict with stuck_type="incomplete" and commits_made when incomplete,
        or None otherwise.
    """
    # already_complete short-circuits every other check -- see docstring point 1.
    if already_complete is True:
        return None

    # When a verify command is present and we are NOT forcing the check, a passing verify is conclusive on the explicit-success path;
    # skip the heuristic gate.
    if verify_cmd is not None and not ignore_verify:
        return None

    # Gate is a no-op when any required input is absent or card_ids is empty.
    if start_sha is None or card_ids is None or len(card_ids) <= 0:
        return None

    # Count content commits (excluding the start-batch housekeeping commit) since start_sha.
    # The housekeeping commit is always present when prepare ran, so raw rev-list over-counts by one;
    # _content_commit_count subtracts it.
    # Returns None on any git failure, which is treated as a gate no-op to avoid crashing finalize.
    content = _content_commit_count(project_root, start_sha)
    if content is None:
        return None

    reason = _cards_incomplete_reason(card_ids, cards_done, content)
    if reason is None:
        return None

    return {
        "status": "stuck",
        "stuck_type": "incomplete",
        "reason": reason,
        "session_id": session_id or "unknown",
        "commits_made": content,
    }


_COMMIT_SHA_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")


def _is_valid_commit_sha(value: str) -> bool:
    """Return True when value is a well-formed full-length git commit SHA (40 or 64 lowercase hex characters)."""
    return bool(_COMMIT_SHA_RE.match(value))


def _attach_commit_sha(stuck_dict: dict, project_root: Path) -> dict:
    """
    Attach the current HEAD SHA to stuck_dict as 'commit_sha' on success.

    Runs git rev-parse HEAD with cwd=project_root.
    On success, sets stuck_dict["commit_sha"] to the trimmed SHA.
    On subprocess failure, the dict is returned unchanged (no commit_sha key added).
    Returns the same dict so callers can chain the call inline.

    Args:
        stuck_dict: The stuck envelope dict to augment in place.
        project_root: Path to the worktree root used as cwd for the git subprocess.

    Returns:
        The same stuck_dict, potentially with "commit_sha" added.
    """
    rev = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
    if rev.returncode == 0:
        stuck_dict["commit_sha"] = rev.stdout.strip()
    return stuck_dict


def _in_scope_dirty_stuck(
    project_root: Path,
    task_dir: Path | None,
    parent_branch: str | None,
    session_id: str | None,
) -> dict | None:
    """
    Check whether any in-scope files are dirty at finalize time.

    Returns None when task_dir or parent_branch is None (gate disabled).
    Otherwise calls _cleanliness.compute_terminal_dirt;
    if the returned list is non-empty, returns a stuck dict.
    Any exception from compute_terminal_dirt (including GitOpsError when project_root is not a real
    git repo) is caught and treated as a no-op -- the authoritative mill-go 2b cleanliness gate
    still runs afterward.

    Args:
        project_root: Path to the worktree root.
        task_dir: Worktree-relative path to the task directory (_mill/);
        None disables the gate.
        parent_branch: Name of the parent branch (e.g. "main");
        None disables the gate.
        session_id: Session identifier included in the returned dict when non-None.

    Returns:
        A stuck dict with stuck_type="logic" when dirty,
        or None otherwise.
    """
    # Gate is a no-op when required inputs are absent.
    if task_dir is None or parent_branch is None:
        return None

    try:
        dirt = _cleanliness.compute_terminal_dirt(project_root, task_dir, parent_branch)
    except Exception:
        # compute_terminal_dirt raises GitOpsError on non-git paths (e.g.
        # test fixtures).
        # Treat any failure as a safe no-op;
        # the mill-go gate is authoritative.
        return None

    if dirt:
        return {
            "status": "stuck",
            "stuck_type": "logic",
            "reason": f"success reported but in-scope working tree dirty: {dirt}",
            "session_id": session_id or "unknown",
        }
    return None


def _has_windows_lock_error_signature(text: str) -> bool:
    """
    Check if text contains a Windows file-locking error signature (case-insensitive).

    Detects file-locking error patterns: winerror 32, process cannot access, being used by another
    process.

    Args:
        text: A string to check (e.g., exception message).

    Returns:
        True if any lock-error signature is present;
        False otherwise.
    """
    text_lower = text.lower()
    lock_error_patterns = [
        "winerror 32",
        "process cannot access",
        "being used by another process",
    ]
    return any(pattern in text_lower for pattern in lock_error_patterns)


def _has_windows_cleanup_race_signature(text: str) -> bool:
    """
    Check if text contains a Windows cleanup-race signature (case-insensitive).

    Detects cleanup-race patterns from tempdir cleanup: unlinkat, access is denied, winerror 5,
    winerror 32.

    Args:
        text: A string to check (e.g., exception message or command output).

    Returns:
        True if any cleanup-race signature is present;
        False otherwise.
    """
    text_lower = text.lower()
    cleanup_signatures = [
        "unlinkat",
        "access is denied",
        "winerror 5",
        "winerror 32",
    ]
    return any(sig in text_lower for sig in cleanup_signatures)


def _has_dotnet_lock_race_signature(text: str) -> bool:
    """
    Check if text contains a dotnet build-server file-lock race signature (case-insensitive).

    Detects the MSB3021/MSB3027 testhost/MSBuild lock signature ("msb3021", "msb3027",
    "is locked by:") distinct from _has_windows_cleanup_race_signature's benign-cleanup
    signatures -- this signature triggers a retry-and-judge response, never a benign pass.

    Args:
        text: A string to check (e.g., a verify command's combined stdout+stderr).

    Returns:
        True if any dotnet-lock-race signature is present;
        False otherwise.
    """
    text_lower = text.lower()
    dotnet_lock_patterns = [
        "msb3021",
        "msb3027",
        "is locked by:",
    ]
    return any(pattern in text_lower for pattern in dotnet_lock_patterns)


def _is_benign_windows_cleanup(output: str) -> bool:
    """
    Check if the combined output contains only a Windows cleanup-race signature with no test
    failures.

    Returns True only when both conditions hold:
    1. The output contains a Windows cleanup-race signature (case-insensitive any of: unlinkat,
        access is denied, winerror 5, winerror 32)
    2. The output contains NO test-failure markers.
        Markers are matched case-insensitively against the lowercased output using line-anchored
            patterns to avoid false positives on benign package paths containing "fail" as a
            substring (e.g. "ok \\tpkg/failover\\t0.1s"): - "--- fail" (Go per-test failure prefix;
            safe as a substring because the leading "--- " makes it unambiguous) - re pattern
            (?m)^fail[\\t ] (Go package-summary line "FAIL\\tpkg" or "FAIL " at the start of a line
            -- a real TAB or space after fail) - "panic:" (Go runtime panic) - "build failed"
            (compiler/linker failure)

    This is used to distinguish benign file-cleanup races from real test failures on Windows.

    Args:
        output: Combined stdout and stderr from a verify command.

    Returns:
        True if output contains cleanup signature with no failure markers;
        False otherwise.
    """
    output_lower = output.lower()

    # Check for cleanup-race signatures.
    has_cleanup_signature = _has_windows_cleanup_race_signature(output)

    # Check for test-failure markers using line-anchored patterns.
    # The bare substring "fail" is intentionally NOT used here because Go test output includes lines like "ok \tpkg/failover\t0.1s" whose path contains "fail" as a substring but represents a passing package.
    has_failure_marker = (
        # Go per-test failure line (e.g. "--- FAIL: TestFoo (0.00s)")
        "--- fail" in output_lower
        # Go package-summary failure line (e.g. "FAIL\tgithub.com/pkg" or "FAIL pkg") anchored to line-start so a path like "pkg/failover" does not match.
        or bool(re.search(r"(?m)^fail[\t ]", output_lower))
        # Go runtime panic
        or "panic:" in output_lower
        # Compiler / linker failure
        or "build failed" in output_lower
    )

    return has_cleanup_signature and not has_failure_marker


def _posix_shell_run_args(cmd: str) -> tuple:
    """
    Build subprocess.run args to route POSIX shell commands through bash on Windows.

    On Windows (os.name == "nt"), when bash is available, returns args to invoke bash -c explicitly.
    On other platforms or when bash is unavailable, returns the command string with shell=True so
    the native shell processes it.

    POSIX verify commands often start with "PYTHONPATH= " (env-prefix syntax) that cmd.exe cannot
    parse.
    Running through bash honours this syntax cross-platform.

    Args:
        cmd: The command string (e.g., "PYTHONPATH= pytest tests/ -q").

    Returns:
        A tuple (run_args, run_kwargs) where run_args is either a list ([bash, "-c", cmd]) or a
        string (cmd), and run_kwargs is either {} or {"shell": True} to be unpacked into
        subprocess.run.
    """
    bash = shutil.which("bash") if os.name == "nt" else None
    if bash:
        return [bash, "-c", cmd], {}
    return cmd, {"shell": True}


def _is_formatter_drift_only(project_root: Path) -> bool:
    """Check if the only remaining dirt is whitespace-only formatter drift.

    Heuristic (deterministic): residual dirt is formatter drift ONLY when:
      - git diff (tracked files) is non-empty
      - git diff -w (ignore-all-space) is empty
      - no untracked files exist

    If either git diff subprocess returns non-zero or raises, treat as "not formatter drift" (skip
    auto-commit, proceed normally).

    Args:
        project_root: Path to the worktree root.

    Returns:
        True if all remaining changes are pure whitespace;
        False otherwise.
    """
    try:
        # Check if there are any untracked files
        result_untracked = _subprocess_util.run(
            [
                "git",
                "-C",
                str(project_root),
                "status",
                "--porcelain",
                "--untracked-files=all",
            ],
            check=False,
        )
        if result_untracked.returncode != 0:
            return False
        # Any line starting with ?? means untracked files exist
        for line in result_untracked.stdout.strip().split("\n"):
            if line.startswith("??"):
                return False

        # Check if tracked files have changes. --ignore-cr-at-eol ensures that a pure CRLF-vs-LF delta (e.g.
        # from text-mode CRLF translation on Windows) is treated the same as whitespace and does not prevent drift detection.
        result_diff = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff", "--ignore-cr-at-eol"],
            check=False,
        )
        if result_diff.returncode != 0:
            return False
        if not result_diff.stdout.strip():
            # No tracked-file changes at all
            return False

        # Check if those changes are purely whitespace. --ignore-cr-at-eol is added here too because git diff -w does not suppress CR-at-EOL diffs on its own;
        # a CRLF-only delta would still appear as content under -w without this flag, causing a false "not formatter drift" result.
        result_diff_w = _subprocess_util.run(
            ["git", "-C", str(project_root), "diff", "-w", "--ignore-cr-at-eol"],
            check=False,
        )
        if result_diff_w.returncode != 0:
            return False
        if result_diff_w.stdout.strip():
            # -w still shows changes, so there's non-whitespace content
            return False

        # All conditions met: it's formatter drift
        return True
    except Exception:
        # On any error, treat as "not formatter drift"
        return False


def _commit_formatter_drift(project_root: Path) -> bool:
    """Auto-commit formatter drift changes.

    Stages all changes and commits with message "chore(format): commit formatter drift".
    Returns True if commit succeeded;
    False on any error.

    Args:
        project_root: Path to the worktree root.

    Returns:
        True if the commit succeeded;
        False otherwise.
    """
    try:
        # Stage all changes
        result_add = _subprocess_util.run(
            ["git", "-C", str(project_root), "add", "-A"],
            check=False,
        )
        if result_add.returncode != 0:
            return False

        # Commit with ASCII-only message
        result_commit = _subprocess_util.run(
            [
                "git",
                "-C",
                str(project_root),
                "commit",
                "-m",
                "chore(format): commit formatter drift",
            ],
            check=False,
        )
        return result_commit.returncode == 0
    except Exception:
        return False


# Fixed prefix tuple recognizing failure-marker lines across the ecosystems this codebase's verify commands actually produce: Go's per-test (`--- FAIL:`) and package-summary (`FAIL\t`) forms, pytest's (`FAILED `) form, and mill's own run-all.py per-test (`--- FAIL `) and summary (`FAIL -- `) forms.
_FAILURE_MARKER_PREFIXES = (
    "--- FAIL:", "FAIL\t", "FAILED ", "--- FAIL ", "FAIL -- ",
)


def _extract_failure_signatures(output: str) -> list[str]:
    """
    Scan every line of a verify command's combined stdout+stderr for known failure-marker prefixes
    and return all matching lines, in order.

    These raw (unnormalized) lines are the failure signature set used both for the human-facing
    truncation excerpt (capped to the caller's own [:20] slice) and, once passed through
    _normalize_failure_signature, for baseline/finalize signature-set comparison.
    This helper itself is deliberately uncapped -- a failure past the 20th matching line must still
    be detectable as a signature.

    Returns:
        A list of every line in output that starts with one of the fixed failure-marker prefixes, in
        the order they appear.
        Empty when output has no recognized failure lines (never raises).
    """
    return [
        line for line in output.splitlines()
        if line.startswith(_FAILURE_MARKER_PREFIXES)
    ]


def _normalize_failure_signature(line: str) -> str:
    """
    Strip volatile per-run duration substrings from a failure-marker line so a genuinely
    pre-existing failure string-matches across separate verify runs.

    Applies three regex substitutions in sequence, each matching anywhere in
    the line (not anchored to line-end), covering every duration shape this
    codebase's verify commands are known to produce: 1. A parenthetical duration
        `(<digits>[.<digits>]s)` or `(...ms)` -- covers Go's `--- FAIL: TestFoo (0.00s)` and mill's
        own run-all.py per-test shape `--- FAIL some_test (1.2s) ---` (identical parenthetical
        shape, position-independent).
        2. A trailing tab-separated duration field `\\t<digits>[.<digits>]s` -- covers Go's
            package-summary shape `FAIL\\tgithub.com/pkg\\t0.123s`.
        3. An ` in <digits>[.<digits>]s` token -- covers mill's own run-all.py summary shape `FAIL
            -- 3 of 10 in 45.6s: [...]`.

    A line with no embedded duration (e.g.
    pytest's `FAILED tests/test_x.py::test_y`) passes through unchanged, since none of the three
    patterns match it.

    Returns:
        The line with all matching duration substrings removed.
    """
    result = re.sub(r"\(\d+(\.\d+)?m?s\)", "", line)
    result = re.sub(r"\t\d+(\.\d+)?s\b", "", result)
    result = re.sub(r"\s+in\s+\d+(\.\d+)?s", "", result)
    return result


def _run_verify_gate(
    project_root: Path,
    verify_cmd: str | None,
    *,
    git_root: Path | None = None,
    cwd_override: Path | None = None,
) -> dict | None:
    """
    Run a verify command and return a stuck dict on failure, None on success or when verify_cmd is
    None.

    When verify_cmd is not None, runs the command via bash on Windows (so the POSIX env-prefix
    syntax is honoured) and via subprocess.run with shell=True elsewhere, capturing output as text.
    On non-zero return code, returns a stuck dict with stuck_type="verify".
    When the combined stdout+stderr is over 2000 characters, reason is an omitted-content marker
    (byte count of the omitted prefix, plus up to 20 extracted earlier-failure summary lines when
    any are found) followed by the last 2000 characters;
    under 2000 characters, reason is the stripped output unchanged.
    The non-zero-exit stuck dict also carries a "signatures" field: every raw (unnormalized)
    failure-marker line extracted from the FULL, untruncated output via _extract_failure_signatures,
    uncapped -- this is the set _run_verify_gates uses for baseline/finalize subset-diff comparison.
    The separate exception-path stuck dict below never gains this field, since it has no subprocess
    output to extract from.
    On success (rc 0) or when verify_cmd is None, returns None.

    On Windows (sys.platform == "win32"), applies an additional gate: if the output contains a
    benign cleanup-race signature and no test failures (per _is_benign_windows_cleanup), treats the
    non-zero exit as success and returns None.

    On Windows, when the command contains "dotnet" and the failure output matches a dotnet
    build-server file-lock signature (per _has_dotnet_lock_race_signature: MSB3021, MSB3027, or
    "is locked by:"), retries the same command once -- after the unconditional post-run shutdown
    below has already run. A passing retry returns None exactly like any other pass. A
    still-failing retry returns a stuck dict built from the retry's own output, with reason
    prefixed by "[retried once after dotnet build-server shutdown; still failing] ".

    After the verify subprocess completes (regardless of exit code), if the platform is win32 and
    the command contains "dotnet", runs `dotnet build-server shutdown` to release
    VBCSCompiler/MSBuild locks that prevent re-runs.
    This call is wrapped in try/except so a TimeoutExpired or FileNotFoundError here never poisons
    the verify verdict -- it is best-effort, non-fatal cleanup.

    Args:
        project_root: Path to the worktree root.
        verify_cmd: Verify command to run (e.g., "pytest tests/ -q"), or None.
        git_root: Optional git root directory used as cwd for the verify subprocess.
            When None, falls back to project_root.
        cwd_override: Explicit verify cwd resolved by parse_verify_field from a `{cwd: hub|git_root,
            command: ...}` mapping.
            When set, it always wins over both git_root and project_root -- it reflects an author's
                explicit choice, whereas git_root/project_root are positional fallbacks for the
                plain-string verify format.

    Returns:
        A stuck dict {"status": "stuck", "stuck_type": "verify", "reason": <tail>, "signatures":
        <raw failure lines>} on non-zero return (unless win32 benign cleanup), or None on success or
        when verify_cmd is None.
        The separate exception-path stuck dict (missing binary, etc.) has no "signatures" key.
    """
    if verify_cmd is None:
        return None

    # cwd_override (an explicit verify: {cwd: ...} resolution) always wins.
    # Absent that, fall back to git_root, and absent that, to project_root -- the original flat-layout behavior where the two paths are identical.
    effective_cwd = (
        cwd_override
        if cwd_override is not None
        else (git_root if git_root is not None else project_root)
    )

    try:
        # Plan verify commands use POSIX syntax (e.g.
        # the mandated "PYTHONPATH= " env-prefix).
        # subprocess shell=True routes through cmd.exe on Windows, which cannot parse a leading VAR= env-prefix and fails with "'PYTHONPATH' is not recognized".
        # Run through bash when available so the POSIX verify command is honoured cross-platform;
        # fall back to shell=True only when bash is absent.
        run_args, run_kwargs = _posix_shell_run_args(verify_cmd)
        result = subprocess.run(
            run_args,
            capture_output=True,
            text=True,
            cwd=effective_cwd,
            **run_kwargs,
        )
        # dotnet cleanup: release testhost/MSBuild locks before caller retries.
        # Wrapped in try/except so a TimeoutExpired or FileNotFoundError here never poisons the verify verdict (best-effort, non-fatal).
        if (
            sys.platform == "win32"
            and verify_cmd is not None
            and "dotnet" in verify_cmd.lower()
        ):
            try:
                subprocess.run(
                    ["dotnet", "build-server", "shutdown"],
                    capture_output=True,
                    timeout=30,
                )
            except Exception:
                pass
        if result.returncode != 0:
            output = result.stdout + result.stderr
            # On Windows, check if this is a benign cleanup-race with no test failure
            if sys.platform == "win32" and _is_benign_windows_cleanup(output):
                return None
            retry_marker = ""
            if (
                sys.platform == "win32"
                and verify_cmd is not None
                and "dotnet" in verify_cmd.lower()
                and _has_dotnet_lock_race_signature(output)
            ):
                # A stale build-server node from an earlier dotnet invocation in this
                # worktree can still hold file handles into bin/obj when this command
                # runs. The unconditional shutdown above already blocked until that
                # process exited, so a bare re-run of the same command usually clears
                # the race with no code changes (GitHub #848, #860).
                retry_result = subprocess.run(
                    run_args,
                    capture_output=True,
                    text=True,
                    cwd=effective_cwd,
                    **run_kwargs,
                )
                if retry_result.returncode == 0:
                    return None
                output = retry_result.stdout + retry_result.stderr
                if sys.platform == "win32" and _is_benign_windows_cleanup(output):
                    return None
                retry_marker = (
                    "[retried once after dotnet build-server shutdown; "
                    "still failing] "
                )
            # Extract every raw failure-marker line from the FULL, untruncated output -- this is the signature set _run_verify_gates uses (after normalization) for baseline/finalize subset-diff comparison, distinct from the capped excerpt used below for the human-facing reason.
            signatures = _extract_failure_signatures(output)
            # Truncation enriches the reason with an omitted-content marker plus up to 20 extracted earlier-failure summary lines recovered from the omitted portion (#731) -- without this, an earlier failing package/test's identity can be silently dropped when a later, less- informative failure lands in the kept tail.
            output_stripped = output.strip()
            if len(output_stripped) > 2000:
                tail = output_stripped[-2000:]
                omitted = output_stripped[:-2000]
                fail_lines = _extract_failure_signatures(omitted)[:20]
                marker = f"[... {len(omitted)} earlier chars omitted"
                if fail_lines:
                    marker += "; earlier failures:\n" + "\n".join(fail_lines)
                marker += " ...]\n"
                reason = marker + tail
            else:
                reason = output_stripped
            return {
                "status": "stuck",
                "stuck_type": "verify",
                "reason": retry_marker + reason,
                "signatures": signatures,
            }
    except Exception as e:
        # On any exception (e.g., missing binary), return stuck dict so caller can distinguish this from a genuine pass
        return {
            "status": "stuck",
            "stuck_type": "verify",
            "reason": f"verify gate raised: {e}",
        }

    return None


def _run_verify_gates(
    project_root: Path,
    verify_cmd: str | None,
    module_wide_verify_cmd: str | None,
    *,
    git_root: Path | None = None,
    module_verify_baseline: str | None = None,
    cwd_override: Path | None = None,
    module_wide_cwd_override: Path | None = None,
    batch_verify_baseline: list[str] | None = None,
) -> dict | None:
    """
    Run the batch-level verify gate and, if it passes, the module-wide verify gate.

    Sequences two calls to _run_verify_gate so that every success-emit path in _forward_output
    passes through both gates with a single call.
    The batch gate runs first;
    only when it returns None (pass or skipped) does the module-wide gate run.
    This ensures a batch failure is never masked by a module-wide pass and that the module-wide gate
    cannot be accidentally skipped on any code path that replaces a bare _run_verify_gate call with
    this helper.

    When module_wide_verify_cmd is None, behavior is identical to calling
    _run_verify_gate(project_root, verify_cmd) alone -- fully backward-compatible.

    When the module-wide gate fails its stuck dict reason is prefixed with "[module-wide verify]" so
    the operator can distinguish it from a batch-level verify failure in the stuck report.

    module_verify_baseline is a cached, task-scoped read-only signal for whether the parent branch's
    own module-wide verify command was already failing before this task started
    ("pre-existing-failures") or was clean ("clean").
    This function never computes or persists that value -- it only reads whatever the caller hands
    it and short-circuits the module-wide gate accordingly:
      - "pre-existing-failures": skip the module-wide gate entirely (do not run
          module_wide_verify_cmd at all) and treat it as passed, same as when module_wide_verify_cmd
          is None.
      - "clean" or None (not yet computed): run the module-wide gate exactly as it always has.
          None is the fail-safe-toward-strict default -- until a baseline has actually been
              computed, the gate behaves as if the baseline were "clean".

    Args:
        project_root: Path to the worktree root.
        verify_cmd: Batch-level verify command,
            or None to skip.
        module_wide_verify_cmd: Module-wide verify command run after the batch gate passes,
            or None to skip.
        git_root: Optional git root directory used as cwd for verify subprocesses.
            Threaded to both _run_verify_gate calls.
            When None, falls back to project_root.
        module_verify_baseline: Cached "clean" | "pre-existing-failures" | None baseline state for
            the module-wide gate.
            When "pre-existing-failures", the module-wide gate is skipped entirely regardless of
                module_wide_verify_cmd.
            Defaults to None (run strictly, as before).
        cwd_override: Explicit verify cwd for the batch-level gate, resolved by parse_verify_field.
            Takes precedence over git_root/project_root;
            see _run_verify_gate.
        module_wide_cwd_override: Explicit verify cwd for the module-wide gate, resolved by
            parse_verify_field.
            Takes precedence over git_root/project_root;
            see _run_verify_gate.
        batch_verify_baseline: Cached, task-scoped stored signature set (RAW,
        unnormalized failure-marker lines) for this batch's own verify
        command, computed once against the parent branch before this task
        started.
            When the batch-level gate fails, and both
        batch_verify_baseline and the failure's own "signatures" field
        (from _run_verify_gate's non-zero-exit stuck dict) are non-empty
        lists, both are normalized via _normalize_failure_signature and the
        batch is waived (treated as passed) only when the normalized replay
        signature set is a NON-EMPTY subset of the normalized baseline set.
        In every other case -- batch_verify_baseline absent/None/empty, or
        the failure's "signatures" absent/None/empty (covers both an
        unrecognized failure shape and _run_verify_gate's exception path,
        which never sets "signatures" at all) -- the gate blocks exactly as
        it always has, unwaived.
            An empty signature set is never eligible
        for waiver: it is mathematically a subset of any set, so treating it
        as waivable would silently mask genuine new regressions and
        infrastructure failures alike.
            Defaults to None (run strictly, as
        before this parameter existed).

    Returns:
        A stuck dict on the first gate that fails,
        or None when both pass (or are skipped).
    """
    # Run the batch-level gate first; propagate any failure immediately.
    batch_result = _run_verify_gate(
        project_root, verify_cmd, git_root=git_root, cwd_override=cwd_override
    )
    if batch_result is not None:
        # Subset-diff waiver: a batch-level failure is waived only when the replay's own extracted signatures are a non-empty subset of the stored baseline signature set (both normalized to strip volatile per-run durations first).
        # Any other case -- no baseline yet,
        # or an empty/absent replay signature set -- blocks exactly as today, since an empty set is vacuously a subset of anything and must never be treated as waivable.
        replay_signatures = batch_result.get("signatures")
        if batch_verify_baseline and replay_signatures:
            normalized_replay = {
                _normalize_failure_signature(line) for line in replay_signatures
            }
            normalized_baseline = {
                _normalize_failure_signature(line) for line in batch_verify_baseline
            }
            if normalized_replay.issubset(normalized_baseline):
                # Waived: fall through to the module-wide gate below exactly as the batch_result is None path already does.
                batch_result = None
        if batch_result is not None:
            return batch_result

    # Batch gate passed (or was skipped); run the module-wide gate if configured.
    if module_wide_verify_cmd is None:
        return None

    # A cached "pre-existing-failures" baseline means the parent branch was already red before this task started -- skip the module-wide gate for the rest of the task rather than blocking on a failure this batch never caused. "clean" and the not-yet-computed None default both fall through to the strict, unchanged behavior below.
    if module_verify_baseline == "pre-existing-failures":
        return None

    module_result = _run_verify_gate(
        project_root,
        module_wide_verify_cmd,
        git_root=git_root,
        cwd_override=module_wide_cwd_override,
    )
    if module_result is not None:
        # Prefix the reason so the operator can identify the source of the failure.
        original_reason = module_result.get("reason", "")
        module_result["reason"] = f"[module-wide verify] {original_reason}"
        return module_result

    return None


# Recognized GOOS/GOARCH values for the removed-tag qualification check in _go_build_tag_retiering_stuck.
# A small fixed set covering the common values, not Go's exhaustive list -- see that function's docstring for why an unrecognized-but-actually-GOOS value degrades safely rather than needing an exhaustive list here.
_GO_BUILD_TAG_GOOS = {"linux", "darwin", "windows", "freebsd"}
_GO_BUILD_TAG_GOARCH = {"amd64", "arm64", "386"}

_GO_BUILD_TAG_ADD_PREFIX = "+//go:build "
_GO_BUILD_TAG_REMOVE_PREFIX = "-//go:build "


def _parse_go_build_tag_diff(diff_text: str) -> dict[str, dict[str, list[str]]]:
    """
    Parse `git diff --unified=0 ... -- '*.go'` output into per-file //go:build deltas.

    Returns a dict mapping each changed .go file's path (as reported by the diff's "diff --git
    a/<path> b/<path>" header, using the post-change b/ path) to {"added": [...], "removed": [...]},
    where each list holds the raw "//go:build ..."
    line content (with the leading +/- diff marker stripped) for every modern-syntax
    build-constraint line touched in that file's hunks.
    Legacy "// +build" lines are ignored -- out of scope for this gate.
    Diff lines that are not build-constraint lines are ignored (unified=0 only shows changed lines,
    so anything else touched by the same hunk is simply not tracked here).

    Args:
        diff_text: stdout of `git diff --unified=0 <range> -- '*.go'`.

    Returns:
        A dict as described above;
        empty when no build-constraint lines changed.
    """
    files: dict[str, dict[str, list[str]]] = {}
    current_file: str | None = None
    diff_git_re = re.compile(r"^diff --git a/(.*) b/(.*)$")
    for line in diff_text.splitlines():
        match = diff_git_re.match(line)
        if match:
            current_file = match.group(2)
            continue
        if current_file is None:
            continue
        if line.startswith(_GO_BUILD_TAG_ADD_PREFIX):
            files.setdefault(current_file, {"added": [], "removed": []})
            files[current_file]["added"].append(line[1:])
        elif line.startswith(_GO_BUILD_TAG_REMOVE_PREFIX):
            files.setdefault(current_file, {"added": [], "removed": []})
            files[current_file]["removed"].append(line[1:])
    return files


def _go_build_tag_dir(file_path: str) -> str:
    """
    Return the POSIX-style parent directory of a diff-reported .go file path.

    Go's one-package-per-directory convention means a changed file's "affected package" is simply
    its immediate containing directory -- no import-graph resolution needed.
    Returns "."
    for a file at the repo root.
    """
    posix_path = file_path.replace("\\", "/")
    return posix_path.rsplit("/", 1)[0] if "/" in posix_path else "."


def _go_build_pattern(dir_str: str) -> str:
    """Build the `go build` package pattern for a directory ("./..." at the repo root)."""
    return "./..." if dir_str == "." else f"./{dir_str}/..."


def _nested_go_module_root_and_pattern(project_root: Path, dir_str: str) -> tuple[Path, str]:
    """
    Resolve the `go build` cwd/pattern for a go-build-tag-retiering compile check.

    Walks up from the affected directory looking for the nearest enclosing `go.mod`, stopping at
    `project_root`.
    When a `go.mod` is found strictly under `project_root`, the compile check must run with that
    nested module as cwd -- `go build` resolves module boundaries relative to cwd, so pointing it at
    `project_root` for a nested module fails with "directory prefix ...
    does not contain main module" even though the nested module compiles fine on its own (fixes
    #751).
    When no nested `go.mod` is found, this returns today's exact `(project_root,
    _go_build_pattern(dir_str))` behavior unchanged -- the single-module-repo fallback.

    Args:
        project_root: Path to the worktree root (also the outermost fallback).
        dir_str: The affected package directory, relative to project_root ("."
            for the repo root).

    Returns:
        A (cwd, pattern) pair for the `go build` invocation.
    """
    affected_dir = project_root / dir_str
    candidate = affected_dir
    while not (candidate / "go.mod").exists() and candidate != project_root:
        candidate = candidate.parent

    if candidate == project_root:
        return project_root, _go_build_pattern(dir_str)

    if candidate == affected_dir:
        return candidate, "./..."
    return candidate, _go_build_pattern(affected_dir.relative_to(candidate).as_posix())


def _is_qualifying_custom_tag(tag: str) -> bool:
    """
    Return True when a removed //go:build constraint is safe to translate to `-tags`.

    Qualifies only when the constraint is a single bare identifier -- no boolean operators (&&, ||,
    !)
    or parentheses,
    and no internal whitespace -- and is not a recognized GOOS/GOARCH value.
    A compound/negated constraint risks compiling under the wrong tag set if naively translated;
    an unrecognized-but-actually- GOOS value degrades safely to "run it as a custom tag" (a
    false-custom-tag build with an invalid -tags value fails closed as stuck/verify, the safe
    direction).

    Args:
        tag: The removed //go:build line's content, with the "//go:build " prefix already stripped
        and the remainder trimmed.

    Returns:
        True when the tag is a single, non-GOOS/GOARCH bare identifier.
    """
    if any(op in tag for op in ("&&", "||", "!", "(", ")")):
        return False
    if len(tag.split()) != 1:
        return False
    return tag not in _GO_BUILD_TAG_GOOS and tag not in _GO_BUILD_TAG_GOARCH


def _go_build_tag_stuck_dict(
    dir_str: str,
    direction: str,
    build_result: subprocess.CompletedProcess,
    session_id: str | None,
) -> dict:
    """Build the stuck/verify dict for a failed go-build-tag-retiering compile check."""
    output = ((build_result.stdout or "") + (build_result.stderr or "")).strip()
    tail = output[-2000:] if len(output) > 2000 else output
    return {
        "status": "stuck",
        "stuck_type": "verify",
        "reason": (
            f"go build-tag retiering check failed: {dir_str}"
            f" ({direction}-tag transition): {tail}"
        ),
        "session_id": session_id or "unknown",
    }


def _go_build_tag_retiering_stuck(
    project_root: Path,
    start_sha: str | None,
    session_id: str | None,
) -> dict | None:
    """
    Detect and compile-check Tier-1 (default-build) membership transitions caused by added or
    removed `//go:build` constraints in this batch's .go file changes.

    Fixes #642: a batch that adds or removes a `//go:build` constraint on a .go file can silently
    move that file into or out of the default (untagged) build without any existing gate noticing --
    the batch's own verify command was written before the transition and has no reason to re-check
    the opposite build membership.
    This gate diffs `*.go` files since start_sha, classifies each changed file's `//go:build` line
    delta as an added-tag transition (file exits the default build), a removed-tag transition (file
    enters the default build), or a value-only edit (no membership change -- skipped), and runs the
    matching `go build` compile check for each affected package directory.

    Algorithm:
      1. start_sha is None: nothing to diff against -- return None.
      2. `git diff --unified=0 start_sha..HEAD -- '*.go'`;
          a failed subprocess or empty output -- return None.
      3. No '.go' files touched at all (no build-constraint lines parsed) -- return None.
          This makes the gate a safe no-op for non-Go batches/repos with no language-detection
              config needed.
      4. Parse the diff for `+//go:build ` / `-//go:build ` lines per file (modern syntax only;
          legacy `// +build` is out of scope).
          A `//go:build` line both added and removed in the same file at different values is a
              value-only edit, not a transition -- skipped, not treated as an added+removed pair.
      5. Exactly one added and zero removed -> added-tag transition.
          Exactly one removed and zero added -> removed-tag transition.
          Anything else (including the value-only case) is not a transition -- skipped.
      6. Affected package = the transitioned file's immediate directory.
          Multiple transitioned files in the same directory dedupe to a single compile check.
      7. Added-tag directories: `go build ./<dir>/...`.
      8. Removed-tag directories: the removed constraint qualifies for a compile check only when it
          is a single bare identifier that is not a recognized GOOS/GOARCH value (see
          _is_qualifying_custom_tag); qualifying directories run `go build -tags <tag> ./<dir>/...`.
          Non-qualifying (compound/negated/ GOOS/GOARCH) constraints are logged (ASCII-only, stderr)
              and skipped.
      9. Before either compile check runs, if the affected directory no longer exists on disk, the
          transition was actually a whole-directory deletion (not a same-directory detagging edit)
          -- log a skip line (ASCII-only, stderr) and skip the compile check for that directory.
      10. Any compile check exiting non-zero -- return a stuck_type="verify" dict naming the
          directory, transition direction, and captured output tail.
      11. All compile checks pass (or none were needed) -- return None.

    Never raises to its caller: any subprocess/parsing failure is caught and degrades to None
    (nothing to report), per this plan's "never raise from a new gate/check function" Shared
    Decision.
    A deliberate compile-check failure (step 9) is a normal return, not an exception, so it is
    unaffected by that guard.

    Args:
        project_root: Path to the worktree root used as cwd for git/go subprocesses.
        start_sha: The SHA recorded at batch start;
        None disables the gate.
        session_id: Session identifier included in the returned stuck dict.

    Returns:
        A stuck dict with stuck_type="verify" on a compile-check failure,
        or None (gate disabled, no transition detected, or all compile checks passed).
    """
    if start_sha is None:
        return None

    try:
        diff_result = _subprocess_util.run(
            ["git", "diff", "--unified=0", f"{start_sha}..HEAD", "--", "*.go"],
            cwd=project_root,
        )
        if diff_result.returncode != 0 or not diff_result.stdout.strip():
            return None

        files_info = _parse_go_build_tag_diff(diff_result.stdout)
        if not files_info:
            return None

        added_dirs: set[str] = set()
        removed_dirs: dict[str, dict] = {}
        for file_path, lines in files_info.items():
            added = lines["added"]
            removed = lines["removed"]
            if len(added) == 1 and len(removed) == 0:
                added_dirs.add(_go_build_tag_dir(file_path))
            elif len(removed) == 1 and len(added) == 0:
                dir_str = _go_build_tag_dir(file_path)
                tag = removed[0][len("//go:build "):].strip()
                entry = removed_dirs.setdefault(dir_str, {"tag": tag, "files": [], "tag_mismatch": False})
                if entry["tag"] != tag:
                    # Multiple files in the same directory with different removed tags.
                    # Mark this directory as conflicted and skip its compile check.
                    entry["tag_mismatch"] = True
                entry["files"].append(file_path)
            # else: value-only edit (or an otherwise-ambiguous delta) -- not a membership transition, skip.

        for dir_str in sorted(added_dirs):
            if not (project_root / dir_str).is_dir():
                # The directory that gained the //go:build tag no longer exists -- this was a whole-directory deletion, not a same-directory detagging edit.
                # There is nothing left to compile-check.
                print(
                    f"[go-build-tag-retiering] skip: {dir_str} no longer exists"
                    f" on disk (directory deleted)",
                    file=sys.stderr,
                )
                continue
            build_cwd, build_pattern = _nested_go_module_root_and_pattern(
                project_root, dir_str
            )
            build_result = _subprocess_util.run(
                ["go", "build", build_pattern],
                cwd=build_cwd,
            )
            if build_result.returncode != 0:
                return _go_build_tag_stuck_dict(
                    dir_str, "added", build_result, session_id
                )

        for dir_str, entry in sorted(removed_dirs.items()):
            if entry.get("tag_mismatch", False):
                print(
                    f"[go-build-tag-retiering] skip: {', '.join(entry['files'])}"
                    f" removed different //go:build constraints in the same directory",
                    file=sys.stderr,
                )
                continue
            tag = entry["tag"]
            if not _is_qualifying_custom_tag(tag):
                print(
                    f"[go-build-tag-retiering] skip: {', '.join(entry['files'])}"
                    f" removed a //go:build constraint not safe to translate"
                    f" to -tags (compound, negated, or GOOS/GOARCH): {tag}",
                    file=sys.stderr,
                )
                continue
            if not (project_root / dir_str).is_dir():
                # The directory that lost the //go:build tag no longer exists -- this was a whole-directory deletion, not a same-directory detagging edit.
                # There is nothing left to compile-check.
                print(
                    f"[go-build-tag-retiering] skip: {dir_str} no longer exists"
                    f" on disk (directory deleted)",
                    file=sys.stderr,
                )
                continue
            build_cwd, build_pattern = _nested_go_module_root_and_pattern(
                project_root, dir_str
            )
            build_result = _subprocess_util.run(
                ["go", "build", "-tags", tag, build_pattern],
                cwd=build_cwd,
            )
            if build_result.returncode != 0:
                return _go_build_tag_stuck_dict(
                    dir_str, "removed", build_result, session_id
                )

        return None
    except Exception:
        # Never raise to the caller -- any git/subprocess/parsing failure degrades to "nothing to report" per this batch's Shared Decision.
        return None


def emit_prepare(
    briefs_dir: Path,
    role: str,
    scope: str,
    round_n: int,
    prompt_text: str,
    model_tier: str,
    session_id: str,
    start_sha: str | None = None,
    nits_only: bool = False,
    effort: str | None = None,
) -> int:
    """Write brief and emit prepare JSON envelope.

    Writes the brief to briefs_dir/<role>-<sanitized_scope>-r<round_n>.md (scope is sanitized for
    Windows filename safety) and prints one JSON line with the brief path and metadata.
    Returns 0.

    Args:
        start_sha: Git SHA recorded at batch start; included in the envelope as "start_sha" when not
            None, omitted otherwise.
        nits_only: When True, the envelope includes `"nits_only": true`, signalling that any
            finalize call re-invoking this scope/round must re-pass `--nits-only`.
            Omitted from the envelope (not emitted as `false`) when this stays at its default.
        effort: Effort tier resolved from the reviewer/implementer registry spec (e.g. "high");
            included in the envelope as "effort" when not None, omitted otherwise.
    """
    brief_path = _agent_dispatch.write_brief(
        briefs_dir, role, scope, round_n, prompt_text
    )
    envelope = {
        "stage": "prepare",
        "brief_path": str(brief_path.resolve()),
        "subagent_type": _agent_dispatch.resolve_subagent_type(
            _agent_dispatch.SUBAGENT_IMPLEMENTER, effort
        ),
        "model": model_tier,
        "session_id": session_id,
        "role": role,
        "scope": scope,
        "round": round_n,
    }
    if start_sha is not None:
        envelope["start_sha"] = start_sha
    if nits_only:
        envelope["nits_only"] = True
    if effort is not None:
        envelope["effort"] = effort
    print(json.dumps(envelope))
    return 0


def emit_prepare_no_dispatch(
    model_tier: str,
    session_id: str,
    role: str,
    scope: str,
    round_n: int,
    project_root: Path,
) -> int:
    """Emit prepare JSON with dispatch_needed:false for verify-fix pass case.

    When verify passes in prepare, there is nothing to dispatch.
    This emits a special prepare envelope with dispatch_needed:false and an embedded success
    envelope.
    Returns 0.
    """
    result = _subprocess_util.run(["git", "rev-parse", "HEAD"], cwd=project_root)
    commit_sha = result.stdout.strip() if result.returncode == 0 else ""

    embedded_envelope = {
        "status": "success",
        "commit_sha": commit_sha,
        "session_id": session_id,
    }

    envelope = {
        "stage": "prepare",
        "dispatch_needed": False,
        "subagent_type": _agent_dispatch.SUBAGENT_IMPLEMENTER,
        "model": model_tier,
        "session_id": session_id,
        "role": role,
        "scope": scope,
        "round": round_n,
        "envelope": embedded_envelope,
    }
    print(json.dumps(envelope))
    return 0


def finalize_from_output(
    agent_output_path: Path,
    project_root: Path,
    *,
    start_sha: str | None = None,
    snapshot_path: Path | None = None,
    session_id: str | None = None,
    verify_cmd: str | None = None,
    module_wide_verify_cmd: str | None = None,
    module_verify_baseline: str | None = None,
    card_ids: set[int] | None = None,
    commit_none_card_ids: set[int] | None = None,
    task_dir: Path | None = None,
    parent_branch: str | None = None,
    nits_only: bool = False,
    status_path: Path | None = None,
    nits_scope: str | None = None,
    git_root: Path | None = None,
    cwd_override: Path | None = None,
    module_wide_cwd_override: Path | None = None,
    batch_verify_baseline: list[str] | None = None,
) -> int:
    """Read sub-agent output and finalize.

    Reads the agent's final text from agent_output_path (utf-8) and delegates to _forward_output
    with the captured output.
    Returns the code from _forward_output.

    Args:
        agent_output_path: Path to the file containing the sub-agent's output text.
        project_root: Path to the worktree root (hub directory).
        start_sha: Git SHA recorded at batch start; used for no-content-commit detection.
        snapshot_path: Path to the cleanliness snapshot file;
            enables new-dirt detection.
        session_id: Session identifier threaded into the output envelope.
        verify_cmd: Batch-level verify command to run before emitting success.
        module_wide_verify_cmd: Module-wide verify command run after the batch gate passes.
        module_verify_baseline: Cached "clean" | "pre-existing-failures" | None baseline state for
            the module-wide gate, forwarded to _run_verify_gates.
            When "pre-existing-failures", the module-wide gate is skipped entirely.
            Defaults to None (run the module-wide gate strictly, as before this parameter existed).
        card_ids: The set of Card numbers declared in the batch file;
            enables the completeness gate.
            cards_done and already_complete (read from the parsed success envelope, not accepted as
                parameters here) are compared against this set inside _forward_output.
        commit_none_card_ids: card numbers whose Commit: field is the literal none, computed by the
            caller from the batch plan file (never self-reported);
            when the coerced cards_done is a non-empty subset of this set, the content==0
                reclassification below is skipped.
        task_dir: Worktree-relative path to the task directory (_mill/).
        parent_branch: Name of the parent branch for in-scope dirty-tree detection.
        nits_only: When True, writes a nits-fixed marker on success.
        status_path: Path to the status.md file; required when nits_only is True.
        nits_scope: Scope label for the nits-fixed marker; required when nits_only is True.
        git_root: Optional git root directory used as cwd for verify subprocesses.
            When None, falls back to project_root.
            Pass the actual git root in nested layouts so the verify command runs from the repo root
                rather than the hub sub-directory, preventing spurious MSB1009 / path-not-found
                errors.
        cwd_override: Explicit batch-level verify cwd resolved by parse_verify_field
        from a `{cwd: hub|git_root, command: ...}` mapping.
            Takes precedence over
        git_root/project_root; forwarded unchanged to _forward_output.
        module_wide_cwd_override: Explicit module-wide verify cwd resolved by parse_verify_field.
            Takes precedence over git_root/project_root; forwarded unchanged to _forward_output.
        batch_verify_baseline: Cached, task-scoped stored signature set for
        this batch's own verify command, forwarded unchanged to
        _forward_output's _run_verify_gates calls.
            See _run_verify_gates
        for the subset-diff waiver rule this enables.
            Defaults to None
        (run strictly, as before this parameter existed).
    """
    # Normalize to Path for safety -- call sites pass this via Path(args.agent_output),
    # but the parameter is documented (not enforced) as Path.
    agent_output_path = Path(agent_output_path)
    if not agent_output_path.is_file():
        # Guard against a raw, unhandled FileNotFoundError (or IsADirectoryError, if a directory occupies the path -- is_file() catches that case too) crashing the implementer/fixer/merge-in CLI with a traceback instead of an actionable message.
        print(
            f"ERROR: --agent-output file not found: {agent_output_path} -- for"
            " implementer/fixer/merge-in dispatches the orchestrator must write the"
            " notification message to this path before calling --stage finalize",
            file=sys.stderr,
        )
        return 1

    # The harness HTML-escapes the <task-notification> payload uniformly before delivery, so the text captured to agent_output_path may contain entities like "&amp;" and "&lt;".
    # Unescape here (at the read site) so downstream JSON parsing and status.md writes see the original, uncorrupted text.
    output = html.unescape(Path(agent_output_path).read_text(encoding="utf-8"))
    return _forward_output(
        output,
        project_root,
        start_sha=start_sha,
        snapshot_path=snapshot_path,
        session_id=session_id,
        verify_cmd=verify_cmd,
        module_wide_verify_cmd=module_wide_verify_cmd,
        module_verify_baseline=module_verify_baseline,
        card_ids=card_ids,
        commit_none_card_ids=commit_none_card_ids,
        task_dir=task_dir,
        parent_branch=parent_branch,
        nits_only=nits_only,
        status_path=status_path,
        nits_scope=nits_scope,
        git_root=git_root,
        cwd_override=cwd_override,
        module_wide_cwd_override=module_wide_cwd_override,
        batch_verify_baseline=batch_verify_baseline,
    )


def _extract_status_json(output: str) -> dict | None:
    """Extract the last JSON object containing a 'status' key from output.

    Iterates through balanced-brace spans and attempts json.loads on each.
    Returns the parsed JSON dict if a valid status object is found;
    None otherwise.
    """
    # Find all potential JSON spans by tracking balanced braces
    candidates = []
    depth = 0
    start = None
    for i, char in enumerate(output):
        if char == "{":
            if depth == 0:
                start = i
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(output[start : i + 1])
                start = None
    # Try to parse candidates in reverse order (last first)
    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "status" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
    return None


def _forward_output(
    output: str,
    project_root: Path,
    *,
    start_sha: str | None = None,
    snapshot_path: Path | None = None,
    session_id: str | None = None,
    verify_cmd: str | None = None,
    module_wide_verify_cmd: str | None = None,
    module_verify_baseline: str | None = None,
    card_ids: set[int] | None = None,
    commit_none_card_ids: set[int] | None = None,
    task_dir: Path | None = None,
    parent_branch: str | None = None,
    nits_only: bool = False,
    status_path: Path | None = None,
    nits_scope: str | None = None,
    git_root: Path | None = None,
    cwd_override: Path | None = None,
    module_wide_cwd_override: Path | None = None,
    batch_verify_baseline: list[str] | None = None,
) -> int:
    """Extract the last JSON object containing a 'status' key from output.

    Returns 0 in both success and fallback cases -- the JSON on stdout is how the caller reads
    state.
    When no valid JSON is found, emits a stuck/logic sentinel.
    When the inferred-success fallback fires, the emitted JSON uses ``session_id`` if supplied,
    falling back to the literal ``"unknown"`` for backwards compatibility with callers that don't
    pass it.
    When verify_cmd is not None, runs it before emitting any success;
    if the command fails, demotes the success to stuck/verify with the command's output in reason.
    When module_wide_verify_cmd is not None, it is run as a second gate after verify_cmd passes (or
    is skipped);
    a module-wide failure also demotes to stuck/verify with a "[module-wide verify]" prefix in the
    reason.
    When module_wide_verify_cmd is None, behavior is unchanged (single gate, backward-compatible).
    module_verify_baseline is forwarded to _run_verify_gates unchanged: a cached "clean" |
    "pre-existing-failures" | None baseline for the module-wide gate.
    When "pre-existing-failures", the module-wide gate is skipped entirely regardless of
    module_wide_verify_cmd. "clean" and the default None both run the module-wide gate exactly as
    before this parameter existed.
    When card_ids is provided, the completeness gate checks that the declared card_ids are all
    accounted for -- either by raw content-commit count (when the parsed success envelope's
    cards_done field is absent or malformed) or by comparing card_ids against a self-reported
    cards_done set (when present and valid).
    already_complete: true in the parsed envelope short-circuits the gate entirely on a
    --resume-incomplete re-verification.
    Both cards_done and already_complete are read from the parsed success envelope inside this
    function, not accepted as separate parameters, since they are only ever meaningful alongside a
    self-reported status: success.
    commit_none_card_ids: card numbers whose Commit: field is the literal none, computed by the
    caller from the batch plan file (never self-reported);
    when the coerced cards_done is a non-empty subset of this set, the content==0 reclassification
    below is skipped.
    When task_dir and parent_branch are provided, the dirty-tree gate checks in-scope cleanliness.
    When nits_only is True and status_path and nits_scope are not None, on the parsed-success emit
    path (where a fixer's own reported status == "success" is about to be printed), adds
    "nits_applied": True to the dict and writes a nits-fixed-<scope> marker to the status file.
    When nits_only is True, the no-content-commit gate (HEAD == start_sha / only-batch-start-commit)
    is also skipped, since a --nits-only pass that correctly pushes back on every finding is
    expected to produce zero commits.
    When git_root is not None, it is used as the cwd for verify subprocesses instead of
    project_root.
    This corrects verify behavior in nested layouts where the plan's verify command must run from
    the git root rather than the hub sub-directory.
    cwd_override and module_wide_cwd_override are explicit verify cwds resolved by
    parse_verify_field from a `{cwd: hub|git_root, command: ...}` mapping;
    each always takes precedence over git_root/project_root for its respective gate (batch-level and
    module-wide, respectively).
    Both default to None, which preserves the git_root/project_root fallback behavior for today's
    plain-string verify format.
    batch_verify_baseline is forwarded unchanged to every _run_verify_gates call site below: a
    cached, task-scoped stored signature set for this batch's own verify command, enabling the
    subset-diff waiver rule documented on _run_verify_gates.
    Defaults to None (run strictly, as before this parameter existed).
    """
    parsed = _extract_status_json(output)
    if parsed is not None:
        # Apply verify gates ONLY for self-reported success
        if parsed.get("status") == "success":
            # Resolve session id now so it is available both for the verify-gate reclassification path and for the completeness / dirty gates below.
            # Hoisted above _run_verify_gates to avoid a NameError in _reclassify_verify_failure when the gate fires.
            _gate_session_id = session_id or parsed.get("session_id")
            # cards_done / already_complete: the implementer's own self-report of which declared card_ids this commit set addresses,
            # and whether a --resume-incomplete re-verification found every card's requirements already satisfied with no new commit.
            # Extracted here (before the gate calls) so both _reclassify_verify_failure and _batch_completeness_stuck see the identical self-reported state.
            # already_complete is threaded ONLY to _batch_completeness_stuck below -- it is a claim about card completeness meaningful solely on the explicit-status:success path,
            # and _reclassify_verify_failure fires on a verify-failure trigger where "success" was never cleanly reported, so it deliberately has no already_complete parameter at all (passing one would raise TypeError).
            _cards_done = parsed.get("cards_done")
            _already_complete = bool(parsed.get("already_complete", False))

            gate_result = _run_verify_gates(
                project_root,
                verify_cmd,
                module_wide_verify_cmd,
                git_root=git_root,
                module_verify_baseline=module_verify_baseline,
                cwd_override=cwd_override,
                module_wide_cwd_override=module_wide_cwd_override,
                batch_verify_baseline=batch_verify_baseline,
            )
            if gate_result is not None:
                # Reclassify a verify failure that is really a partial-batch stop (stuck_type:transient) or a no-content stop (stuck_type:logic).
                gate_result = _reclassify_verify_failure(
                    gate_result,
                    project_root,
                    start_sha,
                    card_ids,
                    _gate_session_id,
                    cards_done=_cards_done,
                    commit_none_card_ids=commit_none_card_ids,
                )
                # Add commit_sha only for verify/transient/incomplete results;
                # logic (no-content) results match the sibling no-content gates that omit commit_sha.
                if gate_result.get("stuck_type") in ("verify", "transient", "incomplete"):
                    result = _subprocess_util.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=project_root,
                    )
                    if result.returncode == 0:
                        gate_result["commit_sha"] = result.stdout.strip()
                print(json.dumps(gate_result))
                return 0

            # Go build-tag retiering gate: catches a Tier-1 (default-build) compile break introduced by an added/removed //go:build constraint (#642).
            # Runs after the verify gate passes and before the no-content-commit and completeness checks, mirroring how the verify gate's own failure already short-circuits ahead of both.
            _retiering_result = _go_build_tag_retiering_stuck(
                project_root, start_sha, _gate_session_id
            )
            if _retiering_result is not None:
                _attach_commit_sha(_retiering_result, project_root)
                print(json.dumps(_retiering_result))
                return 0

            # Check for no-content-commit success: reject if HEAD == start_sha or if the only commit since start_sha is the batch-start housekeeping commit.
            # Skipped entirely when nits_only is True: a --nits-only pass that legitimately pushes back on every finding (per the mill-receiving-review decision tree) is expected to make zero commits,
            # and that is success, not a stuck/logic demotion.
            if start_sha is not None and not nits_only:
                result = _subprocess_util.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=project_root,
                )
                if (
                    result.returncode == 0
                    and result.stdout.strip() == start_sha
                    and not _cards_done_all_commit_none(_cards_done, commit_none_card_ids)
                ):
                    # Implementer reported success but no content commit was made
                    print(
                        json.dumps(
                            {
                                "status": "stuck",
                                "stuck_type": "logic",
                                "reason": "success reported but no content commit (HEAD == start_sha)",
                                "session_id": session_id or parsed.get("session_id"),
                            }
                        )
                    )
                    return 0
                # Guard against the start-batch-commit-only case (Bug #557): prepare makes a "mill-go: start batch" commit, so HEAD != start_sha even when the implementer wrote zero code commits.
                # Detect this and demote to stuck/logic.
                if (
                    result.returncode == 0
                    and _is_only_start_batch_commit(project_root, start_sha)
                    and not _cards_done_all_commit_none(_cards_done, commit_none_card_ids)
                ):
                    print(
                        json.dumps(
                            {
                                "status": "stuck",
                                "stuck_type": "logic",
                                "reason": "success reported but no content commit (only batch-start commit since start_sha)",
                                "session_id": session_id or parsed.get("session_id"),
                            }
                        )
                    )
                    return 0

            # _gate_session_id is already resolved above (hoisted before gate call).

            # Completeness gate: demote to incomplete when the declared card_ids are not all accounted for (by raw count when cards_done is absent/malformed, or by set difference against cards_done when present and valid).
            # ignore_verify stays False here — on the explicit-success path a passing verify is conclusive evidence the batch is complete.
            # already_complete short-circuits the gate entirely on a --resume-incomplete re-verification.
            _completeness_result = _batch_completeness_stuck(
                project_root,
                start_sha,
                card_ids,
                _gate_session_id,
                verify_cmd=verify_cmd,
                cards_done=_cards_done,
                already_complete=_already_complete,
            )
            if _completeness_result is not None:
                _attach_commit_sha(_completeness_result, project_root)
                print(json.dumps(_completeness_result))
                return 0

            # In-scope dirty-tree gate: demote to stuck/logic when tracked in-scope files remain dirty.
            _dirty_result = _in_scope_dirty_stuck(
                project_root, task_dir, parent_branch, _gate_session_id
            )
            if _dirty_result is not None:
                print(json.dumps(_dirty_result))
                return 0

            # On the parsed-success emit path, handle nits-only marker and flag
            if nits_only and status_path and nits_scope:
                parsed["nits_applied"] = True
                _status.append_phase(
                    status_path, f"nits-fixed-{nits_scope}", _timestamp.now_utc_iso()
                )

        # Normalize an implementer-emitted status:incomplete report to the canonical incomplete stuck envelope before the generic commit_sha passthrough runs.
        # This must come before the passthrough so the incomplete envelope gets its own commit_sha injected here rather than the generic success-path commit_sha.
        if parsed.get("status") == "incomplete":
            # Count content commits for commits_made;
            # fall back to the implementer's own cards_completed_count field when git is unavailable.
            _incomplete_commits = _content_commit_count(project_root, start_sha)
            if _incomplete_commits is None:
                _incomplete_commits = parsed.get("cards_completed_count")
            _incomplete_envelope: dict = {
                "status": "stuck",
                "stuck_type": "incomplete",
                "session_id": session_id or parsed.get("session_id") or "unknown",
                "commits_made": _incomplete_commits,
            }
            _attach_commit_sha(_incomplete_envelope, project_root)
            print(json.dumps(_incomplete_envelope))
            return 0

        # The corrective git rev-parse HEAD / _is_valid_commit_sha block below only ever
        # applies to a self-reported status: success -- every other status (already-classified
        # stuck/*, or anything else that reaches this point) must print through unchanged.
        # Running the correction unconditionally here previously let an unrelated corrective-SHA
        # failure silently corrupt an already-correct stuck/transient or stuck/verify report into
        # stuck/logic (see the forward-output-stuck-passthrough postmortem).
        if parsed.get("status") == "success":
            result = _subprocess_util.run(
                ["git", "rev-parse", "HEAD"],
                cwd=project_root,
            )
            if result.returncode == 0 and _is_valid_commit_sha(result.stdout.strip()):
                parsed["commit_sha"] = result.stdout.strip()
                violations = _cleanliness.compute_scope_violations(project_root, git_root)
                if violations:
                    parsed["scope_violations"] = violations
                print(json.dumps(parsed))
            else:
                # The corrective git rev-parse HEAD call failed or returned a malformed SHA -- never pass an agent's unvalidated self-reported commit_sha through on the success path (see #744 postmortem).
                _correction_failure = {
                    "status": "stuck",
                    "stuck_type": "logic",
                    "reason": "commit_sha correction failed: git rev-parse HEAD did not return a well-formed SHA",
                    "session_id": session_id or parsed.get("session_id") or "unknown",
                }
                print(json.dumps(_correction_failure))
        else:
            print(json.dumps(parsed))
        return 0
    try:
        if (
            start_sha is not None
            and snapshot_path is not None
            and snapshot_path.exists()
        ):
            new_dirt = _cleanliness.compute_new_dirt(project_root, snapshot_path)
            if new_dirt == []:
                result = _subprocess_util.run(
                    ["git", "rev-parse", "HEAD"], cwd=project_root
                )
                if result.returncode == 0 and result.stdout.strip() != start_sha:
                    head = result.stdout.strip()
                    result_full = _subprocess_util.run(
                        [
                            "git",
                            "-C",
                            str(project_root),
                            "status",
                            "--porcelain",
                            "--untracked-files=no",
                        ],
                        check=True,
                    )
                    if result_full.stdout.strip():
                        # Check if the remaining dirt is only formatter drift
                        if _is_formatter_drift_only(project_root):
                            # Auto-commit formatter drift
                            if _commit_formatter_drift(project_root):
                                # Re-check that tree is now clean
                                result_check = _subprocess_util.run(
                                    [
                                        "git",
                                        "-C",
                                        str(project_root),
                                        "status",
                                        "--porcelain",
                                        "--untracked-files=no",
                                    ],
                                    check=False,
                                )
                                if (
                                    result_check.returncode == 0
                                    and not result_check.stdout.strip()
                                ):
                                    # Tree is now clean; get the new HEAD after drift commit
                                    result_head = _subprocess_util.run(
                                        ["git", "rev-parse", "HEAD"],
                                        cwd=project_root,
                                    )
                                    if result_head.returncode == 0:
                                        new_head = result_head.stdout.strip()
                                    else:
                                        new_head = head
                                    # Apply verify gates before emitting success
                                    gate_result = _run_verify_gates(
                                        project_root,
                                        verify_cmd,
                                        module_wide_verify_cmd,
                                        git_root=git_root,
                                        module_verify_baseline=module_verify_baseline,
                                        cwd_override=cwd_override,
                                        module_wide_cwd_override=module_wide_cwd_override,
                                        batch_verify_baseline=batch_verify_baseline,
                                    )
                                    if gate_result is not None:
                                        # No parsed success JSON on this inference path -- there is nothing to self-report from, so cards_done is always None here (the absent-field fallback always applies).
                                        gate_result = _reclassify_verify_failure(
                                            gate_result,
                                            project_root,
                                            start_sha,
                                            card_ids,
                                            session_id,
                                            cards_done=None,
                                        )
                                        if gate_result.get("stuck_type") in ("verify", "transient", "incomplete"):
                                            gate_result["commit_sha"] = new_head
                                        print(json.dumps(gate_result))
                                        return 0
                                    # Go build-tag retiering gate (#642) -- see the explicit-success path's comment for rationale.
                                    # This no-JSON inference path must match that same coverage.
                                    _retiering_result = _go_build_tag_retiering_stuck(
                                        project_root, start_sha, session_id
                                    )
                                    if _retiering_result is not None:
                                        _attach_commit_sha(_retiering_result, project_root)
                                        print(json.dumps(_retiering_result))
                                        return 0
                                    # Completeness gate: incomplete batch demotes to stuck/incomplete.
                                    # ignore_verify=True forces the check even when verify passed -- on the no-JSON inference path the implementer never reported success, so a passing verify does not mean the batch is complete.
                                    # cards_done=None: no self-report exists on this inference path.
                                    _comp = _batch_completeness_stuck(
                                        project_root,
                                        start_sha,
                                        card_ids,
                                        session_id,
                                        verify_cmd=verify_cmd,
                                        ignore_verify=True,
                                        cards_done=None,
                                    )
                                    if _comp is not None:
                                        _attach_commit_sha(_comp, project_root)
                                        print(json.dumps(_comp))
                                        return 0
                                    # Emit success
                                    violations = _cleanliness.compute_scope_violations(
                                        project_root, git_root
                                    )
                                    if violations:
                                        print(
                                            json.dumps(
                                                {
                                                    "status": "stuck",
                                                    "stuck_type": "logic",
                                                    "reason": f"untracked files outside scope: {violations}",
                                                    "scope_violations": violations,
                                                    "inferred": True,
                                                }
                                            )
                                        )
                                    else:
                                        # Guard against start-batch-commit-only case on the formatter-drift inference path (Bug #557).
                                        if _is_only_start_batch_commit(
                                            project_root, start_sha
                                        ):
                                            print(
                                                json.dumps(
                                                    {
                                                        "status": "stuck",
                                                        "stuck_type": "logic",
                                                        "reason": "inferred success but only batch-start commit since start_sha",
                                                        "session_id": session_id
                                                        or "unknown",
                                                        "inferred": True,
                                                    }
                                                )
                                            )
                                        else:
                                            print(
                                                json.dumps(
                                                    {
                                                        "status": "success",
                                                        "commit_sha": new_head,
                                                        "session_id": session_id
                                                        or "unknown",
                                                        "inferred": True,
                                                    }
                                                )
                                            )
                                    return 0
                        # Not formatter drift, or commit failed
                        print(
                            json.dumps(
                                {
                                    "status": "stuck",
                                    "stuck_type": "logic",
                                    "reason": "inferred success but working tree dirty -- implementer likely skipped git-commit on modified files",
                                }
                            )
                        )
                        return 0
                    # Apply verify gates before emitting success
                    gate_result = _run_verify_gates(
                        project_root,
                        verify_cmd,
                        module_wide_verify_cmd,
                        git_root=git_root,
                        module_verify_baseline=module_verify_baseline,
                        cwd_override=cwd_override,
                        module_wide_cwd_override=module_wide_cwd_override,
                        batch_verify_baseline=batch_verify_baseline,
                    )
                    if gate_result is not None:
                        # No parsed success JSON on this inference path -- cards_done is always None (the absent-field fallback always applies).
                        gate_result = _reclassify_verify_failure(
                            gate_result,
                            project_root,
                            start_sha,
                            card_ids,
                            session_id,
                            cards_done=None,
                        )
                        if gate_result.get("stuck_type") in ("verify", "transient", "incomplete"):
                            gate_result["commit_sha"] = head
                        print(json.dumps(gate_result))
                        return 0
                    # Go build-tag retiering gate (#642) -- see the explicit-success path's comment for rationale.
                    # This no-JSON inference path must match that same coverage.
                    _retiering_result = _go_build_tag_retiering_stuck(
                        project_root, start_sha, session_id
                    )
                    if _retiering_result is not None:
                        _attach_commit_sha(_retiering_result, project_root)
                        print(json.dumps(_retiering_result))
                        return 0
                    # Completeness gate: incomplete batch demotes to stuck/incomplete.
                    # ignore_verify=True forces the check even when verify passed -- on the no-JSON inference path the implementer never reported success, so a passing verify does not mean the batch is complete.
                    # cards_done=None: no self-report exists on this inference path.
                    _comp = _batch_completeness_stuck(
                        project_root,
                        start_sha,
                        card_ids,
                        session_id,
                        verify_cmd=verify_cmd,
                        ignore_verify=True,
                        cards_done=None,
                    )
                    if _comp is not None:
                        _attach_commit_sha(_comp, project_root)
                        print(json.dumps(_comp))
                        return 0
                    violations = _cleanliness.compute_scope_violations(project_root, git_root)
                    if violations:
                        print(
                            json.dumps(
                                {
                                    "status": "stuck",
                                    "stuck_type": "logic",
                                    "reason": f"untracked files outside scope: {violations}",
                                    "scope_violations": violations,
                                    "inferred": True,
                                }
                            )
                        )
                    else:
                        # Guard against start-batch-commit-only case on the snapshot-present clean-tree inference path (Bug #557).
                        if _is_only_start_batch_commit(project_root, start_sha):
                            print(
                                json.dumps(
                                    {
                                        "status": "stuck",
                                        "stuck_type": "logic",
                                        "reason": "inferred success but only batch-start commit since start_sha",
                                        "session_id": session_id or "unknown",
                                        "inferred": True,
                                    }
                                )
                            )
                        else:
                            print(
                                json.dumps(
                                    {
                                        "status": "success",
                                        "commit_sha": head,
                                        "session_id": session_id or "unknown",
                                        "inferred": True,
                                    }
                                )
                            )
                    return 0
        elif start_sha is not None and snapshot_path is None:
            result = _subprocess_util.run(
                ["git", "rev-parse", "HEAD"], cwd=project_root
            )
            if result.returncode == 0 and result.stdout.strip() != start_sha:
                head = result.stdout.strip()
                result_full = _subprocess_util.run(
                    [
                        "git",
                        "-C",
                        str(project_root),
                        "status",
                        "--porcelain",
                        "--untracked-files=no",
                    ],
                    check=True,
                )
                if not result_full.stdout.strip():
                    # Apply verify gates before emitting success
                    gate_result = _run_verify_gates(
                        project_root,
                        verify_cmd,
                        module_wide_verify_cmd,
                        git_root=git_root,
                        module_verify_baseline=module_verify_baseline,
                        cwd_override=cwd_override,
                        module_wide_cwd_override=module_wide_cwd_override,
                        batch_verify_baseline=batch_verify_baseline,
                    )
                    if gate_result is not None:
                        # No parsed success JSON on this inference path -- cards_done is always None (the absent-field fallback always applies).
                        gate_result = _reclassify_verify_failure(
                            gate_result,
                            project_root,
                            start_sha,
                            card_ids,
                            session_id,
                            cards_done=None,
                        )
                        if gate_result.get("stuck_type") in ("verify", "transient", "incomplete"):
                            gate_result["commit_sha"] = head
                        print(json.dumps(gate_result))
                        return 0
                    # Go build-tag retiering gate (#642) -- see the explicit-success path's comment for rationale.
                    # This no-JSON inference path must match that same coverage.
                    _retiering_result = _go_build_tag_retiering_stuck(
                        project_root, start_sha, session_id
                    )
                    if _retiering_result is not None:
                        _attach_commit_sha(_retiering_result, project_root)
                        print(json.dumps(_retiering_result))
                        return 0
                    # Completeness gate: incomplete batch demotes to stuck/incomplete.
                    # ignore_verify=True forces the check even when verify passed -- on the no-JSON inference path the implementer never reported success, so a passing verify does not mean the batch is complete.
                    # cards_done=None: no self-report exists on this inference path.
                    _comp = _batch_completeness_stuck(
                        project_root,
                        start_sha,
                        card_ids,
                        session_id,
                        verify_cmd=verify_cmd,
                        ignore_verify=True,
                        cards_done=None,
                    )
                    if _comp is not None:
                        _attach_commit_sha(_comp, project_root)
                        print(json.dumps(_comp))
                        return 0
                    # Guard against start-batch-commit-only case on the no-snapshot inference path (Bug #557).
                    if _is_only_start_batch_commit(project_root, start_sha):
                        print(
                            json.dumps(
                                {
                                    "status": "stuck",
                                    "stuck_type": "logic",
                                    "reason": "inferred success but only batch-start commit since start_sha",
                                    "session_id": session_id or "unknown",
                                    "inferred": True,
                                }
                            )
                        )
                    else:
                        print(
                            json.dumps(
                                {
                                    "status": "success",
                                    "commit_sha": head,
                                    "session_id": session_id or "unknown",
                                    "inferred": True,
                                }
                            )
                        )
                    return 0
    except Exception:
        pass
    # Before emitting the no-JSON fallback, check if the output contains API/infrastructure error markers If so, classify as transient (retriable) rather than logic (ask user)
    api_error_markers = [
        "api error",
        "internal server error",
        "bad gateway",
        "service unavailable",
        "gateway timeout",
        "overloaded",
        "500 internal",
    ]
    output_lower = output.lower()
    for marker in api_error_markers:
        if marker in output_lower:
            # Found an API/infrastructure error marker; classify as transient
            print(
                json.dumps(
                    {
                        "status": "stuck",
                        "stuck_type": "transient",
                        "reason": "agent returned a raw API error before producing a structured report",
                    }
                )
            )
            return 0
    # No API error markers found; emit the default logic sentinel
    violations = _cleanliness.compute_scope_violations(project_root, git_root)
    result = {
        "status": "stuck",
        "stuck_type": "logic",
        "reason": "no structured report",
    }
    if violations:
        result["scope_violations"] = violations
    print(json.dumps(result))
    return 0
