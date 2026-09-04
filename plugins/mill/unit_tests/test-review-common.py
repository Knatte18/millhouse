"""Unit tests for plugins/mill/scripts/_review_common.py."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_UNIT_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_UNIT_TESTS))

import _test_helpers  # noqa: E402
from _test_helpers import _make_task_worktree  # noqa: E402
from _paths import ActiveWorktreeSlugMismatch  # noqa: E402
import _config  # noqa: E402
import _marker  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helper for resolve_path tests
# ---------------------------------------------------------------------------


def _make_worktree_fixture(tmp: str, slug: str) -> tuple[Path, Path]:
    """Create a container-form git fixture at ``<tmp>/container/wts/<slug>``.

    Layout:
        <tmp>/container/wts/<slug>/ ← git repo on task branch ``hanf/<slug>`` <tmp>/container/wiki/
        ← wiki with Home.md and config.yaml

    Returns:
        ``(container_path, worktree_path)``

    The caller must ``os.chdir(worktree_path)`` so that ``Path.cwd()`` resolves inside the fixture
    when calling ``resolve_path``.
    """
    container = Path(tmp) / "container"
    worktree = container / "wts" / slug
    worktree.mkdir(parents=True)
    subprocess.run(
        ["git", "-C", str(worktree), "init"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (worktree / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(worktree), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(worktree), "commit", "-m", "init"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "checkout", "-b", f"hanf/{slug}"],
        check=True,
        capture_output=True,
    )
    (worktree / "mill-config.yaml").write_text(
        'paths:\n  discussion_file: discussion.md\nspawn:\n  branch_prefix: "hanf/"\n',
        encoding="utf-8",
    )
    wiki_root = container / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "config.yaml").write_text(
        "paths:\n  discussion_file: task/discussion.md\n"
        'spawn:\n  branch_prefix: "hanf/"\n',
        encoding="utf-8",
    )
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[[{slug}]] [active]\n\n_body_\n",
        encoding="utf-8",
    )
    return container, worktree


def _make_run_result(
    stdout: str = "", returncode: int = 0, stderr: str = ""
) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    result.stderr = stderr
    return result


from _review_common import (  # noqa: E402
    RE_BATCH,
    RE_SIMPLE,
    DisplayRoots,
    ReviewError,
    ReviewResult,
    _load_root_from_overview,
    _read_for_bulk,
    aggregate_verdict,
    apply_actual_model_override,
    apply_cost_metadata,
    build_deletes_section,
    build_manifest_section,
    build_path_roots_section,
    build_reattached_section,
    build_tool_rule,
    bulk_files,
    bulk_files_with_diff,
    compute_creates_union,
    compute_deletes_union,
    compute_moves_union,
    count_unrecognized_severity_findings,
    detect_resume_round,
    discover_round,
    finalize_scope,
    find_active_slug,
    load_config,
    load_task_title,
    parse_batch_refs,
    parse_blocking_count,
    parse_deletes,
    parse_missing_context,
    parse_moves,
    parse_verdict,
    render_prompt,
    resolve_existing_paths,
    resolve_large_prompt_timeout,
    resolve_path,
    resolve_ref_paths,
    sum_optional,
    write_review_file,
)

import _review_code  # noqa: E402


def main() -> int:
    errors = 0

    # discover_round: nonexistent dir -> 1
    assert discover_round(Path("/tmp/__nx_reviews__"), "discussion", "holistic") == 1
    print("PASS: discover_round nonexistent dir returns 1")

    # RE_SIMPLE matches holistic plan file; RE_BATCH is NOT applied
    holistic_name = "20260418-001200-plan-review-r1.md"
    m = RE_SIMPLE.match(holistic_name)
    assert m is not None
    assert m.group("type") == "plan"
    assert m.group("n") == "1"
    _ = RE_BATCH.match(holistic_name)  # noqa: F841 — documented ambiguity
    print("PASS: RE_SIMPLE matches plan-holistic before RE_BATCH could mis-identify")

    # discover_round cross-type isolation
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r2.md").write_text("x")
        assert discover_round(reviews, "discussion", "holistic") == 1
        print(
            "PASS: discover_round cross-type isolation (plan-batch ignored for discussion)"
        )
        result = discover_round(reviews, "plan", "01-setup")
        assert result == 3, f"expected 3, got {result}"
        print(f"PASS: discover_round for plan with batch file: {result}")
        assert discover_round(reviews, "plan", "holistic") == 1
        print("PASS: discover_round plan holistic unaffected by batch file")
        assert discover_round(reviews, "plan", "other-batch") == 1
        print("PASS: discover_round plan other-batch unaffected by 01-setup file")

    # discover_round per-scope isolation across all five (review_type, scope) axes
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        # discussion holistic: 2 files
        (reviews / "20260418-001200-discussion-review-r1.md").write_text("x")
        (reviews / "20260418-001300-discussion-review-r2.md").write_text("x")
        # plan holistic: 1 file
        (reviews / "20260418-001400-plan-review-r1.md").write_text("x")
        # plan batch-a: 2 files
        (reviews / "20260418-001500-plan-review-batch-a-r1.md").write_text("x")
        (reviews / "20260418-001600-plan-review-batch-a-r2.md").write_text("x")
        # plan batch-b: 1 file
        (reviews / "20260418-001700-plan-review-batch-b-r1.md").write_text("x")
        # code holistic: 1 file
        (reviews / "20260418-001800-code-review-r1.md").write_text("x")
        # code batch-a: 1 file
        (reviews / "20260418-001900-code-review-batch-a-r1.md").write_text("x")

        result = discover_round(reviews, "discussion", "holistic")
        assert result == 3, f"expected 3, got {result}"
        print(f"PASS: discover_round per-scope discussion/holistic: {result}")

        result = discover_round(reviews, "plan", "holistic")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope plan/holistic: {result}")

        result = discover_round(reviews, "plan", "batch-a")
        assert result == 3, f"expected 3, got {result}"
        print(f"PASS: discover_round per-scope plan/batch-a: {result}")

        result = discover_round(reviews, "plan", "batch-b")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope plan/batch-b: {result}")

        result = discover_round(reviews, "plan", "batch-c")
        assert result == 1, f"expected 1, got {result}"
        print(f"PASS: discover_round per-scope plan/batch-c (absent): {result}")

        result = discover_round(reviews, "code", "holistic")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/holistic: {result}")

        result = discover_round(reviews, "code", "batch-a")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/batch-a: {result}")

        result = discover_round(reviews, "code", "batch-b")
        assert result == 1, f"expected 1, got {result}"
        print(
            f"PASS: discover_round per-scope code/batch-b (absent for code): {result}"
        )

    # find_active_slug: not on a task branch -> MarkerError re-raised as ReviewError
    with _test_helpers.safe_temp_dir() as tmpdir:
        wt, wiki = _make_task_worktree(
            Path(tmpdir) / "sub", "some-task", "Some Task", branch_prefix="hanf/"
        )
        subprocess.run(
            ["git", "-C", str(wt), "checkout", "main"], check=True, capture_output=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        try:
            find_active_slug(wt, wiki, cfg)
            print(
                "FAIL: find_active_slug: expected ReviewError on non-task branch",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError:
            print(
                "PASS: find_active_slug non-task branch -> ReviewError (MarkerError translation)"
            )

    # find_active_slug: on task branch -> returns slug
    with _test_helpers.safe_temp_dir() as tmpdir:
        wt, wiki = _make_task_worktree(
            Path(tmpdir), "my-task", "My Task", branch_prefix="hanf/", seed_task=True
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        assert find_active_slug(wt, wiki, cfg) == "my-task"
        print("PASS: find_active_slug: 'my-task'")

    # find_active_slug: daemon-skip when a confirmed on-disk marker agrees with the current branch (on-disk-first fast path).
    try:
        with _test_helpers.safe_temp_dir() as tmpdir:
            wt, wiki = _make_task_worktree(
                Path(tmpdir), "my-task", "My Task", branch_prefix="hanf/"
            )
            mill_dir = wt / "_mill"
            mill_dir.mkdir(parents=True, exist_ok=True)
            (mill_dir / "my-task.active").write_text("", encoding="utf-8")
            cfg = {"spawn": {"branch_prefix": "hanf/"}}

            def _fail_if_called(*args, **kwargs):
                raise AssertionError("daemon should not be called")

            with patch(
                "_review_common._marker.slug_from_branch", side_effect=_fail_if_called
            ):
                result = find_active_slug(wt, wiki, cfg)

            assert result == "my-task", f"Expected 'my-task', got {result!r}"
            print(
                "PASS: find_active_slug daemon-skip — confirmed on-disk marker -> 'my-task'"
            )
    except AssertionError as exc:
        print(
            f"FAIL: find_active_slug daemon-skip confirmed marker: {exc}",
            file=sys.stderr,
        )
        errors += 1
    except Exception as exc:
        print(
            f"FAIL: find_active_slug daemon-skip confirmed marker (unexpected {type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        errors += 1

    # find_active_slug: a stale on-disk marker (branch mismatch) must NOT short-circuit the daemon call -- regression test for the plan-review round 1 correctness fix.
    try:
        with _test_helpers.safe_temp_dir() as tmpdir:
            wt, wiki = _make_task_worktree(
                Path(tmpdir), "actual-slug", "Actual Slug", branch_prefix="hanf/"
            )
            mill_dir = wt / "_mill"
            mill_dir.mkdir(parents=True, exist_ok=True)
            # Leftover marker from an aborted claim, naming a DIFFERENT slug than the branch the worktree is actually on.
            (mill_dir / "stale-slug.active").write_text("", encoding="utf-8")
            cfg = {"spawn": {"branch_prefix": "hanf/"}}

            with patch(
                "_review_common._marker.slug_from_branch",
                return_value="actual-slug",
            ) as mocked:
                result = find_active_slug(wt, wiki, cfg)

            assert (
                mocked.called
            ), "expected slug_from_branch to be called since the stale marker did not confirm"
            assert result == "actual-slug", f"Expected 'actual-slug', got {result!r}"
            print(
                "PASS: find_active_slug stale marker (branch mismatch) -> falls through to branch-derived slug"
            )
    except AssertionError as exc:
        print(
            f"FAIL: find_active_slug stale marker fallthrough: {exc}", file=sys.stderr
        )
        errors += 1
    except Exception as exc:
        print(
            f"FAIL: find_active_slug stale marker fallthrough (unexpected {type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        errors += 1

    # load_task_title: task_title present in Home.md
    with _test_helpers.safe_temp_dir() as tmpdir:
        wt, wiki = _make_task_worktree(
            Path(tmpdir),
            "my-task",
            "My Task Title",
            branch_prefix="hanf/",
            seed_task=True,
        )
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        assert load_task_title(wt, wiki, cfg, "my-task") == "My Task Title"
        print("PASS: load_task_title with task_title in Home.md")

    # load_task_title: non-task branch -> falls back to slug
    with _test_helpers.safe_temp_dir() as tmpdir:
        assert load_task_title(Path(tmpdir), Path(tmpdir), {}, "my-task") == "my-task"
        print("PASS: load_task_title non-task branch -> fallback to slug")

    # load_task_title: daemon-skip when status.md is present and well-formed (on-disk-first fast path).
    try:
        with _test_helpers.safe_temp_dir() as tmpdir:
            git_root = Path(tmpdir)
            status_path = git_root / "status.md"
            status_path.write_text(
                "```yaml\n"
                'task: "My On-Disk Title"\n'
                "```\n"
                "\n"
                "## Timeline\n"
                "\n"
                "```text\n"
                "discussing  '2026-01-01T00:00:00Z'\n"
                "```\n",
                encoding="utf-8",
            )
            cfg = {"paths": {"status_md": "status.md"}}

            def _fail_if_called(*args, **kwargs):
                raise AssertionError("daemon should not be called")

            with patch(
                "_review_common._marker.task_data", side_effect=_fail_if_called
            ):
                result = load_task_title(
                    git_root, git_root / "wiki", cfg, "some-slug"
                )

            assert (
                result == "My On-Disk Title"
            ), f"Expected 'My On-Disk Title', got {result!r}"
            print(
                "PASS: load_task_title daemon-skip — status.md present -> 'My On-Disk Title'"
            )
    except AssertionError as exc:
        print(f"FAIL: load_task_title daemon-skip status.md: {exc}", file=sys.stderr)
        errors += 1
    except Exception as exc:
        print(
            f"FAIL: load_task_title daemon-skip status.md (unexpected {type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        errors += 1

    # resolve_path: discussion.md -> worktree root
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            p = resolve_path("discussion.md", slug)
        finally:
            os.chdir(original_cwd)
        expected = worktree / "discussion.md"
        assert p == expected, f"Expected {expected}, got {p}"
        print("PASS: resolve_path('discussion.md', slug) -> worktree/discussion.md")

    # resolve_path: skip_slug_validation=True (its own resolve_active_hub call) avoids the daemon-backed _marker.slug_from_branch round-trip -- resolve_path is always called with an already-resolved slug, so it never needs slug_from_branch's re-validation.
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            with patch(
                "_marker.slug_from_branch",
                side_effect=AssertionError("daemon should not be called"),
            ):
                p = resolve_path("discussion.md", slug)
        finally:
            os.chdir(original_cwd)
        expected = worktree / "discussion.md"
        assert p == expected, f"Expected {expected}, got {p}"
        print(
            "PASS: resolve_path resolves without calling the daemon-backed "
            "_marker.slug_from_branch (skip_slug_validation=True)"
        )

    # resolve_path: plan/ and reviews/ templates
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            p_plan = resolve_path("plan/", slug)
            p_reviews = resolve_path("reviews/", slug)
            p_nested = resolve_path("reviews/r1/holistic.md", slug)
        finally:
            os.chdir(original_cwd)
        assert p_plan == worktree / "plan/", f"plan/ wrong: {p_plan}"
        assert p_reviews == worktree / "reviews/", f"reviews/ wrong: {p_reviews}"
        assert p_nested == worktree / "reviews/r1/holistic.md", (
            f"nested wrong: {p_nested}"
        )
        print(
            "PASS: resolve_path covers plan/, reviews/, nested reviews/r1/holistic.md"
        )

    # resolve_path: stale <SLUG> in template is substituted (not a literal segment)
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            p = resolve_path("active/<SLUG>/discussion.md", slug)
        finally:
            os.chdir(original_cwd)
        # <SLUG> is substituted, so no literal segment named "<SLUG>" in result
        assert "<SLUG>" not in str(p), f"<SLUG> should not appear literally in {p}"
        assert slug in str(p), f"slug {slug!r} should appear in {p}"
        print(
            "PASS: resolve_path stale <SLUG> template substituted (no literal segment)"
        )

    # resolve_path: slug-mismatch raises ActiveWorktreeSlugMismatch
    with _test_helpers.safe_temp_dir() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        # Create a directory named "wrong-slug" but checked out on branch "hanf/my-task" (directory slug ≠ branch-derived slug -> mismatch).
        wrong_slug = "wrong-slug"
        wrong_dir = container / "wts" / wrong_slug
        wrong_dir.mkdir(parents=True)
        subprocess.run(
            ["git", "-C", str(wrong_dir), "init"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "config", "user.email", "test@test.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "config", "user.name", "Test"],
            check=True,
            capture_output=True,
        )
        (wrong_dir / ".keep").write_text("", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(wrong_dir), "add", "."], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "checkout", "-b", "hanf/my-task"],
            check=True,
            capture_output=True,
        )
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            try:
                resolve_path("discussion.md", wrong_slug)
                print(
                    "FAIL: resolve_path: expected ActiveWorktreeSlugMismatch for wrong slug",
                    file=sys.stderr,
                )
                errors += 1
            except ActiveWorktreeSlugMismatch:
                print(
                    "PASS: resolve_path raises ActiveWorktreeSlugMismatch on branch mismatch"
                )
        finally:
            os.chdir(original_cwd)

    # resolve_path: M2 in-place mode (hub_rel=".")
    with _test_helpers.safe_temp_dir() as tmp:
        tmp_path = Path(tmp)
        git_root = tmp_path / "git_root"
        # Real git repo (not a bare mkdir'd dir) -- resolve_path's internal resolve_active_hub call now passes skip_slug_validation=True, whose fast path calls _pygit2_util.current_branch(git_root) against the real filesystem instead of the daemon-backed _marker.slug_from_branch.
        repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
        hub = git_root
        slug = "my-inplace-task"
        # cfg has no spawn.branch_prefix (neither the wiki config.yaml below nor the hub's config.local.yaml sets one), so the cheap prefix-strip check compares the raw branch name against slug with an empty prefix.
        _test_helpers.checkout_new_branch(repo, slug)

        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir()
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: task/discussion.md\n",
            encoding="utf-8",
        )

        hub_mill_dir = hub / ".millhouse"
        hub_mill_dir.mkdir(parents=True)
        (hub_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: .\n", encoding="utf-8"
        )

        worktrees_dir = tmp_path / "wts"
        worktrees_dir.mkdir()

        with (
            patch(
                "_marker.slug_from_branch",
                side_effect=AssertionError("daemon should not be called"),
            ),
            patch("_paths.resolve_git_root", return_value=git_root),
            patch("_paths.resolve_wiki_path", return_value=wiki_root),
            patch("_paths.resolve_hub_path", return_value=hub),
            patch("_paths.resolve_main_worktree_root", return_value=git_root),
            patch("_inplace.resolve_main_worktree_root", return_value=git_root),
        ):
            p = resolve_path("task/discussion.md", slug)

        expected = git_root / "task" / "discussion.md"
        assert p == expected, f"M2 in-place (hub_rel='.'): expected {expected}, got {p}"
        print(
            "PASS: resolve_path M2 in-place (hub_rel='.') -> git_root/task/discussion.md"
        )

    # resolve_path: M2+sub in-place mode (hub_rel="src/Models")
    with _test_helpers.safe_temp_dir() as tmp:
        tmp_path = Path(tmp)
        git_root = tmp_path / "git_root"
        # Real git repo -- same reasoning as the M2 in-place case above: the branch-derived slug now comes from a real _pygit2_util.current_branch call, not the (patched-out) daemon-backed _marker.slug_from_branch.
        repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
        hub = git_root / "src" / "Models"
        slug = "my-subdir-inplace-task"
        _test_helpers.checkout_new_branch(repo, slug)

        wiki_root = tmp_path / "wiki"
        wiki_root.mkdir()
        (wiki_root / "config.yaml").write_text(
            "paths:\n  discussion_file: task/discussion.md\n",
            encoding="utf-8",
        )

        hub_mill_dir = hub / ".millhouse"
        hub_mill_dir.mkdir(parents=True)
        (hub_mill_dir / "config.local.yaml").write_text(
            "hub_relative_path: src/Models\n", encoding="utf-8"
        )

        worktrees_dir = tmp_path / "wts"
        worktrees_dir.mkdir()

        with (
            patch(
                "_marker.slug_from_branch",
                side_effect=AssertionError("daemon should not be called"),
            ),
            patch("_paths.resolve_git_root", return_value=git_root),
            patch("_paths.resolve_wiki_path", return_value=wiki_root),
            patch("_paths.resolve_hub_path", return_value=hub),
            patch("_paths.resolve_main_worktree_root", return_value=git_root),
            patch("_inplace.resolve_main_worktree_root", return_value=git_root),
        ):
            p = resolve_path("task/discussion.md", slug)

        expected = git_root / "src" / "Models" / "task" / "discussion.md"
        assert p == expected, f"M2+sub in-place: expected {expected}, got {p}"
        print(
            "PASS: resolve_path M2+sub in-place (hub_rel='src/Models') -> git_root/src/Models/task/discussion.md"
        )

    # parse_verdict: APPROVE
    raw = "# Review: My Task\n\n```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict APPROVE")

    # parse_verdict: REQUEST_CHANGES
    raw = "# Review: My Task\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"
    assert parse_verdict(raw) == "REQUEST_CHANGES"
    print("PASS: parse_verdict REQUEST_CHANGES")

    # parse_verdict: NEED_CONTEXT
    raw = "# Review: My Task\n\n```yaml\nverdict: NEED_CONTEXT\n```\n"
    assert parse_verdict(raw) == "NEED_CONTEXT"
    print("PASS: parse_verdict NEED_CONTEXT")

    # parse_verdict: yaml block not at top
    raw = "# Review: My Task\n\nPreamble.\n\n```yaml\nverdict: APPROVE\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict yaml block not at top")

    # parse_verdict: no yaml block -> ReviewError
    try:
        parse_verdict("No yaml block here.")
        print(
            "FAIL: parse_verdict: expected ReviewError for no yaml block",
            file=sys.stderr,
        )
        errors += 1
    except ReviewError:
        print("PASS: parse_verdict no yaml block -> ReviewError")

    # parse_verdict: unclosed yaml block -> ReviewError
    try:
        parse_verdict("# Review: X\n\n```yaml\nverdict: APPROVE\n")
        print(
            "FAIL: parse_verdict: expected ReviewError for unclosed yaml block",
            file=sys.stderr,
        )
        errors += 1
    except ReviewError as e:
        assert "not closed" in str(e)
        print("PASS: parse_verdict unclosed yaml block -> ReviewError")

    # parse_verdict: invalid verdict value -> ReviewError
    try:
        parse_verdict("# Review: X\n\n```yaml\nverdict: MAYBE\n```\n")
        print(
            "FAIL: parse_verdict: expected ReviewError for invalid verdict",
            file=sys.stderr,
        )
        errors += 1
    except ReviewError as e:
        assert "MAYBE" in str(e)
        print("PASS: parse_verdict invalid verdict -> ReviewError")

    # parse_verdict: multiple yaml blocks; first wins
    raw = "# Header\n\n```yaml\nverdict: APPROVE\n```\n\nMore text\n\n```yaml\nverdict: REQUEST_CHANGES\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict multiple yaml blocks (first wins)")

    # parse_verdict: trailing prose after yaml
    raw = "```yaml\nverdict: APPROVE\n```\n\nThanks, this looks great.\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict trailing prose after yaml")

    # parse_verdict: yaml fence with trailing whitespace
    raw = "```yaml   \nverdict: APPROVE\n```   \n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict yaml fence with trailing whitespace")

    # parse_verdict: prose preamble + yaml block
    raw = "Review written to file.md. Verdict is APPROVE.\n\n# Review: X\n\n```yaml\nverdict: APPROVE\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict prose preamble + yaml block")

    # parse_verdict: verdict with extra whitespace
    raw = "```yaml\n  verdict:   APPROVE   \n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict verdict with extra whitespace")

    # write_review_file: creates file
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir / "reviews"
        path = write_review_file(
            reviews, "discussion", 1, "---\nverdict: APPROVE\n---\n"
        )
        assert path.exists() and "discussion-review-r1" in path.name
        print(f"PASS: write_review_file discussion: {path.name}")

        path2 = write_review_file(reviews, "plan", 1, "content", scope="01-setup")
        assert "plan-review-01-setup-r1" in path2.name
        print(f"PASS: write_review_file plan-batch: {path2.name}")

        path3 = write_review_file(reviews, "plan", 1, "content", scope="holistic")
        assert "plan-review-r1" in path3.name and "holistic" not in path3.name
        print(f"PASS: write_review_file plan-holistic: {path3.name}")

        path4 = write_review_file(reviews, "code", 1, "content", scope="foundation")
        assert "code-review-foundation-r1" in path4.name
        print(f"PASS: write_review_file code-batch: {path4.name}")

    # apply_actual_model_override: rewrites an existing well-formed reviewer_model line
    raw = "```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\n```\n"
    out = apply_actual_model_override(raw, "sonnet")
    assert out == "```yaml\nverdict: APPROVE\nreviewer_model: sonnet\n```\n"
    print("PASS: apply_actual_model_override rewrites existing reviewer_model line")

    # apply_actual_model_override: injects a reviewer_model line right after the opening ```yaml fence of the block carrying the verdict, when the input text has no reviewer_model line at all
    raw = "```yaml\nverdict: APPROVE\nreviewed_file: x\n```\n"
    out = apply_actual_model_override(raw, "haiku")
    assert out == "```yaml\nreviewer_model: haiku\nverdict: APPROVE\nreviewed_file: x\n```\n"
    print("PASS: apply_actual_model_override injects reviewer_model line after opening fence")

    # apply_actual_model_override: a malformed reviewer_model line (no value) is treated as not-found and does not swallow the rest of the block
    raw = "```yaml\nverdict: APPROVE\nreviewer_model:\n```\n"
    out = apply_actual_model_override(raw, "opus")
    assert out == "```yaml\nreviewer_model: opus\nverdict: APPROVE\nreviewer_model:\n```\n"
    print("PASS: apply_actual_model_override treats malformed reviewer_model line as not-found")

    # apply_actual_model_override: identity when actual_model is None
    raw = "```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\n```\n"
    assert apply_actual_model_override(raw, None) == raw
    print("PASS: apply_actual_model_override identity when actual_model is None")

    # apply_actual_model_override: leaves a reviewer_self_id: line untouched when rewriting reviewer_model: -- only the reviewer_model: line changes.
    raw = (
        "```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\n"
        "reviewer_self_id: claude-sonnet-4-6 (self-reported)\n```\n"
    )
    out = apply_actual_model_override(raw, "sonnet")
    assert out == (
        "```yaml\nverdict: APPROVE\nreviewer_model: sonnet\n"
        "reviewer_self_id: claude-sonnet-4-6 (self-reported)\n```\n"
    )
    print("PASS: apply_actual_model_override leaves reviewer_self_id line untouched")

    # apply_cost_metadata: all-None returns the input unchanged (identity, not merely equal)
    raw = "```yaml\nverdict: APPROVE\n```\n"
    out = apply_cost_metadata(raw)
    assert out is raw
    print("PASS: apply_cost_metadata all-None returns input unchanged (identity)")

    # apply_cost_metadata: injection into a header block with no such fields yields the three
    # lines in the order duration_s, tool_calls, cost_usd directly after the opening fence
    raw = "```yaml\nverdict: APPROVE\n```\n"
    out = apply_cost_metadata(raw, duration_s=12.3, tool_calls=37, cost_usd=0.4212)
    assert out == (
        "```yaml\nduration_s: 12.3\ntool_calls: 37\ncost_usd: 0.4212\n"
        "verdict: APPROVE\n```\n"
    )
    print("PASS: apply_cost_metadata injects duration_s/tool_calls/cost_usd in file order")

    # apply_cost_metadata: a header that already carries the three fields has them rewritten in
    # place with no duplication
    raw = (
        "```yaml\nduration_s: 1.0\ntool_calls: 1\ncost_usd: 0.0001\n"
        "verdict: APPROVE\n```\n"
    )
    out = apply_cost_metadata(raw, duration_s=12.3, tool_calls=37, cost_usd=0.4212)
    assert out == (
        "```yaml\nduration_s: 12.3\ntool_calls: 37\ncost_usd: 0.4212\n"
        "verdict: APPROVE\n```\n"
    )
    print("PASS: apply_cost_metadata rewrites existing fields in place with no duplication")

    # apply_cost_metadata: a partial set (only duration_s) injects only that field
    raw = "```yaml\nverdict: APPROVE\n```\n"
    out = apply_cost_metadata(raw, duration_s=12.3)
    assert out == "```yaml\nduration_s: 12.3\nverdict: APPROVE\n```\n"
    print("PASS: apply_cost_metadata partial set injects only duration_s")

    # apply_cost_metadata: text with no ```yaml``` fence at all is returned unchanged
    raw = "no fence here at all\n"
    out = apply_cost_metadata(raw, duration_s=12.3, tool_calls=37, cost_usd=0.4212)
    assert out == raw
    print("PASS: apply_cost_metadata with no yaml fence returns text unchanged")

    # apply_cost_metadata: a first yaml fence without a verdict: line is skipped in favor of a
    # later block that has one, matching apply_actual_model_override's anchor rule
    raw = (
        "```yaml\nreviewed_file: x\n```\n"
        "some prose\n"
        "```yaml\nverdict: APPROVE\n```\n"
    )
    out = apply_cost_metadata(raw, duration_s=12.3)
    assert out == (
        "```yaml\nreviewed_file: x\n```\n"
        "some prose\n"
        "```yaml\nduration_s: 12.3\nverdict: APPROVE\n```\n"
    )
    print("PASS: apply_cost_metadata anchors on the later block carrying verdict:")

    # sum_optional: both None -> None
    assert sum_optional(None, None) is None
    print("PASS: sum_optional both None returns None")

    # sum_optional: one None -> the other operand unchanged (not coerced to 0)
    assert sum_optional(None, 5) == 5
    assert sum_optional(3.5, None) == 3.5
    print("PASS: sum_optional with one None returns the other operand unchanged")

    # sum_optional: both set -> their sum
    assert sum_optional(2, 3) == 5
    assert sum_optional(1.5, 2.5) == 4.0
    print("PASS: sum_optional with both set returns their sum")

    # finalize_scope: duration_s/tool_calls/cost_usd land both in the returned dict and in the
    # written file's yaml header
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir / "reviews"
        raw = "```yaml\nverdict: APPROVE\n```\n"
        result = finalize_scope(
            reviews,
            "code",
            1,
            raw,
            scope="01-setup",
            duration_s=12.3,
            tool_calls=37,
            cost_usd=0.4212,
        )
        assert result["duration_s"] == 12.3
        assert result["tool_calls"] == 37
        assert result["cost_usd"] == 0.4212
        written = Path(result["file"]).read_text(encoding="utf-8")
        assert "duration_s: 12.3\n" in written
        assert "tool_calls: 37\n" in written
        assert "cost_usd: 0.4212\n" in written
        print("PASS: finalize_scope threads cost metadata into both dict and written file")

        # Omitting all three leaves the written file byte-identical to today's output.
        unmodified = finalize_scope(reviews, "code", 1, raw, scope="02-setup")
        assert unmodified["duration_s"] is None
        assert unmodified["tool_calls"] is None
        assert unmodified["cost_usd"] is None
        unmodified_content = Path(unmodified["file"]).read_text(encoding="utf-8")
        assert unmodified_content == raw
        print("PASS: finalize_scope without cost metadata reproduces unmodified output")

    # write_review_file: preserves a reviewer_self_id: line verbatim
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir / "reviews"
        raw = (
            "```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\n"
            "reviewer_self_id: claude-opus-4-1\n```\n"
        )
        path = write_review_file(reviews, "discussion", 2, raw)
        written = path.read_text(encoding="utf-8")
        assert "reviewer_self_id: claude-opus-4-1" in written
        print("PASS: write_review_file preserves reviewer_self_id line verbatim")

    # finalize_scope: actual_model override is reflected in the written file
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir / "reviews"
        raw = "```yaml\nverdict: APPROVE\nreviewer_model: sonnetmax\n```\n"

        overridden = finalize_scope(
            reviews, "code", 1, raw, scope="01-setup", actual_model="sonnet"
        )
        overridden_content = Path(overridden["file"]).read_text(encoding="utf-8")
        assert "reviewer_model: sonnet\n" in overridden_content
        assert "sonnetmax" not in overridden_content
        print("PASS: finalize_scope applies actual_model override to written file")

        unmodified = finalize_scope(reviews, "code", 1, raw, scope="01-setup")
        unmodified_content = Path(unmodified["file"]).read_text(encoding="utf-8")
        assert unmodified_content == raw
        print("PASS: finalize_scope without actual_model reproduces unmodified behavior")

    # bulk_files: nonexistent skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        existing = Path(tmpdir) / "a.md"
        existing.write_text("hello")
        result = bulk_files([existing, Path("/nonexistent/x.md")])
        assert "hello" in result and "FILE:" in result
        print("PASS: bulk_files skips missing files")

    # bulk_files: END FILE delimiter present
    with _test_helpers.safe_temp_dir() as tmpdir:
        p1 = Path(tmpdir) / "a.py"
        p2 = Path(tmpdir) / "b.py"
        p1.write_text("content-a", encoding="utf-8")
        p2.write_text("content-b", encoding="utf-8")
        result = bulk_files([p1, p2])
        assert f"--- END FILE: {p1} ---" in result, (
            f"END FILE missing for p1: {result!r}"
        )
        assert f"--- END FILE: {p2} ---" in result, (
            f"END FILE missing for p2: {result!r}"
        )
        assert result.index(f"--- FILE: {p1}") < result.index(f"--- END FILE: {p1}"), (
            "opener must precede closer for p1"
        )
        print("PASS: bulk_files END FILE delimiters present and ordered")

    # bulk_files_with_diff: END FILE delimiter present
    with _test_helpers.safe_temp_dir() as tmpdir:
        p1 = Path(tmpdir) / "a.py"
        p2 = Path(tmpdir) / "b.py"
        p1.write_text("content-a", encoding="utf-8")
        p2.write_text("content-b", encoding="utf-8")
        result = bulk_files_with_diff([p1, p2], None, Path(tmpdir), 0.25)
        assert f"--- END FILE: {p1} ---" in result, (
            f"END FILE missing for p1: {result!r}"
        )
        assert f"--- END FILE: {p2} ---" in result, (
            f"END FILE missing for p2: {result!r}"
        )
        assert result.index(f"--- FILE: {p1}") < result.index(f"--- END FILE: {p1}"), (
            "opener must precede closer for p1"
        )
        print(
            "PASS: bulk_files_with_diff END FILE delimiters present and ordered (start_sha=None)"
        )

    # render_prompt: missing template -> FileNotFoundError
    try:
        render_prompt("nonexistent-template-xyz")
        print(
            "FAIL: render_prompt: expected FileNotFoundError for missing template",
            file=sys.stderr,
        )
        errors += 1
    except FileNotFoundError:
        print("PASS: render_prompt missing template -> FileNotFoundError")

    # render_prompt: prior_nonblocking token with digest content
    try:
        tool_rule = build_tool_rule("bulk")
        prompt = render_prompt(
            "review-code-batch",
            task_title="Test Task",
            tool_rule=tool_rule,
            artefact_section="test section",
            constraints="test constraints",
            round=2,
            reviewer_model="test-model",
            batch_name="test-batch",
            prior_nonblocking="- Item 1: description\n- Item 2: description",
        )
        assert "Item 1: description" in prompt, (
            "prior_nonblocking content not in rendered prompt"
        )
        assert "- Item 2: description" in prompt, (
            "prior_nonblocking content not in rendered prompt"
        )
        assert "Do NOT escalate" in prompt, (
            "escalation-justification rule not in prompt"
        )
        assert "Do NOT read `reviews/`" in prompt, (
            "tool rule read-ban not preserved in prompt"
        )
        print("PASS: render_prompt with prior_nonblocking digest renders correctly")
    except KeyError as e:
        print(
            f"FAIL: render_prompt with prior_nonblocking raised KeyError: {e}",
            file=sys.stderr,
        )
        errors += 1
    except AssertionError as e:
        print(f"FAIL: render_prompt prior_nonblocking check: {e}", file=sys.stderr)
        errors += 1

    # render_prompt: prior_nonblocking defaults to (none) on round 1
    try:
        tool_rule = build_tool_rule("bulk")
        prompt_r1 = render_prompt(
            "review-code-batch",
            task_title="Test Task",
            tool_rule=tool_rule,
            artefact_section="test section",
            constraints="test constraints",
            round=1,
            reviewer_model="test-model",
            batch_name="test-batch",
            prior_nonblocking="(none)",
        )
        assert "(none)" in prompt_r1, (
            "prior_nonblocking (none) should appear in round 1 prompt"
        )
        assert "Do NOT read `reviews/`" in prompt_r1, (
            "tool rule read-ban not preserved in round 1 prompt"
        )
        print(
            "PASS: render_prompt round 1 with prior_nonblocking=(none) renders without KeyError"
        )
    except KeyError as e:
        print(f"FAIL: render_prompt round 1 raised KeyError: {e}", file=sys.stderr)
        errors += 1
    except AssertionError as e:
        print(f"FAIL: render_prompt round 1 check: {e}", file=sys.stderr)
        errors += 1

    # aggregate_verdict
    assert aggregate_verdict(["APPROVE", "APPROVE"]) == "APPROVE"
    assert aggregate_verdict(["APPROVE", "REQUEST_CHANGES"]) == "REQUEST_CHANGES"
    assert aggregate_verdict(["APPROVE", "ERROR"]) == "REQUEST_CHANGES"
    assert aggregate_verdict(["APPROVE", "NEED_CONTEXT"]) == "NEED_CONTEXT"
    assert aggregate_verdict(["NEED_CONTEXT", "REQUEST_CHANGES"]) == "NEED_CONTEXT"
    assert aggregate_verdict([]) == "APPROVE"
    print("PASS: aggregate_verdict (incl. NEED_CONTEXT precedence)")

    # build_tool_rule modes
    assert "Do NOT request tool calls" in build_tool_rule("bulk")
    assert "MAY use Read, Grep, and Glob" in build_tool_rule("tool-use")
    print("PASS: build_tool_rule bulk + tool-use")

    try:
        build_tool_rule("weird")
        print(
            "FAIL: build_tool_rule: expected ValueError for unknown mode",
            file=sys.stderr,
        )
        errors += 1
    except ValueError as e:
        assert "weird" in str(e)
        print("PASS: build_tool_rule unknown mode -> ValueError")

    # load_config: valid YAML + local override
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        wiki = tmpdir_path / "wiki"
        wiki.mkdir()
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        _write_mill_config_yaml = tmpdir_path / "mill-config.yaml"
        _write_mill_config_yaml.write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 3\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        cfg = load_config(tmpdir_path, mill)
        assert cfg["roles"]["plan-review"]["batch"]["rounds"] == 3
        print("PASS: load_config loads repo config")

        (mill / "config.local.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 1\n",
            encoding="utf-8",
        )
        cfg = load_config(tmpdir_path, mill)
        assert cfg["roles"]["plan-review"]["batch"]["rounds"] == 1
        assert cfg["roles"]["plan-review"]["batch"]["reviewer"] == "sonnetmax"
        print("PASS: load_config local override wins; other keys preserved")

    # load_config: missing config -> ReviewError
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        try:
            with patch(
                "_review_common.resolve_plugin_template_path",
                return_value=Path("/nonexistent/mill-config.yaml"),
            ):
                load_config(tmpdir_path, mill)
            print(
                "FAIL: load_config: expected ReviewError for missing config",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "Missing config" in str(e)
            print("PASS: load_config missing config -> ReviewError")

    # load_config: stale review: overlay in config.local.yaml -> stderr warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        import io as _io
        import contextlib as _cl

        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        (tmpdir_path / "mill-config.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 3\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        (mill / "config.local.yaml").write_text(
            "review:\n  code:\n    rounds: 1\n",
            encoding="utf-8",
        )
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            cfg = load_config(tmpdir_path, mill)
        _warning = _err_buf.getvalue()
        assert _warning, "expected a stderr warning, got empty string"
        assert "review" in _warning, f"warning should mention 'review': {_warning!r}"
        local_path_str = str(mill / "config.local.yaml")
        assert local_path_str in _warning, (
            f"warning should mention overlay path: {_warning!r}"
        )
        print(
            "PASS: load_config stale review: overlay emits stderr warning with overlay path"
        )

    # load_config bare roles: key does not crash
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        (tmpdir_path / "mill-config.yaml").write_text(
            "roles:\n",
            encoding="utf-8",
        )
        # Create a test template with a full roles: dict
        template_dir = tmpdir_path / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)
        template_path = template_dir / "mill-config.yaml"
        template_path.write_text(
            "roles:\n  plan-review:\n    batch:\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        with patch(
            "_review_common.resolve_plugin_template_path", return_value=template_path
        ):
            cfg = load_config(tmpdir_path, mill)
        assert isinstance(cfg.get("roles"), dict), (
            f"Expected roles to be dict; got {cfg.get('roles')!r}"
        )
        print("PASS: load_config bare roles: does not crash; template roles: preserved")

    # load_config hub_relative_path does not emit unknown-key warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()
        (tmpdir_path / "mill-config.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        (mill / "config.local.yaml").write_text(
            "hub_relative_path: subdir\n",
            encoding="utf-8",
        )
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            with patch(
                "_review_common.resolve_plugin_template_path",
                return_value=tmpdir_path / "mill-config.yaml",
            ):
                cfg = load_config(tmpdir_path, mill)
        _warning = _err_buf.getvalue()
        assert "hub_relative_path" not in _warning, (
            f"hub_relative_path should not appear in warning; got {_warning!r}"
        )
        print(
            "PASS: load_config hub_relative_path in config.local.yaml does not emit unknown-key warning"
        )

    # load_config delegation inherits _config.load_config's worktree-template cache-lag augmentation (regression test for #676/#670: the old duplicate load_config had no augmentation logic at all, so this exact scenario would have printed the unknown-key warning under the pre-refactor code).
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        mill = tmpdir_path / ".millhouse"
        mill.mkdir()

        # Fake installed-cache template missing pipeline.max_cards_per_batch.
        cache_template_dir = tmpdir_path / "cache_templates"
        cache_template_dir.mkdir(parents=True, exist_ok=True)
        cache_template_path = cache_template_dir / "mill-config.yaml"
        cache_template_path.write_text(
            "roles:\n  plan-review:\n    batch:\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )

        # Worktree-local source-tree template that already carries the new key.
        wt_template_dir = tmpdir_path / "plugins" / "mill" / "templates"
        wt_template_dir.mkdir(parents=True, exist_ok=True)
        (wt_template_dir / "mill-config.yaml").write_text(
            "pipeline:\n  max_cards_per_batch: 10\n",
            encoding="utf-8",
        )

        # Repo-layer config also sets the new key.
        (tmpdir_path / "mill-config.yaml").write_text(
            "pipeline:\n  max_cards_per_batch: 10\n",
            encoding="utf-8",
        )

        _err_buf = _io.StringIO()
        with (
            _cl.redirect_stderr(_err_buf),
            patch.object(
                _config, "resolve_plugin_template_path",
                return_value=cache_template_path,
            ),
            patch(
                "_review_common.resolve_plugin_template_path",
                return_value=cache_template_path,
            ),
        ):
            cfg = load_config(tmpdir_path, mill)
        _warning = _err_buf.getvalue()
        assert "unknown key: pipeline.max_cards_per_batch" not in _warning, (
            f"unexpected unknown-key warning; stderr: {_warning!r}"
        )
        assert cfg["pipeline"]["max_cards_per_batch"] == 10
        print(
            "PASS: load_config delegation inherits _config.load_config's "
            "worktree-template cache-lag augmentation"
        )

    # parse_batch_refs: multi-line bullet form returns all sub-bullet paths
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "### Card 1\n\n"
            "- **Context:**\n"
            "  - `path/a`\n"
            "  - `path/b`\n"
            "- **Creates:** none\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == ["path/a", "path/b"], f"Got {refs}"
        print("PASS: parse_batch_refs multi-line bullet form returns both paths")

    # parse_batch_refs: sub-bullet with a leading real path and a parenthetical carrying further backtick-quoted prose keeps only the leading token (#580).
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "### Card 1\n\n"
            "- **Context:**\n"
            "  - `cmd/lyx/main_test.go` (batch 3 routed `boardcli`'s dir through `paths.Resolve`)\n"
            "- **Creates:** none\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == ["cmd/lyx/main_test.go"], f"Got {refs}"
        print(
            "PASS: parse_batch_refs sub-bullet keeps only leading token, drops prose backticks"
        )

    # parse_batch_refs: 'none' token is filtered out
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Creates:** none\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'none' token filtered")

    # parse_batch_refs: single-line form returns both paths
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Context:** `x`, `y`\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == ["x", "y"], f"Got {refs}"
        print("PASS: parse_batch_refs single-line form returns both paths")

    # parse_batch_refs: mixed single-line and multi-line fields
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Context:** `a`\n- **Edits:**\n  - `b`\n  - `c`\n- **Creates:** none\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == ["a", "b", "c"], f"Got {refs}"
        print("PASS: parse_batch_refs mixed single-line and multi-line fields")

    # parse_batch_refs: case-variant none tokens filtered (Block A: None)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Creates:** None\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'None' (capital N) filtered")

    # parse_batch_refs: case-variant none tokens filtered (Block B: NONE)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Edits:** NONE\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'NONE' (all caps) filtered")

    # parse_batch_refs: case-variant none in sub-bullet form (Block C: `None`)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Creates:**\n  - `None`\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs sub-bullet `None` filtered")

    # parse_batch_refs: mixed token + lowercase none inline (Block D: regression pin)
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Context:** `a`, none\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        # backtick tokens win; "none" is comma-fallback and filtered
        assert refs == ["a"], f"Got {refs}"
        print("PASS: parse_batch_refs backtick tokens win; trailing 'none' filtered")

    # parse_batch_refs: Deletes: field extracted alongside Context/Edits/Creates
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Context:** `src/a.py`\n"
            "- **Edits:** `src/b.py`\n"
            "- **Creates:** `src/c.py`\n"
            "- **Deletes:** `src/d.py`\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert "src/a.py" in refs, f"Context token missing: {refs}"
        assert "src/b.py" in refs, f"Edits token missing: {refs}"
        assert "src/c.py" in refs, f"Creates token missing: {refs}"
        assert "src/d.py" in refs, f"Deletes token missing: {refs}"
        print(
            "PASS: parse_batch_refs includes Deletes tokens alongside Context/Edits/Creates"
        )

    # resolve_ref_paths: hit on disk
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths([str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths hit on disk returns resolved path")

    # resolve_ref_paths: suppression via creates_union (no error, empty return)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"],
            tmp_dir,
            root=None,
            creates_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths creates_union suppresses missing path")

    # resolve_ref_paths: hard-fail on unresolved path
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["nonexistent.py"], tmp_dir, root=None)
            print(
                "FAIL: resolve_ref_paths: expected ReviewError for missing path",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            assert "nonexistent.py" in str(e), f"Path not in message: {e}"
            print("PASS: resolve_ref_paths hard-fails with 'referenced path not found'")

    # resolve_ref_paths: wiki path resolved
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        (tmp_wiki / "active" / "x").mkdir(parents=True)
        (tmp_wiki / "active" / "x" / "discussion.md").write_text("d")
        result = resolve_ref_paths(
            ["wiki/active/x/discussion.md"],
            tmp_project,
            root=None,
            wiki_root=tmp_wiki,
        )
        assert result == [tmp_wiki / "active" / "x" / "discussion.md"], f"Got {result}"
        print("PASS: resolve_ref_paths wiki/ prefix resolved via wiki_root")

    # resolve_ref_paths: wiki path missing wiki_root raises ReviewError
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["wiki/foo"], tmp_dir, root=None)
            print(
                "FAIL: resolve_ref_paths: expected ReviewError for wiki/ without wiki_root",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "no wiki_root provided" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths wiki/ without wiki_root raises ReviewError")

    # resolve_ref_paths: wiki path exists in wiki_root but not in creates_union -> hard-fail
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        tmp_wiki.mkdir()
        try:
            resolve_ref_paths(
                ["wiki/active/missing.md"],
                tmp_project,
                root=None,
                wiki_root=tmp_wiki,
            )
            print(
                "FAIL: resolve_ref_paths: expected ReviewError for missing wiki path",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths wiki path missing on disk hard-fails")

    # resolve_ref_paths: caller_label appears in error message
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["missing.py"],
                tmp_dir,
                root=None,
                caller_label="_review_plan",
            )
            print("FAIL: resolve_ref_paths: expected ReviewError", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert str(e).startswith("[_review_plan]"), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths caller_label appears in error message")

    # resolve_ref_paths: defensive None filter (Python None in list)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths([None, str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths defensive None skipped silently")

    # resolve_ref_paths: defensive lowercase 'none' filter
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(["none", str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths 'none' string skipped silently")

    # resolve_ref_paths: defensive 'None' (capital N) filter
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(["None", str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths 'None' string skipped silently")

    # resolve_ref_paths: missing + in deletes_union -> silent suppress
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"],
            tmp_dir,
            root=None,
            deletes_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths deletes_union suppresses missing path")

    # resolve_ref_paths: missing + in both unions -> silent suppress
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"],
            tmp_dir,
            root=None,
            creates_union={"nonexistent.py"},
            deletes_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths missing + in both unions -> silent suppress")

    # resolve_ref_paths: on-disk + in deletes_union -> resolved normally, included
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(
            ["real.py"],
            tmp_dir,
            root=None,
            deletes_union={"real.py"},
        )
        assert result == [real_file], f"Got {result}"
        print(
            "PASS: resolve_ref_paths on-disk + in deletes_union -> resolved and included"
        )

    # resolve_ref_paths: missing + in neither union -> ReviewError (existing behaviour preserved)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["nonexistent.py"],
                tmp_dir,
                root=None,
                deletes_union={"other.py"},
            )
            print(
                "FAIL: resolve_ref_paths: expected ReviewError for missing path not in deletes_union",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print(
                "PASS: resolve_ref_paths missing + not in deletes_union -> ReviewError"
            )

    # resolve_ref_paths: caller_label in error when deletes_union present but path missing
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["missing.py"],
                tmp_dir,
                root=None,
                deletes_union={"other.py"},
                caller_label="test_caller",
            )
            print("FAIL: resolve_ref_paths: expected ReviewError", file=sys.stderr)
            errors += 1
        except ReviewError as e:
            assert str(e).startswith("[test_caller]"), f"Unexpected message: {e}"
            print(
                "PASS: resolve_ref_paths caller_label in error with deletes_union present"
            )

    # resolve_ref_paths: git_root fallback hit
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        git_file = tmp_git / "fallback.py"
        git_file.parent.mkdir(parents=True)
        git_file.write_text("x")
        result = resolve_ref_paths(
            ["fallback.py"],
            tmp_project,
            root=None,
            git_root=tmp_git,
        )
        assert result == [git_file], f"Got {result}"
        print("PASS: resolve_ref_paths git_root fallback hit returns git_root path")

    # resolve_ref_paths: git_root fallback miss (hard-fail)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        try:
            resolve_ref_paths(
                ["missing.py"],
                tmp_project,
                root=None,
                git_root=tmp_git,
            )
            print(
                "FAIL: resolve_ref_paths git_root fallback miss: expected ReviewError",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print(
                "PASS: resolve_ref_paths git_root fallback miss -> hard-fail ReviewError"
            )

    # resolve_ref_paths: no git_root kwarg (current behavior unchanged)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["missing.py"], tmp_dir, root=None)
            print(
                "FAIL: resolve_ref_paths no git_root: expected ReviewError",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths without git_root preserves current behavior")

    # resolve_ref_paths: creates_union precedence over git_root
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        result = resolve_ref_paths(
            ["missing.py"],
            tmp_project,
            root=None,
            creates_union={"missing.py"},
            git_root=tmp_git,
        )
        assert result == [], f"Got {result}"
        print(
            "PASS: resolve_ref_paths creates_union suppresses even with git_root fallback"
        )

    # resolve_ref_paths: wiki/ prefix unaffected by git_root fallback
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        tmp_wiki.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        wiki_file = tmp_wiki / "doc.md"
        wiki_file.write_text("x")
        result = resolve_ref_paths(
            ["wiki/doc.md"],
            tmp_project,
            root=None,
            wiki_root=tmp_wiki,
            git_root=tmp_git,
        )
        assert result == [wiki_file], f"Got {result}"
        print("PASS: resolve_ref_paths wiki/ prefix ignores git_root fallback")

    # resolve_ref_paths: soft_fail_gitignored=True skips a missing ref confirmed git-ignored
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo_root = Path(tmpdir)
        _test_helpers.init_minimal_git_repo(repo_root, branch="main")
        (repo_root / ".gitignore").write_text(".scratch/probe.md\n", encoding="utf-8")
        result = resolve_ref_paths(
            [".scratch/probe.md"],
            repo_root,
            None,
            git_root=repo_root,
            soft_fail_gitignored=True,
        )
        assert result == [], f"Got {result}"
        print(
            "PASS: resolve_ref_paths soft_fail_gitignored skips confirmed-ignored missing ref"
        )

    # resolve_ref_paths: soft_fail_gitignored=True still hard-fails on a missing ref NOT git-ignored
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo_root = Path(tmpdir)
        _test_helpers.init_minimal_git_repo(repo_root, branch="main")
        (repo_root / ".gitignore").write_text(".scratch/probe.md\n", encoding="utf-8")
        try:
            resolve_ref_paths(
                ["not_ignored_missing.py"],
                repo_root,
                None,
                git_root=repo_root,
                soft_fail_gitignored=True,
            )
            print(
                "FAIL: resolve_ref_paths soft_fail_gitignored: expected ReviewError for non-ignored missing ref",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print(
                "PASS: resolve_ref_paths soft_fail_gitignored still hard-fails non-ignored missing ref"
            )

    # resolve_ref_paths: soft_fail_gitignored omitted (default False) -> still hard-fails on git-ignored missing ref
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo_root = Path(tmpdir)
        _test_helpers.init_minimal_git_repo(repo_root, branch="main")
        (repo_root / ".gitignore").write_text(".scratch/probe.md\n", encoding="utf-8")
        try:
            resolve_ref_paths(
                [".scratch/probe.md"],
                repo_root,
                None,
                git_root=repo_root,
            )
            print(
                "FAIL: resolve_ref_paths: expected ReviewError with soft_fail_gitignored omitted",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print(
                "PASS: resolve_ref_paths hard-fails git-ignored missing ref when soft_fail_gitignored omitted"
            )

    # resolve_ref_paths: soft_fail_gitignored=False explicit -> still hard-fails on git-ignored missing ref
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo_root = Path(tmpdir)
        _test_helpers.init_minimal_git_repo(repo_root, branch="main")
        (repo_root / ".gitignore").write_text(".scratch/probe.md\n", encoding="utf-8")
        try:
            resolve_ref_paths(
                [".scratch/probe.md"],
                repo_root,
                None,
                git_root=repo_root,
                soft_fail_gitignored=False,
            )
            print(
                "FAIL: resolve_ref_paths: expected ReviewError with soft_fail_gitignored=False",
                file=sys.stderr,
            )
            errors += 1
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print(
                "PASS: resolve_ref_paths hard-fails git-ignored missing ref when soft_fail_gitignored=False explicit"
            )

    # compute_creates_union: empty plan dir returns empty set
    with _test_helpers.safe_temp_dir() as tmpdir:
        result = compute_creates_union(Path(tmpdir) / "nonexistent")
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union nonexistent plan_dir returns empty set")

    # compute_creates_union: one batch with inline Creates tokens
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** `a`, `b`\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_creates_union inline Creates returns set of tokens")

    # compute_creates_union: none token filtered
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text("- **Creates:** none\n", encoding="utf-8")
        result = compute_creates_union(plan_dir)
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union 'none' token filtered")

    # compute_creates_union: two batches with sub-bullet Creates -> union
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:**\n  - `x.py`\n  - `y.py`\n",
            encoding="utf-8",
        )
        (plan_dir / "02-wire.md").write_text(
            "- **Creates:**\n  - `z.py`\n",
            encoding="utf-8",
        )
        result = compute_creates_union(plan_dir)
        assert result == {"x.py", "y.py", "z.py"}, f"Got {result}"
        print("PASS: compute_creates_union two batches -> union of Creates tokens")

    # compute_creates_union: 00-overview.md excluded
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "00-overview.md").write_text(
            "- **Creates:** `overview-token`\n", encoding="utf-8"
        )
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** `real-token`\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == {"real-token"}, f"Got {result}"
        print("PASS: compute_creates_union 00-overview.md excluded")

    # compute_creates_union: case-variant None filtered
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text("- **Creates:** None\n", encoding="utf-8")
        result = compute_creates_union(plan_dir)
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union 'None' (capital N) filtered")

    # ---------------------------------------------------------------------------
    # compute_deletes_union
    # ---------------------------------------------------------------------------

    # empty plan dir returns empty set
    with _test_helpers.safe_temp_dir() as tmpdir:
        result = compute_deletes_union(Path(tmpdir) / "nonexistent")
        assert result == set(), f"Got {result}"
        print("PASS: compute_deletes_union nonexistent plan_dir returns empty set")

    # single batch single-line Deletes tokens
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:** `a`, `b`\n", encoding="utf-8"
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_deletes_union inline Deletes returns set of tokens")

    # multi-line bullet form
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:**\n  - `a`\n  - `b`\n",
            encoding="utf-8",
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_deletes_union multi-line bullet form returns tokens")

    # 'none' sentinel filtered (case variants)
    for sentinel in ("none", "None", "NONE"):
        with _test_helpers.safe_temp_dir() as tmpdir:
            plan_dir = Path(tmpdir)
            (plan_dir / "01-setup.md").write_text(
                f"- **Deletes:** {sentinel}\n", encoding="utf-8"
            )
            result = compute_deletes_union(plan_dir)
            assert result == set(), f"Got {result} for sentinel {sentinel!r}"
        print(f"PASS: compute_deletes_union '{sentinel}' sentinel filtered")

    # two batches with overlapping deletes — de-duplicated
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:** `x.py`, `y.py`\n", encoding="utf-8"
        )
        (plan_dir / "02-wire.md").write_text(
            "- **Deletes:** `y.py`, `z.py`\n", encoding="utf-8"
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"x.py", "y.py", "z.py"}, f"Got {result}"
        print("PASS: compute_deletes_union two batches with overlap -> de-duplicated")

    # Deletes: absent on a card contributes nothing; other cards in same batch do
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Context:** `src/a.py`\n"
            "- **Deletes:** `old.py`\n"
            "- **Context:** `src/b.py`\n",
            encoding="utf-8",
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"old.py"}, f"Got {result}"
        print(
            "PASS: compute_deletes_union Deletes absent on some cards; present on others"
        )

    # 00-overview.md is skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "00-overview.md").write_text(
            "- **Deletes:** `overview-token`\n", encoding="utf-8"
        )
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:** `real-token`\n", encoding="utf-8"
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"real-token"}, f"Got {result}"
        print("PASS: compute_deletes_union 00-overview.md excluded")

    # ---------------------------------------------------------------------------
    # DisplayRoots.render
    # ---------------------------------------------------------------------------

    with _test_helpers.safe_temp_dir() as tmpdir:
        base = Path(tmpdir).resolve()
        project_root = base / "project"
        git_root = base / "git"
        wiki_root = base / "wiki"
        for d in (project_root, git_root, wiki_root):
            d.mkdir()

        # Path directly under project_root -> bare relative POSIX string.
        roots = DisplayRoots(project_root=project_root)
        p = project_root / "sub" / "file.py"
        result = roots.render(p)
        assert result == "sub/file.py", f"Got {result!r}"
        print("PASS: DisplayRoots.render path under project_root -> bare relative")

        # Path under wiki_root -> `wiki/` prefix.
        roots = DisplayRoots(project_root=project_root, wiki_root=wiki_root)
        p = wiki_root / "task" / "discussion.md"
        result = roots.render(p)
        assert result == "wiki/task/discussion.md", f"Got {result!r}"
        print("PASS: DisplayRoots.render path under wiki_root -> wiki/ prefix")

        # Path under both a git_root and a deeper project_root -> renders against the longer root.
        deeper_project_root = git_root / "sub_project"
        deeper_project_root.mkdir()
        roots = DisplayRoots(project_root=deeper_project_root, git_root=git_root)
        p = deeper_project_root / "nested" / "file.py"
        result = roots.render(p)
        assert result == "nested/file.py", f"Got {result!r}"
        print(
            "PASS: DisplayRoots.render path under git_root and deeper project_root -> longer root wins"
        )

        # Path under both a wiki_root and a deeper project_root -> wiki form wins (rule 1 short-circuits rule 2).
        deeper_project_under_wiki = wiki_root / "sub_project"
        deeper_project_under_wiki.mkdir()
        roots = DisplayRoots(
            project_root=deeper_project_under_wiki, wiki_root=wiki_root
        )
        p = deeper_project_under_wiki / "nested" / "file.py"
        result = roots.render(p)
        assert result == "wiki/sub_project/nested/file.py", f"Got {result!r}"
        print(
            "PASS: DisplayRoots.render path under wiki_root and deeper project_root -> wiki/ wins"
        )

        # Path under no root -> unchanged absolute string.
        roots = DisplayRoots(project_root=project_root)
        outside = base / "outside" / "file.py"
        result = roots.render(outside)
        assert result == str(outside), f"Got {result!r}"
        print("PASS: DisplayRoots.render path under no root -> unchanged absolute")

        # Nested path -> forward slashes.
        roots = DisplayRoots(project_root=project_root)
        p = project_root / "a" / "b" / "c.py"
        result = roots.render(p)
        assert "/" in result and "\\" not in result, f"Got {result!r}"
        assert result == "a/b/c.py", f"Got {result!r}"
        print("PASS: DisplayRoots.render nested path -> forward slashes")

        # git_root=None and wiki_root=None -> no raise, falls back to project_root then absolute.
        roots = DisplayRoots(project_root=project_root)
        p = project_root / "x.py"
        result = roots.render(p)
        assert result == "x.py", f"Got {result!r}"
        outside2 = base / "elsewhere.py"
        result2 = roots.render(outside2)
        assert result2 == str(outside2), f"Got {result2!r}"
        print("PASS: DisplayRoots.render git_root=None wiki_root=None does not raise")

    # ---------------------------------------------------------------------------
    # build_path_roots_section
    # ---------------------------------------------------------------------------

    with _test_helpers.safe_temp_dir() as tmpdir:
        base = Path(tmpdir).resolve()
        project_root = base / "project"
        git_root = base / "git"
        wiki_root = base / "wiki"
        for d in (project_root, git_root, wiki_root):
            d.mkdir()

        # project-root-only -> heading, no wiki/ bullet, no git_root bullet.
        roots = DisplayRoots(project_root=project_root)
        result = build_path_roots_section(roots)
        assert result.startswith("## Path roots"), f"Got {result!r}"
        assert "wiki/" not in result, f"Unexpected wiki/ bullet: {result!r}"
        assert "git_root" not in result, f"Unexpected git_root bullet: {result!r}"
        print("PASS: build_path_roots_section project-root-only -> no extra bullets")

        # wiki_root set -> wiki/ bullet.
        roots = DisplayRoots(project_root=project_root, wiki_root=wiki_root)
        result = build_path_roots_section(roots)
        assert "wiki/" in result, f"Missing wiki/ bullet: {result!r}"
        print("PASS: build_path_roots_section wiki_root set -> wiki/ bullet")

        # git_root equal to project_root -> no git_root bullet.
        roots = DisplayRoots(project_root=project_root, git_root=project_root)
        result = build_path_roots_section(roots)
        assert "git_root" not in result, f"Unexpected git_root bullet: {result!r}"
        print("PASS: build_path_roots_section git_root == project_root -> no bullet")

        # git_root differing from project_root -> one git_root bullet.
        roots = DisplayRoots(project_root=project_root, git_root=git_root)
        result = build_path_roots_section(roots)
        assert result.count("git_root") == 1, f"Got {result!r}"
        print("PASS: build_path_roots_section git_root != project_root -> one bullet")

        # No trailing newline, matching neighbouring builders' convention.
        assert not result.endswith("\n"), f"Expected no trailing newline, got {result!r}"
        print("PASS: build_path_roots_section no trailing newline")

    # ---------------------------------------------------------------------------
    # build_manifest_section
    # ---------------------------------------------------------------------------

    # Empty input
    result = build_manifest_section([])
    assert result == "## Files included (N=0)\n\n(no files)", f"Got {result!r}"
    print("PASS: build_manifest_section empty input")

    # Three-path input
    paths = [Path("/a/foo.py"), Path("/b/bar.py"), Path("/c/baz.py")]
    result = build_manifest_section(paths)
    assert result.startswith("## Files included (N=3)"), f"Got {result!r}"
    lines = result.split("\n")
    assert lines[1] == "", f"Expected blank line, got {lines[1]!r}"
    assert lines[2] == f"- {paths[0]}", f"Got {lines[2]!r}"
    assert lines[3] == f"- {paths[1]}", f"Got {lines[3]!r}"
    assert lines[4] == f"- {paths[2]}", f"Got {lines[4]!r}"
    print("PASS: build_manifest_section three-path input (heading + blank + bullets)")

    # No trailing newline
    assert not result.endswith("\n"), f"Expected no trailing newline, got {result!r}"
    print("PASS: build_manifest_section no trailing newline")

    # roots supplied -> relative bullets, result starts with ## Path roots
    with _test_helpers.safe_temp_dir() as tmpdir:
        project_root = Path(tmpdir).resolve()
        paths = [project_root / "a.py", project_root / "sub" / "b.py"]
        roots = DisplayRoots(project_root=project_root)
        result = build_manifest_section(paths, roots=roots)
        assert result.startswith("## Path roots"), f"Got {result!r}"
        assert "- a.py" in result, f"Missing relative bullet: {result!r}"
        assert "- sub/b.py" in result, f"Missing relative bullet: {result!r}"
        assert str(project_root) not in result.split("## Files included")[1], (
            f"Bullets should not carry absolute prefix: {result!r}"
        )
        print("PASS: build_manifest_section with roots -> relative bullets and Path roots header")

    # roots omitted -> back-compat pin: still absolute bullets and ## Files included first
    with _test_helpers.safe_temp_dir() as tmpdir:
        project_root = Path(tmpdir).resolve()
        paths = [project_root / "a.py"]
        result = build_manifest_section(paths)
        assert result.startswith("## Files included (N="), f"Got {result!r}"
        assert f"- {paths[0]}" in result, f"Expected absolute bullet: {result!r}"
        print("PASS: build_manifest_section without roots -> absolute bullets (back-compat)")

    # ---------------------------------------------------------------------------
    # build_deletes_section
    # ---------------------------------------------------------------------------

    # Empty list -> empty string
    result = build_deletes_section([])
    assert result == "", f"Expected empty string, got {result!r}"
    print("PASS: build_deletes_section empty list -> empty string")

    # Single token
    result = build_deletes_section(["old_module.py"])
    assert result == "## Intentionally deleted (N=1)\n\n- old_module.py", (
        f"Got {result!r}"
    )
    print("PASS: build_deletes_section single token -> heading + bullet")

    # Multiple tokens preserve input order
    result = build_deletes_section(["a.py", "b.py", "c.py"])
    assert result.startswith("## Intentionally deleted (N=3)"), (
        f"Wrong heading: {result!r}"
    )
    lines = result.split("\n")
    assert lines[2] == "- a.py", f"Wrong first bullet: {lines[2]!r}"
    assert lines[3] == "- b.py", f"Wrong second bullet: {lines[3]!r}"
    assert lines[4] == "- c.py", f"Wrong third bullet: {lines[4]!r}"
    print("PASS: build_deletes_section multiple tokens preserve input order")

    # Bullets are exactly '- <token>' — no backticks added
    result = build_deletes_section(["path/to/file.py"])
    assert "- path/to/file.py" in result, f"Expected plain bullet, got {result!r}"
    assert "`" not in result, f"No backticks should be added: {result!r}"
    print("PASS: build_deletes_section bullets have no backticks added")

    # No trailing newline
    result = build_deletes_section(["x.py"])
    assert not result.endswith("\n"), f"Expected no trailing newline, got {result!r}"
    print("PASS: build_deletes_section no trailing newline")

    # ---------------------------------------------------------------------------
    # resolve_existing_paths
    # ---------------------------------------------------------------------------

    with _test_helpers.safe_temp_dir() as tmpdir:
        project = Path(tmpdir) / "project"
        project.mkdir()

        # Path on disk -> returned
        existing = project / "real.py"
        existing.write_text("x")
        result = resolve_existing_paths([str(existing)], project, root=None)
        assert result == [existing], f"Got {result}"
        print("PASS: resolve_existing_paths path on disk returned")

        # Path NOT on disk -> silently dropped
        result = resolve_existing_paths(["nonexistent.py"], project, root=None)
        assert result == [], f"Got {result}"
        print("PASS: resolve_existing_paths missing path silently dropped")

        # Wiki-prefixed path that exists under wiki_root -> returned
        wiki = Path(tmpdir) / "wiki"
        (wiki / "active" / "slug").mkdir(parents=True)
        wiki_file = wiki / "active" / "slug" / "foo.md"
        wiki_file.write_text("w")
        result = resolve_existing_paths(
            ["wiki/active/slug/foo.md"], project, root=None, wiki_root=wiki
        )
        assert result == [wiki_file], f"Got {result}"
        print("PASS: resolve_existing_paths wiki-prefixed path exists -> returned")

        # Wiki-prefixed path missing -> silently dropped (no error)
        result = resolve_existing_paths(
            ["wiki/active/slug/missing.md"], project, root=None, wiki_root=wiki
        )
        assert result == [], f"Got {result}"
        print(
            "PASS: resolve_existing_paths wiki-prefixed path missing -> silently dropped"
        )

        # Wiki-prefixed path with wiki_root=None -> silently dropped (no raise)
        result = resolve_existing_paths(
            ["wiki/active/slug/foo.md"], project, root=None, wiki_root=None
        )
        assert result == [], f"Got {result}"
        print(
            "PASS: resolve_existing_paths wiki/ with wiki_root=None -> silently dropped (no raise)"
        )

        # None token silently dropped
        result = resolve_existing_paths([None, str(existing)], project, root=None)
        assert result == [existing], f"Got {result}"
        print("PASS: resolve_existing_paths None token silently dropped")

        # 'none' (any case) tokens silently dropped
        result = resolve_existing_paths(
            ["none", "NONE", "None", str(existing)], project, root=None
        )
        assert result == [existing], f"Got {result}"
        print(
            "PASS: resolve_existing_paths 'none'/'NONE'/'None' tokens silently dropped"
        )

        # Mixed: [exists, missing, "none", None, wiki-exists] -> [exists, wiki-exists]
        result = resolve_existing_paths(
            [str(existing), "nonexistent.py", "none", None, "wiki/active/slug/foo.md"],
            project,
            root=None,
            wiki_root=wiki,
        )
        assert result == [existing, wiki_file], f"Got {result}"
        print(
            "PASS: resolve_existing_paths mixed input -> only existing paths returned"
        )

    # resolve_existing_paths: git_root fallback hit
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        git_file = tmp_git / "fallback.py"
        git_file.parent.mkdir(parents=True)
        git_file.write_text("x")
        result = resolve_existing_paths(
            ["fallback.py"],
            tmp_project,
            root=None,
            git_root=tmp_git,
        )
        assert result == [git_file], f"Got {result}"
        print(
            "PASS: resolve_existing_paths git_root fallback hit returns git_root path"
        )

    # resolve_existing_paths: git_root fallback miss (silent drop, no error)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        result = resolve_existing_paths(
            ["missing.py"],
            tmp_project,
            root=None,
            git_root=tmp_git,
        )
        assert result == [], f"Got {result}"
        print(
            "PASS: resolve_existing_paths git_root fallback miss silently drops (no error)"
        )

    # resolve_existing_paths: no git_root kwarg (current behavior unchanged)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        result = resolve_existing_paths(
            ["missing.py"],
            tmp_project,
            root=None,
        )
        assert result == [], f"Got {result}"
        print(
            "PASS: resolve_existing_paths without git_root preserves current behavior"
        )

    # resolve_ref_paths: cwd==git_root layout with root set (#471 regression: should NOT double)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        # Create git_root/root/raw file
        (tmp_git / "src").mkdir(parents=True)
        (tmp_git / "src" / "file.py").write_text("x")
        # project_root is git_root (not doubled subfolder)
        result = resolve_ref_paths(
            ["file.py"],
            tmp_git,
            root="src",
            git_root=tmp_git,
        )
        # Should resolve to git_root/src/file.py (primary candidate)
        assert result == [tmp_git / "src" / "file.py"], f"Got {result}"
        print(
            "PASS: resolve_ref_paths cwd==git_root with root set uses git_root/root/raw primary"
        )

    # resolve_existing_paths: cwd==git_root/root layout (#471 regression: should NOT double)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        # Create git_root/src/file.py
        (tmp_git / "src").mkdir(parents=True)
        (tmp_git / "src" / "file.py").write_text("x")
        # When cwd is git_root/src, project_root would be git_root/src
        project_root = tmp_git / "src"
        result = resolve_existing_paths(
            ["file.py"],
            project_root,
            root="src",
            git_root=tmp_git,
        )
        # Should resolve to git_root/src/file.py (NOT doubled git_root/src/src/file.py)
        assert result == [tmp_git / "src" / "file.py"], f"Got {result}"
        print(
            "PASS: resolve_existing_paths cwd==git_root/root returns single-prefixed git_root/root/raw (not doubled)"
        )

    # resolve_ref_paths: git_root=None falls back to project_root/root/raw
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        (tmp_project / "src").mkdir(parents=True)
        (tmp_project / "src" / "file.py").write_text("x")
        result = resolve_ref_paths(
            ["file.py"],
            tmp_project,
            root="src",
            git_root=None,
        )
        # Should resolve to project_root/src/file.py (no git_root candidate)
        assert result == [tmp_project / "src" / "file.py"], f"Got {result}"
        print(
            "PASS: resolve_ref_paths git_root=None falls back to project_root/root/raw"
        )

    # resolve_existing_paths: git_root=None falls back to project_root/root/raw
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        (tmp_project / "src").mkdir(parents=True)
        (tmp_project / "src" / "file.py").write_text("x")
        result = resolve_existing_paths(
            ["file.py"],
            tmp_project,
            root="src",
            git_root=None,
        )
        # Should resolve to project_root/src/file.py
        assert result == [tmp_project / "src" / "file.py"], f"Got {result}"
        print(
            "PASS: resolve_existing_paths git_root=None falls back to project_root/root/raw"
        )

    # resolve_ref_paths: wiki/ prefix unchanged by git_root threading
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        (tmp_wiki / "active" / "x").mkdir(parents=True)
        (tmp_wiki / "active" / "x" / "discussion.md").write_text("w")
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        result = resolve_ref_paths(
            ["wiki/active/x/discussion.md"],
            tmp_project,
            root="src",
            wiki_root=tmp_wiki,
            git_root=tmp_git,
        )
        assert result == [tmp_wiki / "active" / "x" / "discussion.md"], f"Got {result}"
        print("PASS: resolve_ref_paths wiki/ prefix routes through wiki_root unchanged")

    # resolve_existing_paths: wiki/ prefix unchanged by git_root threading
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        (tmp_wiki / "active" / "x").mkdir(parents=True)
        (tmp_wiki / "active" / "x" / "discussion.md").write_text("w")
        tmp_git = Path(tmpdir) / "git"
        tmp_git.mkdir()
        result = resolve_existing_paths(
            ["wiki/active/x/discussion.md"],
            tmp_project,
            root="src",
            wiki_root=tmp_wiki,
            git_root=tmp_git,
        )
        assert result == [tmp_wiki / "active" / "x" / "discussion.md"], f"Got {result}"
        print(
            "PASS: resolve_existing_paths wiki/ prefix routes through wiki_root unchanged"
        )

    # Per-scope counters survive interleaved per-batch + holistic writes (regression for #21, #62, #63)
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        ts = "20260418-002000"
        (reviews / f"{ts}-code-review-helper-modules-r1.md").write_text("x")

        result = discover_round(reviews, "code", "helper-modules")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/helper-modules after r1: {result}")

        result = discover_round(reviews, "code", "spawn-core")
        assert result == 1, f"expected 1, got {result}"
        print(
            f"PASS: discover_round per-scope code/spawn-core (different batch, fresh count): {result}"
        )

        (reviews / f"{ts}-code-review-r1.md").write_text("x")

        result = discover_round(reviews, "code", "holistic")
        assert result == 2, f"expected 2, got {result}"
        print(
            f"PASS: discover_round per-scope code/holistic independent after holistic r1: {result}"
        )

        result = discover_round(reviews, "code", "helper-modules")
        assert result == 2, f"expected 2, got {result}"
        print(
            f"PASS: discover_round per-scope code/helper-modules still independent of holistic: {result}"
        )

    # ---------------------------------------------------------------------------
    # parse_missing_context
    # ---------------------------------------------------------------------------

    # No ## Missing context heading -> []
    result = parse_missing_context("# Review\n\n```yaml\nverdict: NEED_CONTEXT\n```\n")
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context no heading -> []")

    # One path bullet
    text = "## Missing context\n\n- `a/b.py` — reason text\n"
    result = parse_missing_context(text)
    assert result == ["a/b.py"], f"Got {result}"
    print("PASS: parse_missing_context one path bullet -> ['a/b.py']")

    # Two path bullets in order
    text = "## Missing context\n\n- `a/b.py` — reason\n- `c/d.py` — other reason\n"
    result = parse_missing_context(text)
    assert result == ["a/b.py", "c/d.py"], f"Got {result}"
    print("PASS: parse_missing_context two path bullets -> list in order")

    # Empty section (heading present, no bullets)
    text = "## Missing context\n\nNo bullets here.\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context empty section -> []")

    # Section terminated by next ## heading — only paths between headings captured
    text = (
        "## Missing context\n\n"
        "- `x/y.py` — reason\n\n"
        "## Verdict\n\n"
        "- `z/w.py` — should NOT be captured\n"
    )
    result = parse_missing_context(text)
    assert result == ["x/y.py"], f"Got {result}"
    print("PASS: parse_missing_context stops at next ## heading")

    # Bullet without backticks -> not captured
    text = "## Missing context\n\n- a/b.py — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context bullet without backticks not captured")

    # Bullet with `none` token -> filtered (lowercase)
    text = "## Missing context\n\n- `none` — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context `none` token filtered")

    # Bullet with `None` token -> filtered (capital N)
    text = "## Missing context\n\n- `None` — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context `None` token filtered")

    # ---------------------------------------------------------------------------
    # build_reattached_section
    # ---------------------------------------------------------------------------

    # Empty input -> ""
    result = build_reattached_section([])
    assert result == "", f"Got {result!r}"
    print("PASS: build_reattached_section empty input -> ''")

    # One path -> heading + blank line + FILE delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        f = Path(tmpdir) / "foo.py"
        f.write_text("content")
        result = build_reattached_section([f])
        assert "## Re-attached files (you said these were missing)" in result, (
            f"Missing heading in: {result!r}"
        )
        assert str(f) in result, f"Path not in output: {result!r}"
        assert "--- FILE:" in result, f"No FILE delimiter in: {result!r}"
        print("PASS: build_reattached_section one path -> heading + FILE delimiter")

    # Two paths -> both delimiters in order
    with _test_helpers.safe_temp_dir() as tmpdir:
        fa = Path(tmpdir) / "a.py"
        fb = Path(tmpdir) / "b.py"
        fa.write_text("aaa")
        fb.write_text("bbb")
        result = build_reattached_section([fa, fb])
        assert str(fa) in result, "fa not in output"
        assert str(fb) in result, "fb not in output"
        assert result.index(str(fa)) < result.index(str(fb)), (
            "fa should appear before fb"
        )
        print("PASS: build_reattached_section two paths -> both delimiters in order")

    # ---------------------------------------------------------------------------
    # parse_blocking_count
    # ---------------------------------------------------------------------------

    # Empty string -> 0
    result = parse_blocking_count("", severity="BLOCKING")
    assert result == 0, f"expected 0, got {result}"
    print("PASS: parse_blocking_count empty string -> 0")

    # One BLOCKING heading
    result = parse_blocking_count(
        "# Review\n\n## Findings\n\n### [BLOCKING] foo\n",
        severity="BLOCKING",
    )
    assert result == 1, f"expected 1, got {result}"
    print("PASS: parse_blocking_count one BLOCKING heading -> 1")

    # Two BLOCKINGs and one NIT
    text = "### [BLOCKING] one\n### [BLOCKING] two\n### [NIT] three\n"
    result = parse_blocking_count(text, severity="BLOCKING")
    assert result == 2, f"expected 2, got {result}"
    print("PASS: parse_blocking_count two BLOCKINGs -> 2")
    result = parse_blocking_count(text, severity="NIT")
    assert result == 1, f"expected 1, got {result}"
    print("PASS: parse_blocking_count one NIT -> 1")

    # Discussion-style GAP/NOTE
    text = "### [GAP] missing edge case\n### [NOTE] minor\n"
    result = parse_blocking_count(text, severity="GAP")
    assert result == 1, f"expected 1, got {result}"
    print("PASS: parse_blocking_count GAP severity -> 1")

    # Severity match is case-sensitive
    result = parse_blocking_count("### [blocking] foo\n", severity="BLOCKING")
    assert result == 0, f"expected 0, got {result}"
    print(
        "PASS: parse_blocking_count case-sensitive: lowercase blocking with BLOCKING severity -> 0"
    )

    # Heading at start of line only — mid-line marker not counted
    result = parse_blocking_count("text ### [BLOCKING] foo\n", severity="BLOCKING")
    assert result == 0, f"expected 0, got {result}"
    print("PASS: parse_blocking_count mid-line marker not counted -> 0")

    # ---------------------------------------------------------------------------
    # parse_blocking_count YAML-fallback cases (#552)
    # ---------------------------------------------------------------------------

    # yaml-list-only BLOCKING: no markdown headings, one yaml findings entry
    raw = "```yaml\nfindings:\n  - severity: BLOCKING\n    title: foo\n```\n"
    result = parse_blocking_count(raw, severity="BLOCKING")
    assert result == 1, f"expected 1, got {result}"
    print("PASS: parse_blocking_count yaml-list BLOCKING -> 1")

    # yaml-list mixed severities: BLOCKING=1, NIT=2
    raw = (
        "```yaml\n"
        "findings:\n"
        "  - severity: BLOCKING\n"
        "    title: a\n"
        "  - severity: NIT\n"
        "    title: b\n"
        "  - severity: NIT\n"
        "    title: c\n"
        "```\n"
    )
    result = parse_blocking_count(raw, severity="BLOCKING")
    assert result == 1, f"expected 1 BLOCKING, got {result}"
    print("PASS: parse_blocking_count yaml-list mixed severities BLOCKING -> 1")
    result = parse_blocking_count(raw, severity="NIT")
    assert result == 2, f"expected 2 NIT, got {result}"
    print("PASS: parse_blocking_count yaml-list mixed severities NIT -> 2")

    # heading wins over yaml: heading_count > 0 skips the yaml scan entirely
    raw = "### [BLOCKING] foo\n```yaml\nfindings:\n  - severity: BLOCKING\n```\n"
    result = parse_blocking_count(raw, severity="BLOCKING")
    assert result == 1, f"expected 1 (heading wins), got {result}"
    print("PASS: parse_blocking_count heading>0 wins over yaml list")

    # verdict block is not counted: yaml with verdict: key but no findings: key
    raw = "```yaml\nverdict: APPROVE\n```\n"
    result = parse_blocking_count(raw, severity="BLOCKING")
    assert result == 0, f"expected 0 for verdict-only block, got {result}"
    print("PASS: parse_blocking_count verdict-only yaml block -> 0")

    # malformed yaml does not crash: skip the block, return 0
    raw = "```yaml\nfindings: [{\n```\n"
    result = parse_blocking_count(raw, severity="BLOCKING")
    assert result == 0, f"expected 0 for malformed yaml, got {result}"
    print("PASS: parse_blocking_count malformed yaml block -> 0, no crash")

    # case-insensitive severity in yaml: lowercase 'blocking' matches BLOCKING
    raw = "```yaml\nfindings:\n  - severity: blocking\n    title: x\n```\n"
    result = parse_blocking_count(raw, severity="BLOCKING")
    assert result == 1, f"expected 1 (case-insensitive), got {result}"
    print("PASS: parse_blocking_count yaml severity is case-insensitive")

    # ---------------------------------------------------------------------------
    # count_unrecognized_severity_findings
    # ---------------------------------------------------------------------------

    # Empty input -> 0, no crash
    result = count_unrecognized_severity_findings(
        "", blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 0, f"expected 0, got {result}"
    print("PASS: count_unrecognized_severity_findings empty input -> 0")

    # One unrecognized heading -> 1
    result = count_unrecognized_severity_findings(
        "### [MAJOR] foo\n", blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 1, f"expected 1, got {result}"
    print("PASS: count_unrecognized_severity_findings one [MAJOR] heading -> 1")

    # Other off-vocabulary words count identically to MAJOR -- no special-casing by which word the reviewer used.
    for word in ("MEDIUM", "HIGH", "MINOR"):
        result = count_unrecognized_severity_findings(
            f"### [{word}] foo\n", blocking_severity="BLOCKING", nit_severity="NIT"
        )
        assert result == 1, f"expected 1 for [{word}], got {result}"
    print(
        "PASS: count_unrecognized_severity_findings [MEDIUM]/[HIGH]/[MINOR] each count as 1"
    )

    # A recognized BLOCKING heading is not double-counted by this helper -- parse_blocking_count(severity="BLOCKING") already counts it elsewhere.
    result = count_unrecognized_severity_findings(
        "### [BLOCKING] foo\n", blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 0, f"expected 0, got {result}"
    print("PASS: count_unrecognized_severity_findings [BLOCKING] heading -> 0")

    # A recognized NIT heading is never counted by this helper.
    result = count_unrecognized_severity_findings(
        "### [NIT] foo\n", blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 0, f"expected 0, got {result}"
    print("PASS: count_unrecognized_severity_findings [NIT] heading -> 0")

    # Heading matching is case-sensitive, consistent with parse_blocking_count's existing case-sensitive heading behavior -- mixed-case spellings of a recognized severity are not "unrecognized findings" here, they simply fail to match anything (neither known nor counted as unrecognized).
    result = count_unrecognized_severity_findings(
        "### [Major] foo\n### [major] bar\n",
        blocking_severity="BLOCKING",
        nit_severity="NIT",
    )
    assert result == 0, f"expected 0, got {result}"
    print(
        "PASS: count_unrecognized_severity_findings mixed-case [Major]/[major] -> 0"
    )

    # YAML-only unrecognized severity, no markdown headings at all -> 1
    raw = "```yaml\nfindings:\n  - severity: MAJOR\n    title: foo\n```\n"
    result = count_unrecognized_severity_findings(
        raw, blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 1, f"expected 1, got {result}"
    print("PASS: count_unrecognized_severity_findings yaml-only MAJOR entry -> 1")

    # YAML severity matching is case-insensitive, mirroring parse_blocking_count's existing YAML-path case-insensitivity.
    raw = "```yaml\nfindings:\n  - severity: major\n    title: foo\n```\n"
    result = count_unrecognized_severity_findings(
        raw, blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 1, f"expected 1, got {result}"
    print(
        "PASS: count_unrecognized_severity_findings yaml-only lowercase 'major' entry -> 1"
    )

    # Unconditional scan proof #1: a document has a real [MAJOR] heading AND a real [NIT] heading (heading_count > 0 for NIT, so parse_blocking_count's own YAML fallback would never fire for NIT) -- the helper must still find the [MAJOR] heading rather than skipping the heading scan.
    raw = "### [MAJOR] foo\n### [NIT] bar\n"
    result = count_unrecognized_severity_findings(
        raw, blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 1, f"expected 1, got {result}"
    print(
        "PASS: count_unrecognized_severity_findings finds [MAJOR] heading alongside a real [NIT] heading"
    )

    # Unconditional scan proof #2: same document as above, plus an ADDITIONAL unrecognized severity expressed ONLY as a yaml findings: entry (no corresponding heading) -- the helper must count both the [MAJOR] heading AND the yaml-only entry, proving the scan is never gated on which mechanism the known severities happened to use.
    raw = (
        "### [MAJOR] foo\n"
        "### [NIT] bar\n"
        "```yaml\n"
        "findings:\n"
        "  - severity: MEDIUM\n"
        "    title: baz\n"
        "```\n"
    )
    result = count_unrecognized_severity_findings(
        raw, blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 2, f"expected 2, got {result}"
    print(
        "PASS: count_unrecognized_severity_findings counts both a heading-only and a yaml-only unrecognized entry"
    )

    # The helper is not hardcoded to BLOCKING/NIT -- it works for the discussion review type's GAP/NOTE pair too.
    result = count_unrecognized_severity_findings(
        "### [MAJOR] foo\n", blocking_severity="GAP", nit_severity="NOTE"
    )
    assert result == 1, f"expected 1, got {result}"
    print(
        "PASS: count_unrecognized_severity_findings works for the GAP/NOTE severity pair"
    )

    # Double-counting is accepted, documented behavior (see the "Accepted risk" note in _mill/discussion.md), not a bug: a heading and a mirroring yaml entry for what a human would consider "the same finding" are counted twice because the two mechanisms are scanned unconditionally and independently, with no dedup logic.
    raw = "### [MAJOR] foo\n```yaml\nfindings:\n  - severity: MAJOR\n    title: foo\n```\n"
    result = count_unrecognized_severity_findings(
        raw, blocking_severity="BLOCKING", nit_severity="NIT"
    )
    assert result == 2, f"expected 2 (deliberately not deduplicated), got {result}"
    print(
        "PASS: count_unrecognized_severity_findings double-counts a heading + mirroring yaml entry (accepted risk, not a bug)"
    )

    # finalize_scope integration: unrecognized-severity findings fold into blocking_count alongside the existing BLOCKING count, while a recognized NIT heading still lands in nit_count only.
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir / "reviews"
        raw = (
            "```yaml\n"
            "verdict: REQUEST_CHANGES\n"
            "reviewed_file: 01-setup.md\n"
            "date: 2026-01-01\n"
            "```\n"
            "### [BLOCKING] foo\n"
            "### [MAJOR] bar\n"
            "### [NIT] baz\n"
        )
        result = finalize_scope(reviews, "plan", 1, raw, scope="01-setup")
        assert result["blocking_count"] == 2, (
            f"expected blocking_count 2, got {result['blocking_count']}"
        )
        assert result["nit_count"] == 1, (
            f"expected nit_count 1, got {result['nit_count']}"
        )
        print(
            "PASS: finalize_scope folds unrecognized-severity findings into blocking_count"
        )

        # Isolated case: a [MEDIUM]-only response (no recognized [BLOCKING]/[NIT] heading at all) must still fold into blocking_count via count_unrecognized_severity_findings, with nit_count staying 0. Uses round 2 (distinct from round 1 above) so write_review_file does not collide on filename.
        raw_medium_only = (
            "```yaml\n"
            "verdict: REQUEST_CHANGES\n"
            "reviewed_file: 01-setup.md\n"
            "date: 2026-01-01\n"
            "```\n"
            "### [MEDIUM] borderline concern\n"
        )
        result = finalize_scope(reviews, "plan", 2, raw_medium_only, scope="01-setup")
        assert result["blocking_count"] == 1, (
            f"expected blocking_count 1, got {result['blocking_count']}"
        )
        assert result["nit_count"] == 0, (
            f"expected nit_count 0, got {result['nit_count']}"
        )
        print(
            "PASS: finalize_scope folds an isolated [MEDIUM]-only finding into blocking_count with zero recognized findings present"
        )

    # ---------------------------------------------------------------------------
    # parse_blocking_count divergence warning
    # ---------------------------------------------------------------------------

    def test_parse_blocking_count_warns_on_prose_divergence_numeric():
        import contextlib
        import io

        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "There are 5 blocking findings in this review.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert "heading count 3 diverges from prose count 5" in buf.getvalue(), (
            f"expected divergence warning, got: {buf.getvalue()!r}"
        )
        print("PASS: parse_blocking_count_warns_on_prose_divergence_numeric")

    def test_parse_blocking_count_warns_on_prose_divergence_spelled():
        import contextlib
        import io

        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "Five blocking issues remain in this review.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert "heading count 3 diverges from prose count 5" in buf.getvalue(), (
            f"expected divergence warning, got: {buf.getvalue()!r}"
        )
        print("PASS: parse_blocking_count_warns_on_prose_divergence_spelled")

    def test_parse_blocking_count_silent_when_aligned():
        import contextlib
        import io

        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "3 blocking issues found.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert buf.getvalue() == "", f"expected no warning, got: {buf.getvalue()!r}"
        print("PASS: parse_blocking_count_silent_when_aligned")

    def test_parse_blocking_count_silent_when_no_prose_count():
        import contextlib
        import io

        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "### [BLOCKING] finding three\n"
            "No prose count phrase here.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 3, f"expected 3, got {count}"
        assert buf.getvalue() == "", f"expected no warning, got: {buf.getvalue()!r}"
        print("PASS: parse_blocking_count_silent_when_no_prose_count")

    def test_parse_blocking_count_warns_for_gap_severity():
        import contextlib
        import io

        raw = (
            "### [GAP] missing edge case\n"
            "### [GAP] another gap\n"
            "Three gaps remain in the discussion.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="GAP")
        assert count == 2, f"expected 2, got {count}"
        stderr = buf.getvalue()
        assert "heading count 2 diverges from prose count 3 (severity=GAP)" in stderr, (
            f"expected GAP divergence warning, got: {stderr!r}"
        )
        print("PASS: parse_blocking_count_warns_for_gap_severity")

    test_parse_blocking_count_warns_on_prose_divergence_numeric()
    test_parse_blocking_count_warns_on_prose_divergence_spelled()
    test_parse_blocking_count_silent_when_aligned()
    test_parse_blocking_count_silent_when_no_prose_count()
    test_parse_blocking_count_warns_for_gap_severity()

    def test_parse_blocking_count_divergence_warning_ascii_only():
        import contextlib
        import io

        raw = (
            "### [BLOCKING] finding one\n"
            "### [BLOCKING] finding two\n"
            "There are 5 blocking findings in this review.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="BLOCKING")
        assert count == 2, f"expected 2, got {count}"
        stderr_output = buf.getvalue()
        assert stderr_output, "expected stderr warning, got empty"
        # Verify every character is ASCII (ord < 128)
        for i, char in enumerate(stderr_output):
            if ord(char) >= 128:
                print(
                    f"FAIL: parse_blocking_count_divergence_warning_ascii_only: "
                    f"non-ASCII character at position {i}: {char!r} (ord={ord(char)})",
                    file=sys.stderr,
                )
                return False
        print(
            "PASS: parse_blocking_count divergence warning is ASCII-only (no mojibake)"
        )
        return True

    if not test_parse_blocking_count_divergence_warning_ascii_only():
        errors += 1

    # ---------------------------------------------------------------------------
    # _load_root_from_overview: importable from _review_common
    # ---------------------------------------------------------------------------

    # Confirm the function is importable (not AttributeError); do not exercise behaviour
    assert callable(_load_root_from_overview), (
        "_load_root_from_overview should be callable"
    )
    print("PASS: _load_root_from_overview importable from _review_common")

    # ---------------------------------------------------------------------------
    # detect_resume_round
    # ---------------------------------------------------------------------------

    # reviews_dir does not exist -> None
    result = detect_resume_round(Path("/tmp/__nx_detect_resume__"), "plan")
    assert result is None, f"Got {result}"
    print("PASS: detect_resume_round nonexistent dir -> None")

    # no files -> None
    with _test_helpers.safe_temp_dir() as tmpdir:
        result = detect_resume_round(Path(tmpdir), "plan")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round empty dir -> None")

    # per-batch round-1 files + holistic round-1 file -> None
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-r1.md").write_text("x")
        result = detect_resume_round(reviews, "plan")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1 + holistic r1 -> None")

    # per-batch round-1 files + no holistic round-1 -> 1
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-02-wire-r1.md").write_text("x")
        result = detect_resume_round(reviews, "plan")
        assert result == 1, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1 + no holistic -> 1")

    # per-batch rounds 1 and 2 + holistic round-1 + no holistic round-2 -> 2
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-01-setup-r2.md").write_text("x")
        (reviews / "20260418-001400-plan-review-r1.md").write_text("x")  # holistic r1
        result = detect_resume_round(reviews, "plan")
        assert result == 2, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1+r2, holistic r1 only -> 2")

    # per-batch round 2 partial (some at r2, some at r1) + no holistic r2 -> 2
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-01-setup-r2.md").write_text("x")
        (reviews / "20260418-001400-plan-review-02-wire-r1.md").write_text("x")
        # no holistic at any round
        result = detect_resume_round(reviews, "plan")
        assert result == 2, f"Got {result}"
        print(
            "PASS: detect_resume_round partial r2 batches, no holistic -> 2 (highest batch round)"
        )

    # type isolation: plan per-batch files don't affect code detect_resume_round
    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews = tmpdir
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        result = detect_resume_round(reviews, "code")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round type isolation: plan files ignored for code")

    # ---------------------------------------------------------------------------
    # bulk_files_with_diff
    # ---------------------------------------------------------------------------

    # Test A — file with small diff uses DIFF delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(
            ["git", "-C", str(repo), "init"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "T"],
            check=True,
            capture_output=True,
        )
        src = repo / "src"
        src.mkdir()
        (src / "a.py").write_text("x\n" * 2000, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        with open(src / "a.py", "a", encoding="utf-8") as fh:
            fh.write("y\n" * 10)
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "small change"],
            check=True,
            capture_output=True,
        )
        result = bulk_files_with_diff([repo / "src" / "a.py"], start_sha, repo, 0.25)
        assert "--- DIFF:" in result, f"expected DIFF delimiter, got: {result[:200]!r}"
        assert "--- FILE: " not in result, (
            f"expected no FILE delimiter, got: {result[:200]!r}"
        )
        assert start_sha[:8] in result, (
            f"expected start_sha[:8] in result, got: {result[:200]!r}"
        )
        print("PASS: bulk_files_with_diff small diff -> DIFF delimiter")

    # Test B — file with large diff uses FILE delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(
            ["git", "-C", str(repo), "init"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "T"],
            check=True,
            capture_output=True,
        )
        src = repo / "src"
        src.mkdir()
        (src / "b.py").write_text("x\n" * 20, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/b.py"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        (src / "b.py").write_text("y\n" * 20, encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/b.py"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "large change"],
            check=True,
            capture_output=True,
        )
        result = bulk_files_with_diff([repo / "src" / "b.py"], start_sha, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter, got: {result[:200]!r}"
        assert "--- DIFF:" not in result, (
            f"expected no DIFF delimiter, got: {result[:200]!r}"
        )
        print("PASS: bulk_files_with_diff large diff -> FILE delimiter")

    # Test C — unchanged file (empty diff) uses FILE delimiter
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(
            ["git", "-C", str(repo), "init"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "T"],
            check=True,
            capture_output=True,
        )
        src = repo / "src"
        src.mkdir()
        (src / "c.py").write_text("hello\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/c.py"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        (src / "other.py").write_text("z\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/other.py"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "other file"],
            check=True,
            capture_output=True,
        )
        result = bulk_files_with_diff([repo / "src" / "c.py"], start_sha, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter, got: {result[:200]!r}"
        print(
            "PASS: bulk_files_with_diff empty diff (unchanged file) -> FILE delimiter"
        )

    # Test D — non-existent file is skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(
            ["git", "-C", str(repo), "init"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "T"],
            check=True,
            capture_output=True,
        )
        (repo / "dummy.py").write_text("x\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "dummy.py"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        result = bulk_files_with_diff([repo / "nonexistent.py"], start_sha, repo, 0.25)
        assert result == "", f"expected empty string, got: {result!r}"
        print("PASS: bulk_files_with_diff non-existent file skipped")

    # Test E — git diff failure falls back to full file
    with _test_helpers.safe_temp_dir() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(
            ["git", "-C", str(repo), "init"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "t@t.com"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "T"],
            check=True,
            capture_output=True,
        )
        src = repo / "src"
        src.mkdir()
        (src / "a.py").write_text("hello\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-m", "init"],
            check=True,
            capture_output=True,
        )
        result = bulk_files_with_diff(
            [repo / "src" / "a.py"], "deadbeef" * 5, repo, 0.25
        )
        assert "--- FILE: " in result, (
            f"expected FILE delimiter fallback, got: {result[:200]!r}"
        )
        assert "--- DIFF:" not in result, (
            f"expected no DIFF delimiter, got: {result[:200]!r}"
        )
        print("PASS: bulk_files_with_diff git diff failure -> FILE delimiter fallback")

    # _read_for_bulk: code-cell-only notebook -> source concatenated with \n\n
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "code_only.ipynb"
        notebook_path.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "code", "source": "print('hello')"},
                        {"cell_type": "code", "source": "x = 42"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "print('hello')\n\nx = 42", f"Got: {result!r}"
        print("PASS: _read_for_bulk code-cell-only notebook")

    # _read_for_bulk: markdown-cell-only notebook
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "md_only.ipynb"
        notebook_path.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "markdown", "source": "# Title"},
                        {"cell_type": "markdown", "source": "Some text"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "# Title\n\nSome text", f"Got: {result!r}"
        print("PASS: _read_for_bulk markdown-cell-only notebook")

    # _read_for_bulk: mixed code + markdown
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "mixed.ipynb"
        notebook_path.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "markdown", "source": "# Section"},
                        {"cell_type": "code", "source": "x = 1"},
                        {"cell_type": "markdown", "source": "## Subsection"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "# Section\n\nx = 1\n\n## Subsection", f"Got: {result!r}"
        print("PASS: _read_for_bulk mixed code + markdown")

    # _read_for_bulk: cell with source as list of strings
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "list_source.ipynb"
        notebook_path.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "code", "source": ["line1", "line2", "line3"]},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "line1line2line3", f"Got: {result!r}"
        print("PASS: _read_for_bulk cell with list-form source")

    # _read_for_bulk: cell with source as single string
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "str_source.ipynb"
        notebook_path.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "code", "source": "x = 42\ny = 43"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "x = 42\ny = 43", f"Got: {result!r}"
        print("PASS: _read_for_bulk cell with string-form source")

    # _read_for_bulk: raw cell present -> skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        notebook_path = Path(tmpdir) / "with_raw.ipynb"
        notebook_path.write_text(
            json.dumps(
                {
                    "cells": [
                        {"cell_type": "code", "source": "x = 1"},
                        {"cell_type": "raw", "source": "ignore this"},
                        {"cell_type": "markdown", "source": "y"},
                    ]
                }
            ),
            encoding="utf-8",
        )
        result = _read_for_bulk(notebook_path)
        assert result == "x = 1\n\ny", f"Got: {result!r}"
        assert "ignore this" not in result
        print("PASS: _read_for_bulk raw cell skipped")

    # _read_for_bulk: non-.ipynb file (e.g. .py)
    with _test_helpers.safe_temp_dir() as tmpdir:
        py_path = Path(tmpdir) / "code.py"
        py_path.write_text("def hello():\n    return 42", encoding="utf-8")
        result = _read_for_bulk(py_path)
        assert result == "def hello():\n    return 42", f"Got: {result!r}"
        print("PASS: _read_for_bulk .py file returns text as-is")

    # _read_for_bulk: malformed JSON .ipynb -> returns "" with stderr warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        import io as _io
        import contextlib as _cl

        notebook_path = Path(tmpdir) / "bad.ipynb"
        notebook_path.write_text("{bad json", encoding="utf-8")
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            result = _read_for_bulk(notebook_path)
        assert result == "", f"Expected empty string, got: {result!r}"
        stderr_out = _err_buf.getvalue()
        assert "[_read_for_bulk]" in stderr_out, (
            f"Warning should contain [_read_for_bulk]: {stderr_out!r}"
        )
        assert "warning" in stderr_out.lower(), (
            f"Warning should contain 'warning': {stderr_out!r}"
        )
        print("PASS: _read_for_bulk malformed JSON -> empty string + stderr warning")

    # write_review_file: UTC-timestamp regression test (frozen clock)
    import datetime as _dt

    with _test_helpers.safe_temp_dir() as tmpdir:
        reviews_dir = Path(tmpdir)
        frozen_dt = _dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=_dt.timezone.utc)
        with patch("_review_common.datetime") as mock_dt_module:
            mock_dt_module.now.return_value = frozen_dt
            mock_dt_module.timezone = _dt.timezone
            # Test case 1: code review, no scope
            path = write_review_file(reviews_dir, "code", 1, "content")
            assert "20260102-030405" in path.name, (
                f"Expected UTC timestamp 20260102-030405, got: {path.name}"
            )
            assert "code-review-r1" in path.name
            print("PASS: write_review_file UTC timestamp (code, no scope)")

            # Test case 2: code review with scope="holistic"
            path = write_review_file(
                reviews_dir, "code", 1, "content", scope="holistic"
            )
            assert "20260102-030405" in path.name
            assert "code-review-r1" in path.name
            assert "holistic" not in path.name
            print("PASS: write_review_file UTC timestamp (code, scope=holistic)")

            # Test case 3: code review with batch scope
            path = write_review_file(
                reviews_dir, "code", 1, "content", scope="01-foundation"
            )
            assert "20260102-030405" in path.name
            assert "code-review-01-foundation-r1" in path.name
            print("PASS: write_review_file UTC timestamp (code, scope=batch)")

            # Test case 4: discussion review (scope ignored)
            path = write_review_file(reviews_dir, "discussion", 1, "content")
            assert "20260102-030405" in path.name
            assert "discussion-review-r1" in path.name
            print("PASS: write_review_file UTC timestamp (discussion)")

            # Test case 5: plan review with batch scope
            path = write_review_file(
                reviews_dir, "plan", 1, "content", scope="01-foundation"
            )
            assert "20260102-030405" in path.name
            assert "plan-review-01-foundation-r1" in path.name
            print("PASS: write_review_file UTC timestamp (plan, scope=batch)")

    # Test: write_review_file holistic naming (#316)
    # Regression: ensure "-holistic-review-" substring never appears in filenames.
    # scope=None, scope="holistic", and scope="01-foo" should produce the correct patterns.
    try:
        with _test_helpers.safe_temp_dir() as tmpdir:
            reviews_dir = Path(tmpdir)

            # Case 1: scope=None (holistic)
            path1 = write_review_file(reviews_dir, "code", 1, "content", scope=None)
            assert "-holistic-review-" not in path1.name, (
                f"scope=None should not contain '-holistic-review-': {path1.name}"
            )
            assert "code-review-r1" in path1.name, (
                f"scope=None should have code-review-r1 pattern: {path1.name}"
            )

            # Case 2: scope="holistic" (explicit holistic)
            path2 = write_review_file(
                reviews_dir, "code", 1, "content", scope="holistic"
            )
            assert "-holistic-review-" not in path2.name, (
                f"scope='holistic' should not contain '-holistic-review-': {path2.name}"
            )
            assert "code-review-r1" in path2.name, (
                f"scope='holistic' should have code-review-r1 pattern: {path2.name}"
            )

            # Case 3: scope="01-foo" (per-batch)
            path3 = write_review_file(reviews_dir, "code", 1, "content", scope="01-foo")
            assert "-holistic-review-" not in path3.name, (
                f"scope='01-foo' should not contain '-holistic-review-': {path3.name}"
            )
            assert "code-review-01-foo-r1" in path3.name, (
                f"scope='01-foo' should have code-review-01-foo-r1 pattern: {path3.name}"
            )

            print("PASS: write_review_file holistic naming regression (#316)")
    except AssertionError as exc:
        print(f"FAIL: write_review_file holistic naming: {exc}", file=sys.stderr)
        errors += 1
    except Exception as exc:
        print(
            f"FAIL: write_review_file holistic naming (unexpected {type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        errors += 1

    # find_active_slug glob fallback: one .active file -> returns slug
    try:
        with _test_helpers.safe_temp_dir() as tmp:
            hub_root = Path(tmp)
            mill_dir = hub_root / "_mill"
            mill_dir.mkdir(parents=True)
            (mill_dir / "my-task.active").write_text("", encoding="utf-8")

            cfg = {}
            with patch(
                "_review_common._marker.slug_from_branch",
                side_effect=_marker.MarkerError("test"),
            ):
                result = find_active_slug(hub_root, Path(tmp) / "wiki", cfg)

            assert result == "my-task", f"Expected 'my-task', got {result!r}"
            print(
                "PASS: find_active_slug glob fallback — one .active file -> 'my-task'"
            )
    except AssertionError as exc:
        print(f"FAIL: find_active_slug glob fallback one file: {exc}", file=sys.stderr)
        errors += 1
    except Exception as exc:
        print(
            f"FAIL: find_active_slug glob fallback one file (unexpected {type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        errors += 1

    # find_active_slug glob fallback: multiple .active files -> ReviewError
    try:
        with _test_helpers.safe_temp_dir() as tmp:
            hub_root = Path(tmp)
            mill_dir = hub_root / "_mill"
            mill_dir.mkdir(parents=True)
            (mill_dir / "task-a.active").write_text("", encoding="utf-8")
            (mill_dir / "task-b.active").write_text("", encoding="utf-8")

            cfg = {}
            with patch(
                "_review_common._marker.slug_from_branch",
                side_effect=_marker.MarkerError("test"),
            ):
                try:
                    find_active_slug(hub_root, Path(tmp) / "wiki", cfg)
                    print(
                        "FAIL: find_active_slug glob fallback multiple files: expected ReviewError",
                        file=sys.stderr,
                    )
                    errors += 1
                except ReviewError as e:
                    if "use --slug" not in str(e):
                        print(
                            f"FAIL: find_active_slug glob fallback multiple files: expected 'use --slug' in error, got {e!r}",
                            file=sys.stderr,
                        )
                        errors += 1
                    else:
                        print(
                            "PASS: find_active_slug glob fallback — multiple .active files -> ReviewError with 'use --slug'"
                        )
    except Exception as exc:
        if not isinstance(exc, AssertionError):
            print(
                f"FAIL: find_active_slug glob fallback multiple files (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
            errors += 1

    # find_active_slug glob fallback: no _mill/ dir -> ReviewError
    try:
        with _test_helpers.safe_temp_dir() as tmp:
            hub_root = Path(tmp)
            # Do NOT create _mill/

            cfg = {}
            with patch(
                "_review_common._marker.slug_from_branch",
                side_effect=_marker.MarkerError("test"),
            ):
                try:
                    find_active_slug(hub_root, Path(tmp) / "wiki", cfg)
                    print(
                        "FAIL: find_active_slug glob fallback no _mill: expected ReviewError",
                        file=sys.stderr,
                    )
                    errors += 1
                except ReviewError:
                    print(
                        "PASS: find_active_slug glob fallback — no _mill/ dir -> ReviewError"
                    )
    except AssertionError as exc:
        print(f"FAIL: find_active_slug glob fallback no _mill: {exc}", file=sys.stderr)
        errors += 1
    except Exception as exc:
        if not isinstance(exc, (ReviewError, AssertionError)):
            print(
                f"FAIL: find_active_slug glob fallback no _mill (unexpected {type(exc).__name__}): {exc}",
                file=sys.stderr,
            )
            errors += 1

    # ---------------------------------------------------------------------------
    # ReviewResult.nit_count field
    # ---------------------------------------------------------------------------

    # nit_count defaults to 0
    result = ReviewResult(type="code", round=1, verdict="APPROVE")
    assert result.nit_count == 0, (
        f"Expected nit_count=0 by default, got {result.nit_count}"
    )
    print("PASS: ReviewResult nit_count defaults to 0")

    # to_dict() includes nit_count
    result_dict = result.to_dict()
    assert "nit_count" in result_dict, (
        f"nit_count not in to_dict(): {result_dict.keys()}"
    )
    assert result_dict["nit_count"] == 0, (
        f"Expected to_dict()['nit_count']=0, got {result_dict['nit_count']}"
    )
    print("PASS: ReviewResult.to_dict() includes nit_count field")

    # nit_count non-default value round-trips
    result_with_nits = ReviewResult(
        type="code", round=1, verdict="APPROVE", nit_count=5
    )
    assert result_with_nits.nit_count == 5, (
        f"Expected nit_count=5, got {result_with_nits.nit_count}"
    )
    result_dict = result_with_nits.to_dict()
    assert result_dict["nit_count"] == 5, (
        f"Expected to_dict()['nit_count']=5, got {result_dict['nit_count']}"
    )
    print(
        "PASS: ReviewResult nit_count non-default value round-trips through to_dict()"
    )

    # ---------------------------------------------------------------------------
    # parse_verdict: unfenced fallback line
    # ---------------------------------------------------------------------------

    # parse_verdict: unfenced verdict line with leading whitespace -- GAPS_FOUND is a historical v1
    # discussion-review value, accepted for archive readability but normalised to REQUEST_CHANGES.
    raw = "  verdict: GAPS_FOUND\n"
    assert parse_verdict(raw) == "REQUEST_CHANGES"
    print(
        "PASS: parse_verdict unfenced verdict line with leading whitespace "
        "normalises GAPS_FOUND to REQUEST_CHANGES"
    )

    # parse_verdict: fenced block still works as primary path
    raw = "# Review: X\n\n```yaml\nverdict: APPROVE\n```\n"
    assert parse_verdict(raw) == "APPROVE"
    print("PASS: parse_verdict fenced block (primary path)")

    # parse_verdict: no verdict at all (no fenced, no unfenced) raises ReviewError
    try:
        parse_verdict("No verdict anywhere in this text.")
        print(
            "FAIL: parse_verdict: expected ReviewError for no verdict", file=sys.stderr
        )
        errors += 1
    except ReviewError:
        print("PASS: parse_verdict no verdict -> ReviewError")

    # parse_verdict: invalid value inside fenced block raises even with unfenced fallback available
    try:
        raw = "```yaml\nverdict: INVALID_VALUE\n```\n\nverdict: APPROVE\n"
        parse_verdict(raw)
        print(
            "FAIL: parse_verdict: expected ReviewError for invalid fenced value",
            file=sys.stderr,
        )
        errors += 1
    except ReviewError as e:
        assert "INVALID_VALUE" in str(e)
        print("PASS: parse_verdict invalid fenced value raises (fallback not used)")

    # ---------------------------------------------------------------------------
    # _read_for_bulk and bulk_files: directory handling
    # ---------------------------------------------------------------------------

    # _read_for_bulk: directory path returns empty string with warning
    with _test_helpers.safe_temp_dir() as tmpdir:
        import io as _io
        import contextlib as _cl

        tmpdir_path = Path(tmpdir)
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            result = _read_for_bulk(subdir)
        assert result == "", f"Expected empty string for directory, got {result!r}"
        stderr_out = _err_buf.getvalue()
        assert "is a directory" in stderr_out, (
            f"Expected 'is a directory' warning, got {stderr_out!r}"
        )
        print("PASS: _read_for_bulk directory path -> empty string + warning")

    # bulk_files: real file and directory in path list -> file included, directory skipped
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)
        real_file = tmpdir_path / "real.py"
        real_file.write_text("content")
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()
        result = bulk_files([real_file, subdir])
        assert "real.py" in result and "content" in result, (
            f"File should be bulked: {result!r}"
        )
        assert "--- FILE:" in result, f"FILE delimiter expected: {result!r}"
        print("PASS: bulk_files directory skipped, file included")

    # ---------------------------------------------------------------------------
    # tool-use mode: artefact omits inlined bodies, build_tool_rule grants tools
    # ---------------------------------------------------------------------------

    # tool-use reviewer must NOT inline source file content (sentinel line must be absent)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a fixture source file with a unique sentinel line
        source_file = tmpdir_path / "source.py"
        sentinel_line = "UNIQUE_SENTINEL_LINE_FOR_TEST_xyz123"
        source_file.write_text(
            f"def foo():\n    # {sentinel_line}\n    return 42\n", encoding="utf-8"
        )

        # Create overview and batch files (empty for this test)
        overview = tmpdir_path / "overview.md"
        overview.write_text("# Overview", encoding="utf-8")

        batch_file = tmpdir_path / "01-batch.md"
        batch_file.write_text("# Batch 1", encoding="utf-8")

        # Build artefact section in tool-use mode (as prepare() does)
        artefact = _review_code._build_artefact_section(
            reviewer_mode="tool-use",
            overview_path=overview,
            batch_files=[batch_file],
            source_files=[source_file],
            ancestors_on_disk=[],
            deletes_union=set(),
        )

        # Also build the tool-use TOOL_RULE (as the template would)
        tool_rule = build_tool_rule("tool-use")

        # Verify: tool-use TOOL_RULE grants tools
        assert "MAY use Read, Grep, and Glob" in tool_rule, (
            f"Expected tool-use TOOL_RULE to grant tools, got: {tool_rule!r}"
        )

        # Verify: source file PATH is present in artefact
        assert str(source_file) in artefact, (
            f"Source file path not in artefact: {artefact!r}"
        )

        # Verify: sentinel line (the body content) is NOT present in artefact
        assert sentinel_line not in artefact, (
            f"Sentinel line should NOT be inlined in tool-use mode, but found it: {artefact!r}"
        )

        print("PASS: tool-use omits bulked bodies and build_tool_rule grants tools")

    # ---------------------------------------------------------------------------
    # bulk mode: artefact inlines source content, build_tool_rule forbids tools
    # ---------------------------------------------------------------------------

    # bulk reviewer must inline source file content (sentinel line must be present)
    with _test_helpers.safe_temp_dir() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Create a fixture source file with a unique sentinel line
        source_file = tmpdir_path / "source.py"
        sentinel_line = "UNIQUE_SENTINEL_LINE_FOR_BULK_TEST_abc789"
        source_file.write_text(
            f"def bar():\n    # {sentinel_line}\n    return 99\n", encoding="utf-8"
        )

        # Create overview and batch files (empty for this test)
        overview = tmpdir_path / "overview.md"
        overview.write_text("# Overview", encoding="utf-8")

        batch_file = tmpdir_path / "01-batch.md"
        batch_file.write_text("# Batch 1", encoding="utf-8")

        # Build artefact section in bulk mode (as prepare() does)
        artefact = _review_code._build_artefact_section(
            reviewer_mode="bulk",
            overview_path=overview,
            batch_files=[batch_file],
            source_files=[source_file],
            ancestors_on_disk=[],
            deletes_union=set(),
        )

        # Also build the bulk TOOL_RULE (as the template would)
        tool_rule = build_tool_rule("bulk")

        # Verify: bulk TOOL_RULE forbids tools
        assert "Do NOT request tool calls" in tool_rule, (
            f"Expected bulk TOOL_RULE to forbid tools, got: {tool_rule!r}"
        )

        # Verify: sentinel line (the body content) IS present in bulk mode
        assert sentinel_line in artefact, (
            f"Sentinel line should be inlined in bulk mode, but missing from: {artefact!r}"
        )

        # Verify: source file path is also present
        assert str(source_file) in artefact, (
            f"Source file path not in artefact: {artefact!r}"
        )

        print("PASS: bulk inlines source content and build_tool_rule forbids tools")

    # ---------------------------------------------------------------------------
    # resolve_large_prompt_timeout
    # ---------------------------------------------------------------------------

    # resolve_large_prompt_timeout: under threshold -> returns default
    cfg = {
        "roles": {
            "plan-review": {
                "holistic": {
                    "large_prompt": {
                        "threshold_ktok": 100,
                        "timeout": 3600,
                    }
                }
            }
        }
    }
    prompt = "x" * 50000  # ~12 ktok
    timeout = resolve_large_prompt_timeout(
        prompt, cfg, "plan-review", "holistic", default_timeout=1800
    )
    assert timeout == 1800, f"Expected default 1800, got {timeout}"
    print("PASS: resolve_large_prompt_timeout under threshold -> default timeout")

    # resolve_large_prompt_timeout: over threshold, key set -> returns override
    cfg = {
        "roles": {
            "plan-review": {
                "holistic": {
                    "large_prompt": {
                        "threshold_ktok": 100,
                        "timeout": 3600,
                    }
                }
            }
        }
    }
    prompt = "x" * 500000  # ~125 ktok
    timeout = resolve_large_prompt_timeout(
        prompt, cfg, "plan-review", "holistic", default_timeout=1800
    )
    assert timeout == 3600, f"Expected override 3600, got {timeout}"
    print(
        "PASS: resolve_large_prompt_timeout over threshold + timeout key set -> override"
    )

    # resolve_large_prompt_timeout: over threshold, key not set -> returns default
    cfg = {
        "roles": {
            "plan-review": {
                "holistic": {
                    "large_prompt": {
                        "threshold_ktok": 100,
                    }
                }
            }
        }
    }
    prompt = "x" * 500000  # ~125 ktok
    timeout = resolve_large_prompt_timeout(
        prompt, cfg, "plan-review", "holistic", default_timeout=1800
    )
    assert timeout == 1800, f"Expected default 1800, got {timeout}"
    print(
        "PASS: resolve_large_prompt_timeout over threshold but key not set -> default"
    )

    # resolve_large_prompt_timeout: no large_prompt key -> returns default
    cfg = {"roles": {"plan-review": {"holistic": {}}}}
    prompt = "x" * 500000
    timeout = resolve_large_prompt_timeout(
        prompt, cfg, "plan-review", "holistic", default_timeout=1800
    )
    assert timeout == 1800, f"Expected default 1800, got {timeout}"
    print("PASS: resolve_large_prompt_timeout no large_prompt key -> default")

    # ---------------------------------------------------------------------------
    # parse_blocking_count / _warn_if_prose_diverges: #489 clean review tests
    # ---------------------------------------------------------------------------

    # parse_blocking_count: zero headings suppress divergence warning
    try:
        import contextlib
        import io

        raw = (
            "### Overview\n"
            "This is a clean review with no findings.\n"
            "There are 1 gap in the discussion.\n"
            "verdict: GAPS_FOUND\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="GAP")
        if count != 0:
            print(
                f"FAIL: parse_blocking_count zero headings: expected heading_count 0, got {count}",
                file=sys.stderr,
            )
            errors += 1
        else:
            stderr = buf.getvalue()
            if "diverges from prose count" in stderr:
                print(
                    f"FAIL: parse_blocking_count zero headings: expected no divergence warning, got: {stderr!r}",
                    file=sys.stderr,
                )
                errors += 1
            else:
                print(
                    "PASS: parse_blocking_count zero headings suppresses divergence warning"
                )
    except Exception as exc:
        print(f"FAIL: parse_blocking_count zero headings: {exc}", file=sys.stderr)
        errors += 1

    # parse_blocking_count: one heading + verdict line, diverging prose count
    try:
        import contextlib
        import io

        raw = (
            "### [GAP] issue one\n"
            "There are 2 gaps in the discussion.\n"
            "verdict: GAPS_FOUND\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="GAP")
        if count != 1:
            print(
                f"FAIL: parse_blocking_count one heading + verdict: expected heading_count 1, got {count}",
                file=sys.stderr,
            )
            errors += 1
        else:
            stderr = buf.getvalue()
            if "heading count 1 diverges from prose count 2" not in stderr:
                print(
                    f"FAIL: parse_blocking_count one heading + verdict: expected divergence warning (verdict line not inflating count), got: {stderr!r}",
                    file=sys.stderr,
                )
                errors += 1
            else:
                print(
                    "PASS: parse_blocking_count one heading + verdict: verdict line filtered from prose count"
                )
    except Exception as exc:
        print(
            f"FAIL: parse_blocking_count one heading + verdict: {exc}", file=sys.stderr
        )
        errors += 1

    # parse_blocking_count: non-zero headings still emit divergence warning
    try:
        import contextlib
        import io

        raw = (
            "### [GAP] issue one\n"
            "### [GAP] issue two\n"
            "Three gaps were identified in the discussion.\n"
        )
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            count = parse_blocking_count(raw, severity="GAP")
        if count != 2:
            print(
                f"FAIL: parse_blocking_count with headings: expected heading_count 2, got {count}",
                file=sys.stderr,
            )
            errors += 1
        else:
            stderr = buf.getvalue()
            if "heading count 2 diverges from prose count 3" not in stderr:
                print(
                    f"FAIL: parse_blocking_count with headings: expected divergence warning, got: {stderr!r}",
                    file=sys.stderr,
                )
                errors += 1
            else:
                print(
                    "PASS: parse_blocking_count with headings still warns on divergence"
                )
    except Exception as exc:
        print(f"FAIL: parse_blocking_count with headings: {exc}", file=sys.stderr)
        errors += 1

    # ---------------------------------------------------------------------------
    # parse_moves
    # ---------------------------------------------------------------------------

    # Single pair in multi-line sub-bullet form.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Moves:**\n  - `old/a.py` -> `new/a.py`\n",
            encoding="utf-8",
        )
        result = parse_moves(batch)
        assert result == [("old/a.py", "new/a.py")], f"Got {result}"
        print("PASS: parse_moves single pair returns list with one tuple")

    # Multiple pairs in multi-line sub-bullet form.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Moves:**\n"
            "  - `src/alpha.py` -> `dst/alpha.py`\n"
            "  - `src/beta.py` -> `dst/beta.py`\n",
            encoding="utf-8",
        )
        result = parse_moves(batch)
        assert result == [
            ("src/alpha.py", "dst/alpha.py"),
            ("src/beta.py", "dst/beta.py"),
        ], f"Got {result}"
        print("PASS: parse_moves multiple pairs returns all tuples in order")

    # Inline 'none' (case-insensitive) returns empty list.
    for sentinel in ("none", "None", "NONE", " none"):
        with _test_helpers.safe_temp_dir() as tmpdir:
            batch = Path(tmpdir) / "batch.md"
            batch.write_text(f"- **Moves:** {sentinel}\n", encoding="utf-8")
            result = parse_moves(batch)
            assert result == [], f"Got {result} for sentinel {sentinel!r}"
        print(f"PASS: parse_moves inline '{sentinel.strip()}' sentinel returns []")

    # Moves field mixed among other card fields (Context/Edits/Creates/Deletes).
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "### Card 1\n\n"
            "- **Context:** `plugins/mill/scripts/_review_common.py`\n"
            "- **Edits:** `plugins/mill/scripts/_review_plan.py`\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:**\n"
            "  - `old/seam.py` -> `new/seam.py`\n"
            "- **Requirements:** ...\n",
            encoding="utf-8",
        )
        result = parse_moves(batch)
        assert result == [("old/seam.py", "new/seam.py")], f"Got {result}"
        print("PASS: parse_moves Moves field mixed among other card fields")

    # Malformed sub-bullet (missing arrow) is skipped without raising.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Moves:**\n"
            "  - `only-one-path.py`\n"
            "  - `src/good.py` -> `dst/good.py`\n",
            encoding="utf-8",
        )
        result = parse_moves(batch)
        # The malformed bullet (only one backtick path) is silently skipped.
        assert result == [("src/good.py", "dst/good.py")], f"Got {result}"
        print(
            "PASS: parse_moves malformed sub-bullet (one path only) is skipped without raising"
        )

    # Malformed sub-bullet (two paths but no arrow) is skipped without raising.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Moves:**\n  - `src/x.py` `dst/x.py`\n  - `src/y.py` -> `dst/y.py`\n",
            encoding="utf-8",
        )
        result = parse_moves(batch)
        assert result == [("src/y.py", "dst/y.py")], f"Got {result}"
        print(
            "PASS: parse_moves malformed sub-bullet (no arrow) is skipped without raising"
        )

    # Duplicate pairs across two Moves: headers are deduplicated, first-seen order preserved.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Moves:**\n"
            "  - `src/a.py` -> `dst/a.py`\n"
            "- **Moves:**\n"
            "  - `src/a.py` -> `dst/a.py`\n"
            "  - `src/b.py` -> `dst/b.py`\n",
            encoding="utf-8",
        )
        result = parse_moves(batch)
        assert result == [
            ("src/a.py", "dst/a.py"),
            ("src/b.py", "dst/b.py"),
        ], f"Got {result}"
        print(
            "PASS: parse_moves duplicate pairs deduplicated, first-seen order preserved"
        )

    # ---------------------------------------------------------------------------
    # parse_deletes
    # ---------------------------------------------------------------------------

    # Single-line inline form.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Deletes:** `a`, `b`\n", encoding="utf-8")
        result = parse_deletes(batch)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: parse_deletes single-line inline form returns set of tokens")

    # Multi-line sub-bullet form.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Deletes:**\n  - `old/a.py`\n  - `old/b.py`\n",
            encoding="utf-8",
        )
        result = parse_deletes(batch)
        assert result == {"old/a.py", "old/b.py"}, f"Got {result}"
        print("PASS: parse_deletes multi-line sub-bullet form returns set of tokens")

    # 'none' sentinel (case-insensitive) returns empty set.
    for sentinel in ("none", "None", "NONE"):
        with _test_helpers.safe_temp_dir() as tmpdir:
            batch = Path(tmpdir) / "batch.md"
            batch.write_text(f"- **Deletes:** {sentinel}\n", encoding="utf-8")
            result = parse_deletes(batch)
            assert result == set(), f"Got {result} for sentinel {sentinel!r}"
        print(f"PASS: parse_deletes '{sentinel}' sentinel returns empty set")

    # Deletes field mixed among other card fields (Context/Edits/Creates/Moves).
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "### Card 1\n\n"
            "- **Context:** `plugins/mill/scripts/_review_common.py`\n"
            "- **Edits:** `plugins/mill/scripts/_review_plan.py`\n"
            "- **Creates:** none\n"
            "- **Deletes:** `old/seam.py`\n"
            "- **Moves:** none\n"
            "- **Requirements:** ...\n",
            encoding="utf-8",
        )
        result = parse_deletes(batch)
        assert result == {"old/seam.py"}, f"Got {result}"
        print("PASS: parse_deletes Deletes field mixed among other card fields")

    # Malformed sub-bullet (no backtick path) is tolerated without raising.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Deletes:**\n  - no-backticks-here\n  - `good.py`\n",
            encoding="utf-8",
        )
        result = parse_deletes(batch)
        # The malformed bullet (no backtick-quoted token) contributes nothing.
        assert result == {"good.py"}, f"Got {result}"
        print(
            "PASS: parse_deletes malformed sub-bullet (no backtick path) tolerated without raising"
        )

    # ---------------------------------------------------------------------------
    # compute_moves_union
    # ---------------------------------------------------------------------------

    # Non-existent plan_dir returns (set(), set()).
    with _test_helpers.safe_temp_dir() as tmpdir:
        sources, targets = compute_moves_union(Path(tmpdir) / "nonexistent")
        assert sources == set() and targets == set(), f"Got ({sources!r}, {targets!r})"
        print("PASS: compute_moves_union nonexistent plan_dir returns (set(), set())")

    # Empty plan_dir (no batch files) returns (set(), set()).
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        sources, targets = compute_moves_union(plan_dir)
        assert sources == set() and targets == set(), f"Got ({sources!r}, {targets!r})"
        print("PASS: compute_moves_union empty plan_dir returns (set(), set())")

    # Single batch file with one move pair: correct source/target split.
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Moves:**\n  - `old/x.py` -> `new/x.py`\n",
            encoding="utf-8",
        )
        sources, targets = compute_moves_union(plan_dir)
        assert sources == {"old/x.py"}, f"Got sources={sources!r}"
        assert targets == {"new/x.py"}, f"Got targets={targets!r}"
        print(
            "PASS: compute_moves_union single batch returns correct source/target split"
        )

    # Two batch files: sources and targets accumulate into the same sets.
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Moves:**\n"
            "  - `old/a.py` -> `new/a.py`\n"
            "  - `old/b.py` -> `new/b.py`\n",
            encoding="utf-8",
        )
        (plan_dir / "02-wire.md").write_text(
            "- **Moves:**\n  - `old/c.py` -> `new/c.py`\n",
            encoding="utf-8",
        )
        sources, targets = compute_moves_union(plan_dir)
        assert sources == {"old/a.py", "old/b.py", "old/c.py"}, (
            f"Got sources={sources!r}"
        )
        assert targets == {"new/a.py", "new/b.py", "new/c.py"}, (
            f"Got targets={targets!r}"
        )
        print(
            "PASS: compute_moves_union two batch files aggregates sources and targets"
        )

    # 'none' sentinel filtered: batch with Moves: none contributes nothing.
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text("- **Moves:** none\n", encoding="utf-8")
        (plan_dir / "02-wire.md").write_text(
            "- **Moves:**\n  - `old/z.py` -> `new/z.py`\n",
            encoding="utf-8",
        )
        sources, targets = compute_moves_union(plan_dir)
        assert sources == {"old/z.py"}, f"Got sources={sources!r}"
        assert targets == {"new/z.py"}, f"Got targets={targets!r}"
        print("PASS: compute_moves_union 'none' batch contributes nothing to sets")

    # 00-overview.md is excluded even when it contains Moves: content.
    with _test_helpers.safe_temp_dir() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "00-overview.md").write_text(
            "- **Moves:**\n  - `overview-src.py` -> `overview-dst.py`\n",
            encoding="utf-8",
        )
        (plan_dir / "01-setup.md").write_text(
            "- **Moves:**\n  - `real-src.py` -> `real-dst.py`\n",
            encoding="utf-8",
        )
        sources, targets = compute_moves_union(plan_dir)
        assert sources == {"real-src.py"}, f"Got sources={sources!r}"
        assert targets == {"real-dst.py"}, f"Got targets={targets!r}"
        print("PASS: compute_moves_union 00-overview.md excluded")

    # ---------------------------------------------------------------------------
    # Regression: parse_batch_refs must NOT return tokens from Moves: bullets
    # ---------------------------------------------------------------------------

    # A Moves: bullet uses two-path grammar (`src` -> `dst`) which is incompatible with the reads-not-backtick-path validator rule (rejects >1 backtick per sub-bullet when processed by parse_batch_refs).
    # parse_batch_refs must stay blind to Moves: headers so that move tokens never contaminate the Context/Edits/Creates/Deletes bulk.
    with _test_helpers.safe_temp_dir() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Context:** `ctx/file.py`\n"
            "- **Edits:** `edit/file.py`\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:**\n"
            "  - `old/moved.py` -> `new/moved.py`\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        # Context and Edits tokens are present.
        assert "ctx/file.py" in refs, f"Context token missing from refs: {refs}"
        assert "edit/file.py" in refs, f"Edits token missing from refs: {refs}"
        # Moves tokens must NOT appear in refs — parse_batch_refs is blind to Moves:.
        assert "old/moved.py" not in refs, (
            f"Moves source token leaked into parse_batch_refs result: {refs}"
        )
        assert "new/moved.py" not in refs, (
            f"Moves target token leaked into parse_batch_refs result: {refs}"
        )
        print(
            "PASS: parse_batch_refs does not return any token from a Moves: bullet (regression)"
        )

    # ---------------------------------------------------------------------------
    # build_tool_rule: four-cell dispatch matrix (bulk/tool-use x non-agent/agent)
    # ---------------------------------------------------------------------------

    # (a) Non-agent cells stay byte-identical to today's pre-agent-mode text.
    # Pinned as literals so a future edit that collaterally changes these strings is caught here -- these are also what the reviewer's `--stage full` API-error fallback relies on staying verbatim.
    _EXPECTED_BULK_NON_AGENT = (
        "**CRITICAL: Do NOT request tool calls. All content you need is in this prompt.**\n"
        "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
        "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**\n"
        "**CRITICAL: Do NOT use Write. Return review as text.**"
    )
    _EXPECTED_TOOL_USE_NON_AGENT = (
        "**You MAY use Read, Grep, and Glob to verify claims against source files.**\n"
        "**CRITICAL: Do NOT use Write, Edit, or run git/bash. Return review as text.**\n"
        "**CRITICAL: Review-only. Do NOT suggest modifications. Findings only.**\n"
        "**CRITICAL: Do NOT read `reviews/`. Evaluate fresh each round.**"
    )
    assert build_tool_rule("bulk", agent_mode=False) == _EXPECTED_BULK_NON_AGENT, (
        f"bulk x non-agent must stay byte-identical to today's text: "
        f"{build_tool_rule('bulk', agent_mode=False)!r}"
    )
    assert build_tool_rule("tool-use", agent_mode=False) == _EXPECTED_TOOL_USE_NON_AGENT, (
        f"tool-use x non-agent must stay byte-identical to today's text: "
        f"{build_tool_rule('tool-use', agent_mode=False)!r}"
    )
    print("PASS: build_tool_rule bulk/tool-use x non-agent byte-identical to pinned literals")

    # (e) agent_mode defaults to False: a single positional argument must equal the non-agent cell.
    # This pins the default that keeps the file's seven existing positional callsites green.
    assert build_tool_rule("bulk") == _EXPECTED_BULK_NON_AGENT, (
        "build_tool_rule('bulk') with one positional arg must default to non-agent"
    )
    assert build_tool_rule("tool-use") == _EXPECTED_TOOL_USE_NON_AGENT, (
        "build_tool_rule('tool-use') with one positional arg must default to non-agent"
    )
    print("PASS: build_tool_rule agent_mode defaults to False (positional-callsite compatibility)")

    # (b) bulk x agent: must NOT contain the bare "Do NOT request tool calls" clause (it would contradict the Write grant below),
    # and must grant exactly one Write for the report.
    bulk_agent = build_tool_rule("bulk", agent_mode=True)
    assert "Do NOT request tool calls" not in bulk_agent, (
        f"bulk x agent must not contain the bare non-agent tool-call ban: {bulk_agent!r}"
    )
    assert "Write" in bulk_agent, f"bulk x agent must grant a Write carve-out: {bulk_agent!r}"
    assert bulk_agent.count("Write") == 1, (
        f"bulk x agent must grant exactly one Write carve-out, found {bulk_agent.count('Write')}: {bulk_agent!r}"
    )
    print("PASS: build_tool_rule bulk x agent avoids bare tool-call ban and grants exactly one Write")

    # (c) tool-use x agent: still grants Read/Grep/Glob,
    # and grants Write for the report.
    tool_use_agent = build_tool_rule("tool-use", agent_mode=True)
    assert "MAY use Read, Grep, and Glob" in tool_use_agent, (
        f"tool-use x agent must still grant Read/Grep/Glob: {tool_use_agent!r}"
    )
    assert "Write" in tool_use_agent, f"tool-use x agent must grant a Write carve-out: {tool_use_agent!r}"
    print("PASS: build_tool_rule tool-use x agent still grants Read/Grep/Glob and a Write carve-out")

    # (d) Both agent cells still forbid Edit, git, and bash.
    for cell_name, cell_text in (("bulk x agent", bulk_agent), ("tool-use x agent", tool_use_agent)):
        assert "Edit" in cell_text and "NOT use Edit" in cell_text, (
            f"{cell_name} must still forbid Edit: {cell_text!r}"
        )
        assert "git" in cell_text.lower() and "bash" in cell_text.lower(), (
            f"{cell_name} must still forbid git/bash: {cell_text!r}"
        )
    print("PASS: build_tool_rule both agent cells still forbid Edit, git, and bash")

    # (f) Unknown mode still raises ValueError in both agent_mode states.
    for agent_mode_value in (False, True):
        try:
            build_tool_rule("weird", agent_mode=agent_mode_value)
            print(
                f"FAIL: build_tool_rule: expected ValueError for unknown mode (agent_mode={agent_mode_value})",
                file=sys.stderr,
            )
            errors += 1
        except ValueError as e:
            assert "weird" in str(e)
    print("PASS: build_tool_rule unknown mode -> ValueError in both agent_mode states")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_common unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
