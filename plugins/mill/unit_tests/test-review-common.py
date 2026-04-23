"""Unit tests for plugins/mill/scripts/_review_common.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _review_common import (  # noqa: E402
    RE_BATCH,
    RE_SIMPLE,
    ReviewError,
    aggregate_verdict,
    build_tool_rule,
    bulk_files,
    discover_round,
    find_active_slug,
    load_config,
    load_reviewer,
    load_task_title,
    parse_verdict,
    render_prompt,
    resolve_path,
    write_review_file,
)


def main() -> int:
    errors = 0

    # discover_round: nonexistent dir -> 1
    assert discover_round(Path("/tmp/__nx_reviews__"), "discussion") == 1
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
        assert discover_round(reviews, "discussion") == 1
        print("PASS: discover_round cross-type isolation (plan-batch ignored for discussion)")
        result = discover_round(reviews, "plan")
        assert result == 3
        print(f"PASS: discover_round for plan with batch file: {result}")

    # find_active_slug: empty dir -> ReviewError
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            find_active_slug(Path(tmpdir))
            errors += 1
            print("FAIL: expected ReviewError for empty mill_dir", file=sys.stderr)
        except ReviewError as e:
            assert "No active task" in str(e)
            print("PASS: find_active_slug empty dir -> ReviewError")

    # find_active_slug: one slug file -> returns slug
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        (mill_dir / ".my-task.slug.md").write_text("---\ntask_title: My Task\n---\n")
        assert find_active_slug(mill_dir) == "my-task"
        print("PASS: find_active_slug: 'my-task'")

    # load_task_title: present field
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        (mill_dir / ".my-task.slug.md").write_text(
            "---\ntask_title: My Task Title\nslug: my-task\n---\n"
        )
        assert load_task_title(mill_dir, "my-task") == "My Task Title"
        print("PASS: load_task_title with field")

    # load_task_title: missing field -> falls back to slug
    with tempfile.TemporaryDirectory() as tmpdir:
        mill_dir = Path(tmpdir)
        (mill_dir / ".my-task.slug.md").write_text("---\nslug: my-task\n---\n")
        assert load_task_title(mill_dir, "my-task") == "my-task"
        print("PASS: load_task_title fallback")

    # resolve_path
    p = resolve_path("active/<SLUG>/discussion.md", "my-slug", Path("/wiki"))
    assert str(p).replace("\\", "/") == "/wiki/active/my-slug/discussion.md"
    print("PASS: resolve_path")

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

    # load_reviewer: nonexistent -> ReviewError
    try:
        load_reviewer("nonexistent_xyz_abc")
        errors += 1
    except ReviewError as e:
        assert "nonexistent_xyz_abc" in str(e)
        print("PASS: load_reviewer nonexistent -> ReviewError")

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
            "review:\n  plan:\n    rounds: 3\n    batch: sonnetmax\n",
            encoding="utf-8",
        )
        cfg = load_config(wiki, mill)
        assert cfg["review"]["plan"]["rounds"] == 3
        print("PASS: load_config loads shared config")

        (mill / "config.local.yaml").write_text(
            "review:\n  plan:\n    rounds: 1\n",
            encoding="utf-8",
        )
        cfg = load_config(wiki, mill)
        assert cfg["review"]["plan"]["rounds"] == 1
        assert cfg["review"]["plan"]["batch"] == "sonnetmax"
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

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _review_common unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
