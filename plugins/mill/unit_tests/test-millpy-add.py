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


def _load_add_module(wiki_path: Path) -> tuple[types.ModuleType, MagicMock, MagicMock]:
    """Load millpy-add.py with all external dependencies stubbed.

    Returns ``(mod, wiki_stub, sidebar_stub)``.
    """
    spec = importlib.util.spec_from_file_location("mill_add", ADD_PATH)
    if spec is None or spec.loader is None:
        raise AssertionError(f"Could not build module spec for {ADD_PATH}")
    mod = importlib.util.module_from_spec(spec)

    wiki_stub = MagicMock()
    sidebar_stub = MagicMock()
    paths_stub = MagicMock()
    paths_stub.resolve_git_root = MagicMock(return_value=Path("/fake/repo"))
    paths_stub.resolve_wiki_path = MagicMock(return_value=wiki_path)

    stub_map: dict[str, object] = {
        "_sidebar": sidebar_stub,
        "_wiki": wiki_stub,
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

    return mod, wiki_stub, sidebar_stub


def test_proposal_body_file_reads_content() -> None:
    """--proposal-body-file reads file content and uses it as the proposal body."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)
        (wiki_path / "Home.md").write_text("# Tasks\n", encoding="utf-8")

        body_file = wiki_path / "body.md"
        body_file.write_text(_BODY_FIXTURE, encoding="utf-8")

        mod, _wiki_stub, _sidebar_stub = _load_add_module(wiki_path)

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

        proposal_path = wiki_path / "proposal-test-slug.md"
        if not proposal_path.exists():
            raise AssertionError(f"proposal file not created at {proposal_path}")

        actual = proposal_path.read_text(encoding="utf-8")
        # Production code normalises trailing newlines: rstrip("\n") + "\n"
        expected = _BODY_FIXTURE.rstrip("\n") + "\n"
        if actual != expected:
            raise AssertionError(
                f"proposal content mismatch.\nExpected: {expected!r}\nGot:      {actual!r}"
            )

    print("PASS: --proposal-body-file reads file content byte-for-byte")


def test_proposal_body_and_file_mutually_exclusive() -> None:
    """--proposal-body and --proposal-body-file together -> non-zero SystemExit."""
    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)
        (wiki_path / "Home.md").write_text("# Tasks\n", encoding="utf-8")

        mod, _, _ = _load_add_module(wiki_path)

        try:
            with (
                patch.object(mod, "resolve_git_root", return_value=Path("/fake/repo")),
                patch.object(mod, "resolve_wiki_path", return_value=wiki_path),
            ):
                mod.main(
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
            if exc.code == 0:
                raise AssertionError(
                    "expected non-zero SystemExit for mutually-exclusive flags, got code 0"
                )
        else:
            raise AssertionError(
                "expected SystemExit for mutually-exclusive flags, but main() returned normally"
            )

    print("PASS: --proposal-body and --proposal-body-file together cause non-zero SystemExit")


def test_proposal_body_file_missing_path() -> None:
    """--proposal-body-file with non-existent path -> clean SystemExit, no partial wiki writes."""
    missing_path = "/nonexistent/path/that/cannot/exist/body.md"

    with tempfile.TemporaryDirectory() as tmpdir:
        wiki_path = Path(tmpdir)
        original_home = "# Tasks\n"
        (wiki_path / "Home.md").write_text(original_home, encoding="utf-8")

        mod, _, _ = _load_add_module(wiki_path)

        try:
            with (
                patch.object(mod, "resolve_git_root", return_value=Path("/fake/repo")),
                patch.object(mod, "resolve_wiki_path", return_value=wiki_path),
            ):
                mod.main(
                    [
                        "test-slug",
                        "--title",
                        "Test",
                        "--proposal-body-file",
                        missing_path,
                    ]
                )
        except SystemExit as exc:
            if exc.code == 0:
                raise AssertionError(
                    "expected non-zero SystemExit for missing body file, got code 0"
                )
            home_text = (wiki_path / "Home.md").read_text(encoding="utf-8")
            if home_text != original_home:
                raise AssertionError(
                    "Home.md was modified despite --proposal-body-file pointing to a missing file"
                )
        else:
            raise AssertionError(
                "expected SystemExit for missing --proposal-body-file, but main() returned normally"
            )

    print("PASS: missing --proposal-body-file causes clean non-zero exit without partial wiki writes")


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
