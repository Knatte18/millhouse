"""Unit tests for plugins/mill/scripts/millpy-add.py — --proposal-body-file flag.

Written TDD-style: tests fail until Card 12 implements the flag.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

ADD_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-add.py"

# Multi-line markdown payload exercising heredoc-loss characters:
# backticks, code fences, headings, quotes, and blank lines.
_BODY_FIXTURE = (
    "# Proposal Heading\n"
    "\n"
    "```python\n"
    "def example():\n"
    '    return "hello"\n'
    "```\n"
    "\n"
    'Some "quoted" text with backticks `here`.\n'
    "\n"
    "Blank line above.\n"
)


def _load_add_module(wiki_path: Path) -> tuple[types.ModuleType, MagicMock]:
    """Load millpy-add.py with wiki module stubbed.

    Returns ``(mod, wiki_stub)``.
    """
    spec = importlib.util.spec_from_file_location("mill_add", ADD_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not build module spec for {ADD_PATH}")
    mod = importlib.util.module_from_spec(spec)

    wiki_stub = MagicMock()
    wiki_stub.get_task = MagicMock(return_value=None)
    wiki_stub.upsert_task = MagicMock()
    paths_stub = MagicMock()
    paths_stub.resolve_git_root = MagicMock(return_value=Path("/fake/repo"))
    paths_stub.resolve_wiki_path = MagicMock(return_value=wiki_path)

    stub_map: dict[str, object] = {
        "wiki._client": wiki_stub,
        "_paths": paths_stub,
    }
    saved: dict[str, object] = {}
    for name, stub in stub_map.items():
        saved[name] = sys.modules.get(name)
        sys.modules[name] = stub  # type: ignore[assignment]

    try:
        spec.loader.exec_module(mod)
    finally:
        for name, original in saved.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original  # type: ignore[assignment]

    return mod, wiki_stub


def test_proposal_body_file_reads_content() -> None:
    """--proposal-body-file reads file content and passes to wiki.upsert_task."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)
        (wiki_path / "Home.md").write_text("# Tasks\n", encoding="utf-8")

        body_file = wiki_path / "body.md"
        body_file.write_text(_BODY_FIXTURE, encoding="utf-8")

        mod, wiki_stub = _load_add_module(wiki_path)

        try:
            with (
                patch.object(mod, "resolve_git_root", return_value=Path("/fake/repo")),
                patch.object(mod, "resolve_wiki_path", return_value=wiki_path),
            ):
                exit_code = mod.main(
                    ["test-slug", "--title", "Test Title", "--proposal-body-file", str(body_file)]
                )
        except SystemExit as exc:
            raise AssertionError(
                f"main() raised unexpected SystemExit({exc.code!r}) — "
                "--proposal-body-file flag not implemented yet?"
            ) from exc

        if exit_code != 0:
            raise AssertionError(f"expected exit 0, got {exit_code}")

        if not wiki_stub.upsert_task.called:
            raise AssertionError("wiki.upsert_task was not called")

        call_args = wiki_stub.upsert_task.call_args
        if call_args is None:
            raise AssertionError("wiki.upsert_task called but no args captured")

        # Normalize expected body (production code: rstrip("\n") + "\n")
        expected_body = _BODY_FIXTURE.rstrip("\n") + "\n"
        actual_body = call_args.kwargs.get("body")

        if actual_body != expected_body:
            raise AssertionError(
                f"proposal body mismatch.\nExpected: {expected_body!r}\nGot:      {actual_body!r}"
            )

    print("PASS: --proposal-body-file reads file content and passes to wiki.upsert_task")


def test_proposal_body_and_file_mutually_exclusive() -> None:
    """--proposal-body and --proposal-body-file together -> non-zero exit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)
        (wiki_path / "Home.md").write_text("# Tasks\n", encoding="utf-8")

        mod, _wiki_stub = _load_add_module(wiki_path)

        exit_code = None
        try:
            with (
                patch.object(mod, "resolve_git_root", return_value=Path("/fake/repo")),
                patch.object(mod, "resolve_wiki_path", return_value=wiki_path),
            ):
                exit_code = mod.main(
                    [
                        "test-slug",
                        "--title",
                        "T",
                        "--proposal-body",
                        "x",
                        "--proposal-body-file",
                        "/fake/nonexistent",
                    ]
                )
        except SystemExit as exc:
            exit_code = exc.code

        if exit_code == 0 or exit_code is None:
            raise AssertionError(
                f"expected non-zero exit for mutually-exclusive flags, got {exit_code}"
            )

    print("PASS: --proposal-body and --proposal-body-file together cause non-zero exit")


def test_proposal_body_file_missing_path() -> None:
    """--proposal-body-file with non-existent path -> clean non-zero exit."""
    missing_path = "/nonexistent/path/that/cannot/exist/body.md"

    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)
        (wiki_path / "Home.md").write_text("# Tasks\n", encoding="utf-8")

        mod, wiki_stub = _load_add_module(wiki_path)

        exit_code = None
        try:
            with (
                patch.object(mod, "resolve_git_root", return_value=Path("/fake/repo")),
                patch.object(mod, "resolve_wiki_path", return_value=wiki_path),
            ):
                exit_code = mod.main(
                    [
                        "test-slug",
                        "--title",
                        "Test",
                        "--proposal-body-file",
                        missing_path,
                    ]
                )
        except SystemExit as exc:
            exit_code = exc.code

        if exit_code == 0 or exit_code is None:
            raise AssertionError(
                f"expected non-zero exit for missing body file, got {exit_code}"
            )

        if wiki_stub.upsert_task.called:
            raise AssertionError(
                "wiki.upsert_task should not be called for missing --proposal-body-file"
            )

    print("PASS: missing --proposal-body-file causes clean non-zero exit without upsert")


def main() -> int:
    tests = [
        test_proposal_body_file_reads_content,
        test_proposal_body_and_file_mutually_exclusive,
        test_proposal_body_file_missing_path,
    ]

    failures: list[str] = []
    for test_fn in tests:
        try:
            test_fn()
        except AssertionError as exc:
            print(f"FAIL [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{test_fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(test_fn.__name__)

    print()
    if failures:
        print(f"FAIL -- {len(failures)} of {len(tests)} tests: {failures}", file=sys.stderr)
        return 1
    print(f"All {len(tests)} millpy-add unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
