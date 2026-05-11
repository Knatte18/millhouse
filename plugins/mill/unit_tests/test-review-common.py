"""Unit tests for plugins/mill/scripts/_review_common.py."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_UNIT_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_UNIT_TESTS))

from _test_helpers import _make_task_worktree  # noqa: E402
from _paths import ActiveWorktreeSlugMismatch  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture helper for resolve_path tests
# ---------------------------------------------------------------------------


def _make_worktree_fixture(tmp: str, slug: str) -> tuple[Path, Path]:
    """Create a container-form git fixture at ``<tmp>/container/wts/<slug>``.

    Layout:
        <tmp>/container/wts/<slug>/  ← git repo on task branch ``hanf/<slug>``
        <tmp>/container/wiki/        ← wiki with Home.md and config.yaml

    Returns:
        ``(container_path, worktree_path)``

    The caller must ``os.chdir(worktree_path)`` so that ``Path.cwd()`` resolves
    inside the fixture when calling ``resolve_path``.
    """
    container = Path(tmp) / "container"
    worktree = container / "wts" / slug
    worktree.mkdir(parents=True)
    subprocess.run(["git", "-C", str(worktree), "init"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.email", "test@test.com"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "config", "user.name", "Test"],
        check=True, capture_output=True,
    )
    (worktree / "README.md").write_text("# test\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(worktree), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(worktree), "commit", "-m", "init"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(worktree), "checkout", "-b", f"hanf/{slug}"],
        check=True, capture_output=True,
    )
    wiki_root = container / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "config.yaml").write_text(
        "paths:\n  discussion_file: task/discussion.md\n"
        "spawn:\n  branch_prefix: \"hanf/\"\n",
        encoding="utf-8",
    )
    (wiki_root / "Home.md").write_text(
        f"## Test Task\n[[{slug}]] [active]\n\n_body_\n",
        encoding="utf-8",
    )
    return container, worktree


def _make_run_result(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.returncode = returncode
    result.stderr = stderr
    return result


from _review_common import (  # noqa: E402
    RE_BATCH,
    RE_SIMPLE,
    ReviewError,
    _load_root_from_overview,
    aggregate_verdict,
    build_deletes_section,
    build_manifest_section,
    build_reattached_section,
    build_tool_rule,
    bulk_files,
    bulk_files_with_diff,
    compute_creates_union,
    compute_deletes_union,
    detect_resume_round,
    discover_round,
    find_active_slug,
    load_config,
    load_task_title,
    parse_batch_refs,
    parse_blocking_count,
    parse_missing_context,
    parse_verdict,
    render_prompt,
    resolve_existing_paths,
    resolve_path,
    resolve_ref_paths,
    write_review_file,
)


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
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        (reviews / "20260418-001200-plan-review-01-setup-r2.md").write_text("x")
        assert discover_round(reviews, "discussion", "holistic") == 1
        print("PASS: discover_round cross-type isolation (plan-batch ignored for discussion)")
        result = discover_round(reviews, "plan", "01-setup")
        assert result == 3, f"expected 3, got {result}"
        print(f"PASS: discover_round for plan with batch file: {result}")
        assert discover_round(reviews, "plan", "holistic") == 1
        print("PASS: discover_round plan holistic unaffected by batch file")
        assert discover_round(reviews, "plan", "other-batch") == 1
        print("PASS: discover_round plan other-batch unaffected by 01-setup file")

    # discover_round per-scope isolation across all five (review_type, scope) axes
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
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
        print(f"PASS: discover_round per-scope code/batch-b (absent for code): {result}")

    # find_active_slug: not on a task branch -> MarkerError re-raised as ReviewError
    with tempfile.TemporaryDirectory() as tmpdir:
        wt, wiki = _make_task_worktree(Path(tmpdir) / "sub", "some-task", "Some Task", branch_prefix="hanf/")
        subprocess.run(["git", "-C", str(wt), "checkout", "main"], check=True, capture_output=True)
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        try:
            find_active_slug(wt, wiki, cfg)
            errors += 1
            print("FAIL: expected ReviewError for non-task branch", file=sys.stderr)
        except ReviewError:
            print("PASS: find_active_slug non-task branch -> ReviewError (MarkerError translation)")

    # find_active_slug: on task branch -> returns slug
    with tempfile.TemporaryDirectory() as tmpdir:
        wt, wiki = _make_task_worktree(Path(tmpdir), "my-task", "My Task", branch_prefix="hanf/")
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        assert find_active_slug(wt, wiki, cfg) == "my-task"
        print("PASS: find_active_slug: 'my-task'")

    # load_task_title: task_title present in Home.md
    with tempfile.TemporaryDirectory() as tmpdir:
        wt, wiki = _make_task_worktree(Path(tmpdir), "my-task", "My Task Title", branch_prefix="hanf/")
        cfg = {"spawn": {"branch_prefix": "hanf/"}}
        assert load_task_title(wt, wiki, cfg, "my-task") == "My Task Title"
        print("PASS: load_task_title with task_title in Home.md")

    # load_task_title: non-task branch -> falls back to slug
    with tempfile.TemporaryDirectory() as tmpdir:
        assert load_task_title(Path(tmpdir), Path(tmpdir), {}, "my-task") == "my-task"
        print("PASS: load_task_title non-task branch -> fallback to slug")

    # resolve_path: discussion.md → worktree root
    with tempfile.TemporaryDirectory() as tmp:
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
        print("PASS: resolve_path('discussion.md', slug) → worktree/discussion.md")

    # resolve_path: plan/ and reviews/ templates
    with tempfile.TemporaryDirectory() as tmp:
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
        assert p_nested == worktree / "reviews/r1/holistic.md", f"nested wrong: {p_nested}"
        print("PASS: resolve_path covers plan/, reviews/, nested reviews/r1/holistic.md")

    # resolve_path: stale <SLUG> in template is substituted (not a literal segment)
    with tempfile.TemporaryDirectory() as tmp:
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
        print("PASS: resolve_path stale <SLUG> template substituted (no literal segment)")

    # resolve_path: slug-mismatch raises ActiveWorktreeSlugMismatch
    with tempfile.TemporaryDirectory() as tmp:
        slug = "my-task"
        container, worktree = _make_worktree_fixture(tmp, slug)
        # Create a directory named "wrong-slug" but checked out on branch "hanf/my-task"
        # (directory slug ≠ branch-derived slug → mismatch).
        wrong_slug = "wrong-slug"
        wrong_dir = container / "wts" / wrong_slug
        wrong_dir.mkdir(parents=True)
        subprocess.run(["git", "-C", str(wrong_dir), "init"], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(wrong_dir), "config", "user.email", "test@test.com"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "config", "user.name", "Test"],
            check=True, capture_output=True,
        )
        (wrong_dir / ".keep").write_text("", encoding="utf-8")
        subprocess.run(["git", "-C", str(wrong_dir), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(wrong_dir), "commit", "-m", "init"],
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(wrong_dir), "checkout", "-b", "hanf/my-task"],
            check=True, capture_output=True,
        )
        original_cwd = Path.cwd()
        os.chdir(worktree)
        try:
            try:
                resolve_path("discussion.md", wrong_slug)
                errors += 1
                print("FAIL: expected ActiveWorktreeSlugMismatch for wrong slug", file=sys.stderr)
            except ActiveWorktreeSlugMismatch:
                print("PASS: resolve_path raises ActiveWorktreeSlugMismatch on branch mismatch")
        finally:
            os.chdir(original_cwd)

    # resolve_path: M2 in-place mode (hub_rel=".")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        git_root = tmp_path / "git_root"
        git_root.mkdir()
        hub = git_root
        slug = "my-inplace-task"

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

        with patch("_marker.slug_from_branch", return_value=slug), \
             patch("_paths.resolve_git_root", return_value=git_root), \
             patch("_paths.resolve_wiki_path", return_value=wiki_root), \
             patch("_paths.resolve_hub_path", return_value=hub), \
             patch("_paths.resolve_main_worktree_root", return_value=git_root), \
             patch("_inplace.resolve_worktrees_dir", return_value=worktrees_dir):
            p = resolve_path("task/discussion.md", slug)

        expected = git_root / "task" / "discussion.md"
        assert p == expected, f"M2 in-place (hub_rel='.'): expected {expected}, got {p}"
        print("PASS: resolve_path M2 in-place (hub_rel='.') → git_root/task/discussion.md")

    # resolve_path: M2+sub in-place mode (hub_rel="src/Models")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        git_root = tmp_path / "git_root"
        git_root.mkdir()
        hub = git_root / "src" / "Models"
        slug = "my-subdir-inplace-task"

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

        with patch("_marker.slug_from_branch", return_value=slug), \
             patch("_paths.resolve_git_root", return_value=git_root), \
             patch("_paths.resolve_wiki_path", return_value=wiki_root), \
             patch("_paths.resolve_hub_path", return_value=hub), \
             patch("_paths.resolve_main_worktree_root", return_value=git_root), \
             patch("_inplace.resolve_worktrees_dir", return_value=worktrees_dir):
            p = resolve_path("task/discussion.md", slug)

        expected = git_root / "src" / "Models" / "task" / "discussion.md"
        assert p == expected, f"M2+sub in-place: expected {expected}, got {p}"
        print("PASS: resolve_path M2+sub in-place (hub_rel='src/Models') → git_root/src/Models/task/discussion.md")

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
        errors += 1
    except ReviewError:
        print("PASS: parse_verdict no yaml block -> ReviewError")

    # parse_verdict: unclosed yaml block -> ReviewError
    try:
        parse_verdict("# Review: X\n\n```yaml\nverdict: APPROVE\n")
        errors += 1
    except ReviewError as e:
        assert "not closed" in str(e)
        print("PASS: parse_verdict unclosed yaml block -> ReviewError")

    # parse_verdict: invalid verdict value -> ReviewError
    try:
        parse_verdict("# Review: X\n\n```yaml\nverdict: MAYBE\n```\n")
        errors += 1
    except ReviewError as e:
        assert "MAYBE" in str(e)
        print("PASS: parse_verdict invalid verdict -> ReviewError")

    # write_review_file: creates file
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir) / "reviews"
        path = write_review_file(reviews, "discussion", 1, "---\nverdict: APPROVE\n---\n")
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

    # bulk_files: nonexistent skipped
    with tempfile.TemporaryDirectory() as tmpdir:
        existing = Path(tmpdir) / "a.md"
        existing.write_text("hello")
        result = bulk_files([existing, Path("/nonexistent/x.md")])
        assert "hello" in result and "FILE:" in result
        print("PASS: bulk_files skips missing files")

    # render_prompt: missing template -> FileNotFoundError
    try:
        render_prompt("nonexistent-template-xyz")
        errors += 1
    except FileNotFoundError:
        print("PASS: render_prompt missing template -> FileNotFoundError")

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
        errors += 1
    except ValueError as e:
        assert "weird" in str(e)
        print("PASS: build_tool_rule unknown mode -> ValueError")

    # load_config: valid YAML + local override
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki = Path(tmpdir) / "wiki"
        wiki.mkdir()
        mill = Path(tmpdir) / ".millhouse"
        mill.mkdir()
        (wiki / "config.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 3\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        cfg = load_config(wiki, mill)
        assert cfg["roles"]["plan-review"]["batch"]["rounds"] == 3
        print("PASS: load_config loads shared config")

        (mill / "config.local.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 1\n",
            encoding="utf-8",
        )
        cfg = load_config(wiki, mill)
        assert cfg["roles"]["plan-review"]["batch"]["rounds"] == 1
        assert cfg["roles"]["plan-review"]["batch"]["reviewer"] == "sonnetmax"
        print("PASS: load_config local override wins; other keys preserved")

    # load_config: missing config -> ReviewError
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki = Path(tmpdir) / "wiki"
        wiki.mkdir()
        mill = Path(tmpdir) / ".millhouse"
        mill.mkdir()
        try:
            load_config(wiki, mill)
            errors += 1
        except ReviewError as e:
            assert "Missing config" in str(e)
            print("PASS: load_config missing config -> ReviewError")

    # load_config: stale review: overlay in config.local.yaml -> stderr warning
    with tempfile.TemporaryDirectory() as tmpdir:
        import io as _io
        import contextlib as _cl
        wiki = Path(tmpdir) / "wiki"
        wiki.mkdir()
        mill = Path(tmpdir) / ".millhouse"
        mill.mkdir()
        (wiki / "config.yaml").write_text(
            "roles:\n  plan-review:\n    batch:\n      rounds: 3\n      reviewer: sonnetmax\n",
            encoding="utf-8",
        )
        (mill / "config.local.yaml").write_text(
            "review:\n  code:\n    rounds: 1\n",
            encoding="utf-8",
        )
        _err_buf = _io.StringIO()
        with _cl.redirect_stderr(_err_buf):
            cfg = load_config(wiki, mill)
        _warning = _err_buf.getvalue()
        assert _warning, "expected a stderr warning, got empty string"
        assert "review" in _warning, f"warning should mention 'review': {_warning!r}"
        local_path_str = str(mill / "config.local.yaml")
        assert local_path_str in _warning, f"warning should mention overlay path: {_warning!r}"
        print("PASS: load_config stale review: overlay emits stderr warning with overlay path")

    # parse_batch_refs: multi-line bullet form returns all sub-bullet paths
    with tempfile.TemporaryDirectory() as tmpdir:
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

    # parse_batch_refs: 'none' token is filtered out
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Creates:** none\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'none' token filtered")

    # parse_batch_refs: single-line form returns both paths
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Context:** `x`, `y`\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == ["x", "y"], f"Got {refs}"
        print("PASS: parse_batch_refs single-line form returns both paths")

    # parse_batch_refs: mixed single-line and multi-line fields
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Context:** `a`\n"
            "- **Edits:**\n"
            "  - `b`\n"
            "  - `c`\n"
            "- **Creates:** none\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == ["a", "b", "c"], f"Got {refs}"
        print("PASS: parse_batch_refs mixed single-line and multi-line fields")

    # parse_batch_refs: case-variant none tokens filtered (Block A: None)
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Creates:** None\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'None' (capital N) filtered")

    # parse_batch_refs: case-variant none tokens filtered (Block B: NONE)
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Edits:** NONE\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs 'NONE' (all caps) filtered")

    # parse_batch_refs: case-variant none in sub-bullet form (Block C: `None`)
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text(
            "- **Creates:**\n"
            "  - `None`\n",
            encoding="utf-8",
        )
        refs = parse_batch_refs(batch)
        assert refs == [], f"Got {refs}"
        print("PASS: parse_batch_refs sub-bullet `None` filtered")

    # parse_batch_refs: mixed token + lowercase none inline (Block D: regression pin)
    with tempfile.TemporaryDirectory() as tmpdir:
        batch = Path(tmpdir) / "batch.md"
        batch.write_text("- **Context:** `a`, none\n", encoding="utf-8")
        refs = parse_batch_refs(batch)
        # backtick tokens win; "none" is comma-fallback and filtered
        assert refs == ["a"], f"Got {refs}"
        print("PASS: parse_batch_refs backtick tokens win; trailing 'none' filtered")

    # parse_batch_refs: Deletes: field extracted alongside Context/Edits/Creates
    with tempfile.TemporaryDirectory() as tmpdir:
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
        print("PASS: parse_batch_refs includes Deletes tokens alongside Context/Edits/Creates")

    # resolve_ref_paths: hit on disk
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths([str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths hit on disk returns resolved path")

    # resolve_ref_paths: suppression via creates_union (no error, empty return)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"], tmp_dir, root=None,
            creates_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths creates_union suppresses missing path")

    # resolve_ref_paths: hard-fail on unresolved path
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["nonexistent.py"], tmp_dir, root=None)
            errors += 1
            print("FAIL: expected ReviewError for missing path", file=sys.stderr)
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            assert "nonexistent.py" in str(e), f"Path not in message: {e}"
            print("PASS: resolve_ref_paths hard-fails with 'referenced path not found'")

    # resolve_ref_paths: wiki path resolved
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        (tmp_wiki / "active" / "x").mkdir(parents=True)
        (tmp_wiki / "active" / "x" / "discussion.md").write_text("d")
        result = resolve_ref_paths(
            ["wiki/active/x/discussion.md"], tmp_project, root=None,
            wiki_root=tmp_wiki,
        )
        assert result == [tmp_wiki / "active" / "x" / "discussion.md"], f"Got {result}"
        print("PASS: resolve_ref_paths wiki/ prefix resolved via wiki_root")

    # resolve_ref_paths: wiki path missing wiki_root raises ReviewError
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(["wiki/foo"], tmp_dir, root=None)
            errors += 1
            print("FAIL: expected ReviewError for wiki/ without wiki_root", file=sys.stderr)
        except ReviewError as e:
            assert "no wiki_root provided" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths wiki/ without wiki_root raises ReviewError")

    # resolve_ref_paths: wiki path exists in wiki_root but not in creates_union -> hard-fail
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_project = Path(tmpdir) / "project"
        tmp_project.mkdir()
        tmp_wiki = Path(tmpdir) / "wiki"
        tmp_wiki.mkdir()
        try:
            resolve_ref_paths(
                ["wiki/active/missing.md"], tmp_project, root=None,
                wiki_root=tmp_wiki,
            )
            errors += 1
            print("FAIL: expected ReviewError for missing wiki path", file=sys.stderr)
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths wiki path missing on disk hard-fails")

    # resolve_ref_paths: caller_label appears in error message
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["missing.py"], tmp_dir, root=None,
                caller_label="_review_plan",
            )
            errors += 1
            print("FAIL: expected ReviewError", file=sys.stderr)
        except ReviewError as e:
            assert str(e).startswith("[_review_plan]"), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths caller_label appears in error message")

    # resolve_ref_paths: defensive None filter (Python None in list)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths([None, str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths defensive None skipped silently")

    # resolve_ref_paths: defensive lowercase 'none' filter
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(["none", str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths 'none' string skipped silently")

    # resolve_ref_paths: defensive 'None' (capital N) filter
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(["None", str(real_file)], tmp_dir, root=None)
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths 'None' string skipped silently")

    # resolve_ref_paths: missing + in deletes_union -> silent suppress
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"], tmp_dir, root=None,
            deletes_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths deletes_union suppresses missing path")

    # resolve_ref_paths: missing + in both unions -> silent suppress
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        result = resolve_ref_paths(
            ["nonexistent.py"], tmp_dir, root=None,
            creates_union={"nonexistent.py"},
            deletes_union={"nonexistent.py"},
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_ref_paths missing + in both unions -> silent suppress")

    # resolve_ref_paths: on-disk + in deletes_union -> resolved normally, included
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        real_file = tmp_dir / "real.py"
        real_file.write_text("x")
        result = resolve_ref_paths(
            ["real.py"], tmp_dir, root=None,
            deletes_union={"real.py"},
        )
        assert result == [real_file], f"Got {result}"
        print("PASS: resolve_ref_paths on-disk + in deletes_union -> resolved and included")

    # resolve_ref_paths: missing + in neither union -> ReviewError (existing behaviour preserved)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["nonexistent.py"], tmp_dir, root=None,
                deletes_union={"other.py"},
            )
            errors += 1
            print("FAIL: expected ReviewError for missing path not in deletes_union", file=sys.stderr)
        except ReviewError as e:
            assert "referenced path not found" in str(e), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths missing + not in deletes_union -> ReviewError")

    # resolve_ref_paths: caller_label in error when deletes_union present but path missing
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_dir = Path(tmpdir)
        try:
            resolve_ref_paths(
                ["missing.py"], tmp_dir, root=None,
                deletes_union={"other.py"},
                caller_label="test_caller",
            )
            errors += 1
            print("FAIL: expected ReviewError", file=sys.stderr)
        except ReviewError as e:
            assert str(e).startswith("[test_caller]"), f"Unexpected message: {e}"
            print("PASS: resolve_ref_paths caller_label in error with deletes_union present")

    # compute_creates_union: empty plan dir returns empty set
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compute_creates_union(Path(tmpdir) / "nonexistent")
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union nonexistent plan_dir returns empty set")

    # compute_creates_union: one batch with inline Creates tokens
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** `a`, `b`\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_creates_union inline Creates returns set of tokens")

    # compute_creates_union: none token filtered
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** none\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union 'none' token filtered")

    # compute_creates_union: two batches with sub-bullet Creates -> union
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:**\n"
            "  - `x.py`\n"
            "  - `y.py`\n",
            encoding="utf-8",
        )
        (plan_dir / "02-wire.md").write_text(
            "- **Creates:**\n"
            "  - `z.py`\n",
            encoding="utf-8",
        )
        result = compute_creates_union(plan_dir)
        assert result == {"x.py", "y.py", "z.py"}, f"Got {result}"
        print("PASS: compute_creates_union two batches -> union of Creates tokens")

    # compute_creates_union: 00-overview.md excluded
    with tempfile.TemporaryDirectory() as tmpdir:
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
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Creates:** None\n", encoding="utf-8"
        )
        result = compute_creates_union(plan_dir)
        assert result == set(), f"Got {result}"
        print("PASS: compute_creates_union 'None' (capital N) filtered")

    # ---------------------------------------------------------------------------
    # compute_deletes_union
    # ---------------------------------------------------------------------------

    # empty plan dir returns empty set
    with tempfile.TemporaryDirectory() as tmpdir:
        result = compute_deletes_union(Path(tmpdir) / "nonexistent")
        assert result == set(), f"Got {result}"
        print("PASS: compute_deletes_union nonexistent plan_dir returns empty set")

    # single batch single-line Deletes tokens
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:** `a`, `b`\n", encoding="utf-8"
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_deletes_union inline Deletes returns set of tokens")

    # multi-line bullet form
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Deletes:**\n"
            "  - `a`\n"
            "  - `b`\n",
            encoding="utf-8",
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"a", "b"}, f"Got {result}"
        print("PASS: compute_deletes_union multi-line bullet form returns tokens")

    # 'none' sentinel filtered (case variants)
    for sentinel in ("none", "None", "NONE"):
        with tempfile.TemporaryDirectory() as tmpdir:
            plan_dir = Path(tmpdir)
            (plan_dir / "01-setup.md").write_text(
                f"- **Deletes:** {sentinel}\n", encoding="utf-8"
            )
            result = compute_deletes_union(plan_dir)
            assert result == set(), f"Got {result} for sentinel {sentinel!r}"
        print(f"PASS: compute_deletes_union '{sentinel}' sentinel filtered")

    # two batches with overlapping deletes — de-duplicated
    with tempfile.TemporaryDirectory() as tmpdir:
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
    with tempfile.TemporaryDirectory() as tmpdir:
        plan_dir = Path(tmpdir)
        (plan_dir / "01-setup.md").write_text(
            "- **Context:** `src/a.py`\n"
            "- **Deletes:** `old.py`\n"
            "- **Context:** `src/b.py`\n",
            encoding="utf-8",
        )
        result = compute_deletes_union(plan_dir)
        assert result == {"old.py"}, f"Got {result}"
        print("PASS: compute_deletes_union Deletes absent on some cards; present on others")

    # 00-overview.md is skipped
    with tempfile.TemporaryDirectory() as tmpdir:
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

    # ---------------------------------------------------------------------------
    # build_deletes_section
    # ---------------------------------------------------------------------------

    # Empty list -> empty string
    result = build_deletes_section([])
    assert result == "", f"Expected empty string, got {result!r}"
    print("PASS: build_deletes_section empty list -> empty string")

    # Single token
    result = build_deletes_section(["old_module.py"])
    assert result == "## Intentionally deleted (N=1)\n\n- old_module.py", f"Got {result!r}"
    print("PASS: build_deletes_section single token -> heading + bullet")

    # Multiple tokens preserve input order
    result = build_deletes_section(["a.py", "b.py", "c.py"])
    assert result.startswith("## Intentionally deleted (N=3)"), f"Wrong heading: {result!r}"
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

    with tempfile.TemporaryDirectory() as tmpdir:
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
        print("PASS: resolve_existing_paths wiki-prefixed path missing -> silently dropped")

        # Wiki-prefixed path with wiki_root=None -> silently dropped (no raise)
        result = resolve_existing_paths(
            ["wiki/active/slug/foo.md"], project, root=None, wiki_root=None
        )
        assert result == [], f"Got {result}"
        print("PASS: resolve_existing_paths wiki/ with wiki_root=None -> silently dropped (no raise)")

        # None token silently dropped
        result = resolve_existing_paths([None, str(existing)], project, root=None)
        assert result == [existing], f"Got {result}"
        print("PASS: resolve_existing_paths None token silently dropped")

        # 'none' (any case) tokens silently dropped
        result = resolve_existing_paths(["none", "NONE", "None", str(existing)], project, root=None)
        assert result == [existing], f"Got {result}"
        print("PASS: resolve_existing_paths 'none'/'NONE'/'None' tokens silently dropped")

        # Mixed: [exists, missing, "none", None, wiki-exists] -> [exists, wiki-exists]
        result = resolve_existing_paths(
            [str(existing), "nonexistent.py", "none", None, "wiki/active/slug/foo.md"],
            project,
            root=None,
            wiki_root=wiki,
        )
        assert result == [existing, wiki_file], f"Got {result}"
        print("PASS: resolve_existing_paths mixed input -> only existing paths returned")

    # Per-scope counters survive interleaved per-batch + holistic writes (regression for #21, #62, #63)
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        ts = "20260418-002000"
        (reviews / f"{ts}-code-review-helper-modules-r1.md").write_text("x")

        result = discover_round(reviews, "code", "helper-modules")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/helper-modules after r1: {result}")

        result = discover_round(reviews, "code", "spawn-core")
        assert result == 1, f"expected 1, got {result}"
        print(f"PASS: discover_round per-scope code/spawn-core (different batch, fresh count): {result}")

        (reviews / f"{ts}-code-review-r1.md").write_text("x")

        result = discover_round(reviews, "code", "holistic")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/holistic independent after holistic r1: {result}")

        result = discover_round(reviews, "code", "helper-modules")
        assert result == 2, f"expected 2, got {result}"
        print(f"PASS: discover_round per-scope code/helper-modules still independent of holistic: {result}")

    # ---------------------------------------------------------------------------
    # parse_missing_context
    # ---------------------------------------------------------------------------

    # No ## Missing context heading → []
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

    # Bullet without backticks → not captured
    text = "## Missing context\n\n- a/b.py — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context bullet without backticks not captured")

    # Bullet with `none` token → filtered (lowercase)
    text = "## Missing context\n\n- `none` — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context `none` token filtered")

    # Bullet with `None` token → filtered (capital N)
    text = "## Missing context\n\n- `None` — reason\n"
    result = parse_missing_context(text)
    assert result == [], f"Got {result}"
    print("PASS: parse_missing_context `None` token filtered")

    # ---------------------------------------------------------------------------
    # build_reattached_section
    # ---------------------------------------------------------------------------

    # Empty input → ""
    result = build_reattached_section([])
    assert result == "", f"Got {result!r}"
    print("PASS: build_reattached_section empty input -> ''")

    # One path → heading + blank line + FILE delimiter
    with tempfile.TemporaryDirectory() as tmpdir:
        f = Path(tmpdir) / "foo.py"
        f.write_text("content")
        result = build_reattached_section([f])
        assert "## Re-attached files (you said these were missing)" in result, f"Missing heading in: {result!r}"
        assert str(f) in result, f"Path not in output: {result!r}"
        assert "--- FILE:" in result, f"No FILE delimiter in: {result!r}"
        print("PASS: build_reattached_section one path -> heading + FILE delimiter")

    # Two paths → both delimiters in order
    with tempfile.TemporaryDirectory() as tmpdir:
        fa = Path(tmpdir) / "a.py"
        fb = Path(tmpdir) / "b.py"
        fa.write_text("aaa")
        fb.write_text("bbb")
        result = build_reattached_section([fa, fb])
        assert str(fa) in result, "fa not in output"
        assert str(fb) in result, "fb not in output"
        assert result.index(str(fa)) < result.index(str(fb)), "fa should appear before fb"
        print("PASS: build_reattached_section two paths -> both delimiters in order")

    # ---------------------------------------------------------------------------
    # parse_blocking_count
    # ---------------------------------------------------------------------------

    # Empty string → 0
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
    print("PASS: parse_blocking_count case-sensitive: lowercase blocking with BLOCKING severity -> 0")

    # Heading at start of line only — mid-line marker not counted
    result = parse_blocking_count("text ### [BLOCKING] foo\n", severity="BLOCKING")
    assert result == 0, f"expected 0, got {result}"
    print("PASS: parse_blocking_count mid-line marker not counted -> 0")

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

    # ---------------------------------------------------------------------------
    # _load_root_from_overview: importable from _review_common
    # ---------------------------------------------------------------------------

    # Confirm the function is importable (not AttributeError); do not exercise behaviour
    assert callable(_load_root_from_overview), "_load_root_from_overview should be callable"
    print("PASS: _load_root_from_overview importable from _review_common")

    # ---------------------------------------------------------------------------
    # detect_resume_round
    # ---------------------------------------------------------------------------

    # reviews_dir does not exist -> None
    result = detect_resume_round(Path("/tmp/__nx_detect_resume__"), "plan")
    assert result is None, f"Got {result}"
    print("PASS: detect_resume_round nonexistent dir -> None")

    # no files -> None
    with tempfile.TemporaryDirectory() as tmpdir:
        result = detect_resume_round(Path(tmpdir), "plan")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round empty dir -> None")

    # per-batch round-1 files + holistic round-1 file -> None
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-r1.md").write_text("x")
        result = detect_resume_round(reviews, "plan")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1 + holistic r1 -> None")

    # per-batch round-1 files + no holistic round-1 -> 1
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-02-wire-r1.md").write_text("x")
        result = detect_resume_round(reviews, "plan")
        assert result == 1, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1 + no holistic -> 1")

    # per-batch rounds 1 and 2 + holistic round-1 + no holistic round-2 -> 2
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-01-setup-r2.md").write_text("x")
        (reviews / "20260418-001400-plan-review-r1.md").write_text("x")  # holistic r1
        result = detect_resume_round(reviews, "plan")
        assert result == 2, f"Got {result}"
        print("PASS: detect_resume_round per-batch r1+r2, holistic r1 only -> 2")

    # per-batch round 2 partial (some at r2, some at r1) + no holistic r2 -> 2
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        (reviews / "20260418-001300-plan-review-01-setup-r2.md").write_text("x")
        (reviews / "20260418-001400-plan-review-02-wire-r1.md").write_text("x")
        # no holistic at any round
        result = detect_resume_round(reviews, "plan")
        assert result == 2, f"Got {result}"
        print("PASS: detect_resume_round partial r2 batches, no holistic -> 2 (highest batch round)")

    # type isolation: plan per-batch files don't affect code detect_resume_round
    with tempfile.TemporaryDirectory() as tmpdir:
        reviews = Path(tmpdir)
        (reviews / "20260418-001200-plan-review-01-setup-r1.md").write_text("x")
        result = detect_resume_round(reviews, "code")
        assert result is None, f"Got {result}"
        print("PASS: detect_resume_round type isolation: plan files ignored for code")

    # ---------------------------------------------------------------------------
    # bulk_files_with_diff
    # ---------------------------------------------------------------------------

    # Test A — file with small diff uses DIFF delimiter
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "a.py").write_text("x\n" * 2000, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        with open(src / "a.py", "a", encoding="utf-8") as fh:
            fh.write("y\n" * 10)
        subprocess.run(["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "small change"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "a.py"], start_sha, repo, 0.25)
        assert "--- DIFF:" in result, f"expected DIFF delimiter, got: {result[:200]!r}"
        assert "--- FILE: " not in result, f"expected no FILE delimiter, got: {result[:200]!r}"
        assert start_sha[:8] in result, f"expected start_sha[:8] in result, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff small diff -> DIFF delimiter")

    # Test B — file with large diff uses FILE delimiter
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "b.py").write_text("x\n" * 20, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/b.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (src / "b.py").write_text("y\n" * 20, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/b.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "large change"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "b.py"], start_sha, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter, got: {result[:200]!r}"
        assert "--- DIFF:" not in result, f"expected no DIFF delimiter, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff large diff -> FILE delimiter")

    # Test C — unchanged file (empty diff) uses FILE delimiter
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "c.py").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/c.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        (src / "other.py").write_text("z\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/other.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "other file"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "c.py"], start_sha, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff empty diff (unchanged file) -> FILE delimiter")

    # Test D — non-existent file is skipped
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        (repo / "dummy.py").write_text("x\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "dummy.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        start_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        result = bulk_files_with_diff([repo / "nonexistent.py"], start_sha, repo, 0.25)
        assert result == "", f"expected empty string, got: {result!r}"
        print("PASS: bulk_files_with_diff non-existent file skipped")

    # Test E — git diff failure falls back to full file
    with tempfile.TemporaryDirectory() as tmpdir:
        repo = Path(tmpdir)
        subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t.com"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "T"], check=True, capture_output=True)
        src = repo / "src"
        src.mkdir()
        (src / "a.py").write_text("hello\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "src/a.py"], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True, capture_output=True)
        result = bulk_files_with_diff([repo / "src" / "a.py"], "deadbeef" * 5, repo, 0.25)
        assert "--- FILE: " in result, f"expected FILE delimiter fallback, got: {result[:200]!r}"
        assert "--- DIFF:" not in result, f"expected no DIFF delimiter, got: {result[:200]!r}"
        print("PASS: bulk_files_with_diff git diff failure -> FILE delimiter fallback")

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_common unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
