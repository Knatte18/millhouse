"""Unit tests for framework-type and ``Type.Member`` resolution in the context-completeness check.

Standalone file with hand-written plan text; each fixture builds a project root with real source
files and runs ``_plan_validate.run`` over it, keeping only context-completeness findings.
"""
from __future__ import annotations

import sys
import tempfile
import traceback
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _plan_validate  # noqa: E402


def _overview_text(batch_count: int) -> str:
    entries = "".join(
        f"  - number: {number}\n"
        f"    name: demo{number}\n"
        f"    file: {number:02d}-demo{number}.md\n"
        f"    depends-on: []\n"
        f"    verify: null\n"
        for number in range(1, batch_count + 1)
    )
    return (
        "# Plan: demo\n\n"
        "```yaml\ntask: \"demo\"\nslug: \"demo\"\nverify: null\n```\n\n"
        "## Batch Index\n\n"
        "```yaml\nbatches:\n" + entries + "```\n"
    )


def _bullets(paths: list[str]) -> str:
    return "".join(f"  - `{path}`\n" for path in paths) if paths else " none\n"


def _card(number: int, context: list[str], edits: list[str], requirements: str) -> str:
    context_block = "- **Context:**\n" + _bullets(context) if context else "- **Context:** none\n"
    edits_block = "- **Edits:**\n" + _bullets(edits) if edits else "- **Edits:** none\n"
    return (
        f"### Card {number}: demo card {number}\n\n"
        + context_block
        + edits_block
        + "- **Creates:** none\n"
        "- **Deletes:** none\n"
        "- **Moves:** none\n"
        f"- **Requirements:**\n  {requirements}\n"
        f"- **Commit:** `demo: card {number}`\n\n"
    )


def _batch_text(cards: list[str]) -> str:
    return (
        "# Batch: demo1\n\n"
        "```yaml\ntask: \"demo\"\nbatch: \"demo1\"\nnumber: 1\n"
        f"cards: {len(cards)}\nverify: null\ndepends-on: []\n```\n\n"
        "## Cards\n\n" + "".join(cards)
    )


def _run_findings(files: dict[str, str], cards: list[str]) -> list[dict]:
    """Write ``files`` under a temp project root, run the validator, return context-completeness findings."""
    with tempfile.TemporaryDirectory() as tmp:
        project_root = Path(tmp) / "project"
        for relative, content in files.items():
            target = project_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        plan_dir = Path(tmp) / "plan"
        plan_dir.mkdir()
        (plan_dir / "00-overview.md").write_text(_overview_text(1), encoding="utf-8")
        (plan_dir / "01-demo1.md").write_text(_batch_text(cards), encoding="utf-8")
        errors = _plan_validate.run(plan_dir, project_root)
    return [error for error in errors if error["check"] == "context-completeness"]


def _assert_no_findings(findings: list[dict]) -> None:
    if findings:
        raise AssertionError(f"expected no context-completeness findings, got {findings}")


def test_framework_exception_in_member_shaped_line_not_flagged() -> None:
    files = {
        "src/Other.cs": "namespace Demo;\npublic class Other { }\n",
        "src/Svc.cs": (
            "namespace Demo;\n"
            "public class Svc\n{\n"
            "    public void Raise() => InvalidOperationException(\"x\");\n"
            "}\n"
        ),
    }
    cards = [
        _card(1, [], ["src/Other.cs"], "Throw `InvalidOperationException` when the state is empty."),
        _card(2, ["src/Svc.cs"], [], "Nothing else."),
    ]
    _assert_no_findings(_run_findings(files, cards))
    print("PASS: test_framework_exception_in_member_shaped_line_not_flagged")


def test_framework_name_declared_as_repo_class_still_flagged() -> None:
    files = {
        "src/Other.cs": "namespace Demo;\npublic class Other { }\n",
        "src/Errors.cs": "namespace Demo;\npublic class InvalidOperationException { }\n",
    }
    cards = [
        _card(1, [], ["src/Other.cs"], "Throw `InvalidOperationException` when the state is empty."),
        _card(2, ["src/Errors.cs"], [], "Nothing else."),
    ]
    findings = _run_findings(files, cards)
    if len(findings) != 1 or "src/Errors.cs" not in findings[0]["message"]:
        raise AssertionError(f"expected one finding naming src/Errors.cs, got {findings}")
    print("PASS: test_framework_name_declared_as_repo_class_still_flagged")


def test_framework_qualified_members_not_flagged() -> None:
    files = {
        "src/Other.cs": "namespace Demo;\npublic class Other { }\n",
        "src/Helpers.cs": (
            "namespace Demo;\n"
            "public class Helpers\n{\n"
            "    public string Combine(string a) { return a; }\n"
            "    public int Max(int a) { return a; }\n"
            "}\n"
        ),
    }
    cards = [
        _card(1, [], ["src/Other.cs"], "Join with `Path.Combine` and clamp with `Math.Max`."),
        _card(2, ["src/Helpers.cs"], [], "Nothing else."),
    ]
    _assert_no_findings(_run_findings(files, cards))
    print("PASS: test_framework_qualified_members_not_flagged")


_PARTICIPANT_WITHOUT_REPLACE = "namespace Demo;\npublic class HydraulicsParticipant\n{\n}\n"
_PARTICIPANT_WITH_REPLACE = (
    "namespace Demo;\npublic class HydraulicsParticipant\n{\n"
    "    public void Replace(int x) { }\n}\n"
)
_REPLACE_ELSEWHERE = "namespace Demo;\npublic class Swapper\n{\n    public void Replace(int x) { }\n}\n"
_REPLACE_REQUIREMENT = "Call `HydraulicsParticipant.Replace` from the loop."


def test_type_member_not_yet_declared_in_edits_file_not_flagged() -> None:
    files = {
        "src/HydraulicsParticipant.cs": _PARTICIPANT_WITHOUT_REPLACE,
        "src/Swapper.cs": _REPLACE_ELSEWHERE,
    }
    cards = [
        _card(1, [], ["src/HydraulicsParticipant.cs"], _REPLACE_REQUIREMENT),
        _card(2, ["src/Swapper.cs"], [], "Nothing else."),
    ]
    _assert_no_findings(_run_findings(files, cards))
    print("PASS: test_type_member_not_yet_declared_in_edits_file_not_flagged")


def test_type_member_declared_in_edits_file_not_flagged() -> None:
    files = {
        "src/HydraulicsParticipant.cs": _PARTICIPANT_WITH_REPLACE,
        "src/Swapper.cs": _REPLACE_ELSEWHERE,
    }
    cards = [
        _card(1, [], ["src/HydraulicsParticipant.cs"], _REPLACE_REQUIREMENT),
        _card(2, ["src/Swapper.cs"], [], "Nothing else."),
    ]
    _assert_no_findings(_run_findings(files, cards))
    print("PASS: test_type_member_declared_in_edits_file_not_flagged")


def test_type_member_class_file_outside_own_refs_flagged_once() -> None:
    files = {
        "src/Other.cs": "namespace Demo;\npublic class Other { }\n",
        "src/HydraulicsParticipant.cs": _PARTICIPANT_WITH_REPLACE,
        "src/Swapper.cs": _REPLACE_ELSEWHERE,
    }
    cards = [
        _card(1, [], ["src/Other.cs"], _REPLACE_REQUIREMENT),
        _card(2, ["src/HydraulicsParticipant.cs", "src/Swapper.cs"], [], "Nothing else."),
    ]
    findings = _run_findings(files, cards)
    if len(findings) != 1:
        raise AssertionError(f"expected exactly one finding, got {findings}")
    message = findings[0]["message"]
    if "src/HydraulicsParticipant.cs" not in message or "which resolves to '" not in message:
        raise AssertionError(f"finding does not resolve to the class file: {message}")
    print("PASS: test_type_member_class_file_outside_own_refs_flagged_once")


def test_type_member_absent_from_class_file_not_flagged() -> None:
    files = {
        "src/Other.cs": "namespace Demo;\npublic class Other { }\n",
        "src/HydraulicsParticipant.cs": _PARTICIPANT_WITHOUT_REPLACE,
        "src/Swapper.cs": _REPLACE_ELSEWHERE,
    }
    cards = [
        _card(1, [], ["src/Other.cs"], _REPLACE_REQUIREMENT),
        _card(2, ["src/HydraulicsParticipant.cs", "src/Swapper.cs"], [], "Nothing else."),
    ]
    _assert_no_findings(_run_findings(files, cards))
    print("PASS: test_type_member_absent_from_class_file_not_flagged")


def test_duplicate_type_falls_through_to_qualifier_filtering() -> None:
    files = {
        "src/Other.cs": "namespace Demo;\npublic class Other { }\n",
        "src/a/Widget.cs": (
            "namespace Alpha;\npublic class Widget\n{\n    public void Run() { }\n}\n"
        ),
        "src/b/Widget.cs": (
            "namespace Beta;\npublic class Widget\n{\n    public void Run() { }\n}\n"
        ),
    }
    cards = [
        _card(1, [], ["src/Other.cs"], "Invoke `Widget.Run` on each item."),
        _card(2, ["src/a/Widget.cs", "src/b/Widget.cs"], [], "Nothing else."),
    ]
    _assert_no_findings(_run_findings(files, cards))
    print("PASS: test_duplicate_type_falls_through_to_qualifier_filtering")


def test_lowercase_go_package_qualifier_still_narrows() -> None:
    files = {
        "src/Other.cs": "namespace Demo;\npublic class Other { }\n",
        "src/reedengine/engine.go": "package reedengine\n\nfunc New() int { return 1 }\n",
        "src/other/engine.go": "package other\n\nfunc New() int { return 2 }\n",
    }
    cards = [
        _card(1, [], ["src/Other.cs"], "Construct via `reedengine.New` at startup."),
        _card(2, ["src/reedengine/engine.go", "src/other/engine.go"], [], "Nothing else."),
    ]
    findings = _run_findings(files, cards)
    if len(findings) != 1 or "src/reedengine/engine.go" not in findings[0]["message"]:
        raise AssertionError(f"expected one finding naming src/reedengine/engine.go, got {findings}")
    print("PASS: test_lowercase_go_package_qualifier_still_narrows")


def main() -> int:
    failures = 0
    for name, function in sorted(globals().items()):
        if name.startswith("test_") and callable(function):
            try:
                function()
            except AssertionError:
                failures += 1
                print(f"FAIL: {name}", file=sys.stderr)
                traceback.print_exc()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
