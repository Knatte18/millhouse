"""Unit tests for _plan_validate.py.

One test function per check (clean + dirty fixtures).
Tests use in-memory tempfile fixtures;
no real LLM, no real git, no network, except the one gitignore-fixture case in
`test_check_non_existent_path_*` which shells out to real `git check-ignore` via
`_test_helpers.init_minimal_git_repo`.

Check coverage:
  check 1 — non-existent-path (incl.
      gitignore-aware Context: soft-fail, #868)
  check 2 — card-missing-field
  check 3 — card-numbering (within-batch gap, cross-batch duplicate)
  check 4 — depends-on-unknown
  check 5 — parallel-modifies-overlap
  cross-batch-creates-no-depends-on (#887) — Context:/Edits: reference to a file another batch
      creates, with no depends-on edge to that creating batch
  verify-batch-mismatch — a batch's overview Batch Index verify: disagrees with that batch file's
      own frontmatter verify: (command or cwd)
  check 6 — reads-not-backtick-path (incl.
      none-exempt)
  check 8 — all-files-touched-mismatch
  context-completeness (#742) — card Requirements: references a resolvable file-path-shaped token
      absent from that card's own Context:/Edits:/Creates:/Deletes:/Moves:
  verify cwd mapping form — verify-not-isolated/verify-full-suite accept the {cwd, command} mapping
      and the overview-level verify:;
      verify-malformed-cwd;
      verify-mixed-cwd
  verify-unrelated-test-file — --only token untouched by its own batch and byte-identical to a
      non-main parent branch (#638)
  meta — sorted output, missing overview
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _plan_validate  # noqa: E402

_UNIT_TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_UNIT_TESTS))


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

# Sentinel for _make_overview's per-entry `verify` override: signals "omit the verify: line
# entirely from this Batch Index entry" (distinct from an explicit `verify: null`, even though both
# normalize to the same `entry.get("verify") is None` result -- the two spellings are still tested
# separately by the verify-batch-mismatch "absent" scenarios).
_OMIT_VERIFY = object()


def _make_overview(
    batches: list[dict],
    *,
    all_files_touched: list[str] | None = None,
    overview_verify: str | None = None,
) -> str:
    """Return 00-overview.md text.

    Each batch dict: {name, file, number (optional), depends-on (optional, default []),
        verify (optional)}.
    all_files_touched: optional list of path strings for the section.
    overview_verify: optional module-wide verify: command string written into the overview's own
        frontmatter block (first fenced-yaml block, above the Batch Index).
        Omitted entirely when None, matching the plain real-world overview shape where module-wide
            verify: is optional.

    Per-entry ``verify`` key (batch dict): when absent, the entry's ``verify:`` line renders as the
    literal ``    verify: null`` exactly as before this override was added -- every existing caller
    that omits this key is unaffected. When present, the caller controls the rendered line(s)
    directly:
      - ``_OMIT_VERIFY`` sentinel -> the ``verify:`` line is omitted entirely from this entry.
      - ``None`` -> rendered as the literal ``verify: null`` (same text as the absent-key default,
        provided for symmetry with the batch-file frontmatter's own explicit-null spelling).
      - a plain string -> rendered verbatim as ``verify: <value>``.
      - a ``{cwd: ..., command: ...}`` dict -> rendered as the nested mapping form, one sub-key per
        dict key present (so a caller can omit ``cwd`` or ``command`` to test a malformed mapping).
    """
    entries = []
    for b in batches:
        deps = b.get("depends-on", [])
        deps_yaml = "[" + ", ".join(str(d) if isinstance(d, int) else f'"{d}"' for d in deps) + "]"
        if "number" in b:
            first_line = f"  - number: {b['number']}\n    name: {b['name']}\n"
        else:
            first_line = f"  - name: {b['name']}\n"
        base = (
            first_line
            + f"    file: {b['file']}\n"
            + f"    depends-on: {deps_yaml}"
        )
        if "verify" not in b:
            entries.append(base + "\n    verify: null")
            continue
        v = b["verify"]
        if v is _OMIT_VERIFY:
            entries.append(base)
        elif isinstance(v, dict):
            lines = ["    verify:"]
            if "cwd" in v:
                lines.append(f"      cwd: {v['cwd']}")
            if "command" in v:
                lines.append(f"      command: {v['command']}")
            entries.append(base + "\n" + "\n".join(lines))
        else:
            rendered = "null" if v is None else v
            entries.append(base + f"\n    verify: {rendered}")
    batch_list = "\n".join(entries)
    frontmatter = 'task: test\nslug: test-slug\nroot: ""\n'
    if overview_verify is not None:
        frontmatter += f"verify: {overview_verify}\n"
    text = (
        "# Overview\n\n"
        "```yaml\n"
        f"{frontmatter}"
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        f"batches:\n{batch_list}\n"
        "```\n"
    )
    if all_files_touched is not None:
        if all_files_touched:
            bullets = "\n".join(f"- `{p}`" for p in all_files_touched)
        else:
            bullets = ""
        text += f"\n## All Files Touched\n\n{bullets}\n"
    return text


def _make_batch_file(
    name: str,
    card_num: int = 1,
    *,
    context: list[str] | None = None,
    edits: list[str] | None = None,
    creates: list[str] | None = None,
    deletes: list[str] | None = None,
    moves: list[tuple[str, str]] | None = None,
    missing_fields: set[str] | None = None,
    commit: str | None = None,
    requirements: str | None = None,
) -> str:
    """Return a well-formed batch file with one card.

    context/edits/creates/deletes: list of path strings (backtick-wrapped automatically),
        or None to default to "none".
    moves: list of (src, dst) tuples for Moves: sub-bullets, or None/[] to write the "none"
        sentinel.
        Each tuple is formatted as `src` -> `dst`.
    missing_fields: set of field names to omit (for check 2 tests).
    commit: optional literal text for the Commit: field's inline value (e.g. "none" for a
        verification-only card).
        When None (the default), the Commit: line keeps its pre-existing hardcoded shape
            (`feat({name}): card {card_num}`) unchanged, so every existing call site that omits this
            argument is unaffected.
    requirements: optional literal text for the Requirements: field's body, used verbatim instead of
        the hardcoded "See scope.\\n" text.
        When None (the default), every existing call site's output is byte-for-byte unchanged.
    """
    missing_fields = missing_fields or set()

    def fmt(paths: list[str] | None) -> str:
        if not paths:
            return "none"
        return ", ".join(f"`{p}`" for p in paths)

    parts = [
        f"# Batch: {name}\n\n",
        "```yaml\n",
        f"task: test\nbatch: {name}\ncards: 1\nverify: null\ndepends-on: []\n",
        "```\n\n",
        "## Cards\n\n",
        f"### Card {card_num}: card {card_num}\n\n",
    ]
    if "Context" not in missing_fields:
        parts.append(f"- **Context:** {fmt(context)}\n")
    if "Edits" not in missing_fields:
        parts.append(f"- **Edits:** {fmt(edits)}\n")
    if "Creates" not in missing_fields:
        parts.append(f"- **Creates:** {fmt(creates)}\n")
    if "Deletes" not in missing_fields:
        parts.append(f"- **Deletes:** {fmt(deletes)}\n")
    if "Moves" not in missing_fields:
        # Write inline "none" sentinel when no moves are provided;
        # otherwise write multi-line sub-bullets in the `src` -> `dst` grammar.
        if not moves:
            parts.append("- **Moves:** none\n")
        else:
            parts.append("- **Moves:**\n")
            for src, dst in moves:
                parts.append(f"  - `{src}` -> `{dst}`\n")
    if "Requirements" not in missing_fields:
        if requirements is not None:
            parts.append(f"- **Requirements:**\n{requirements}")
        else:
            parts.append("- **Requirements:**\n  See scope.\n")
    if "Commit" not in missing_fields:
        commit_value = commit if commit is not None else f"feat({name}): card {card_num}"
        parts.append(f"- **Commit:** {commit_value}\n")
    return "".join(parts)


def _make_batch_file_cards(name: str, card_nums: list[int]) -> str:
    """Return a batch file with multiple cards (all fields present)."""
    parts = [
        f"# Batch: {name}\n\n",
        "```yaml\n",
        f"task: test\nbatch: {name}\ncards: {len(card_nums)}\nverify: null\ndepends-on: []\n",
        "```\n\n",
        "## Cards\n",
    ]
    for n in card_nums:
        parts.append(
            f"\n### Card {n}: card {n}\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            f"- **Commit:** feat({name}): card {n}\n"
        )
    return "".join(parts)


def _write_plan(plan_dir: Path, overview_text: str, batches: list[tuple[str, str]]) -> None:
    """Write overview + batch files into plan_dir."""
    plan_dir.mkdir(parents=True, exist_ok=True)
    (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
    for filename, content in batches:
        (plan_dir / filename).write_text(content, encoding="utf-8")


def _make_verify_only_batch_text(
    name: str,
    verify_command: str,
    *,
    edits: list[str] | None = None,
) -> str:
    """Return a one-card batch file text with a caller-controlled verify: command.

    ``_make_batch_file`` hardcodes ``verify: null``, which cannot express the exact ``--only`` token
    list the verify-unrelated-test-file tests need to control precisely.
    """
    edits_part = ", ".join(f"`{e}`" for e in edits) if edits else "none"
    return (
        f"# Batch: {name}\n\n"
        "```yaml\n"
        f"task: test\nbatch: {name}\ncards: 1\nverify: {verify_command}\ndepends-on: []\n"
        "```\n\n"
        "## Cards\n\n"
        "### Card 1: card 1\n\n"
        "- **Context:** none\n"
        f"- **Edits:** {edits_part}\n"
        "- **Creates:** none\n"
        "- **Deletes:** none\n"
        "- **Moves:** none\n"
        "- **Requirements:**\n  See scope.\n"
        f"- **Commit:** feat({name}): card 1\n"
    )


def _make_batch_verify_only_text(name: str, verify_block: str | None) -> str:
    """Return a one-card batch file text with a caller-controlled own-frontmatter `verify:` block.

    ``verify_block`` is the raw text spliced in place of the frontmatter's `verify:` value: e.g.
    ``"null"``, a plain command string, or a multi-line mapping block (e.g.
    ``"\\n  cwd: hub\\n  command: some cmd"``).
    When ``None``, the `verify:` key is omitted from the frontmatter entirely -- the batch-file-side
    counterpart to ``_make_overview``'s ``_OMIT_VERIFY`` "absent" case.
    """
    verify_line = "" if verify_block is None else f"verify: {verify_block}\n"
    return (
        f"# Batch: {name}\n\n"
        "```yaml\n"
        f"task: test\nbatch: {name}\ncards: 1\ndepends-on: []\n"
        f"{verify_line}"
        "```\n\n"
        "## Cards\n\n"
        "### Card 1: card 1\n\n"
        "- **Context:** none\n"
        "- **Edits:** none\n"
        "- **Creates:** none\n"
        "- **Deletes:** none\n"
        "- **Moves:** none\n"
        "- **Requirements:**\n  See scope.\n"
        f"- **Commit:** feat({name}): card 1\n"
    )


def _git_commit_new_file(repo_root: Path, rel_path: str, content: str, message: str) -> None:
    """Write ``rel_path`` under ``repo_root`` and commit it onto the branch HEAD currently points to."""
    target = repo_root / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo_root), "add", rel_path], check=True, capture_output=True, text=True,
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "commit", "-q", "-m", message],
        check=True, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# Test functions
# ---------------------------------------------------------------------------

def test_check_non_existent_path_clean() -> int:
    """Clean: all Reads:/Creates: paths exist on disk -> no errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        existing_file = project_root / "src" / "a.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["src/a.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(f"FAIL test_check_non_existent_path_clean: unexpected errors: {check1}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_non_existent_path_clean")
        return 0


def test_check_non_existent_path_dirty() -> int:
    """Dirty: Reads: has nonexistent/path.py -> one non-existent-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["nonexistent/path.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            assert check1[0]["path"] == "nonexistent/path.py", (
                f"wrong path: {check1[0]['path']!r}"
            )
            assert check1[0]["batch"] == "01-alpha", f"wrong batch: {check1[0]['batch']!r}"
            print("PASS test_check_non_existent_path_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_non_existent_path_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_non_existent_path_context_gitignored_clean() -> int:
    """(a) missing Context: ref confirmed git-ignored -> zero non-existent-path findings (#868)."""
    import _test_helpers  # noqa: E402 (local import; sys.path set up at module scope)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        _test_helpers.init_minimal_git_repo(project_root, branch="main")
        # A .gitignore rule only takes effect once the repository recognizes the directory as a
        # git worktree, so the .gitignore file itself must be committed.
        _git_commit_new_file(project_root, ".gitignore", "ignored_dir/\n", "add gitignore")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # The referenced file is never created -- it is confirmed git-ignored instead.
        batch = _make_batch_file("alpha", context=["ignored_dir/runtime_artifact.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [
            e for e in result
            if e["check"] == "non-existent-path" and e["path"] == "ignored_dir/runtime_artifact.py"
        ]
        if check1:
            print(
                f"FAIL test_check_non_existent_path_context_gitignored_clean: unexpected: {check1}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_non_existent_path_context_gitignored_clean")
        return 0


def test_check_non_existent_path_context_not_gitignored_dirty() -> int:
    """(b) missing Context: ref NOT covered by any .gitignore rule -> finding still fires (#868)."""
    import _test_helpers  # noqa: E402

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        _test_helpers.init_minimal_git_repo(project_root, branch="main")
        _git_commit_new_file(project_root, ".gitignore", "ignored_dir/\n", "add gitignore")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["not_ignored_dir/missing.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [
            e for e in result
            if e["check"] == "non-existent-path" and e["path"] == "not_ignored_dir/missing.py"
        ]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            print("PASS test_check_non_existent_path_context_not_gitignored_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_non_existent_path_context_not_gitignored_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_non_existent_path_edits_gitignored_still_dirty() -> int:
    """(c) missing Edits: ref confirmed git-ignored -> finding STILL fires, no leniency (#868)."""
    import _test_helpers  # noqa: E402

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        _test_helpers.init_minimal_git_repo(project_root, branch="main")
        _git_commit_new_file(project_root, ".gitignore", "ignored_dir/\n", "add gitignore")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["ignored_dir/runtime_artifact.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [
            e for e in result
            if e["check"] == "non-existent-path" and e["path"] == "ignored_dir/runtime_artifact.py"
        ]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            print("PASS test_check_non_existent_path_edits_gitignored_still_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_non_existent_path_edits_gitignored_still_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_card_missing_field_clean() -> int:
    """Clean: all required fields present -> no card-missing-field errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check2 = [e for e in result if e["check"] == "card-missing-field"]
        if check2:
            print(f"FAIL test_check_card_missing_field_clean: unexpected errors: {check2}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_card_missing_field_clean")
        return 0


def test_check_card_missing_field_dirty() -> int:
    """Dirty: card omits Edits: -> one card-missing-field error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Edits"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check2 = [e for e in result if e["check"] == "card-missing-field"]
        try:
            assert len(check2) == 1, f"expected 1 error, got {len(check2)}: {check2}"
            assert check2[0]["card"] == 1, f"wrong card: {check2[0]['card']}"
            assert "Edits" in check2[0]["message"], (
                f"message should mention 'Edits': {check2[0]['message']!r}"
            )
            print("PASS test_check_card_missing_field_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_missing_field_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_commit_none_with_content_clean_all_none() -> int:
    """Clean: Commit: none with every other field also none -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", commit="none")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "commit-none-with-content"]
        try:
            assert check == [], f"expected no errors, got: {check}"
            print("PASS test_check_commit_none_with_content_clean_all_none")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_commit_none_with_content_clean_all_none: {exc}", file=sys.stderr)
            return 1


def test_check_commit_none_with_content_dirty_edits() -> int:
    """Dirty: Commit: none with a non-none Edits: -> one error mentioning Edits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", commit="none", edits=["src/a.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "commit-none-with-content"]
        try:
            assert len(check) == 1, f"expected 1 error, got {len(check)}: {check}"
            assert check[0]["card"] == 1, f"wrong card: {check[0]['card']}"
            assert "Edits" in check[0]["message"], (
                f"message should mention 'Edits': {check[0]['message']!r}"
            )
            print("PASS test_check_commit_none_with_content_dirty_edits")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_commit_none_with_content_dirty_edits: {exc}", file=sys.stderr)
            return 1


def test_check_commit_none_with_content_dirty_edits_and_creates() -> int:
    """Dirty: Commit: none with non-none Edits: AND Creates: -> two errors, one per field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha", commit="none", edits=["src/a.py"], creates=["src/b.py"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "commit-none-with-content"]
        try:
            assert len(check) == 2, f"expected 2 errors, got {len(check)}: {check}"
            fields_mentioned = {
                field for field in ("Edits", "Creates")
                if any(field in e["message"] for e in check)
            }
            assert fields_mentioned == {"Edits", "Creates"}, (
                f"expected one error per offending field, got messages: "
                f"{[e['message'] for e in check]}"
            )
            print("PASS test_check_commit_none_with_content_dirty_edits_and_creates")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_commit_none_with_content_dirty_edits_and_creates: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_commit_none_with_content_regression_real_commit_unaffected() -> int:
    """Regression: a real Commit: message with real edits fires zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["src/a.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "commit-none-with-content"]
        try:
            assert check == [], f"expected no errors, got: {check}"
            print("PASS test_check_commit_none_with_content_regression_real_commit_unaffected")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_commit_none_with_content_regression_real_commit_unaffected: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_commit_none_with_content_missing_commit_field_independent() -> int:
    """A card missing Commit: entirely fires card-missing-field, not commit-none-with-content."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Commit"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        commit_none_check = [e for e in result if e["check"] == "commit-none-with-content"]
        missing_field_check = [e for e in result if e["check"] == "card-missing-field"]
        try:
            assert commit_none_check == [], (
                f"expected no commit-none-with-content errors, got: {commit_none_check}"
            )
            assert len(missing_field_check) == 1, (
                f"expected 1 card-missing-field error, got {len(missing_field_check)}: "
                f"{missing_field_check}"
            )
            assert "Commit" in missing_field_check[0]["message"], (
                f"message should mention 'Commit': {missing_field_check[0]['message']!r}"
            )
            print("PASS test_check_commit_none_with_content_missing_commit_field_independent")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_commit_none_with_content_missing_commit_field_independent: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_card_numbering_clean() -> int:
    """Clean: sequential cards [1, 2, 3] -> no card-numbering errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", [1, 2, 3])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check3 = [e for e in result if e["check"] == "card-numbering"]
        if check3:
            print(f"FAIL test_check_card_numbering_clean: unexpected errors: {check3}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_card_numbering_clean")
        return 0


def test_check_card_numbering_dirty_gap() -> int:
    """Dirty: cards [1, 2, 4] in one batch -> one card-numbering error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", [1, 2, 4])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check3 = [e for e in result if e["check"] == "card-numbering"]
        try:
            assert len(check3) == 1, f"expected 1 error, got {len(check3)}: {check3}"
            assert check3[0]["batch"] == "01-alpha", f"wrong batch: {check3[0]['batch']!r}"
            # card 4 is the one that breaks sequence (or 3 is the missing one)
            assert check3[0]["card"] in (3, 4), (
                f"expected card 3 or 4, got {check3[0]['card']}"
            )
            assert "numbering" in check3[0]["message"].lower() or \
                   "sequential" in check3[0]["message"].lower(), (
                f"message should mention numbering/sequential: {check3[0]['message']!r}"
            )
            print("PASS test_check_card_numbering_dirty_gap")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_numbering_dirty_gap: {exc}", file=sys.stderr)
            return 1


def test_check_card_numbering_dirty_cross_batch() -> int:
    """Dirty: card 1 in batch-a AND batch-b -> two card-numbering errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md"},
            {"name": "beta",  "file": "02-beta.md"},
        ])
        batch_a = _make_batch_file("alpha", card_num=1)
        batch_b = _make_batch_file("beta",  card_num=1)
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check3 = [e for e in result if e["check"] == "card-numbering"]
        try:
            assert len(check3) == 2, f"expected 2 errors, got {len(check3)}: {check3}"
            batches = {e["batch"] for e in check3}
            assert "01-alpha" in batches, f"expected 01-alpha in {batches}"
            assert "02-beta" in batches, f"expected 02-beta in {batches}"
            for e in check3:
                assert e["card"] == 1, f"wrong card: {e['card']}"
            print("PASS test_check_card_numbering_dirty_cross_batch")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_numbering_dirty_cross_batch: {exc}", file=sys.stderr)
            return 1


def test_check_depends_on_unknown_clean() -> int:
    """Clean: no depends-on entries -> no depends-on-unknown errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check4 = [e for e in result if e["check"] == "depends-on-unknown"]
        if check4:
            print(f"FAIL test_check_depends_on_unknown_clean: unexpected: {check4}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_depends_on_unknown_clean")
        return 0


def test_check_depends_on_unknown_dirty() -> int:
    """Dirty: depends-on has integer reference to unknown batch number -> one depends-on-unknown error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {
                "name": "alpha",
                "file": "01-alpha.md",
                "number": 1,
                "depends-on": [99],
            }
        ])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check4 = [e for e in result if e["check"] == "depends-on-unknown"]
        try:
            assert len(check4) == 1, f"expected 1 error, got {len(check4)}: {check4}"
            assert check4[0]["batch"] == "alpha", f"wrong batch: {check4[0]['batch']!r}"
            assert "99" in check4[0]["message"], (
                f"message should mention the unknown number: {check4[0]['message']!r}"
            )
            print("PASS test_check_depends_on_unknown_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_depends_on_unknown_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_depends_on_unknown_dirty_legacy_string() -> int:
    """Dirty (legacy): depends-on string references unknown batch name -> one depends-on-unknown error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {
                "name": "alpha",
                "file": "01-alpha.md",
                "depends-on": ["non-existent-batch"],
            }
        ])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check4 = [e for e in result if e["check"] == "depends-on-unknown"]
        try:
            assert len(check4) == 1, f"expected 1 error, got {len(check4)}: {check4}"
            assert check4[0]["batch"] == "alpha", f"wrong batch: {check4[0]['batch']!r}"
            assert "non-existent-batch" in check4[0]["message"], (
                f"message should mention the unknown name: {check4[0]['message']!r}"
            )
            print("PASS test_check_depends_on_unknown_dirty_legacy_string")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_depends_on_unknown_dirty_legacy_string: {exc}", file=sys.stderr)
            return 1


def test_check_parallel_modifies_overlap_clean() -> int:
    """Clean: batch-b depends on batch-a, both modify same file -> no error (not parallel-eligible)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", edits=["shared/file.py"])
        batch_b = _make_batch_file("beta",  edits=["shared/file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check5 = [e for e in result if e["check"] == "parallel-modifies-overlap"]
        if check5:
            print(f"FAIL test_check_parallel_modifies_overlap_clean: unexpected: {check5}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_parallel_modifies_overlap_clean")
        return 0


def test_check_parallel_modifies_overlap_dirty() -> int:
    """Dirty: two batches with no deps both modify shared/file.py -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, edits=["shared/file.py"])
        batch_b = _make_batch_file("beta",  card_num=2, edits=["shared/file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check5 = [e for e in result if e["check"] == "parallel-modifies-overlap"]
        try:
            assert len(check5) == 1, f"expected 1 error, got {len(check5)}: {check5}"
            assert check5[0]["path"] == "shared/file.py", (
                f"wrong path: {check5[0]['path']!r}"
            )
            assert "alpha" in check5[0]["message"] and "beta" in check5[0]["message"], (
                f"message should mention both batch names: {check5[0]['message']!r}"
            )
            print("PASS test_check_parallel_modifies_overlap_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_parallel_modifies_overlap_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_cross_batch_creates_no_depends_on_clean() -> int:
    """Clean: beta depends-on alpha and references alpha's Creates: target -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, creates=["shared/new_file.py"])
        batch_b = _make_batch_file("beta",  card_num=2, context=["shared/new_file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "cross-batch-creates-no-depends-on"]
        if check:
            print(f"FAIL test_check_cross_batch_creates_no_depends_on_clean: unexpected: {check}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_cross_batch_creates_no_depends_on_clean")
        return 0


def test_check_cross_batch_creates_no_depends_on_dirty() -> int:
    """Dirty: beta references alpha's Creates: target but has no depends-on edge -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, creates=["shared/new_file.py"])
        batch_b = _make_batch_file("beta",  card_num=2, context=["shared/new_file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "cross-batch-creates-no-depends-on"]
        try:
            assert len(check) == 1, f"expected 1 error, got {len(check)}: {check}"
            assert check[0]["path"] == "shared/new_file.py", (
                f"wrong path: {check[0]['path']!r}"
            )
            assert "alpha" in check[0]["message"] and "beta" in check[0]["message"], (
                f"message should mention both batch names: {check[0]['message']!r}"
            )
            print("PASS test_check_cross_batch_creates_no_depends_on_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_cross_batch_creates_no_depends_on_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_cross_batch_creates_no_depends_on_transitive_clean() -> int:
    """Clean: gamma depends-on beta depends-on alpha; gamma references alpha's Creates: target -> no error (transitive ancestry honored)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
            {"name": "gamma", "file": "03-gamma.md", "depends-on": ["beta"]},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, creates=["shared/new_file.py"])
        batch_b = _make_batch_file("beta",  card_num=2)
        batch_c = _make_batch_file("gamma", card_num=3, context=["shared/new_file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
            ("03-gamma.md", batch_c),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "cross-batch-creates-no-depends-on"]
        if check:
            print(
                f"FAIL test_check_cross_batch_creates_no_depends_on_transitive_clean: "
                f"unexpected: {check}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_cross_batch_creates_no_depends_on_transitive_clean")
        return 0


def test_check_reads_not_backtick_path_clean() -> int:
    """Clean: backtick-only bullets and 'none' sentinel -> no reads-not-backtick-path errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # Create the referenced file so check 1 doesn't fire.
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # Single-line backtick: clean; Edits: none (exempt)
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: description\n\n"
            "- **Context:** `src/a.py`\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]
        if check6:
            print(f"FAIL test_check_reads_not_backtick_path_clean: unexpected: {check6}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_reads_not_backtick_path_clean")
        return 0


def test_check_reads_not_backtick_path_none_exempt() -> int:
    """Clean: `- **Context:** none` returns [] for check 6."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")  # defaults to "none" for reads/modifies/creates
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]
        if check6:
            print(
                f"FAIL test_check_reads_not_backtick_path_none_exempt: "
                f"'none' should be exempt: {check6}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_reads_not_backtick_path_none_exempt")
        return 0


def test_check_reads_not_backtick_path_dirty() -> int:
    """Dirty: Reads: bullet has prose alongside backtick path -> one reads-not-backtick-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # Create file so check 1 doesn't fire.
        (project_root / "src").mkdir(parents=True)
        (project_root / "src" / "foo.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: description\n\n"
            "- **Context:** `src/foo.py` (used by foo)\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]
        try:
            assert len(check6) == 1, f"expected 1 error, got {len(check6)}: {check6}"
            assert check6[0]["check"] == "reads-not-backtick-path"
            print("PASS test_check_reads_not_backtick_path_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_reads_not_backtick_path_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_reads_not_backtick_path_dirty_multiline_multi_backtick() -> int:
    """Dirty: multi-line sub-bullet has a leading path plus a parenthetical with further backtick
    spans -> Check 6 independently flags the sub-bullet.

    This is the same repro shape as the #580 bug that motivated the parse_batch_refs leading-token
    fix in _review_common.py.
    Check 6 catches it independently at plan-validate --stage prepare time (layered defense; Check 6
    is unmodified by this plan)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # Create the file so check 1 (non-existent-path) doesn't also fire.
        (project_root / "cmd" / "lyx").mkdir(parents=True)
        (project_root / "cmd" / "lyx" / "main_test.go").write_text(
            "# placeholder", encoding="utf-8"
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: description\n\n"
            "- **Context:**\n"
            "  - `cmd/lyx/main_test.go` (batch 3 routed `boardcli`'s dir through `paths.Resolve`)\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check6 = [e for e in result if e["check"] == "reads-not-backtick-path"]
        try:
            assert len(check6) >= 1, (
                f"expected at least 1 error, got {len(check6)}: {check6}"
            )
            print(
                "PASS: test_check_reads_not_backtick_path_dirty_multiline_multi_backtick"
            )
            return 0
        except AssertionError as exc:
            print(
                f"FAIL: test_check_reads_not_backtick_path_dirty_multiline_multi_backtick: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_all_files_touched_mismatch_clean_no_section() -> int:
    """Clean: overview without All Files Touched section -> no errors for check 8."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check8 = [e for e in result if e["check"] == "all-files-touched-mismatch"]
        if check8:
            print(
                f"FAIL test_check_all_files_touched_mismatch_clean_no_section: "
                f"no section should produce no errors: {check8}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_all_files_touched_mismatch_clean_no_section")
        return 0


def test_check_all_files_touched_mismatch_dirty() -> int:
    """Dirty: overview lists path/extra.py not in any card's Modifies:/Creates: -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Overview declares "path/extra.py" but no card modifies/creates it.
        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            all_files_touched=["path/extra.py"],
        )
        batch = _make_batch_file("alpha")  # Modifies: none, Creates: none
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check8 = [e for e in result if e["check"] == "all-files-touched-mismatch"]
        try:
            assert len(check8) == 1, f"expected 1 error, got {len(check8)}: {check8}"
            assert check8[0]["path"] == "path/extra.py", (
                f"wrong path: {check8[0]['path']!r}"
            )
            assert "All Files Touched" in check8[0]["message"], (
                f"message should mention 'All Files Touched': {check8[0]['message']!r}"
            )
            print("PASS test_check_all_files_touched_mismatch_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_all_files_touched_mismatch_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_all_files_touched_mismatch_deletes_only_excluded() -> int:
    """Deletes-only path not in All Files Touched -> zero all-files-touched-mismatch errors
    (regression for #494).

    This tests the git-mv rename shape: a card has Deletes: old/path and Creates: new/path, with
    only the created path in overview's All Files Touched.
    The deleted path should NOT trigger an all-files-touched-mismatch error, because Deletes: tokens
    are excluded from the check per issue #494.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Overview includes only the new path (created by the card).
        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            all_files_touched=["new/path.py"],
        )
        # Card deletes old/path.py, creates new/path.py.
        # Only new/path.py is in All Files Touched (correct for git-mv pattern).
        batch = _make_batch_file(
            "alpha",
            deletes=["old/path.py"],
            creates=["new/path.py"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [e for e in result if e["check"] == "all-files-touched-mismatch"]
        try:
            assert len(mismatch_errs) == 0, (
                f"Deletes-only path should be excluded from all-files-touched check, "
                f"got: {mismatch_errs}"
            )
            print("PASS test_check_all_files_touched_mismatch_deletes_only_excluded")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_all_files_touched_mismatch_deletes_only_excluded: {exc}", file=sys.stderr)
            return 1


def test_run_returns_sorted() -> int:
    """Output is sorted by (batch or '', card or 0, check)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md"},
            {"name": "beta",  "file": "02-beta.md"},
        ])
        # 01-alpha: card missing Edits -> card-missing-field (batch=01-alpha, card=1)
        batch_a = _make_batch_file("alpha", missing_fields={"Edits"})
        # 02-beta: nonexistent path -> non-existent-path (batch=02-beta, card=None->0)
        batch_b = _make_batch_file("beta", context=["nonexistent/thing.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        try:
            assert len(result) >= 2, f"expected at least 2 errors, got {len(result)}: {result}"
            # Verify sort key: (batch or "", card or 0, check)
            keys = [(e["batch"] or "", e["card"] or 0, e["check"]) for e in result]
            assert keys == sorted(keys), f"result is not sorted: {keys}"
            print("PASS test_run_returns_sorted")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_run_returns_sorted: {exc}", file=sys.stderr)
            return 1


def test_run_no_overview() -> int:
    """Empty plan_dir (no overview) -> one missing-overview error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        plan_dir.mkdir()
        project_root.mkdir()

        result = _plan_validate.run(plan_dir, project_root)
        try:
            assert len(result) == 1, f"expected 1 error, got {len(result)}: {result}"
            assert result[0]["check"] == "missing-overview", (
                f"wrong check: {result[0]['check']!r}"
            )
            print("PASS test_run_no_overview")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_run_no_overview: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Tests for Deletes-aware behaviour (Cards 26–28)
# ---------------------------------------------------------------------------

def test_deletes_field_required() -> int:
    """(a) Card without - **Deletes:** line -> card-missing-field error mentioning 'Deletes:'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Deletes"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        deletes_errs = [
            e for e in result
            if e["check"] == "card-missing-field" and "Deletes:" in e["message"]
        ]
        try:
            assert len(deletes_errs) == 1, (
                f"expected 1 Deletes: card-missing-field error, got: {deletes_errs}"
            )
            assert deletes_errs[0]["card"] == 1, f"wrong card: {deletes_errs[0]['card']}"
            assert "missing required field: Deletes:" in deletes_errs[0]["message"], (
                f"message should contain 'missing required field: Deletes:': "
                f"{deletes_errs[0]['message']!r}"
            )
            print("PASS test_deletes_field_required")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_deletes_field_required: {exc}", file=sys.stderr)
            return 1


def test_deletes_token_on_disk_clean() -> int:
    """(b) Deletes: token resolves to an on-disk file -> no non-existent-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        existing_file = project_root / "src" / "to_delete.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", deletes=["src/to_delete.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(
                f"FAIL test_deletes_token_on_disk_clean: unexpected errors: {check1}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_deletes_token_on_disk_clean")
        return 0


def test_deletes_token_in_creates_union_clean() -> int:
    """(c) Deletes: token missing on disk + in another batch's Creates: -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, creates=["generated/file.py"])
        batch_b = _make_batch_file("beta",  card_num=2, deletes=["generated/file.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(
                f"FAIL test_deletes_token_in_creates_union_clean: unexpected errors: {check1}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_deletes_token_in_creates_union_clean")
        return 0


def test_deletes_token_missing_not_in_creates_dirty() -> int:
    """(d) Deletes: token missing on disk + not in any Creates: -> non-existent-path with Deletes-specific message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", deletes=["missing/file.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            assert check1[0]["path"] == "missing/file.py", (
                f"wrong path: {check1[0]['path']!r}"
            )
            assert check1[0]["message"].startswith("Deletes: token '"), (
                f"message should start with \"Deletes: token '\": {check1[0]['message']!r}"
            )
            print("PASS test_deletes_token_missing_not_in_creates_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_deletes_token_missing_not_in_creates_dirty: {exc}", file=sys.stderr)
            return 1


def test_reads_token_in_deletes_union_clean() -> int:
    """(e) Reads: token missing on disk + in another batch's Deletes: -> no error for that token."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        # alpha reads going/away.py (not on disk);
        # beta declares it as Deletes:.
        # Alpha's Reads: reference must be suppressed by deletes_union.
        batch_a = _make_batch_file("alpha", card_num=1, context=["going/away.py"])
        batch_b = _make_batch_file("beta",  card_num=2, deletes=["going/away.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        alpha_errs = [
            e for e in result
            if e["check"] == "non-existent-path"
            and e["batch"] == "01-alpha"
            and e["path"] == "going/away.py"
        ]
        try:
            assert len(alpha_errs) == 0, (
                f"expected no error for alpha's Reads: token, got: {alpha_errs}"
            )
            print("PASS test_reads_token_in_deletes_union_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_reads_token_in_deletes_union_clean: {exc}", file=sys.stderr)
            return 1


def test_reads_token_in_creates_union_suppressed() -> int:
    """(f) Reads: token missing on disk + in creates_union -> no error (existing behaviour)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": ["alpha"]},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, creates=["generated/output.py"])
        batch_b = _make_batch_file("beta",  card_num=2, context=["generated/output.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        if check1:
            print(
                f"FAIL test_reads_token_in_creates_union_suppressed: unexpected errors: {check1}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_reads_token_in_creates_union_suppressed")
        return 0


def test_wiki_config_mutation_clean() -> int:
    """mill-config.yaml only in Reads: (not Modifies/Creates) -> zero wiki-config-mutation errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 wiki-config-mutation errors, got: {check_errors}"
            )
            print("PASS test_wiki_config_mutation_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_clean: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_modifies() -> int:
    """mill-config.yaml in Modifies: -> exactly one wiki-config-mutation error with correct shape."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 wiki-config-mutation error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["check"] == "wiki-config-mutation", f"wrong check: {e['check']!r}"
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"card should be None, got: {e['card']!r}"
            assert e["path"] == "mill-config.yaml", f"wrong path: {e['path']!r}"
            print("PASS test_wiki_config_mutation_modifies")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_modifies: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_creates() -> int:
    """mill-config.yaml in Creates: -> exactly one wiki-config-mutation error with correct shape."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", creates=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 wiki-config-mutation error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["check"] == "wiki-config-mutation", f"wrong check: {e['check']!r}"
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"card should be None, got: {e['card']!r}"
            assert e["path"] == "mill-config.yaml", f"wrong path: {e['path']!r}"
            print("PASS test_wiki_config_mutation_creates")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_creates: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_multi_batch() -> int:
    """Two batches each with mill-config.yaml in Modifies: -> exactly two wiki-config-mutation errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = _make_batch_file("alpha", card_num=1, edits=["mill-config.yaml"])
        batch_b = _make_batch_file("beta",  card_num=2, edits=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 2, (
                f"expected 2 wiki-config-mutation errors (one per batch), got: {check_errors}"
            )
            batches = {e["batch"] for e in check_errors}
            assert "01-alpha" in batches, f"expected 01-alpha in {batches}"
            assert "02-beta" in batches, f"expected 02-beta in {batches}"
            print("PASS test_wiki_config_mutation_multi_batch")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_multi_batch: {exc}", file=sys.stderr)
            return 1


def test_wiki_config_mutation_modifies_and_creates() -> int:
    """mill-config.yaml in both Modifies: and Creates: -> exactly one error (deduplicated)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["mill-config.yaml"],
            creates=["mill-config.yaml"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "wiki-config-mutation"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 wiki-config-mutation error (deduplicated), got: {check_errors}"
            )
            print("PASS test_wiki_config_mutation_modifies_and_creates")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_wiki_config_mutation_modifies_and_creates: {exc}", file=sys.stderr)
            return 1


def test_plugin_manifest_context_missing_creates_dirty() -> int:
    """Creates: touches plugins/mill/agents/ with no manifest ref -> exactly one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", creates=["plugins/mill/agents/new-agent.md"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "plugin-manifest-context-missing"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 plugin-manifest-context-missing error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"card should be None, got: {e['card']!r}"
            assert e["path"] == "plugins/mill/.claude-plugin/plugin.json", f"wrong path: {e['path']!r}"
            print("PASS test_plugin_manifest_context_missing_creates_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_plugin_manifest_context_missing_creates_dirty: {exc}", file=sys.stderr)
            return 1


def test_plugin_manifest_context_missing_creates_with_context_clean() -> int:
    """Creates: touches agents/ with manifest in Context: -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            creates=["plugins/mill/agents/new-agent.md"],
            context=["plugins/mill/.claude-plugin/plugin.json"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "plugin-manifest-context-missing"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 plugin-manifest-context-missing errors, got: {check_errors}"
            )
            print("PASS test_plugin_manifest_context_missing_creates_with_context_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_plugin_manifest_context_missing_creates_with_context_clean: {exc}", file=sys.stderr)
            return 1


def test_plugin_manifest_context_missing_creates_with_edits_clean() -> int:
    """Creates: touches agents/ with manifest in Edits: (the primary case) -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            creates=["plugins/mill/agents/new-agent.md"],
            edits=["plugins/mill/.claude-plugin/plugin.json"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "plugin-manifest-context-missing"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 plugin-manifest-context-missing errors, got: {check_errors}"
            )
            print("PASS test_plugin_manifest_context_missing_creates_with_edits_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_plugin_manifest_context_missing_creates_with_edits_clean: {exc}", file=sys.stderr)
            return 1


def test_plugin_manifest_context_missing_deletes_dirty() -> int:
    """Deletes: touches agents/ (symmetric removal case) with no manifest ref -> exactly one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", deletes=["plugins/mill/agents/old-agent.md"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "plugin-manifest-context-missing"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 plugin-manifest-context-missing error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"card should be None, got: {e['card']!r}"
            assert e["path"] == "plugins/mill/.claude-plugin/plugin.json", f"wrong path: {e['path']!r}"
            print("PASS test_plugin_manifest_context_missing_deletes_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_plugin_manifest_context_missing_deletes_dirty: {exc}", file=sys.stderr)
            return 1


def test_plugin_manifest_context_missing_unrelated_batch_clean() -> int:
    """Batch never touches plugins/mill/agents/ -> zero errors regardless of manifest presence."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["plugins/mill/scripts/_review_plan.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "plugin-manifest-context-missing"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 plugin-manifest-context-missing errors, got: {check_errors}"
            )
            print("PASS test_plugin_manifest_context_missing_unrelated_batch_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_plugin_manifest_context_missing_unrelated_batch_clean: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_in_context() -> int:
    """Requirements: token also present in this card's own Context: -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            context=["src/a.py"],
            requirements="  Read `src/a.py` before editing.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_in_context")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_in_context: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_in_edits() -> int:
    """Requirements: token also present in this card's own Edits: -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  Edit `src/a.py` to add the new field.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_in_edits")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_in_edits: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_in_creates() -> int:
    """Requirements: token present in Creates: (not yet on disk) -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            creates=["src/new.py"],
            requirements="  Create `src/new.py` with the new helper.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_in_creates")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_in_creates: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_dirty_missing() -> int:
    """Requirements: token exists on disk but absent from this card's own refs -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "helper.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `src/helper.py` for the pattern to follow.\n",
        )
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["check"] == "context-completeness", f"wrong check: {e['check']!r}"
            assert e["card"] == 1, f"wrong card: {e['card']!r}"
            assert e["path"] == "src/helper.py", f"wrong path: {e['path']!r}"
            assert e["line"] == "See `src/helper.py` for the pattern to follow.", (
                f"wrong line: {e['line']!r}"
            )
            print("PASS test_check_context_completeness_dirty_missing")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_dirty_missing: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_dirty_missing_scoped_to_own_card() -> int:
    """Missing token present in a DIFFERENT card's Context: -> error still raised (per-card scoping)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "shared.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "c.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta", "file": "02-beta.md", "depends-on": []},
        ])
        batch_a = _make_batch_file(
            "alpha",
            card_num=1,
            edits=["src/a.py"],
            requirements="  Follow the pattern in `src/shared.py`.\n",
        )
        batch_b = _make_batch_file(
            "beta",
            card_num=2,
            context=["src/shared.py"],
            edits=["src/c.py"],
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] == 1, f"wrong card: {e['card']!r}"
            assert e["path"] == "src/shared.py", f"wrong path: {e['path']!r}"
            print("PASS test_check_context_completeness_dirty_missing_scoped_to_own_card")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_dirty_missing_scoped_to_own_card: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_non_path_token() -> int:
    """Requirements: token has no '/' and no recognized extension -> zero errors (not path-shaped)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  Call `_load_config` from the existing helper module.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_non_path_token")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_non_path_token: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_unresolvable_token() -> int:
    """Path-shaped Requirements: token that does not exist anywhere -> zero errors (never flagged)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  The API returns a `response.json` body with a status field.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_unresolvable_token")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_unresolvable_token: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_in_deletes() -> int:
    """Requirements: token present in this card's own Deletes: -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            deletes=["src/gone.py"],
            requirements="  Remove `src/gone.py`, which is now dead code.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_in_deletes")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_in_deletes: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_in_moves_source() -> int:
    """Requirements: token names the SOURCE half of this card's own Moves: pair -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "old.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            moves=[("src/old.py", "src/new.py")],
            requirements="  Relocate the logic currently in `src/old.py`.\n",
        )
        batch += "\n## Rename mechanic\n\nUse `git mv` then apply surgical edits.\n"
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_in_moves_source")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_in_moves_source: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_dirty_moves_target_only() -> int:
    """Requirements: token names the TARGET half of a Moves: pair -> one error (only source is exempt)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "old2.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            moves=[("src/old2.py", "src/new2.py")],
            requirements="  The relocated file will live at `src/new2.py`.\n",
        )
        batch += "\n## Rename mechanic\n\nUse `git mv` then apply surgical edits.\n"
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            assert check_errors[0]["path"] == "src/new2.py", (
                f"wrong path: {check_errors[0]['path']!r}"
            )
            print("PASS test_check_context_completeness_dirty_moves_target_only")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_dirty_moves_target_only: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_run_wiring_no_false_positives() -> int:
    """Full plan fixture with one broken card -> exactly one finding, and it is context-completeness."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "c.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview(
            [
                {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
                {"name": "beta", "file": "02-beta.md", "depends-on": []},
            ],
            all_files_touched=["src/a.py", "src/c.py"],
        )
        batch_a = _make_batch_file(
            "alpha",
            card_num=1,
            edits=["src/a.py"],
            requirements="  Model this card's edit on `src/b.py`.\n",
        )
        batch_b = _make_batch_file(
            "beta",
            card_num=2,
            edits=["src/c.py"],
            requirements="  Edit `src/c.py` to add the new behavior.\n",
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        try:
            context_completeness_errors = [e for e in result if e["check"] == "context-completeness"]
            other_errors = [e for e in result if e["check"] != "context-completeness"]
            assert len(context_completeness_errors) == 1, (
                f"expected 1 context-completeness error, got: {context_completeness_errors}"
            )
            assert context_completeness_errors[0]["path"] == "src/b.py", (
                f"wrong path: {context_completeness_errors[0]['path']!r}"
            )
            assert other_errors == [], (
                f"expected zero errors from other checks, got: {other_errors}"
            )
            print("PASS test_check_context_completeness_run_wiring_no_false_positives")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_run_wiring_no_false_positives: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_prohibition_marker() -> int:
    """Requirements: prohibition sentence naming a real file -> zero errors (exemption)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "mill-config.yaml").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  This card must forbid touching `mill-config.yaml`.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_prohibition_marker")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_prohibition_marker: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_line_range_suffix_in_context() -> int:
    """Line-range-suffixed Requirements: token whose un-suffixed form is in Context: -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            context=["src/a.py"],
            requirements="  See `src/a.py:10-20` for the relevant function.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_line_range_suffix_in_context")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_clean_line_range_suffix_in_context: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_dirty_line_range_suffix_missing() -> int:
    """Line-range-suffixed token absent from own refs -> one error whose path keeps the suffix."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `src/b.py:10-20` for the relevant function.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            assert check_errors[0]["path"] == "src/b.py:10-20", (
                f"wrong path: {check_errors[0]['path']!r}"
            )
            print("PASS test_check_context_completeness_dirty_line_range_suffix_missing")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_dirty_line_range_suffix_missing: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_directory_reference() -> int:
    """Directory-only backtick token that exists on disk as a directory (no file of that name) -> clean, no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "internal" / "gitrepo").mkdir(parents=True)
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `internal/gitrepo` for the existing repo-handling conventions.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_directory_reference")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_directory_reference: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_clean_directory_reference_not_on_disk() -> int:
    """Same directory-shaped token, nothing exists at that path on disk -> also clean (deterministic regardless of on-disk state)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `internal/gitrepo` for the existing repo-handling conventions.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_directory_reference_not_on_disk")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_clean_directory_reference_not_on_disk: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_double_slash_token() -> int:
    """Root-path-shaped backtick token (two consecutive forward slashes) always resolves to the filesystem root and so always "exists" -> must still be clean, no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `//` for the existing repo-handling conventions.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_double_slash_token")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_clean_double_slash_token: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_dirty_odd_backtick_count_line_field() -> int:
    """Odd backtick count on one Requirements: line mis-pairs `findall` -> the span between a stray,
    incompletely-closed backtick and the next backtick (never meant to delimit a path reference)
    is captured as a token instead.
    Reproduces the actual false-positive mechanism from discussion.md's Gap 1 Problem section: the
        line intends two independent references, `src/a.py` (correct, and present in this card's own
        Edits:) and `src/b.py` (correct, but never captured at all because its own opening backtick
        gets consumed as the CLOSING backtick of the stray, unrelated one before it) -- but a stray
        backtick left after "config" (as if from an incompletely-closed inline-code span) makes
        `findall`'s greedy left-to-right pairing group the text between that stray backtick and
        `src/b.py`'s opening backtick -- which is exactly `src/other.py` -- as its own mis-paired
        token. `src/other.py` is path-shaped (ends in .py), exists on disk, and is absent from this
        card's own refs, so exactly one context-completeness error should be raised, and its line
        field must name this single malformed line verbatim (stripped), not any other."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "other.py").write_text("# placeholder", encoding="utf-8")

        malformed_line = (
            "  See `src/a.py` for pattern, per config`src/other.py`src/b.py` too.\n"
        )
        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements=malformed_line,
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["path"] == "src/other.py", f"wrong path: {e['path']!r}"
            assert e["line"] == malformed_line.strip(), f"wrong line: {e['line']!r}"
            print("PASS test_check_context_completeness_dirty_odd_backtick_count_line_field")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_dirty_odd_backtick_count_line_field: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_citation_marker() -> int:
    """Requirements: names a file via a _CITATION_MARKERS phrase -> zero errors (citation exemption)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/b.py"],
            requirements="  Follow the pattern shown, citing `src/a.py` as an example of the pattern to follow.\n",
        )
        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_citation_marker")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_context_completeness_clean_citation_marker: {exc}", file=sys.stderr)
            return 1


def test_check_context_completeness_dirty_citation_marker_absent() -> int:
    """Same file reference reworded to drop every citation-marker phrase -> one error (no over-exemption)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/b.py"],
            requirements="  See `src/a.py` for the pattern to follow.\n",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_dirty_citation_marker_absent")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_dirty_citation_marker_absent: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_signature_inlined_marker() -> int:
    """Requirements: names a real, resolvable, backtick-wrapped file absent from the card's own refs, together with 'signature inlined' -> zero errors (inline-signature citation exemption)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/b.py"],
            requirements=(
                "  Call `helper()` (signature inlined from `src/a.py`: `def helper() -> int`).\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_signature_inlined_marker")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_clean_signature_inlined_marker: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_no_file_read_needed_marker() -> int:
    """Same shape as the 'signature inlined' case, but the line instead carries 'no file read needed' -> zero errors (inline-signature citation exemption, second marker spelling)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/b.py"],
            requirements=(
                "  Call `helper()` (defined in `src/a.py` as `def helper() -> int`; "
                "no file read needed).\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_no_file_read_needed_marker")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_clean_no_file_read_needed_marker: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_dirty_inline_signature_marker_absent() -> int:
    """Identical file reference and inlined signature, but with neither 'signature inlined' nor 'no file read needed' present -> one error, proving the exemption (not an unrelated change) is responsible."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/b.py"],
            requirements=(
                "  Call `helper()` (defined in `src/a.py` as `def helper() -> int`).\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_dirty_inline_signature_marker_absent")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_dirty_inline_signature_marker_absent: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_moves_source_plan_wide() -> int:
    """Requirements: token in a LATER batch names an EARLIER batch's Moves: source -> zero errors (plan-wide exemption)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "old.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta", "file": "02-beta.md", "number": 2, "depends-on": [1]},
        ])
        batch_a = _make_batch_file(
            "alpha",
            card_num=1,
            moves=[("old.py", "new.py")],
        )
        batch_a += "\n## Rename mechanic\n\nUse `git mv` then apply surgical edits.\n"
        batch_b = _make_batch_file(
            "beta",
            card_num=2,
            edits=["src/c.py"],
            requirements="  Reuse the logic that used to live in `old.py`.\n",
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_moves_source_plan_wide")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_context_completeness_clean_moves_source_plan_wide: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_dirty_moves_target_plan_wide_still_flagged() -> int:
    """Same two-batch shape, but the later batch's Requirements: names the Moves: TARGET instead of the source -> one error (target-only exemption stays per-card)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "old.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta", "file": "02-beta.md", "number": 2, "depends-on": [1]},
        ])
        batch_a = _make_batch_file(
            "alpha",
            card_num=1,
            moves=[("old.py", "new.py")],
        )
        batch_a += "\n## Rename mechanic\n\nUse `git mv` then apply surgical edits.\n"
        batch_b = _make_batch_file(
            "beta",
            card_num=2,
            edits=["src/c.py"],
            requirements="  The relocated file will live at `new.py`.\n",
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            assert check_errors[0]["path"] == "new.py", (
                f"wrong path: {check_errors[0]['path']!r}"
            )
            print("PASS test_check_context_completeness_dirty_moves_target_plan_wide_still_flagged")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_dirty_moves_target_plan_wide_still_flagged: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_message_includes_moves_source_qualifier() -> int:
    """Error message field's trailing field list reads Moves:-source, not bare Moves:."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "helper.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements="  See `src/helper.py` for the pattern to follow.\n",
        )
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            assert "Moves:-source" in check_errors[0]["message"], (
                f"expected 'Moves:-source' in message, got: {check_errors[0]['message']!r}"
            )
            print("PASS test_check_context_completeness_message_includes_moves_source_qualifier")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_message_includes_moves_source_qualifier: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_prohibition_marker_change_modify() -> int:
    """Requirements: lines using "do not change"/"must not modify" phrasing on real files -> zero errors (prohibition exemption)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "x.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "y.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements=(
                "  Implementers do not change `src/x.py` as part of this card.\n"
                "  Implementers must not modify `src/y.py` as part of this card.\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_prohibition_marker_change_modify")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_clean_prohibition_marker_change_modify: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_prohibition_marker_untested_existing() -> int:
    """Requirements: lines using the 6 previously-untested existing prohibition markers -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "m1.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "m2.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "m3.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "m4.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "m5.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "m6.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements=(
                "  Implementers must never touch `src/m1.py` as part of this card.\n"
                "  Implementers must not touch `src/m2.py` as part of this card.\n"
                "  Implementers do not touch `src/m3.py` as part of this card.\n"
                "  Reviewers should not touch `src/m4.py` for this card.\n"
                "  This card must never change `src/m5.py`.\n"
                "  This card must never modify `src/m6.py`.\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_prohibition_marker_untested_existing")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_clean_prohibition_marker_untested_existing: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_prohibition_marker_new_verbs() -> int:
    """Requirements: lines using the new verb/negation combinations -> zero errors (prohibition exemption)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "n1.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "n2.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "n3.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "n4.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "n5.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements=(
                "  Implementers do not edit `src/n1.py` as part of this card.\n"
                "  Implementers do not add `src/n2.py` as part of this card.\n"
                "  Implementers do not link `src/n3.py` as part of this card.\n"
                "  Implementers do not read `src/n4.py` as part of this card.\n"
                "  Implementers don't touch `src/n5.py` as part of this card.\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_prohibition_marker_new_verbs")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_clean_prohibition_marker_new_verbs: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_clean_prohibition_marker_write_irregular() -> int:
    """Requirements: lines using write's irregular inflected forms (write/written) -> zero errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "w1.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "w2.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements=(
                "  Implementers do not write to `src/w1.py` as part of this card.\n"
                "  Implementers must not have written `src/w2.py` as part of this card.\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 context-completeness errors, got: {check_errors}"
            )
            print("PASS test_check_context_completeness_clean_prohibition_marker_write_irregular")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_clean_prohibition_marker_write_irregular: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_dirty_prohibition_marker_unrelated_negation_not_exempted() -> int:
    """A negation word with no verb-form match on the line does not exempt a genuine dependency."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "dep.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements=(
                "  The parser doesn't stop early; consult `src/dep.py` for the shared logic.\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            assert check_errors[0]["path"] == "src/dep.py", (
                f"expected path 'src/dep.py', got: {check_errors[0]['path']!r}"
            )
            print(
                "PASS test_check_context_completeness_dirty_prohibition_marker_unrelated_negation_not_exempted"
            )
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_dirty_prohibition_marker_unrelated_negation_not_exempted: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_context_completeness_dirty_prohibition_marker_verb_without_negation_not_exempted() -> int:
    """A verb-form match with no negation word on the line does not exempt a genuine dependency."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
        (project_root / "src" / "dep2.py").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/a.py"],
            requirements=(
                "  Read `src/dep2.py` to understand the shared helper.\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "context-completeness"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 context-completeness error, got: {check_errors}"
            )
            assert check_errors[0]["path"] == "src/dep2.py", (
                f"expected path 'src/dep2.py', got: {check_errors[0]['path']!r}"
            )
            print(
                "PASS test_check_context_completeness_dirty_prohibition_marker_verb_without_negation_not_exempted"
            )
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_context_completeness_dirty_prohibition_marker_verb_without_negation_not_exempted: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_exact_match() -> int:
    """Fence content is already a byte-exact substring of the target Edits: file -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "def helper():\n    return 1\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "def helper():\n"
                "    return 1\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_exact_match")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_exact_match: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_illustrative_snippet() -> int:
    """Fence shows plausible but different code, not a substring at any N in 1..40 -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "def helper():\n    return 1\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Illustrative:\n"
                "```\n"
                "def other_func():\n"
                "    return 999\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_illustrative_snippet")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_illustrative_snippet: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_no_edits_field() -> int:
    """Card's Edits: is none -> check is a no-op, nothing to compare against."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=None,
            requirements=(
                "  Quote:\n"
                "```\n"
                "def helper():\n"
                "    return 1\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_no_edits_field")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_no_edits_field: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_list_continuation_indent() -> int:
    """Flush-left source snippet, fence has a uniform 2-space list-continuation indent baked in."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "alpha\nbeta\ngamma\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "  ```\n"
                "  alpha\n"
                "  beta\n"
                "  gamma\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["card"] == 1, f"wrong card: {e['card']!r}"
            assert e["path"] == "src/target.py", f"wrong path: {e['path']!r}"
            assert "N=2" in e["message"], f"message missing N=2: {e['message']!r}"
            print("PASS test_check_requirements_quote_indent_drift_dirty_list_continuation_indent")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_dirty_list_continuation_indent: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent() -> int:
    """Source has its own 4-space baseline indent; fence adds a further uniform 2 spaces on top."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "    alpha\n    beta\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "  ```\n"
                "      alpha\n"
                "      beta\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            e = check_errors[0]
            assert "N=2" in e["message"], f"message missing N=2: {e['message']!r}"
            print("PASS test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card() -> int:
    """Two fences under one card; only the second has the drift bug -> exactly one error, fence 2."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "first_line\nsecond_line\nthird_line\nfourth_line\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Clean fence:\n"
                "```\n"
                "first_line\n"
                "second_line\n"
                "```\n"
                "  Drifted fence:\n"
                "  ```\n"
                "   third_line\n"
                "   fourth_line\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            e = check_errors[0]
            assert "fence 2" in e["message"], f"message missing fence 2: {e['message']!r}"
            print("PASS test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_crlf_source_lf_fence() -> int:
    """Target file on disk uses CRLF;
    the plan's fence body uses LF, with a drift bug on top.
    Verifies that the check correctly detects the indent drift despite mismatched line-ending styles
        on disk, relying on Path.read_text()'s built-in universal-newlines translation which
        normalizes all line-ending styles to LF before comparison.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "line one\r\nline two\r\n", encoding="utf-8", newline="",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "  ```\n"
                "  line one\n"
                "  line two\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_dirty_crlf_source_lf_fence")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_dirty_crlf_source_lf_fence: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_fence_contains_nested_heading() -> int:
    """Fence body with flush-left look-alike lines tests in_fence boundary detection.
    Fence contains a flush-left '- **Field:**'-shaped line that should NOT terminate field body
        extraction when in_fence is True.
    The indented `### ` heading prevents _parse_cards from mis-splitting the card, while flush-left
        look-alike line and fence delimiters test that in_fence guard actually prevents boundary
        truncation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "### Nested Heading\n- **SomeField:** value\nalpha\nbeta\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # Build batch file as raw string to isolate from _parse_cards boundary logic: - Indented `### ` heading prevents _parse_cards from terminating the card - Flush-left fence delimiters and look-alike lines test in_fence guard - Drift indentation (2 spaces) only on lines that don't need regex matching
        batch = """# Batch: alpha

```yaml
task: test
batch: alpha
cards: 1
verify: null
depends-on: []
```

## Cards

### Card 1: card 1

- **Context:** none
- **Edits:** `src/target.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**
```
  ### Nested Heading
- **SomeField:** value
  alpha
  beta
```
- **Commit:** feat(alpha): card 1
"""
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            print(
                "PASS test_check_requirements_quote_indent_drift_dirty_fence_contains_nested_heading"
            )
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_requirements_quote_indent_drift_dirty_fence_contains_nested_heading: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break() -> int:
    """Both Edits: files independently contain the stripped fence content -> error names the first."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "first.py").write_text(
            "shared_line_one\nshared_line_two\n", encoding="utf-8",
        )
        (project_root / "src" / "second.py").write_text(
            "shared_line_one\nshared_line_two\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/first.py", "src/second.py"],
            requirements=(
                "  Quote:\n"
                "  ```\n"
                "  shared_line_one\n"
                "  shared_line_two\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            assert check_errors[0]["path"] == "src/first.py", (
                f"wrong path: {check_errors[0]['path']!r}"
            )
            print("PASS test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer() -> int:
    """Mid-line fragment quote, fence at zero indent, closer also zero indent -> clean (#761: previously reported a spurious N=1 via _strip_n_leading_spaces's splitlines() side effect of dropping the fence's own trailing newline)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "value = compute(x, y) + offset\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "compute(x, y)\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer() -> int:
    """Byte-exact quoted content, closing fence carries list-continuation indentation -> clean (#754: previously fell through to the N-search and matched via incidental adjacent-content coincidence instead of the byte-exact pre-check)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "alpha\nbeta\ngamma\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "beta\n"
                "gamma\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence() -> int:
    """Source has a 2-space baseline indent, fence is flattened to column zero -> one finding, message states it matched after ADDING 2 leading spaces per line (the under-indent direction, #the add pass)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "  alpha\n  beta\n  gamma\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "alpha\n"
                "beta\n"
                "gamma\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            e = check_errors[0]
            assert e["path"] == "src/target.py", f"wrong path: {e['path']!r}"
            assert "after adding 2 leading spaces per line" in e["message"], (
                f"message should state the add direction: {e['message']!r}"
            )
            print("PASS test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line() -> int:
    """Same under-indent shape, but the source excerpt's separator line is genuinely empty -> still detected via the default non-blank-only add variant."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "  alpha\n\n  beta\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "alpha\n"
                "\n"
                "beta\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            assert "after adding 2 leading spaces per line" in check_errors[0]["message"], (
                f"message should state the add direction: {check_errors[0]['message']!r}"
            )
            print("PASS test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line")
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line() -> int:
    """Same under-indent shape, but the source's separator line is whitespace-only with its own indent (not genuinely empty) -> still detected, exercising the include_blank=True add variant."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "  alpha\n  \n  beta\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "```\n"
                "alpha\n"
                "\n"
                "beta\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            assert "after adding 2 leading spaces per line" in check_errors[0]["message"], (
                f"message should state the add direction: {check_errors[0]['message']!r}"
            )
            print(
                "PASS test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line"
            )
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen() -> int:
    """An existing over-indented fence still produces the unchanged 'after stripping N leading spaces per line' message, asserted on the exact message text so a regression in the frozen wording fails the test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "alpha\nbeta\ngamma\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "  ```\n"
                "  alpha\n"
                "  beta\n"
                "  gamma\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 1, (
                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
            )
            expected = (
                "card 1's Requirements: fence 1 matches 'src/target.py' after stripping 2 "
                "leading spaces per line (found N=2)"
            )
            assert check_errors[0]["message"] == expected, (
                f"frozen message wording regressed: {check_errors[0]['message']!r}"
            )
            print("PASS test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact() -> int:
    """Fence content is already a byte-exact substring of the target Edits: file -> no error (regression guard: the byte-exact pre-check must still win before the add pass ever runs)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "  alpha\n  beta\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Quote:\n"
                "  ```\n"
                "  alpha\n"
                "  beta\n"
                "  ```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print("PASS test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match() -> int:
    """Fence shows plausible but different code, not a substring at any N in 1..40 in either direction -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "src").mkdir()
        (project_root / "src" / "target.py").write_text(
            "  alpha\n  beta\n", encoding="utf-8",
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file(
            "alpha",
            edits=["src/target.py"],
            requirements=(
                "  Illustrative:\n"
                "```\n"
                "gamma\n"
                "delta\n"
                "```\n"
            ),
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
        try:
            assert len(check_errors) == 0, (
                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
            )
            print(
                "PASS test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match"
            )
            return 0
        except AssertionError as exc:
            print(
                "FAIL test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match: "
                f"{exc}",
                file=sys.stderr,
            )
            return 1


def test_skip_checks_filters_wiki_config_mutation() -> int:
    """skip_checks={"wiki-config-mutation"} suppresses that check entirely."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "mill-config.yaml").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["mill-config.yaml"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(
            plan_dir, project_root,
            skip_checks=frozenset({"wiki-config-mutation"}),
        )
        try:
            assert result == [], f"expected no errors, got: {result}"
            print("PASS test_skip_checks_filters_wiki_config_mutation")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_skip_checks_filters_wiki_config_mutation: {exc}", file=sys.stderr)
            return 1


def test_skip_checks_does_not_suppress_other_checks() -> int:
    """skip_checks={"wiki-config-mutation"} suppresses that check but not card-missing-field."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "mill-config.yaml").write_text("# placeholder", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["mill-config.yaml"], missing_fields={"Commit"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(
            plan_dir, project_root,
            skip_checks=frozenset({"wiki-config-mutation"}),
        )
        try:
            assert len(result) == 1, f"expected exactly 1 error, got: {result}"
            assert result[0]["check"] == "card-missing-field", (
                f"expected card-missing-field, got: {result[0]['check']!r}"
            )
            print("PASS test_skip_checks_does_not_suppress_other_checks")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_skip_checks_does_not_suppress_other_checks: {exc}", file=sys.stderr)
            return 1


def test_skip_checks_unknown_check_silently_ignored() -> int:
    """Unknown check name in skip_checks raises no exception and returns empty list."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        try:
            result = _plan_validate.run(
                plan_dir, project_root,
                skip_checks=frozenset({"nonexistent-check"}),
            )
            assert result == [], f"expected no errors, got: {result}"
            print("PASS test_skip_checks_unknown_check_silently_ignored")
            return 0
        except Exception as exc:
            print(f"FAIL test_skip_checks_unknown_check_silently_ignored: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_null() -> int:
    """Clean: per-batch frontmatter verify: null -> no verify-not-isolated error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_null")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_null: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_missing_key() -> int:
    """Clean: per-batch frontmatter omits verify: entirely -> no verify-not-isolated error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_missing_key")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_missing_key: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_dirty_no_prefix() -> int:
    """Dirty: Python project + per-batch frontmatter verify: without PYTHONPATH= prefix -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Add Python marker to make this a Python project
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run --project plugins/mill python test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            e = verify_errs[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"wrong card: {e['card']!r}"
            assert e["path"] == "uv run --project plugins/mill python test.py", f"wrong path: {e['path']!r}"
            assert e["message"] == "verify command missing PYTHONPATH= prefix", f"wrong message: {e['message']!r}"
            # Verify 5-key envelope
            assert set(e.keys()) == {"check", "batch", "card", "path", "message"}, (
                f"wrong keys: {set(e.keys())}"
            )
            print("PASS test_check_verify_not_isolated_dirty_no_prefix")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_dirty_no_prefix: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_clean_with_prefix() -> int:
    """Clean: per-batch frontmatter verify: with PYTHONPATH= prefix -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_clean_with_prefix")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_clean_with_prefix: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_two_batches_dirty() -> int:
    """Dirty: Python project + two batch files both unprefixed -> exactly two verify-not-isolated errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Add Python marker to make this a Python project
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md"},
            {"name": "beta", "file": "02-beta.md"},
        ])
        batch_a = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run test-a.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        batch_b = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\nbatch: beta\ncards: 1\nverify: uv run test-b.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_a), ("02-beta.md", batch_b)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 2, f"expected 2 errors, got {len(verify_errs)}: {verify_errs}"
            batches = {e["batch"] for e in verify_errs}
            assert batches == {"01-alpha", "02-beta"}, f"wrong batch names: {batches}"
            print("PASS test_check_verify_not_isolated_two_batches_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_two_batches_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_leading_whitespace() -> int:
    """Clean: extra leading whitespace before PYTHONPATH= -> no error (uses .strip())."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify:   PYTHONPATH= uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_leading_whitespace")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_leading_whitespace: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_non_empty_pythonpath_value() -> int:
    """Clean: verify: PYTHONPATH=/some/path uv run ... -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH=/some/path uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_non_empty_pythonpath_value")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_non_empty_pythonpath_value: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_run_integration() -> int:
    """Integration: Python project + unprefixed batch, verify 5-key envelope."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Add Python marker to make this a Python project
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        try:
            result = _plan_validate.run(plan_dir, project_root)
            verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            e = verify_errs[0]
            # Verify all 5 keys are present
            assert set(e.keys()) == {"check", "batch", "card", "path", "message"}, (
                f"envelope missing keys: {set(e.keys())}"
            )
            assert e["check"] == "verify-not-isolated"
            assert e["batch"] == "01-alpha"
            assert e["card"] is None
            assert e["path"] == "uv run test.py"
            assert e["message"] == "verify command missing PYTHONPATH= prefix"
            print("PASS test_check_verify_not_isolated_run_integration")
            return 0
        except (AssertionError, KeyError) as exc:
            print(f"FAIL test_check_verify_not_isolated_run_integration: {exc}", file=sys.stderr)
            return 1


def test_reads_token_missing_both_unions_dirty() -> int:
    """(g) Reads: token missing on disk + in neither union -> non-existent-path error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["totally/missing.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 1, f"expected 1 error, got {len(check1)}: {check1}"
            assert check1[0]["path"] == "totally/missing.py", (
                f"wrong path: {check1[0]['path']!r}"
            )
            assert not check1[0]["message"].startswith("Deletes: token '"), (
                f"Reads: token should not use Deletes prefix: {check1[0]['message']!r}"
            )
            print("PASS test_reads_token_missing_both_unions_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_reads_token_missing_both_unions_dirty: {exc}", file=sys.stderr)
            return 1


def test_all_files_touched_deletes_not_required() -> int:
    """Deletes: token NOT required in All Files Touched -> no error (per issue #494).

    When a card has a Deletes: path, that path does NOT need to appear in the overview's All Files
    Touched section.
    Deletes: tokens are excluded from the all-files-touched check per issue #494 (validator was
    incorrectly requiring them).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        # foo.md must exist on disk so non-existent-path check doesn't fire.
        (project_root / "foo.md").parent.mkdir(parents=True)
        (project_root / "foo.md").write_text("# foo", encoding="utf-8")

        # Overview does NOT include foo.md (it will be deleted, not touched as Edits/Creates).
        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            all_files_touched=[],
        )
        batch = _make_batch_file("alpha", deletes=["foo.md"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [
            e for e in result
            if e["check"] == "all-files-touched-mismatch" and e["path"] == "foo.md"
        ]
        try:
            assert len(mismatch_errs) == 0, (
                f"Deletes: token should NOT be required in All Files Touched, "
                f"got: {mismatch_errs}"
            )
            print("PASS test_all_files_touched_deletes_not_required")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_all_files_touched_deletes_not_required: {exc}", file=sys.stderr)
            return 1


def test_depends_on_batch_mismatch_no_finding_on_match() -> int:
    """Clean: per-batch file's depends-on matches overview's -> no mismatch error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "number": 2, "depends-on": [1]},
        ])
        # Batch file with depends-on matching overview: [1] -> ["alpha"]
        batch_a = _make_batch_file("alpha")
        batch_b_text = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\n"
            "batch: beta\n"
            "cards: 1\n"
            "verify: null\n"
            "depends-on: [1]\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b_text),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [e for e in result if e["check"] == "depends-on-batch-mismatch"]
        if mismatch_errs:
            print(f"FAIL test_depends_on_batch_mismatch_no_finding_on_match: unexpected errors: {mismatch_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_depends_on_batch_mismatch_no_finding_on_match")
        return 0


def test_depends_on_batch_mismatch_emits_finding() -> int:
    """Dirty: per-batch file's depends-on disagrees with overview's -> one mismatch error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "number": 2, "depends-on": [1]},
        ])
        # Batch file with depends-on NOT matching overview: [] instead of [1]
        batch_a = _make_batch_file("alpha")
        batch_b_text = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\n"
            "batch: beta\n"
            "cards: 1\n"
            "verify: null\n"
            "depends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b_text),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [e for e in result if e["check"] == "depends-on-batch-mismatch"]
        try:
            assert len(mismatch_errs) == 1, f"expected 1 error, got {len(mismatch_errs)}: {mismatch_errs}"
            assert mismatch_errs[0]["batch"] == "beta", f"wrong batch: {mismatch_errs[0]['batch']!r}"
            assert "depends-on" in mismatch_errs[0]["message"], (
                f"message should mention 'depends-on': {mismatch_errs[0]['message']!r}"
            )
            print("PASS test_depends_on_batch_mismatch_emits_finding")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_depends_on_batch_mismatch_emits_finding: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Language-aware verify-not-isolated check (Python markers)
# ---------------------------------------------------------------------------

def test_check_verify_not_isolated_python_marker_pyproject_dirty() -> int:
    """Dirty: Python marker (pyproject.toml) present + no PYTHONPATH= -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create Python marker at project root
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            assert verify_errs[0]["batch"] == "01-alpha", (
                f"wrong batch: {verify_errs[0]['batch']!r}"
            )
            print("PASS test_check_verify_not_isolated_python_marker_pyproject_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_python_marker_pyproject_dirty: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_python_marker_setup_py_dirty() -> int:
    """Dirty: Python marker (setup.py) present + no PYTHONPATH= -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create Python marker at project root
        (project_root / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: pytest test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_python_marker_setup_py_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_python_marker_setup_py_dirty: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_python_marker_plugins_mill_clean() -> int:
    """Clean: Python marker (plugins/mill/pyproject.toml) + PYTHONPATH= present -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create Python marker in plugins/mill subdirectory
        (project_root / "plugins" / "mill").mkdir(parents=True)
        (project_root / "plugins" / "mill" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run test.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_python_marker_plugins_mill_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_python_marker_plugins_mill_clean: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_no_python_marker_native_command_clean() -> int:
    """Clean: no Python marker + native verify command (go test) -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a non-Python marker (go.mod)
        (project_root / "go.mod").write_text("module example.com/test\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: go test ./...\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_no_python_marker_native_command_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_no_python_marker_native_command_clean: {exc}",
                  file=sys.stderr)
            return 1


def test_check_verify_not_isolated_no_python_marker_dotnet_test_clean() -> int:
    """Clean: C# project (no Python marker) + dotnet test -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a C# marker (.csproj)
        (project_root / "Project.csproj").write_text("<Project Sdk=\"Microsoft.NET.Sdk\">\n</Project>\n",
                                                       encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: dotnet test\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 0, f"expected no errors, got {len(verify_errs)}: {verify_errs}"
            print("PASS test_check_verify_not_isolated_no_python_marker_dotnet_test_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_no_python_marker_dotnet_test_clean: {exc}",
                  file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# out-of-worktree-target check
# ---------------------------------------------------------------------------

def test_out_of_worktree_target_home_dir_flags() -> int:
    """Dirty: Edits/Creates with ~/ prefix -> out-of-worktree-target error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["~/.claude/CLAUDE.md"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        try:
            assert len(target_errs) == 1, f"expected 1 error, got {len(target_errs)}: {target_errs}"
            assert target_errs[0]["path"] == "~/.claude/CLAUDE.md", (
                f"wrong path: {target_errs[0]['path']!r}"
            )
            assert "resolves outside the worktree" in target_errs[0]["message"], (
                f"message should mention 'resolves outside': {target_errs[0]['message']!r}"
            )
            print("PASS test_out_of_worktree_target_home_dir_flags")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_out_of_worktree_target_home_dir_flags: {exc}", file=sys.stderr)
            return 1


def test_out_of_worktree_target_absolute_path_flags() -> int:
    """Dirty: Edits/Creates with absolute path outside tree -> out-of-worktree-target error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create an external directory for the absolute path test
        external_dir = tmp / "external"
        external_dir.mkdir()
        external_file = external_dir / "file.txt"
        external_file.write_text("content", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=[str(external_file)])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        try:
            assert len(target_errs) == 1, f"expected 1 error, got {len(target_errs)}: {target_errs}"
            assert "resolves outside the worktree" in target_errs[0]["message"], (
                f"message should mention 'resolves outside': {target_errs[0]['message']!r}"
            )
            print("PASS test_out_of_worktree_target_absolute_path_flags")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_out_of_worktree_target_absolute_path_flags: {exc}", file=sys.stderr)
            return 1


def test_out_of_worktree_target_relative_path_clean() -> int:
    """Clean: Edits/Creates with relative path inside tree -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create file to reference
        (project_root / "src" / "main.py").parent.mkdir(parents=True)
        (project_root / "src" / "main.py").write_text("# code", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", edits=["src/main.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        if target_errs:
            print(f"FAIL test_out_of_worktree_target_relative_path_clean: unexpected errors: {target_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_out_of_worktree_target_relative_path_clean")
        return 0


def test_out_of_worktree_target_creates_nonexistent_clean() -> int:
    """Clean: Creates: target that doesn't yet exist + inside tree -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", creates=["generated/output.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        target_errs = [e for e in result if e["check"] == "out-of-worktree-target"]
        if target_errs:
            print(f"FAIL test_out_of_worktree_target_creates_nonexistent_clean: unexpected errors: {target_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_out_of_worktree_target_creates_nonexistent_clean")
        return 0


# ---------------------------------------------------------------------------
# batch-oversized check
# ---------------------------------------------------------------------------

def test_batch_oversized_card_count_clean() -> int:
    """Clean: batch with 5 cards (under cap of 10) -> no batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", [1, 2, 3, 4, 5])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_cards_per_batch=10)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized"]
        if oversized_errs:
            print(f"FAIL test_batch_oversized_card_count_clean: unexpected errors: {oversized_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_batch_oversized_card_count_clean")
        return 0


def test_batch_oversized_card_count_dirty() -> int:
    """Dirty: batch with 12 cards (over cap of 10) -> one batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", list(range(1, 13)))
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_cards_per_batch=10)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized" and "cards" in e["message"]]
        try:
            assert len(oversized_errs) == 1, f"expected 1 error, got {len(oversized_errs)}: {oversized_errs}"
            assert "12 cards" in oversized_errs[0]["message"], f"message should mention '12 cards': {oversized_errs[0]['message']!r}"
            assert "cap 10" in oversized_errs[0]["message"], f"message should mention 'cap 10': {oversized_errs[0]['message']!r}"
            print("PASS test_batch_oversized_card_count_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_batch_oversized_card_count_dirty: {exc}", file=sys.stderr)
            return 1


def test_batch_oversized_context_tokens_clean() -> int:
    """Clean: batch with small file (under 480k token cap) -> no batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a small 10KB file (2500 token estimate)
        existing_file = project_root / "src" / "small.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("x" * 10000, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["src/small.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_batch_context_tokens=120000)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized" and "tokens" in e["message"]]
        if oversized_errs:
            print(f"FAIL test_batch_oversized_context_tokens_clean: unexpected errors: {oversized_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_batch_oversized_context_tokens_clean")
        return 0


def test_batch_oversized_context_tokens_dirty() -> int:
    """Dirty: batch with large file (over 12k token cap) -> one batch-oversized error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create a file that's 50KB = 12500 tokens (over 12k cap)
        large_file = project_root / "src" / "large.py"
        large_file.parent.mkdir(parents=True)
        large_file.write_text("x" * 50000, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", context=["src/large.py"])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, max_batch_context_tokens=12000)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized" and "tokens" in e["message"]]
        try:
            assert len(oversized_errs) == 1, f"expected 1 error, got {len(oversized_errs)}: {oversized_errs}"
            assert "tokens" in oversized_errs[0]["message"], f"message should mention 'tokens': {oversized_errs[0]['message']!r}"
            assert "cap 12000" in oversized_errs[0]["message"], f"message should mention 'cap 12000': {oversized_errs[0]['message']!r}"
            print("PASS test_batch_oversized_context_tokens_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_batch_oversized_context_tokens_dirty: {exc}", file=sys.stderr)
            return 1


def test_batch_oversized_defaults_applied() -> int:
    """Clean: run() called without max_*_per_batch kwargs applies 10 and 120000 defaults."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file_cards("alpha", list(range(1, 11)))
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        # Call without max_cards_per_batch/max_batch_context_tokens to test defaults
        result = _plan_validate.run(plan_dir, project_root)
        oversized_errs = [e for e in result if e["check"] == "batch-oversized"]
        try:
            assert len(oversized_errs) == 0, (
                f"batch with exactly 10 cards and small files should pass defaults, "
                f"got: {oversized_errs}"
            )
            print("PASS test_batch_oversized_defaults_applied")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_batch_oversized_defaults_applied: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# verify-full-suite check
# ---------------------------------------------------------------------------

def test_check_verify_full_suite_run_all_py_without_filter_is_error() -> int:
    """Dirty: verify invokes run-all.py without -k or --only filter -> one verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            assert check_full_suite[0]["batch"] == "01-alpha", f"wrong batch: {check_full_suite[0]['batch']!r}"
            assert "run-all.py" in check_full_suite[0]["message"], (
                f"message should mention run-all.py: {check_full_suite[0]['message']!r}"
            )
            print("PASS test_check_verify_full_suite_run_all_py_without_filter_is_error")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_run_all_py_without_filter_is_error: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_run_all_py_with_k_filter_is_ok() -> int:
    """Clean: verify invokes run-all.py with -k filter -> no verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py -k test_foo\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_run_all_py_with_k_filter_is_ok: unexpected error: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_run_all_py_with_k_filter_is_ok")
        return 0


def test_check_verify_full_suite_run_all_py_with_only_is_ok() -> int:
    """Clean: verify invokes run-all.py with --only flag -> no verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-foo.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_run_all_py_with_only_is_ok: unexpected error: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_run_all_py_with_only_is_ok")
        return 0


def test_check_verify_full_suite_go_test_dotdotdot_without_run_is_error() -> int:
    """Dirty: verify invokes 'go test ./...' without a -run filter -> one verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: go test ./...\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            assert "go test ./..." in check_full_suite[0]["message"], (
                f"message should mention go test ./...: {check_full_suite[0]['message']!r}"
            )
            print("PASS test_check_verify_full_suite_go_test_dotdotdot_without_run_is_error")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_go_test_dotdotdot_without_run_is_error: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_go_test_dotdotdot_with_run_is_ok() -> int:
    """Clean: verify invokes 'go test ./...' with a -run filter -> no verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: go test ./... -run TestFoo\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_go_test_dotdotdot_with_run_is_ok: unexpected: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_go_test_dotdotdot_with_run_is_ok")
        return 0


def test_check_verify_full_suite_go_test_compound_command_scoped_dotdotdot_is_ok() -> int:
    """Clean: compound command where ./... belongs to a later go vet invocation, not the earlier go test -> no verify-full-suite error (#961)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "go test ./internal/quarryengine/lsp/ && go vet -tags lsp ./...",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(
                f"FAIL test_check_verify_full_suite_go_test_compound_command_scoped_dotdotdot_is_ok: "
                f"unexpected: {check_full_suite}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_verify_full_suite_go_test_compound_command_scoped_dotdotdot_is_ok")
        return 0


def test_check_verify_full_suite_go_dash_c_test_dotdotdot_without_run_is_error() -> int:
    """Dirty: 'go -C <dir> test ./...' (Go 1.20+ nested-module form) without a -run filter -> one verify-full-suite error (#933)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text("alpha", "go -C plugins/prowler test ./...")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            assert "go test ./..." in check_full_suite[0]["message"], (
                f"message should mention go test ./...: {check_full_suite[0]['message']!r}"
            )
            print("PASS test_check_verify_full_suite_go_dash_c_test_dotdotdot_without_run_is_error")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_go_dash_c_test_dotdotdot_without_run_is_error: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_go_dash_c_test_dotdotdot_with_run_is_ok() -> int:
    """Clean: 'go -C <dir> test ./...' with a -run filter -> no verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text("alpha", "go -C plugins/prowler test ./... -run TestFoo")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(
                f"FAIL test_check_verify_full_suite_go_dash_c_test_dotdotdot_with_run_is_ok: unexpected: {check_full_suite}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_verify_full_suite_go_dash_c_test_dotdotdot_with_run_is_ok")
        return 0


def test_check_verify_full_suite_done_gate_exact_match_is_ok() -> int:
    """Clean: verify command exactly equals the configured done_gate -> no verify-full-suite error even though it would otherwise match the go-test branch (#950)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        done_gate = "go test ./... && go test -tags integration ./..."
        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text("alpha", done_gate)
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root, done_gate=done_gate)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(
                f"FAIL test_check_verify_full_suite_done_gate_exact_match_is_ok: unexpected: {check_full_suite}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_verify_full_suite_done_gate_exact_match_is_ok")
        return 0


def test_check_verify_full_suite_done_gate_subset_still_flagged() -> int:
    """Dirty: verify command is a scoped SUBSET of done_gate, not an exact match -> still flagged (exact-match only, not prefix/subset)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text("alpha", "go test ./...")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(
            plan_dir, project_root, done_gate="go test ./... && golangci-lint run",
        )
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            print("PASS test_check_verify_full_suite_done_gate_subset_still_flagged")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_done_gate_subset_still_flagged: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_done_gate_exact_match_overview_level_is_ok() -> int:
    """Clean: overview's own module-wide verify: exactly equals done_gate -> no verify-full-suite error with batch: None (the exemption applies to the overview-level call path too, not just the per-batch loop)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        done_gate = "go test ./... && go test -tags integration ./..."
        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            overview_verify=done_gate,
        )
        batch = _make_batch_file("alpha")  # per-batch verify: null, clean
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root, done_gate=done_gate)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(
                f"FAIL test_check_verify_full_suite_done_gate_exact_match_overview_level_is_ok: "
                f"unexpected: {check_full_suite}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_check_verify_full_suite_done_gate_exact_match_overview_level_is_ok")
        return 0


def test_check_verify_full_suite_dotnet_test_without_filter_is_error() -> int:
    """Dirty: verify invokes 'dotnet test' without --filter -> one verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: dotnet test MyProject.csproj\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            assert "dotnet test" in check_full_suite[0]["message"], (
                f"message should mention dotnet test: {check_full_suite[0]['message']!r}"
            )
            print("PASS test_check_verify_full_suite_dotnet_test_without_filter_is_error")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_dotnet_test_without_filter_is_error: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_dotnet_test_with_filter_is_ok() -> int:
    """Clean: verify invokes 'dotnet test' with --filter -> no verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: dotnet test MyProject.csproj --filter Category=Unit\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_dotnet_test_with_filter_is_ok: unexpected: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_dotnet_test_with_filter_is_ok")
        return 0


def test_check_verify_full_suite_bare_pytest_without_filter_is_error() -> int:
    """Dirty: Python project + bare 'pytest' with no path/-k filter -> one verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        # Marker file required so _is_python_project returns True for this fixture's project_root.
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: pytest\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            assert "pytest" in check_full_suite[0]["message"], (
                f"message should mention pytest: {check_full_suite[0]['message']!r}"
            )
            print("PASS test_check_verify_full_suite_bare_pytest_without_filter_is_error")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_bare_pytest_without_filter_is_error: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_bare_python_m_pytest_without_filter_is_error() -> int:
    """Dirty: Python project + bare 'python -m pytest' with no path/-k filter -> one verify-full-suite error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        # Marker file required so _is_python_project returns True for this fixture's project_root.
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: python -m pytest\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            print("PASS test_check_verify_full_suite_bare_python_m_pytest_without_filter_is_error")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_check_verify_full_suite_bare_python_m_pytest_without_filter_is_error: {exc}",
                file=sys.stderr,
            )
            return 1


def test_check_verify_full_suite_pytest_with_k_filter_is_ok() -> int:
    """Clean: Python project + 'pytest -k foo' -> no verify-full-suite error (scoped)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: pytest -k foo\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_pytest_with_k_filter_is_ok: unexpected: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_pytest_with_k_filter_is_ok")
        return 0


def test_check_verify_full_suite_pytest_with_path_is_ok() -> int:
    """Clean: Python project + 'pytest tests/test_foo.py' -> no verify-full-suite error (scoped)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: pytest tests/test_foo.py\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_pytest_with_path_is_ok: unexpected: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_pytest_with_path_is_ok")
        return 0


def test_check_verify_full_suite_bare_pytest_no_python_marker_clean() -> int:
    """Clean: no Python marker present + bare 'pytest' -> no verify-full-suite error (check 4 gated on _is_python_project)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: pytest\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        if check_full_suite:
            print(f"FAIL test_check_verify_full_suite_bare_pytest_no_python_marker_clean: unexpected: {check_full_suite}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_full_suite_bare_pytest_no_python_marker_clean")
        return 0


# ---------------------------------------------------------------------------
# verify cwd mapping form (Cards 23-25 / #604)
# ---------------------------------------------------------------------------

def test_check_verify_not_isolated_mapping_form_dirty() -> int:
    """Dirty: verify authored as a {cwd, command} mapping, command missing PYTHONPATH= -> one verify-not-isolated error naming the extracted command (not the mapping)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: hub\n  command: uv run test.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            e = verify_errs[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["path"] == "uv run test.py", (
                f"expected the extracted command string, got: {e['path']!r}"
            )
            print("PASS test_check_verify_not_isolated_mapping_form_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_mapping_form_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_mapping_form_clean() -> int:
    """Clean: verify authored as a {cwd, command} mapping, command has PYTHONPATH= prefix -> no verify-not-isolated error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: git_root\n  command: PYTHONPATH= uv run test.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        if verify_errs:
            print(f"FAIL test_check_verify_not_isolated_mapping_form_clean: unexpected: {verify_errs}",
                  file=sys.stderr)
            return 1
        print("PASS test_check_verify_not_isolated_mapping_form_clean")
        return 0


def test_check_verify_full_suite_mapping_form_dirty() -> int:
    """Dirty: verify authored as a {cwd, command} mapping, command invokes run-all.py without a filter -> one verify-full-suite error naming the extracted command."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: git_root\n"
            "  command: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            e = check_full_suite[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["path"] == (
                "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py"
            ), f"expected the extracted command string, got: {e['path']!r}"
            print("PASS test_check_verify_full_suite_mapping_form_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_mapping_form_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_not_isolated_overview_level_dirty() -> int:
    """Dirty: overview's own module-wide verify: is missing PYTHONPATH= -> one verify-not-isolated error with batch=None (previously silently ignored)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")

        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            overview_verify="uv run --project plugins/mill python overview_test.py",
        )
        batch = _make_batch_file("alpha")  # per-batch verify: null, clean
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        verify_errs = [e for e in result if e["check"] == "verify-not-isolated"]
        try:
            assert len(verify_errs) == 1, f"expected 1 error, got {len(verify_errs)}: {verify_errs}"
            e = verify_errs[0]
            assert e["batch"] is None, f"overview-level finding should have batch=None, got: {e['batch']!r}"
            assert e["path"] == "uv run --project plugins/mill python overview_test.py", (
                f"wrong path: {e['path']!r}"
            )
            print("PASS test_check_verify_not_isolated_overview_level_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_not_isolated_overview_level_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_full_suite_overview_level_dirty() -> int:
    """Dirty: overview's own module-wide verify: invokes run-all.py without a filter -> one verify-full-suite error with batch=None (previously silently ignored)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            overview_verify=(
                "PYTHONPATH= uv run --project plugins/mill python "
                "plugins/mill/unit_tests/run-all.py"
            ),
        )
        batch = _make_batch_file("alpha")  # per-batch verify: null, clean
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        check_full_suite = [e for e in result if e["check"] == "verify-full-suite"]
        try:
            assert len(check_full_suite) == 1, f"expected 1 error, got {len(check_full_suite)}: {check_full_suite}"
            assert check_full_suite[0]["batch"] is None, (
                f"overview-level finding should have batch=None, got: {check_full_suite[0]['batch']!r}"
            )
            print("PASS test_check_verify_full_suite_overview_level_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_full_suite_overview_level_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_malformed_cwd_missing_command_dirty() -> int:
    """Dirty: verify mapping missing `command:` -> one verify-malformed-cwd finding, no uncaught exception, and no duplicate verify-not-isolated/verify-full-suite finding for the same batch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: hub\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        # run() must not raise -- the ValueError parse_verify_field raises for a malformed mapping is caught and surfaced as a finding.
        result = _plan_validate.run(plan_dir, project_root)
        malformed = [e for e in result if e["check"] == "verify-malformed-cwd"]
        duplicate = [e for e in result if e["check"] in ("verify-not-isolated", "verify-full-suite")]
        try:
            assert len(malformed) == 1, f"expected 1 verify-malformed-cwd finding, got {len(malformed)}: {malformed}"
            e = malformed[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert "command" in e["message"], f"message should quote the ValueError text: {e['message']!r}"
            assert len(duplicate) == 0, (
                f"expected no duplicate verify-not-isolated/verify-full-suite finding, got: {duplicate}"
            )
            print("PASS test_check_verify_malformed_cwd_missing_command_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_malformed_cwd_missing_command_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_malformed_cwd_bad_cwd_value_dirty() -> int:
    """Dirty: verify mapping has an unrecognized cwd value -> one verify-malformed-cwd finding quoting the bad value."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: nowhere\n  command: uv run test.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        malformed = [e for e in result if e["check"] == "verify-malformed-cwd"]
        try:
            assert len(malformed) == 1, f"expected 1 verify-malformed-cwd finding, got {len(malformed)}: {malformed}"
            e = malformed[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert "nowhere" in e["message"], f"message should quote the bad cwd value: {e['message']!r}"
            print("PASS test_check_verify_malformed_cwd_bad_cwd_value_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_malformed_cwd_bad_cwd_value_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_mixed_cwd_dirty() -> int:
    """Dirty: two batches resolve verify cwd to different roots (hub vs git_root) -> a verify-mixed-cwd finding naming both conflicting batches."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        project_root = git_root / "hub"
        plan_dir = tmp / "plan"
        project_root.mkdir(parents=True)

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: hub\n  command: uv run test-a.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        batch_b = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\nbatch: beta\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: git_root\n  command: uv run test-b.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_a), ("02-beta.md", batch_b)])

        result = _plan_validate.run(plan_dir, project_root, git_root=git_root)
        mixed = [e for e in result if e["check"] == "verify-mixed-cwd"]
        try:
            assert len(mixed) == 2, f"expected 2 verify-mixed-cwd findings, got {len(mixed)}: {mixed}"
            batches = {e["batch"] for e in mixed}
            assert batches == {"alpha", "beta"}, f"wrong batch names: {batches}"
            for e in mixed:
                assert "alpha" in e["message"] and "beta" in e["message"], (
                    f"message should name both conflicting batches: {e['message']!r}"
                )
            print("PASS test_check_verify_mixed_cwd_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_mixed_cwd_dirty: {exc}", file=sys.stderr)
            return 1


def test_check_verify_mixed_cwd_single_cwd_clean() -> int:
    """Clean: two batches both resolve verify cwd to the same root -> no verify-mixed-cwd finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        project_root = git_root / "hub"
        plan_dir = tmp / "plan"
        project_root.mkdir(parents=True)

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: hub\n  command: uv run test-a.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        batch_b = (
            "# Batch: beta\n\n"
            "```yaml\n"
            "task: test\nbatch: beta\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: hub\n  command: uv run test-b.py\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(beta): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_a), ("02-beta.md", batch_b)])

        result = _plan_validate.run(plan_dir, project_root, git_root=git_root)
        mixed = [e for e in result if e["check"] == "verify-mixed-cwd"]
        if mixed:
            print(f"FAIL test_check_verify_mixed_cwd_single_cwd_clean: unexpected: {mixed}", file=sys.stderr)
            return 1
        print("PASS test_check_verify_mixed_cwd_single_cwd_clean")
        return 0


# ---------------------------------------------------------------------------
# verify-batch-mismatch check (Card 6)
# ---------------------------------------------------------------------------

def test_verify_batch_mismatch_clean_identical_string() -> int:
    """Clean: identical plain-string verify: on both the overview entry and the batch file -> no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
        ])
        batch = _make_batch_verify_only_text("alpha", "some cmd")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        if mismatch:
            print(f"FAIL test_verify_batch_mismatch_clean_identical_string: unexpected: {mismatch}",
                  file=sys.stderr)
            return 1
        print("PASS test_verify_batch_mismatch_clean_identical_string")
        return 0


def test_verify_batch_mismatch_dirty_null_vs_command() -> int:
    """Dirty: overview names a real command, batch file's own verify: is null -> exactly one finding naming that batch."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
        ])
        batch = _make_batch_verify_only_text("alpha", "null")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        try:
            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
            print("PASS test_verify_batch_mismatch_dirty_null_vs_command")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_batch_mismatch_dirty_null_vs_command: {exc}", file=sys.stderr)
            return 1


def test_verify_batch_mismatch_dirty_trailing_clause() -> int:
    """Dirty: overview and batch commands differ only by a trailing clause -> exactly one finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": "pytest test_foo.py"},
        ])
        batch = _make_batch_verify_only_text("alpha", "pytest test_foo.py -k mytest")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        try:
            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
            print("PASS test_verify_batch_mismatch_dirty_trailing_clause")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_batch_mismatch_dirty_trailing_clause: {exc}", file=sys.stderr)
            return 1


def test_verify_batch_mismatch_clean_absent_vs_null() -> int:
    """Clean: verify: absent from the overview entry, explicitly null on the batch file -> no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": _OMIT_VERIFY},
        ])
        batch = _make_batch_verify_only_text("alpha", "null")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        if mismatch:
            print(f"FAIL test_verify_batch_mismatch_clean_absent_vs_null: unexpected: {mismatch}",
                  file=sys.stderr)
            return 1
        print("PASS test_verify_batch_mismatch_clean_absent_vs_null")
        return 0


def test_verify_batch_mismatch_clean_both_absent() -> int:
    """Clean: verify: key absent from both the overview entry and the batch file's own frontmatter -> no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": _OMIT_VERIFY},
        ])
        batch = _make_batch_verify_only_text("alpha", None)
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        if mismatch:
            print(f"FAIL test_verify_batch_mismatch_clean_both_absent: unexpected: {mismatch}",
                  file=sys.stderr)
            return 1
        print("PASS test_verify_batch_mismatch_clean_both_absent")
        return 0


def test_verify_batch_mismatch_clean_both_null() -> int:
    """Clean: verify: explicitly null on both the overview entry and the batch file -> no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": None},
        ])
        batch = _make_batch_verify_only_text("alpha", "null")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        if mismatch:
            print(f"FAIL test_verify_batch_mismatch_clean_both_null: unexpected: {mismatch}",
                  file=sys.stderr)
            return 1
        print("PASS test_verify_batch_mismatch_clean_both_null")
        return 0


def test_verify_batch_mismatch_dirty_string_vs_mapping_cwd() -> int:
    """Dirty: overview has a plain-string verify:, batch file has the same command as a {cwd: git_root, ...} mapping -> one finding, because the raw cwd keys differ (None vs 'git_root')."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
        ])
        batch = _make_batch_verify_only_text("alpha", "\n  cwd: git_root\n  command: some cmd")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        try:
            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
            print("PASS test_verify_batch_mismatch_dirty_string_vs_mapping_cwd")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_batch_mismatch_dirty_string_vs_mapping_cwd: {exc}", file=sys.stderr)
            return 1


def test_verify_batch_mismatch_clean_matching_mapping() -> int:
    """Clean: identical {cwd, command} mapping form on both sides -> no finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": {"cwd": "hub", "command": "some cmd"}},
        ])
        batch = _make_batch_verify_only_text("alpha", "\n  cwd: hub\n  command: some cmd")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        if mismatch:
            print(f"FAIL test_verify_batch_mismatch_clean_matching_mapping: unexpected: {mismatch}",
                  file=sys.stderr)
            return 1
        print("PASS test_verify_batch_mismatch_clean_matching_mapping")
        return 0


def test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root() -> int:
    """Dirty: identical command, but cwd: hub on the overview side vs cwd: git_root on the batch side -> one finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": {"cwd": "hub", "command": "some cmd"}},
        ])
        batch = _make_batch_verify_only_text("alpha", "\n  cwd: git_root\n  command: some cmd")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        try:
            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
            print("PASS test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root: {exc}", file=sys.stderr)
            return 1


def test_verify_batch_mismatch_dirty_overview_malformed_mapping() -> int:
    """Dirty: the overview entry's verify: mapping has no command: -> exactly one verify-batch-mismatch finding whose message contains the normalizer's error text, and no verify-malformed-cwd finding for that entry (the overview side is check-verify-batch-mismatch's sole reporter)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": {"cwd": "hub"}},
        ])
        batch = _make_batch_verify_only_text("alpha", "null")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        malformed = [e for e in result if e["check"] == "verify-malformed-cwd"]
        try:
            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
            assert "command" in mismatch[0]["message"], (
                f"message should quote the normalizer's error text: {mismatch[0]['message']!r}"
            )
            assert len(malformed) == 0, f"expected no verify-malformed-cwd finding, got: {malformed}"
            print("PASS test_verify_batch_mismatch_dirty_overview_malformed_mapping")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_batch_mismatch_dirty_overview_malformed_mapping: {exc}", file=sys.stderr)
            return 1


def test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report() -> int:
    """Clean (for this check): the batch file's own verify: mapping has no command: -> zero verify-batch-mismatch findings, exactly one verify-malformed-cwd finding (that check is the sole reporter for the batch-file side)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": "null"},
        ])
        batch = _make_batch_verify_only_text("alpha", "\n  cwd: hub")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        malformed = [e for e in result if e["check"] == "verify-malformed-cwd"]
        try:
            assert len(mismatch) == 0, f"expected 0 verify-batch-mismatch findings, got: {mismatch}"
            assert len(malformed) == 1, f"expected 1 verify-malformed-cwd finding, got {len(malformed)}: {malformed}"
            print("PASS test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report")
            return 0
        except AssertionError as exc:
            print(
                f"FAIL test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report: {exc}",
                file=sys.stderr,
            )
            return 1


def test_verify_batch_mismatch_clean_overview_batches_unparseable() -> int:
    """Clean (for this check): the overview's Batch Index fenced yaml is unparseable -> zero verify-batch-mismatch findings (check 4 already records the parse error; this check silently defers)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview_text = (
            "# Overview\n\n"
            "```yaml\n"
            'task: test\nslug: test-slug\nroot: ""\n'
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches: [this is not: valid: yaml: at all\n"
            "```\n"
        )
        batch = _make_batch_verify_only_text("alpha", "some cmd")
        _write_plan(plan_dir, overview_text, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        if mismatch:
            print(
                f"FAIL test_verify_batch_mismatch_clean_overview_batches_unparseable: unexpected: {mismatch}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_verify_batch_mismatch_clean_overview_batches_unparseable")
        return 0


def test_verify_batch_mismatch_clean_missing_batch_file() -> int:
    """Clean: the overview entry's file: names a batch file that does not exist on disk -> zero verify-batch-mismatch findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
        ])
        # Deliberately do not write 01-alpha.md -- _write_plan([]) writes only the overview.
        _write_plan(plan_dir, overview, [])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
        if mismatch:
            print(
                f"FAIL test_verify_batch_mismatch_clean_missing_batch_file: unexpected: {mismatch}",
                file=sys.stderr,
            )
            return 1
        print("PASS test_verify_batch_mismatch_clean_missing_batch_file")
        return 0


# ---------------------------------------------------------------------------
# git_root threading tests (Card 5)
# ---------------------------------------------------------------------------

def test_git_root_threading_with_subfolder_cwd_clean() -> int:
    """Clean: project_root is git_root/root subfolder, files at git_root/root/<path>, git_root
    threaded.

    This test verifies the fix for #471 layout: when project_root is a subfolder (root:) of the git
    repo,
    and git_root is threaded through the validator, resolve_existing_paths should find files at
    git_root/root/raw correctly instead of mis-resolving under a doubled path.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"                    # repo top
        project_root = git_root / "subproject"     # project_root is a subfolder
        plan_dir = git_root / "plan"               # plan dir at repo top

        # Create the project root
        project_root.mkdir(parents=True)

        # Create a source file at git_root/subproject/src/code.py
        source_file = project_root / "src" / "code.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# source code", encoding="utf-8")

        # Create the plan at git_root/plan/ with root: "subproject"
        overview = (
            "# Overview\n\n"
            "```yaml\n"
            'task: test\nslug: test-slug\nroot: "subproject"\n'
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: alpha\n"
            "    file: 01-alpha.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        batch = _make_batch_file("alpha", context=["src/code.py"])
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(overview, encoding="utf-8")
        (plan_dir / "01-alpha.md").write_text(batch, encoding="utf-8")

        # When git_root is provided, the validator should resolve src/code.py against git_root/subproject/src/code.py (primary) before trying project_root/subproject/src/code.py (fallback).
        result = _plan_validate.run(plan_dir, project_root, root="subproject", git_root=git_root)

        # Should have no non-existent-path errors
        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 0, (
                f"expected no non-existent-path errors with git_root threading, "
                f"got: {check1}"
            )
            print("PASS test_git_root_threading_with_subfolder_cwd_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_git_root_threading_with_subfolder_cwd_clean: {exc}", file=sys.stderr)
            return 1


def test_git_root_threading_without_git_root_default_none_documents_required() -> int:
    """Comment: demonstrates why git_root threading is necessary.

    This test documents the potential issue: when project_root is the root subfolder itself
    (git_root/subproject) and root="subproject" is set, resolve_existing_paths without git_root will
    try: 1. project_root / "subproject" / raw -> DOUBLED, wrong path 2. project_root / raw ->
    correct, file is here

    So the file IS found,
    but only by luck (via the fallback).
    Threading git_root makes git_root/root/raw PRIMARY, which is safer and doesn't depend on correct
    project_root positioning in the worktree.

    This test skips root param to avoid the doubling issue and focus on the threading mechanism: it
    shows that when root="" (default empty), files resolve correctly either way.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        project_root = git_root / "subproject"
        plan_dir = git_root / "plan"

        project_root.mkdir(parents=True)
        source_file = project_root / "src" / "code.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text("# source code", encoding="utf-8")

        # Use empty root (the default) to test that the mechanism works
        overview = (
            "# Overview\n\n"
            "```yaml\n"
            'task: test\nslug: test-slug\nroot: ""\n'
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: alpha\n"
            "    file: 01-alpha.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        batch = _make_batch_file("alpha", context=["src/code.py"])
        plan_dir.mkdir(parents=True)
        (plan_dir / "00-overview.md").write_text(overview, encoding="utf-8")
        (plan_dir / "01-alpha.md").write_text(batch, encoding="utf-8")

        # Without git_root and without root param, the validator finds the file at project_root/src/code.py.
        # This test confirms the basic resolution works and documents why git_root threading is still necessary for the subfolder layout case (root="subproject").
        result = _plan_validate.run(plan_dir, project_root)

        check1 = [e for e in result if e["check"] == "non-existent-path"]
        try:
            assert len(check1) == 0, (
                f"expected no non-existent-path errors when root='', "
                f"got: {check1}"
            )
            print("PASS test_git_root_threading_without_git_root_default_none_documents_required")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_git_root_threading_without_git_root_default_none_documents_required: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Move-specific checks (batch validator-move-checks)
# ---------------------------------------------------------------------------

def test_moves_field_required_dirty() -> int:
    """Dirty: card without Moves: field -> card-missing-field error mentioning 'Moves:'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch = _make_batch_file("alpha", missing_fields={"Moves"})
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        moves_errs = [
            e for e in result
            if e["check"] == "card-missing-field" and "Moves:" in e["message"]
        ]
        try:
            assert len(moves_errs) == 1, f"expected 1 error, got: {moves_errs}"
            assert moves_errs[0]["card"] == 1, f"wrong card: {moves_errs[0]['card']}"
            assert "missing required field: Moves:" in moves_errs[0]["message"], (
                f"message should contain 'missing required field: Moves:': "
                f"{moves_errs[0]['message']!r}"
            )
            print("PASS test_moves_field_required_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_moves_field_required_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_format_well_formed_passes() -> int:
    """Clean: well-formed `src` -> `dst` move bullet -> no move-format error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create the Move source so move-source-missing does not fire.
        (project_root / "old").mkdir(parents=True)
        (project_root / "old" / "path.py").write_text("# code", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_raw = _make_batch_file("alpha", moves=[("old/path.py", "new/path.py")])
        # Insert ## Rename mechanic before ## Cards so move-mechanic-missing does not fire.
        batch = batch_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        fmt_errs = [e for e in result if e["check"] == "move-format"]
        try:
            assert len(fmt_errs) == 0, f"expected no move-format errors, got: {fmt_errs}"
            print("PASS test_move_format_well_formed_passes")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_format_well_formed_passes: {exc}", file=sys.stderr)
            return 1


def test_move_format_malformed_missing_arrow_dirty() -> int:
    """Dirty: Moves: sub-bullet missing the -> arrow -> one move-format error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:**\n"
            "  - `old/path.py` `new/path.py`\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        fmt_errs = [e for e in result if e["check"] == "move-format"]
        try:
            assert len(fmt_errs) == 1, f"expected 1 move-format error, got: {fmt_errs}"
            assert fmt_errs[0]["batch"] == "01-alpha", f"wrong batch: {fmt_errs[0]['batch']!r}"
            assert fmt_errs[0]["card"] == 1, f"wrong card: {fmt_errs[0]['card']}"
            assert "`src` -> `dst`" in fmt_errs[0]["message"], (
                f"message should mention grammar: {fmt_errs[0]['message']!r}"
            )
            print("PASS test_move_format_malformed_missing_arrow_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_format_malformed_missing_arrow_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_redundant_same_path_in_creates_dirty() -> int:
    """Dirty: Move target also in Creates: of the same batch -> move-redundant error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # new/path.py is both the Moves: target AND in Creates: of the same batch.
        batch = _make_batch_file(
            "alpha",
            creates=["new/path.py"],
            moves=[("old/path.py", "new/path.py")],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        redundant_errs = [e for e in result if e["check"] == "move-redundant"]
        try:
            assert len(redundant_errs) == 1, (
                f"expected 1 move-redundant error, got: {redundant_errs}"
            )
            assert redundant_errs[0]["path"] == "new/path.py", (
                f"wrong path: {redundant_errs[0]['path']!r}"
            )
            assert "Moves: endpoint" in redundant_errs[0]["message"], (
                f"message should mention 'Moves: endpoint': {redundant_errs[0]['message']!r}"
            )
            print("PASS test_move_redundant_same_path_in_creates_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_redundant_same_path_in_creates_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_redundant_different_creates_path_passes() -> int:
    """Clean: Move target + DIFFERENT Creates: path (extraction pattern) -> no move-redundant error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # Creates other/file.py (different from Moves target new/path.py) -- the canonical rename-plus-extraction pattern;
        # must NOT trigger move-redundant.
        batch = _make_batch_file(
            "alpha",
            creates=["other/file.py"],
            moves=[("old/path.py", "new/path.py")],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        redundant_errs = [e for e in result if e["check"] == "move-redundant"]
        try:
            assert len(redundant_errs) == 0, (
                f"different Creates: path should NOT trigger move-redundant, got: {redundant_errs}"
            )
            print("PASS test_move_redundant_different_creates_path_passes")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_redundant_different_creates_path_passes: {exc}", file=sys.stderr)
            return 1


def test_move_source_missing_dirty() -> int:
    """Dirty: Move source not on disk and not in creates/moves union -> move-source-missing error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # missing/source.py does not exist on disk and is not in any creates/moves union.
        batch = _make_batch_file("alpha", moves=[("missing/source.py", "new/dest.py")])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        source_errs = [e for e in result if e["check"] == "move-source-missing"]
        try:
            assert len(source_errs) == 1, f"expected 1 move-source-missing error, got: {source_errs}"
            assert source_errs[0]["path"] == "missing/source.py", (
                f"wrong path: {source_errs[0]['path']!r}"
            )
            assert "does not exist on disk" in source_errs[0]["message"], (
                f"message should mention 'does not exist on disk': {source_errs[0]['message']!r}"
            )
            print("PASS test_move_source_missing_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_source_missing_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_source_missing_suppressed_by_creates_union() -> int:
    """Clean: Move source not on disk but in creates_union (earlier batch creates it) -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "number": 2, "depends-on": [1]},
        ])
        # Batch A creates generated/file.py (not on disk; will be created at runtime).
        batch_a = _make_batch_file("alpha", card_num=1, creates=["generated/file.py"])
        # Batch B moves generated/file.py -> final/file.py.
        # generated/file.py is in creates_union from Batch A -> move-source-missing is suppressed.
        batch_b_raw = _make_batch_file("beta", card_num=2, moves=[("generated/file.py", "final/file.py")])
        batch_b = batch_b_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md", batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        source_errs = [
            e for e in result
            if e["check"] == "move-source-missing" and e["path"] == "generated/file.py"
        ]
        try:
            assert len(source_errs) == 0, (
                f"Move source in creates_union should be suppressed, got: {source_errs}"
            )
            print("PASS test_move_source_missing_suppressed_by_creates_union")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_source_missing_suppressed_by_creates_union: {exc}", file=sys.stderr)
            return 1


def test_move_target_collision_pre_existing_dirty() -> int:
    """Dirty: Move target already exists on disk -> move-target-collision error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create BOTH the source and the target; the target pre-existing triggers collision.
        (project_root / "old.py").write_text("# old", encoding="utf-8")
        (project_root / "new.py").write_text("# new", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_raw = _make_batch_file("alpha", moves=[("old.py", "new.py")])
        batch = batch_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        collision_errs = [e for e in result if e["check"] == "move-target-collision"]
        try:
            assert len(collision_errs) == 1, (
                f"expected 1 move-target-collision error, got: {collision_errs}"
            )
            assert collision_errs[0]["path"] == "new.py", (
                f"wrong path: {collision_errs[0]['path']!r}"
            )
            assert "already exists on disk" in collision_errs[0]["message"], (
                f"message should mention 'already exists on disk': {collision_errs[0]['message']!r}"
            )
            print("PASS test_move_target_collision_pre_existing_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_target_collision_pre_existing_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_target_collision_duplicate_target_dirty() -> int:
    """Dirty: two parallel batches target the same destination -> move-target-collision on each."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create source files; dest.py does NOT exist so condition 1 does not fire.
        (project_root / "a.py").write_text("# a", encoding="utf-8")
        (project_root / "b.py").write_text("# b", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        batch_a_raw = _make_batch_file("alpha", card_num=1, moves=[("a.py", "dest.py")])
        batch_a = batch_a_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        batch_b_raw = _make_batch_file("beta", card_num=2, moves=[("b.py", "dest.py")])
        batch_b = batch_b_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        collision_errs = [
            e for e in result
            if e["check"] == "move-target-collision" and e["path"] == "dest.py"
        ]
        try:
            assert len(collision_errs) == 2, (
                f"expected 2 move-target-collision errors (one per batch), got: {collision_errs}"
            )
            batches = {e["batch"] for e in collision_errs}
            assert "01-alpha" in batches, f"expected 01-alpha in {batches}"
            assert "02-beta" in batches, f"expected 02-beta in {batches}"
            print("PASS test_move_target_collision_duplicate_target_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_target_collision_duplicate_target_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_target_collision_cross_batch_creates_dirty() -> int:
    """Dirty: Move target in Batch A collides with Creates: new.py in Batch B -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create the Move source so move-source-missing does not fire.
        (project_root / "old.py").write_text("# source", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "number": 2, "depends-on": []},
        ])
        # Batch A moves old.py -> new.py; new.py does not exist on disk.
        batch_a_raw = _make_batch_file("alpha", card_num=1, moves=[("old.py", "new.py")])
        batch_a = batch_a_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        # Batch B creates new.py -- cross-batch Creates: collision with Batch A's Move target.
        batch_b = _make_batch_file("beta", card_num=2, creates=["new.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        collision_errs = [
            e for e in result
            if e["check"] == "move-target-collision" and e["path"] == "new.py"
        ]
        try:
            assert len(collision_errs) == 1, (
                f"expected 1 move-target-collision error, got: {collision_errs}"
            )
            assert collision_errs[0]["batch"] == "01-alpha", (
                f"expected error on 01-alpha, got: {collision_errs[0]['batch']!r}"
            )
            assert "02-beta" in collision_errs[0]["message"] or "beta" in collision_errs[0]["message"], (
                f"message should mention the conflicting batch: {collision_errs[0]['message']!r}"
            )
            print("PASS test_move_target_collision_cross_batch_creates_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_target_collision_cross_batch_creates_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_mechanic_missing_dirty() -> int:
    """Dirty: batch with non-empty Moves: and no ## Rename mechanic section -> one error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # Batch has Moves: non-empty but NO ## Rename mechanic section inserted.
        batch = _make_batch_file("alpha", moves=[("old/path.py", "new/path.py")])
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mechanic_errs = [e for e in result if e["check"] == "move-mechanic-missing"]
        try:
            assert len(mechanic_errs) == 1, (
                f"expected 1 move-mechanic-missing error, got: {mechanic_errs}"
            )
            assert mechanic_errs[0]["batch"] == "01-alpha", (
                f"wrong batch: {mechanic_errs[0]['batch']!r}"
            )
            assert "Rename mechanic" in mechanic_errs[0]["message"], (
                f"message should mention 'Rename mechanic': {mechanic_errs[0]['message']!r}"
            )
            print("PASS test_move_mechanic_missing_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_mechanic_missing_dirty: {exc}", file=sys.stderr)
            return 1


def test_move_mechanic_missing_with_section_passes() -> int:
    """Clean: batch with non-empty Moves: AND ## Rename mechanic section -> no error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create Move source so move-source-missing does not fire.
        (project_root / "old").mkdir(parents=True)
        (project_root / "old" / "path.py").write_text("# code", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_raw = _make_batch_file("alpha", moves=[("old/path.py", "new/path.py")])
        batch = batch_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mechanic_errs = [e for e in result if e["check"] == "move-mechanic-missing"]
        try:
            assert len(mechanic_errs) == 0, (
                f"expected no move-mechanic-missing errors when section present, got: {mechanic_errs}"
            )
            print("PASS test_move_mechanic_missing_with_section_passes")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_mechanic_missing_with_section_passes: {exc}", file=sys.stderr)
            return 1


def test_move_mechanic_missing_all_none_skipped() -> int:
    """Clean: batch with all Moves: none sentinel -> no move-mechanic-missing error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        # Default Moves: none sentinel; parse_moves returns [] -> check is skipped entirely.
        batch = _make_batch_file("alpha")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mechanic_errs = [e for e in result if e["check"] == "move-mechanic-missing"]
        try:
            assert len(mechanic_errs) == 0, (
                f"Moves: none should not trigger move-mechanic-missing, got: {mechanic_errs}"
            )
            print("PASS test_move_mechanic_missing_all_none_skipped")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_move_mechanic_missing_all_none_skipped: {exc}", file=sys.stderr)
            return 1


def test_non_existent_path_move_target_suppressed() -> int:
    """Clean: downstream card's Context: references a Move target -> no non-existent-path error.

    When Batch A moves old.py -> new.py and Batch B has Context: new.py, the validator must NOT
    raise non-existent-path for new.py because it is in moves_targets (suppressed alongside
    creates_union per move-endpoint-accounting).
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create the Move source; new.py does NOT exist yet.
        (project_root / "old.py").write_text("# old code", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "number": 1, "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "number": 2, "depends-on": [1]},
        ])
        # Batch A: moves old.py -> new.py.
        batch_a_raw = _make_batch_file("alpha", card_num=1, moves=[("old.py", "new.py")])
        batch_a = batch_a_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        # Batch B: reads new.py in Context: -- new.py does not exist on disk yet.
        batch_b = _make_batch_file("beta", card_num=2, context=["new.py"])
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        nonexistent_errs = [
            e for e in result
            if e["check"] == "non-existent-path" and e["path"] == "new.py"
        ]
        try:
            assert len(nonexistent_errs) == 0, (
                f"Move target in Context: should be suppressed, got: {nonexistent_errs}"
            )
            print("PASS test_non_existent_path_move_target_suppressed")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_non_existent_path_move_target_suppressed: {exc}", file=sys.stderr)
            return 1


def test_all_files_touched_move_target_included() -> int:
    """Clean: Move target listed in All Files Touched -> no all-files-touched-mismatch error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create the Move source; new.py does NOT exist yet.
        (project_root / "old.py").write_text("# code", encoding="utf-8")

        # Overview lists the Move target new.py in All Files Touched.
        overview = _make_overview(
            [{"name": "alpha", "file": "01-alpha.md"}],
            all_files_touched=["new.py"],
        )
        batch_raw = _make_batch_file("alpha", moves=[("old.py", "new.py")])
        batch = batch_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])

        result = _plan_validate.run(plan_dir, project_root)
        mismatch_errs = [
            e for e in result
            if e["check"] == "all-files-touched-mismatch" and e["path"] == "new.py"
        ]
        try:
            assert len(mismatch_errs) == 0, (
                f"Move target in All Files Touched should not raise mismatch, got: {mismatch_errs}"
            )
            print("PASS test_all_files_touched_move_target_included")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_all_files_touched_move_target_included: {exc}", file=sys.stderr)
            return 1


def test_parallel_modifies_overlap_move_endpoint_fires() -> int:
    """Dirty: two parallel batches touching the same Move source -> parallel-modifies-overlap error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        # Create the shared source file; both batches declare a Move from it.
        (project_root / "shared.py").write_text("# shared", encoding="utf-8")

        overview = _make_overview([
            {"name": "alpha", "file": "01-alpha.md", "depends-on": []},
            {"name": "beta",  "file": "02-beta.md",  "depends-on": []},
        ])
        # Both batches are parallel-eligible (no dependency) and both touch shared.py as a Move source;
        # the validator must report the overlap.
        batch_a_raw = _make_batch_file("alpha", card_num=1, moves=[("shared.py", "a.py")])
        batch_a = batch_a_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        batch_b_raw = _make_batch_file("beta", card_num=2, moves=[("shared.py", "b.py")])
        batch_b = batch_b_raw.replace("## Cards\n\n", "## Rename mechanic\n\nRun git mv.\n\n## Cards\n\n")
        _write_plan(plan_dir, overview, [
            ("01-alpha.md", batch_a),
            ("02-beta.md",  batch_b),
        ])

        result = _plan_validate.run(plan_dir, project_root)
        overlap_errs = [
            e for e in result
            if e["check"] == "parallel-modifies-overlap" and e["path"] == "shared.py"
        ]
        try:
            assert len(overlap_errs) >= 1, (
                f"expected at least 1 parallel-modifies-overlap error for shared.py, got: {overlap_errs}"
            )
            assert any("alpha" in e["message"] and "beta" in e["message"] for e in overlap_errs), (
                f"message should mention both batch names: {overlap_errs}"
            )
            print("PASS test_parallel_modifies_overlap_move_endpoint_fires")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_parallel_modifies_overlap_move_endpoint_fires: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# verify-unrelated-test-file check (#638)
# ---------------------------------------------------------------------------

def test_check_verify_unrelated_test_files_flagged_non_main_parent() -> int:
    """(a) --only token untouched by the batch + byte-identical to a non-main parent branch ->
    flagged.

    Exercises the exact discrepancy round 4 of discussion review flagged: this task's own parent is
    'hanf/linux-port-more', not 'main', so the fixture deliberately uses a non-'main' parent branch
    name.
    """
    import _test_helpers  # noqa: E402 (local import; sys.path set up at module scope)

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        plan_dir = tmp / "plan"

        repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
        _test_helpers.checkout_new_branch(repo, "hanf/some-parent")
        _git_commit_new_file(git_root, "unrelated_test.py", "print('parent')\n", "add unrelated test")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= python run-all.py --only unrelated_test.py",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(
            plan_dir, git_root, git_root=git_root, parent_branch="hanf/some-parent",
        )
        errs = [e for e in result if e["check"] == "verify-unrelated-test-file"]
        try:
            assert len(errs) == 1, f"expected 1 finding, got {len(errs)}: {errs}"
            e = errs[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["card"] is None, f"wrong card: {e['card']!r}"
            assert e["path"] == "unrelated_test.py", f"wrong path: {e['path']!r}"
            assert "hanf/some-parent" in e["message"], f"message missing parent branch: {e['message']!r}"
            print("PASS test_check_verify_unrelated_test_files_flagged_non_main_parent")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_unrelated_test_files_flagged_non_main_parent: {exc}", file=sys.stderr)
            return 1


def test_check_verify_unrelated_test_files_touched_not_flagged() -> int:
    """(b) --only token IS in the batch's own Files Touched -> not flagged, regardless of parent-branch diff."""
    import _test_helpers  # noqa: E402

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        plan_dir = tmp / "plan"

        repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
        _test_helpers.checkout_new_branch(repo, "hanf/some-parent")
        _git_commit_new_file(git_root, "unrelated_test.py", "print('parent')\n", "add unrelated test")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= python run-all.py --only unrelated_test.py",
            edits=["unrelated_test.py"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(
            plan_dir, git_root, git_root=git_root, parent_branch="hanf/some-parent",
        )
        errs = [e for e in result if e["check"] == "verify-unrelated-test-file"]
        try:
            assert len(errs) == 0, f"expected no findings for a touched token, got: {errs}"
            print("PASS test_check_verify_unrelated_test_files_touched_not_flagged")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_unrelated_test_files_touched_not_flagged: {exc}", file=sys.stderr)
            return 1


def test_check_verify_unrelated_test_files_differs_not_flagged() -> int:
    """(c) --only token NOT in Files Touched but content DIFFERS from the parent branch -> not flagged."""
    import _test_helpers  # noqa: E402

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        plan_dir = tmp / "plan"

        repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
        _test_helpers.checkout_new_branch(repo, "hanf/some-parent")
        _git_commit_new_file(git_root, "unrelated_test.py", "print('parent')\n", "add unrelated test")
        # Working-tree content now diverges from the committed parent-branch blob -- simulates a file that was legitimately changed by something else.
        (git_root / "unrelated_test.py").write_text("print('changed')\n", encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= python run-all.py --only unrelated_test.py",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(
            plan_dir, git_root, git_root=git_root, parent_branch="hanf/some-parent",
        )
        errs = [e for e in result if e["check"] == "verify-unrelated-test-file"]
        try:
            assert len(errs) == 0, f"expected no findings for a differing token, got: {errs}"
            print("PASS test_check_verify_unrelated_test_files_differs_not_flagged")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_unrelated_test_files_differs_not_flagged: {exc}", file=sys.stderr)
            return 1


def test_check_verify_unrelated_test_files_parent_branch_none_no_findings() -> int:
    """(d) parent_branch=None -> no findings at all, regardless of any other condition (fail-safe no-op)."""
    import _test_helpers  # noqa: E402

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        plan_dir = tmp / "plan"

        repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
        _test_helpers.checkout_new_branch(repo, "hanf/some-parent")
        _git_commit_new_file(git_root, "unrelated_test.py", "print('parent')\n", "add unrelated test")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= python run-all.py --only unrelated_test.py",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        # Same fixture as the flagged case (a),
        # but parent_branch=None must short-circuit to zero findings before any diff is even attempted.
        result = _plan_validate.run(
            plan_dir, git_root, git_root=git_root, parent_branch=None,
        )
        errs = [e for e in result if e["check"] == "verify-unrelated-test-file"]
        try:
            assert len(errs) == 0, f"expected no findings with parent_branch=None, got: {errs}"
            print("PASS test_check_verify_unrelated_test_files_parent_branch_none_no_findings")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_unrelated_test_files_parent_branch_none_no_findings: {exc}", file=sys.stderr)
            return 1


def test_check_verify_unrelated_test_files_no_only_segment_no_findings() -> int:
    """(e) verify: command with no --only segment -> no candidate tokens -> no findings."""
    import _test_helpers  # noqa: E402

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        git_root = tmp / "repo"
        plan_dir = tmp / "plan"

        repo = _test_helpers.init_minimal_git_repo(git_root, branch="main")
        _test_helpers.checkout_new_branch(repo, "hanf/some-parent")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= python run-all.py -k pattern",
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(
            plan_dir, git_root, git_root=git_root, parent_branch="hanf/some-parent",
        )
        errs = [e for e in result if e["check"] == "verify-unrelated-test-file"]
        try:
            assert len(errs) == 0, f"expected no findings with no --only segment, got: {errs}"
            print("PASS test_check_verify_unrelated_test_files_no_only_segment_no_findings")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_verify_unrelated_test_files_no_only_segment_no_findings: {exc}", file=sys.stderr)
            return 1


def test_check_cards_legend_in_comment_not_parsed_as_refs() -> int:
    """Regression guard for #734: the Cards field-legend must not be parsed as refs.

    Part 1 reproduces the pre-fix bug: ``plan-batch.md`` used to render its field-legend bullets
    (``- **Context:** every file the implementer reads...`` and the six sibling fields) as literal
    content directly under ``## Cards``, outside any HTML comment.
    Every validator check that scans a batch file line-by-line for ``- **Context:**``/``-
    **Edits:**``/etc. headers (``_check_non_existent_path`` via ``_review_common.parse_batch_refs``,
    ``_check_ref_not_backtick_path``) matches those lines regardless of whether they are genuine
    card content or template prose, so the legend's bare (non-backtick) prose was misparsed as real
    path refs.

    Part 2 validates the corrected post-fix shape.
    The actual fix (``plan-batch.md`` Card 1) moves the field-legend into the template's single
    leading HTML comment, which ``_render.render()``'s ``_strip_leading_comment`` drops wholesale
    before a real per-task batch file is ever written -- a genuine post-fix batch file contains no
    trace of the legend at all, not a commented-out copy of it.
    This fixture therefore validates a batch file whose ``## Cards`` section goes straight from the
    heading to the real ``### Card 1:`` block, matching actual rendered output. (A literal ``<!-- ...
    -->``-wrapped legend still present in the batch file text would not clear this test even
    post-fix: ``_check_non_existent_path`` sources its Context:/Edits:/ Creates: tokens from
    ``_review_common.parse_batch_refs``, which has no HTML-comment awareness and is owned by a
    different batch in this plan -- out of this batch's edit scope -- so a
    comment-wrapped-but-present legend would still trip ``non-existent-path`` regardless of anything
    changed inside this batch's own ``_plan_validate.py``.)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        existing_file = project_root / "src" / "a.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# placeholder", encoding="utf-8")

        legend_lines = (
            "- **Context:** every file the implementer reads but does not change.\n"
            "- **Edits:** files the implementer changes.\n"
            "- **Creates:** files the implementer creates.\n"
            "- **Deletes:** files the implementer deletes.\n"
            "- **Moves:** old-to-new rename pairs this card performs.\n"
            "- **Requirements:** what the card must achieve.\n"
            "- **Commit:** one-line commit message the implementer will use.\n"
        )
        card_block = (
            "### Card 1: example\n\n"
            "- **Context:** none\n"
            "- **Edits:** `src/a.py`\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        frontmatter = (
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: null\ndepends-on: []\n"
            "```\n\n"
        )

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])

        # Part 1: legend prose sits directly under ## Cards, outside any HTML comment -- the original #734 bug shape.
        dirty_text = (
            "# Batch: alpha\n\n" + frontmatter
            + "## Cards\n\n" + legend_lines + "\n" + card_block
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", dirty_text)])
        dirty_result = _plan_validate.run(plan_dir, project_root)
        dirty_hits = [
            e for e in dirty_result
            if e["check"] in {"reads-not-backtick-path", "non-existent-path"}
        ]

        # Part 2: the corrected post-fix shape -- ## Cards goes straight to the real card, matching what a per-task batch file actually contains once plan-batch.md's leading HTML comment (now including the legend) is stripped during rendering.
        clean_text = (
            "# Batch: alpha\n\n" + frontmatter
            + "## Cards\n\n" + card_block
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", clean_text)])
        clean_result = _plan_validate.run(plan_dir, project_root)
        clean_hits = [
            e for e in clean_result
            if e["check"] in {
                "non-existent-path", "reads-not-backtick-path",
                "all-files-touched-mismatch", "parallel-modifies-overlap",
            }
        ]

        try:
            assert dirty_hits, (
                "expected at least one non-existent-path/reads-not-backtick-path "
                f"finding for the pre-fix legend-outside-comment shape, got none: {dirty_result}"
            )
            assert clean_hits == [], f"expected no findings for the post-fix shape, got: {clean_hits}"
            print("PASS test_check_cards_legend_in_comment_not_parsed_as_refs")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_cards_legend_in_comment_not_parsed_as_refs: {exc}", file=sys.stderr)
            return 1


def test_check_card_missing_field_fence_guard_clean() -> int:
    """Issue #776's exact repro: a fenced ### heading in Requirements: must not truncate the card."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"

        existing_file = project_root / "src" / "a.py"
        existing_file.parent.mkdir(parents=True)
        existing_file.write_text("# placeholder", encoding="utf-8")

        requirements = (
            "  Write the following exact heading into the target file:\n"
            "  ```markdown\n"
            "  ### Some Heading\n"
            "  ```\n"
        )
        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_batch_file("alpha", edits=["src/a.py"], requirements=requirements)
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "card-missing-field"]
        try:
            assert check == [], (
                f"expected no card-missing-field findings for a fenced ### heading "
                f"in Requirements:, got: {check}"
            )
            print("PASS test_check_card_missing_field_fence_guard_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_missing_field_fence_guard_clean: {exc}", file=sys.stderr)
            return 1


def test_check_card_missing_field_fence_guard_real_boundary_still_detected() -> int:
    """Regression guard: the fence guard must not over-suppress a genuine card boundary."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()

        frontmatter = (
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 2\nverify: null\ndepends-on: []\n"
            "```\n\n"
        )
        card1 = (
            "### Card 1: example\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n"
            "  Write the following exact heading into the target file:\n"
            "  ```markdown\n"
            "  ### Not A Real Heading\n"
            "  ```\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        card2 = (
            "### Card 2: card 2\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 2\n"
        )
        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n" + frontmatter
            + "## Cards\n\n" + card1 + "\n" + card2
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        missing_field_hits = [e for e in result if e["check"] == "card-missing-field"]
        numbering_hits = [e for e in result if e["check"] == "card-numbering"]
        try:
            assert missing_field_hits == [], (
                f"expected no card-missing-field findings, got: {missing_field_hits}"
            )
            assert numbering_hits == [], (
                f"expected no card-numbering findings, got: {numbering_hits}"
            )
            print("PASS test_check_card_missing_field_fence_guard_real_boundary_still_detected")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_check_card_missing_field_fence_guard_real_boundary_still_detected: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# verify-excludes-edited-tagged-test check (#724)
# ---------------------------------------------------------------------------

_GO_MOD_TEXT = "module example.com/alpha\n\ngo 1.21\n"

_INTEGRATION_TAGGED_TEST_GO = "//go:build integration\n\npackage foo\n"

_UNTAGGED_TEST_GO = "package foo\n\nfunc TestFoo(t *testing.T) {}\n"

_SCOUT_TAGGED_TEST_GO = "//go:build scout\n\npackage foo\n"
_SMOKE_TAGGED_TEST_GO = "//go:build smoke\n\npackage foo\n"
_GOOS_ONLY_TAGGED_TEST_GO = "//go:build linux\n\npackage foo\n"
_SCOUT_AND_SMOKE_TAGGED_TEST_GO = "//go:build scout && smoke\n\npackage foo\n"
_LINUX_AND_SCOUT_TAGGED_TEST_GO = "//go:build linux && scout\n\npackage foo\n"

_HEADER_COMMENT_INTEGRATION_TAGGED_TEST_GO = (
    "// Copyright 2024 Foo Corp.\n"
    "// Licensed under the Apache License, Version 2.0 (the \"License\");\n"
    "// you may not use this file except in compliance with the License.\n"
    "// You may obtain a copy of the License at\n"
    "//\n"
    "//     http://www.apache.org/licenses/LICENSE-2.0\n"
    "//\n"
    "//go:build integration\n\n"
    "package foo\n"
)


def test_verify_excludes_edited_tagged_test_no_tags_flag_dirty() -> int:
    """(a) Go project, edited integration-tagged test, verify: has no -tags -> one finding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_INTEGRATION_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
            e = check[0]
            assert e["batch"] == "01-alpha", f"wrong batch: {e['batch']!r}"
            assert e["path"] == "pkg/foo_test.go", f"wrong path: {e['path']!r}"
            print("PASS test_verify_excludes_edited_tagged_test_no_tags_flag_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_no_tags_flag_dirty: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_tags_integration_clean() -> int:
    """(b) Same fixture, verify: includes -tags integration -> zero findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_INTEGRATION_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./... -tags integration", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_tags_integration_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_tags_integration_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_tags_integration_comma_other_clean() -> int:
    """(c) Same fixture, verify: includes -tags integration,other -> zero findings (comma-split)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_INTEGRATION_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./... -tags integration,other", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_tags_integration_comma_other_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_tags_integration_comma_other_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_no_build_tag_clean() -> int:
    """(d) Go project, edited _test.go has no //go:build line at all -> zero findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_UNTAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_no_build_tag_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_no_build_tag_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_not_go_project_clean() -> int:
    """(e) NOT a Go project (no go.mod) -- otherwise identical to (a)'s dirty fixture -> zero findings (fail-open language gate)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_INTEGRATION_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings for a non-Go project, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_not_go_project_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_not_go_project_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_malformed_verify_no_crash() -> int:
    """(f) Go project, malformed verify: {cwd, command} mapping -> zero findings, no crash."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_INTEGRATION_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\ndepends-on: []\n"
            "verify:\n  cwd: hub\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** `pkg/foo_test.go`\n"
            "- **Creates:** none\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        # run() must not raise -- the ValueError parse_verify_field raises for a malformed mapping (missing command:) is caught and skipped by this check.
        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings for a malformed verify: mapping, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_malformed_verify_no_crash")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_malformed_verify_no_crash: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_header_comment_scan_dirty() -> int:
    """(g) Leading //-comment header before //go:build integration -> finding still raised."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_HEADER_COMMENT_INTEGRATION_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert len(check) == 1, (
                f"expected 1 finding despite the leading header comment, got {len(check)}: {check}"
            )
            print("PASS test_verify_excludes_edited_tagged_test_header_comment_scan_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_header_comment_scan_dirty: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_creates_only_clean() -> int:
    """(h) Tagged file referenced only via Creates: (not Edits:) -> zero findings (documented limitation)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        # The file is intentionally never written to disk -- Creates: targets do not exist at plan-validation time, per this codebase's convention.

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = (
            "# Batch: alpha\n\n"
            "```yaml\n"
            "task: test\nbatch: alpha\ncards: 1\nverify: PYTHONPATH= go test ./...\ndepends-on: []\n"
            "```\n\n"
            "## Cards\n\n"
            "### Card 1: card 1\n\n"
            "- **Context:** none\n"
            "- **Edits:** none\n"
            "- **Creates:** `pkg/foo_test.go`\n"
            "- **Deletes:** none\n"
            "- **Moves:** none\n"
            "- **Requirements:**\n  See scope.\n"
            "- **Commit:** feat(alpha): card 1\n"
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings for a Creates:-only reference, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_creates_only_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_creates_only_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty() -> int:
    """Custom "scout" tag, verify: has no -tags -> one finding naming "scout"."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
            e = check[0]
            assert e["path"] == "pkg/foo_test.go", f"wrong path: {e['path']!r}"
            assert "scout" in e["message"], f"message missing 'scout': {e['message']!r}"
            print("PASS test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean() -> int:
    """Custom "scout" tag, verify: has -tags scout -> zero findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./... -tags scout", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty() -> int:
    """Custom "smoke" tag, verify: has no -tags -> one finding naming "smoke"."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
            assert "smoke" in check[0]["message"], f"message missing 'smoke': {check[0]['message']!r}"
            print("PASS test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean() -> int:
    """Custom "smoke" tag, verify: has -tags smoke -> zero findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./... -tags smoke", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean() -> int:
    """Denylist-correctness regression guard: a plain //go:build linux file never needs -tags linux."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_GOOS_ONLY_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings for a GOOS-only build tag, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty() -> int:
    """Two tagged files in one batch, verify: only covers the first -> one finding for the second."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        foo_file = project_root / "pkg" / "foo_test.go"
        foo_file.parent.mkdir(parents=True, exist_ok=True)
        foo_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")
        bar_file = project_root / "pkg" / "bar_test.go"
        bar_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./... -tags scout",
            edits=["pkg/foo_test.go", "pkg/bar_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
            e = check[0]
            assert e["path"] == "pkg/bar_test.go", f"wrong path: {e['path']!r}"
            assert "smoke" in e["message"], f"message missing 'smoke': {e['message']!r}"
            print("PASS test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean() -> int:
    """Two tagged files in one batch, verify: covers both tags -> zero findings."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        foo_file = project_root / "pkg" / "foo_test.go"
        foo_file.parent.mkdir(parents=True, exist_ok=True)
        foo_file.write_text(_SCOUT_TAGGED_TEST_GO, encoding="utf-8")
        bar_file = project_root / "pkg" / "bar_test.go"
        bar_file.write_text(_SMOKE_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./... -tags scout,smoke",
            edits=["pkg/foo_test.go", "pkg/bar_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty() -> int:
    """One file composed of two custom tags, no -tags flag -> one finding naming the alphabetically-first tag."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "baz_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_SCOUT_AND_SMOKE_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/baz_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
            e = check[0]
            assert e["path"] == "pkg/baz_test.go", f"wrong path: {e['path']!r}"
            assert "scout" in e["message"], f"message missing 'scout': {e['message']!r}"
            assert "smoke" not in e["message"], f"message unexpectedly contains 'smoke': {e['message']!r}"
            print("PASS test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean() -> int:
    """Same composed-tag file, verify: names only the second/non-first tag -> zero findings (ANY-tag rule)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "baz_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_SCOUT_AND_SMOKE_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./... -tags smoke", edits=["pkg/baz_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert check == [], f"expected no findings, got: {check}"
            print("PASS test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean: {exc}", file=sys.stderr)
            return 1


def test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty() -> int:
    """GOOS + custom tag composed in one expression -> denylist strips "linux", custom "scout" still discovered."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        plan_dir = tmp / "plan"
        project_root = tmp / "project"
        project_root.mkdir()
        (project_root / "go.mod").write_text(_GO_MOD_TEXT, encoding="utf-8")
        test_file = project_root / "pkg" / "foo_test.go"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text(_LINUX_AND_SCOUT_TAGGED_TEST_GO, encoding="utf-8")

        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
        batch_text = _make_verify_only_batch_text(
            "alpha", "PYTHONPATH= go test ./...", edits=["pkg/foo_test.go"],
        )
        _write_plan(plan_dir, overview, [("01-alpha.md", batch_text)])

        result = _plan_validate.run(plan_dir, project_root)
        check = [e for e in result if e["check"] == "verify-excludes-edited-tagged-test"]
        try:
            assert len(check) == 1, f"expected 1 finding, got {len(check)}: {check}"
            e = check[0]
            assert e["path"] == "pkg/foo_test.go", f"wrong path: {e['path']!r}"
            assert "scout" in e["message"], f"message missing 'scout': {e['message']!r}"
            assert "linux" not in e["message"], f"message unexpectedly contains 'linux': {e['message']!r}"
            print("PASS test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty")
            return 0
        except AssertionError as exc:
            print(f"FAIL test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty: {exc}", file=sys.stderr)
            return 1


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main() -> int:
    tests = [
        test_check_non_existent_path_clean,
        test_check_non_existent_path_dirty,
        # gitignore-aware Context: refs (#868)
        test_check_non_existent_path_context_gitignored_clean,
        test_check_non_existent_path_context_not_gitignored_dirty,
        test_check_non_existent_path_edits_gitignored_still_dirty,
        test_check_card_missing_field_clean,
        test_check_card_missing_field_dirty,
        # commit-none-with-content check (issue #664)
        test_check_commit_none_with_content_clean_all_none,
        test_check_commit_none_with_content_dirty_edits,
        test_check_commit_none_with_content_dirty_edits_and_creates,
        test_check_commit_none_with_content_regression_real_commit_unaffected,
        test_check_commit_none_with_content_missing_commit_field_independent,
        test_check_card_numbering_clean,
        test_check_card_numbering_dirty_gap,
        test_check_card_numbering_dirty_cross_batch,
        test_check_depends_on_unknown_clean,
        test_check_depends_on_unknown_dirty,
        test_check_depends_on_unknown_dirty_legacy_string,
        test_depends_on_batch_mismatch_no_finding_on_match,
        test_depends_on_batch_mismatch_emits_finding,
        test_check_parallel_modifies_overlap_clean,
        test_check_parallel_modifies_overlap_dirty,
        test_check_cross_batch_creates_no_depends_on_clean,
        test_check_cross_batch_creates_no_depends_on_dirty,
        test_check_cross_batch_creates_no_depends_on_transitive_clean,
        test_check_reads_not_backtick_path_clean,
        test_check_reads_not_backtick_path_none_exempt,
        test_check_reads_not_backtick_path_dirty,
        test_check_reads_not_backtick_path_dirty_multiline_multi_backtick,
        test_check_all_files_touched_mismatch_clean_no_section,
        test_check_all_files_touched_mismatch_dirty,
        test_check_all_files_touched_mismatch_deletes_only_excluded,
        test_run_returns_sorted,
        test_run_no_overview,
        # Deletes-aware behaviour (Cards 26–28)
        test_deletes_field_required,
        test_deletes_token_on_disk_clean,
        test_deletes_token_in_creates_union_clean,
        test_deletes_token_missing_not_in_creates_dirty,
        test_reads_token_in_deletes_union_clean,
        test_reads_token_in_creates_union_suppressed,
        test_reads_token_missing_both_unions_dirty,
        test_all_files_touched_deletes_not_required,

        test_wiki_config_mutation_clean,
        test_wiki_config_mutation_modifies,
        test_wiki_config_mutation_creates,
        test_wiki_config_mutation_multi_batch,
        test_wiki_config_mutation_modifies_and_creates,
        # plugin-manifest-context-missing check
        test_plugin_manifest_context_missing_creates_dirty,
        test_plugin_manifest_context_missing_creates_with_context_clean,
        test_plugin_manifest_context_missing_creates_with_edits_clean,
        test_plugin_manifest_context_missing_deletes_dirty,
        test_plugin_manifest_context_missing_unrelated_batch_clean,
        # context-completeness check (#742)
        test_check_context_completeness_clean_in_context,
        test_check_context_completeness_clean_in_edits,
        test_check_context_completeness_clean_in_creates,
        test_check_context_completeness_dirty_missing,
        test_check_context_completeness_dirty_missing_scoped_to_own_card,
        test_check_context_completeness_clean_non_path_token,
        test_check_context_completeness_clean_unresolvable_token,
        test_check_context_completeness_clean_in_deletes,
        test_check_context_completeness_clean_in_moves_source,
        test_check_context_completeness_dirty_moves_target_only,
        test_check_context_completeness_run_wiring_no_false_positives,
        test_check_context_completeness_clean_prohibition_marker,
        test_check_context_completeness_clean_line_range_suffix_in_context,
        test_check_context_completeness_dirty_line_range_suffix_missing,
        test_check_context_completeness_clean_directory_reference,
        test_check_context_completeness_clean_directory_reference_not_on_disk,
        test_check_context_completeness_clean_double_slash_token,
        test_check_context_completeness_dirty_odd_backtick_count_line_field,
        test_check_context_completeness_clean_citation_marker,
        test_check_context_completeness_dirty_citation_marker_absent,
        # inline-signature citation markers (validator-tests batch, Card 8)
        test_check_context_completeness_clean_signature_inlined_marker,
        test_check_context_completeness_clean_no_file_read_needed_marker,
        test_check_context_completeness_dirty_inline_signature_marker_absent,
        test_check_context_completeness_clean_moves_source_plan_wide,
        test_check_context_completeness_dirty_moves_target_plan_wide_still_flagged,
        test_check_context_completeness_message_includes_moves_source_qualifier,
        test_check_context_completeness_clean_prohibition_marker_change_modify,
        test_check_context_completeness_clean_prohibition_marker_untested_existing,
        test_check_context_completeness_clean_prohibition_marker_new_verbs,
        test_check_context_completeness_clean_prohibition_marker_write_irregular,
        test_check_context_completeness_dirty_prohibition_marker_unrelated_negation_not_exempted,
        test_check_context_completeness_dirty_prohibition_marker_verb_without_negation_not_exempted,
        # requirements-quote-indent-drift check (mill-plan-requirements-byte-exactness-gap)
        test_check_requirements_quote_indent_drift_clean_exact_match,
        test_check_requirements_quote_indent_drift_clean_illustrative_snippet,
        test_check_requirements_quote_indent_drift_clean_no_edits_field,
        test_check_requirements_quote_indent_drift_dirty_list_continuation_indent,
        test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent,
        test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card,
        test_check_requirements_quote_indent_drift_dirty_crlf_source_lf_fence,
        test_check_requirements_quote_indent_drift_dirty_fence_contains_nested_heading,
        test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break,
        test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer,
        test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer,
        # under-indented requirements fences (validator-tests batch, Card 7)
        test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence,
        test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line,
        test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line,
        test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen,
        test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact,
        test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match,
        # skip_checks filtering (Card 7 / #188)
        test_skip_checks_filters_wiki_config_mutation,
        test_skip_checks_does_not_suppress_other_checks,
        test_skip_checks_unknown_check_silently_ignored,
        # verify-not-isolated check
        test_check_verify_not_isolated_null,
        test_check_verify_not_isolated_missing_key,
        test_check_verify_not_isolated_dirty_no_prefix,
        test_check_verify_not_isolated_clean_with_prefix,
        test_check_verify_not_isolated_two_batches_dirty,
        test_check_verify_not_isolated_leading_whitespace,
        test_check_verify_not_isolated_non_empty_pythonpath_value,
        test_check_verify_not_isolated_run_integration,
        # Language-aware verify-not-isolated check (Python markers)
        test_check_verify_not_isolated_python_marker_pyproject_dirty,
        test_check_verify_not_isolated_python_marker_setup_py_dirty,
        test_check_verify_not_isolated_python_marker_plugins_mill_clean,
        test_check_verify_not_isolated_no_python_marker_native_command_clean,
        test_check_verify_not_isolated_no_python_marker_dotnet_test_clean,
        # out-of-worktree-target check
        test_out_of_worktree_target_home_dir_flags,
        test_out_of_worktree_target_absolute_path_flags,
        test_out_of_worktree_target_relative_path_clean,
        test_out_of_worktree_target_creates_nonexistent_clean,
        # batch-oversized check
        test_batch_oversized_card_count_clean,
        test_batch_oversized_card_count_dirty,
        test_batch_oversized_context_tokens_clean,
        test_batch_oversized_context_tokens_dirty,
        test_batch_oversized_defaults_applied,
        # verify-full-suite check
        test_check_verify_full_suite_run_all_py_without_filter_is_error,
        test_check_verify_full_suite_run_all_py_with_k_filter_is_ok,
        test_check_verify_full_suite_run_all_py_with_only_is_ok,
        # verify-full-suite: language-aware unbounded-verify guard (#881)
        test_check_verify_full_suite_go_test_dotdotdot_without_run_is_error,
        test_check_verify_full_suite_go_test_dotdotdot_with_run_is_ok,
        test_check_verify_full_suite_dotnet_test_without_filter_is_error,
        test_check_verify_full_suite_dotnet_test_with_filter_is_ok,
        test_check_verify_full_suite_bare_pytest_without_filter_is_error,
        test_check_verify_full_suite_bare_python_m_pytest_without_filter_is_error,
        test_check_verify_full_suite_pytest_with_k_filter_is_ok,
        test_check_verify_full_suite_pytest_with_path_is_ok,
        test_check_verify_full_suite_bare_pytest_no_python_marker_clean,
        # verify-full-suite: segment scoping + done_gate exemption (#933, #950, #961)
        test_check_verify_full_suite_go_test_compound_command_scoped_dotdotdot_is_ok,
        test_check_verify_full_suite_go_dash_c_test_dotdotdot_without_run_is_error,
        test_check_verify_full_suite_go_dash_c_test_dotdotdot_with_run_is_ok,
        test_check_verify_full_suite_done_gate_exact_match_is_ok,
        test_check_verify_full_suite_done_gate_subset_still_flagged,
        test_check_verify_full_suite_done_gate_exact_match_overview_level_is_ok,
        # verify cwd mapping form (Cards 23-25 / #604)
        test_check_verify_not_isolated_mapping_form_dirty,
        test_check_verify_not_isolated_mapping_form_clean,
        test_check_verify_full_suite_mapping_form_dirty,
        test_check_verify_not_isolated_overview_level_dirty,
        test_check_verify_full_suite_overview_level_dirty,
        test_check_verify_malformed_cwd_missing_command_dirty,
        test_check_verify_malformed_cwd_bad_cwd_value_dirty,
        test_check_verify_mixed_cwd_dirty,
        test_check_verify_mixed_cwd_single_cwd_clean,
        # verify-batch-mismatch check (Card 6)
        test_verify_batch_mismatch_clean_identical_string,
        test_verify_batch_mismatch_dirty_null_vs_command,
        test_verify_batch_mismatch_dirty_trailing_clause,
        test_verify_batch_mismatch_clean_absent_vs_null,
        test_verify_batch_mismatch_clean_both_absent,
        test_verify_batch_mismatch_clean_both_null,
        test_verify_batch_mismatch_dirty_string_vs_mapping_cwd,
        test_verify_batch_mismatch_clean_matching_mapping,
        test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root,
        test_verify_batch_mismatch_dirty_overview_malformed_mapping,
        test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report,
        test_verify_batch_mismatch_clean_overview_batches_unparseable,
        test_verify_batch_mismatch_clean_missing_batch_file,
        # git_root threading (Card 5 / #471)
        test_git_root_threading_with_subfolder_cwd_clean,
        test_git_root_threading_without_git_root_default_none_documents_required,
        # Move-specific checks (batch validator-move-checks)
        test_moves_field_required_dirty,
        test_move_format_well_formed_passes,
        test_move_format_malformed_missing_arrow_dirty,
        test_move_redundant_same_path_in_creates_dirty,
        test_move_redundant_different_creates_path_passes,
        test_move_source_missing_dirty,
        test_move_source_missing_suppressed_by_creates_union,
        test_move_target_collision_pre_existing_dirty,
        test_move_target_collision_duplicate_target_dirty,
        test_move_target_collision_cross_batch_creates_dirty,
        test_move_mechanic_missing_dirty,
        test_move_mechanic_missing_with_section_passes,
        test_move_mechanic_missing_all_none_skipped,
        test_non_existent_path_move_target_suppressed,
        test_all_files_touched_move_target_included,
        test_parallel_modifies_overlap_move_endpoint_fires,
        # verify-unrelated-test-file check (#638)
        test_check_verify_unrelated_test_files_flagged_non_main_parent,
        test_check_verify_unrelated_test_files_touched_not_flagged,
        test_check_verify_unrelated_test_files_differs_not_flagged,
        test_check_verify_unrelated_test_files_parent_branch_none_no_findings,
        test_check_verify_unrelated_test_files_no_only_segment_no_findings,
        # Cards field-legend HTML-comment regression guard (#734)
        test_check_cards_legend_in_comment_not_parsed_as_refs,
        test_check_card_missing_field_fence_guard_clean,
        test_check_card_missing_field_fence_guard_real_boundary_still_detected,
        # verify-excludes-edited-tagged-test check (#724)
        test_verify_excludes_edited_tagged_test_no_tags_flag_dirty,
        test_verify_excludes_edited_tagged_test_tags_integration_clean,
        test_verify_excludes_edited_tagged_test_tags_integration_comma_other_clean,
        test_verify_excludes_edited_tagged_test_no_build_tag_clean,
        test_verify_excludes_edited_tagged_test_not_go_project_clean,
        test_verify_excludes_edited_tagged_test_malformed_verify_no_crash,
        test_verify_excludes_edited_tagged_test_header_comment_scan_dirty,
        test_verify_excludes_edited_tagged_test_creates_only_clean,
        test_verify_excludes_edited_tagged_test_scout_tag_no_tags_flag_dirty,
        test_verify_excludes_edited_tagged_test_scout_tag_tags_scout_clean,
        test_verify_excludes_edited_tagged_test_smoke_tag_no_tags_flag_dirty,
        test_verify_excludes_edited_tagged_test_smoke_tag_tags_smoke_clean,
        test_verify_excludes_edited_tagged_test_goos_only_no_tags_flag_clean,
        test_verify_excludes_edited_tagged_test_multi_file_batch_untested_second_file_dirty,
        test_verify_excludes_edited_tagged_test_multi_file_batch_both_tags_clean,
        test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_no_tags_dirty,
        test_verify_excludes_edited_tagged_test_multi_composed_tag_single_file_second_tag_only_clean,
        test_verify_excludes_edited_tagged_test_goos_and_custom_composed_dirty,
    ]

    errors = 0
    for t in tests:
        try:
            rc = t()
            if rc != 0:
                errors += 1
        except Exception as exc:
            errors += 1
            print(f"FAIL {t.__name__} (unexpected {type(exc).__name__}): {exc}",
                  file=sys.stderr)

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _plan_validate unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
