"""Unit tests for _sandbox_report.read()."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _sandbox_report  # noqa: E402


def _write_fixture(directory: Path, name: str, content) -> Path:
    """Write ``content`` as JSON (or raw text, if ``content`` is a str) to ``directory / name``."""
    fixture_path = directory / name
    if isinstance(content, str):
        fixture_path.write_text(content, encoding="utf-8")
    else:
        with fixture_path.open("w", encoding="utf-8") as f:
            json.dump(content, f)
    return fixture_path


def main() -> int:
    errors = 0

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        # 1. Valid file with two well-formed items and an explicit meta value.
        _valid = {
            "source": "sandbox-report",
            "meta": {"suite": "loomyard-sandbox"},
            "items": [
                {"ref": "S6", "title": "Verdict S6", "body": "FAIL: repro steps for S6"},
                {"ref": "S7", "title": "Verdict S7", "body": "PASS: nothing to report"},
            ],
        }
        _path = _write_fixture(tmp_dir, "valid.json", _valid)
        _result = _sandbox_report.read(_path)
        if _result["ref_prefix"] != "":
            print(f"FAIL: read/valid — expected ref_prefix '', got {_result['ref_prefix']!r}", file=sys.stderr)
            errors += 1
        elif _result["detail_hint"] is not None:
            print(f"FAIL: read/valid — expected detail_hint None, got {_result['detail_hint']!r}", file=sys.stderr)
            errors += 1
        elif _result["embed_body"] is not True:
            print(f"FAIL: read/valid — expected embed_body True, got {_result['embed_body']!r}", file=sys.stderr)
            errors += 1
        elif _result["items"] != [
            {"ref": "S6", "title": "Verdict S6", "body": "FAIL: repro steps for S6"},
            {"ref": "S7", "title": "Verdict S7", "body": "PASS: nothing to report"},
        ]:
            print(f"FAIL: read/valid — items mapped incorrectly: {_result['items']!r}", file=sys.stderr)
            errors += 1
        elif _result["meta"] != {"suite": "loomyard-sandbox"}:
            print(f"FAIL: read/valid — expected meta passthrough, got {_result['meta']!r}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: read/valid — two items map correctly, ref_prefix/detail_hint/embed_body/meta correct")

        # 2. Valid file where the meta key is entirely absent -> returned meta == {}.
        _no_meta = {
            "source": "sandbox-report",
            "items": [{"ref": "S1", "title": "T1", "body": "B1"}],
        }
        _path = _write_fixture(tmp_dir, "no-meta.json", _no_meta)
        _result = _sandbox_report.read(_path)
        if _result["meta"] != {}:
            print(f"FAIL: read/no-meta — expected meta {{}}, got {_result['meta']!r}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: read/no-meta — meta defaults to {} when absent")

        # 3. Valid file with items: [] -> returns successfully with items == [].
        _empty_items = {"source": "sandbox-report", "items": []}
        _path = _write_fixture(tmp_dir, "empty-items.json", _empty_items)
        _result = _sandbox_report.read(_path)
        if _result["items"] != []:
            print(f"FAIL: read/empty-items — expected items [], got {_result['items']!r}", file=sys.stderr)
            errors += 1
        else:
            print("PASS: read/empty-items — empty items array accepted without error")

        # 4. An item missing ref (or title, or body) -> raises SandboxReportError.
        for _missing_field in ("ref", "title", "body"):
            _item = {"ref": "S1", "title": "T1", "body": "B1"}
            del _item[_missing_field]
            _missing = {"source": "sandbox-report", "items": [_item]}
            _path = _write_fixture(tmp_dir, f"missing-{_missing_field}.json", _missing)
            try:
                _sandbox_report.read(_path)
                print(f"FAIL: read/missing-{_missing_field} — expected SandboxReportError, none raised", file=sys.stderr)
                errors += 1
            except _sandbox_report.SandboxReportError:
                print(f"PASS: read/missing-{_missing_field} — SandboxReportError raised")

        # 5a. source set to something other than "sandbox-report" -> raises.
        _wrong_source = {"source": "ghissues", "items": []}
        _path = _write_fixture(tmp_dir, "wrong-source.json", _wrong_source)
        try:
            _sandbox_report.read(_path)
            print("FAIL: read/wrong-source — expected SandboxReportError, none raised", file=sys.stderr)
            errors += 1
        except _sandbox_report.SandboxReportError:
            print("PASS: read/wrong-source — SandboxReportError raised")

        # 5b. source missing entirely -> raises.
        _missing_source = {"items": []}
        _path = _write_fixture(tmp_dir, "missing-source.json", _missing_source)
        try:
            _sandbox_report.read(_path)
            print("FAIL: read/missing-source — expected SandboxReportError, none raised", file=sys.stderr)
            errors += 1
        except _sandbox_report.SandboxReportError:
            print("PASS: read/missing-source — SandboxReportError raised")

        # 6. Two items sharing the same ref -> raises, naming that ref.
        _dup_ref = {
            "source": "sandbox-report",
            "items": [
                {"ref": "S1", "title": "T1", "body": "B1"},
                {"ref": "S1", "title": "T2", "body": "B2"},
            ],
        }
        _path = _write_fixture(tmp_dir, "dup-ref.json", _dup_ref)
        try:
            _sandbox_report.read(_path)
            print("FAIL: read/dup-ref — expected SandboxReportError, none raised", file=sys.stderr)
            errors += 1
        except _sandbox_report.SandboxReportError as exc:
            if "S1" not in str(exc):
                print(f"FAIL: read/dup-ref — error does not name duplicate ref 'S1': {exc}", file=sys.stderr)
                errors += 1
            else:
                print("PASS: read/dup-ref — SandboxReportError raised naming the duplicate ref")

        # 7. A file containing invalid JSON syntax -> raises SandboxReportError.
        _path = _write_fixture(tmp_dir, "invalid-json.json", "{not valid json")
        try:
            _sandbox_report.read(_path)
            print("FAIL: read/invalid-json — expected SandboxReportError, none raised", file=sys.stderr)
            errors += 1
        except _sandbox_report.SandboxReportError:
            print("PASS: read/invalid-json — SandboxReportError raised")

        # 8. A file whose top-level parsed JSON value is not an object -> raises SandboxReportError, not an uncaught AttributeError.
        for _name, _bad_top_level in (("top-level-array.json", [1, 2, 3]), ("top-level-string.json", "hello")):
            _path = _write_fixture(tmp_dir, _name, _bad_top_level)
            try:
                _sandbox_report.read(_path)
                print(f"FAIL: read/{_name} — expected SandboxReportError, none raised", file=sys.stderr)
                errors += 1
            except _sandbox_report.SandboxReportError:
                print(f"PASS: read/{_name} — SandboxReportError raised for non-object top level")
            except AttributeError:
                print(f"FAIL: read/{_name} — raised uncaught AttributeError instead of SandboxReportError", file=sys.stderr)
                errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All sandbox-report unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
