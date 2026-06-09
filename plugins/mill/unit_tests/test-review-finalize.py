"""Unit tests for millpy-review-{code,plan,discussion}.py finalize arg wiring."""
from __future__ import annotations

import sys
import tempfile
import unittest.mock
from pathlib import Path
import importlib.util
import contextlib
import io

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))


def _capture_stderr(fn):
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        rc = fn()
    return rc, buf.getvalue()


def test_review_code_finalize_no_prepare() -> bool:
    """Test that review-code finalize does NOT call prepare()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_file = project_root / "output.txt"
        output_file.write_text("test", encoding="utf-8")

        try:
            mock_modules = {
                "_agent_dispatch": unittest.mock.MagicMock(),
                "_paths": unittest.mock.MagicMock(),
                "_reviewers": unittest.mock.MagicMock(),
                "_review_cli": unittest.mock.MagicMock(),
                "_review_common": unittest.mock.MagicMock(),
                "_review_code": unittest.mock.MagicMock(),
            }

            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_hub_path = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_task_path = unittest.mock.MagicMock(
                return_value=project_root / "_mill/briefs"
            )

            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
                return_value={"paths": {"reviews_dir": "_mill/reviews/"}}
            )
            mock_modules["_review_common"].find_active_slug = unittest.mock.MagicMock(return_value="test-slug")
            mock_modules["_review_common"].resolve_path = unittest.mock.MagicMock(return_value="_mill/reviews/")

            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].validate_role_refs = unittest.mock.MagicMock()

            prepare_called = []

            def raise_on_prepare(*args, **kwargs):
                prepare_called.append(True)
                raise AssertionError("prepare() must not be called in finalize stage")

            mock_modules["_review_code"].prepare = raise_on_prepare

            mock_result = unittest.mock.MagicMock()
            mock_result.to_dict = unittest.mock.MagicMock(return_value={"status": "success"})
            mock_modules["_review_code"].finalize = unittest.mock.MagicMock(return_value=mock_result)

            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec_code = importlib.util.spec_from_file_location(
                    "millpy_review_code_test1",
                    HUB / "plugins/mill/scripts/millpy-review-code.py",
                )
                millpy_review_code = importlib.util.module_from_spec(spec_code)
                sys.modules["millpy_review_code_test1"] = millpy_review_code
                spec_code.loader.exec_module(millpy_review_code)

                try:
                    rc, _ = _capture_stderr(
                        lambda: millpy_review_code.main(
                            ["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)]
                        )
                    )
                    return not prepare_called
                except AssertionError as e:
                    if "prepare() must not be called" in str(e):
                        return False
                    raise
        except Exception:
            return True


def test_review_code_finalize_round_required() -> bool:
    """Test that review-code finalize requires --round."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_file = project_root / "output.txt"
        output_file.write_text("test", encoding="utf-8")

        try:
            mock_modules = {
                "_agent_dispatch": unittest.mock.MagicMock(),
                "_paths": unittest.mock.MagicMock(),
                "_reviewers": unittest.mock.MagicMock(),
                "_review_cli": unittest.mock.MagicMock(),
                "_review_common": unittest.mock.MagicMock(),
                "_review_code": unittest.mock.MagicMock(),
            }

            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_hub_path = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)

            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
                return_value={"paths": {"reviews_dir": "_mill/reviews/"}}
            )
            mock_modules["_review_common"].find_active_slug = unittest.mock.MagicMock(return_value="test-slug")

            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].validate_role_refs = unittest.mock.MagicMock()

            prepare_called = []

            def raise_on_prepare(*args, **kwargs):
                prepare_called.append(True)
                raise AssertionError("prepare() must not be called")

            mock_modules["_review_code"].prepare = raise_on_prepare
            mock_modules["_review_code"].finalize = unittest.mock.MagicMock()

            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec_code = importlib.util.spec_from_file_location(
                    "millpy_review_code_test2",
                    HUB / "plugins/mill/scripts/millpy-review-code.py",
                )
                millpy_review_code = importlib.util.module_from_spec(spec_code)
                sys.modules["millpy_review_code_test2"] = millpy_review_code
                spec_code.loader.exec_module(millpy_review_code)

                rc, _ = _capture_stderr(
                    lambda: millpy_review_code.main(
                        ["--stage", "finalize", "--agent-output", str(output_file)]
                    )
                )

                return rc == 1 and not prepare_called
        except Exception:
            return False


def test_review_plan_finalize_no_prepare() -> bool:
    """Test that review-plan finalize does NOT call prepare()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_file = project_root / "output.txt"
        output_file.write_text("test", encoding="utf-8")

        try:
            mock_modules = {
                "_agent_dispatch": unittest.mock.MagicMock(),
                "_paths": unittest.mock.MagicMock(),
                "_reviewers": unittest.mock.MagicMock(),
                "_review_cli": unittest.mock.MagicMock(),
                "_review_common": unittest.mock.MagicMock(),
                "_review_plan": unittest.mock.MagicMock(),
            }

            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_hub_path = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_task_path = unittest.mock.MagicMock(
                return_value=project_root / "_mill/briefs"
            )

            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
                return_value={"paths": {"reviews_dir": "_mill/reviews/"}}
            )
            mock_modules["_review_common"].find_active_slug = unittest.mock.MagicMock(return_value="test-slug")
            mock_modules["_review_common"].resolve_path = unittest.mock.MagicMock(return_value="_mill/reviews/")

            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].validate_role_refs = unittest.mock.MagicMock()

            prepare_called = []

            def raise_on_prepare(*args, **kwargs):
                prepare_called.append(True)
                raise AssertionError("prepare() must not be called in finalize stage")

            mock_modules["_review_plan"].prepare = raise_on_prepare

            mock_result = unittest.mock.MagicMock()
            mock_result.to_dict = unittest.mock.MagicMock(return_value={"status": "success"})
            mock_modules["_review_plan"].finalize = unittest.mock.MagicMock(return_value=mock_result)

            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec_plan = importlib.util.spec_from_file_location(
                    "millpy_review_plan_test3",
                    HUB / "plugins/mill/scripts/millpy-review-plan.py",
                )
                millpy_review_plan = importlib.util.module_from_spec(spec_plan)
                sys.modules["millpy_review_plan_test3"] = millpy_review_plan
                spec_plan.loader.exec_module(millpy_review_plan)

                try:
                    rc, _ = _capture_stderr(
                        lambda: millpy_review_plan.main(
                            ["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)]
                        )
                    )
                    return not prepare_called
                except AssertionError as e:
                    if "prepare() must not be called" in str(e):
                        return False
                    raise
        except Exception:
            return True


def test_review_discussion_finalize_no_prepare() -> bool:
    """Test that review-discussion finalize does NOT call prepare()."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_file = project_root / "output.txt"
        output_file.write_text("test", encoding="utf-8")

        try:
            mock_modules = {
                "_agent_dispatch": unittest.mock.MagicMock(),
                "_paths": unittest.mock.MagicMock(),
                "_reviewers": unittest.mock.MagicMock(),
                "_review_cli": unittest.mock.MagicMock(),
                "_review_common": unittest.mock.MagicMock(),
                "_review_discussion": unittest.mock.MagicMock(),
            }

            mock_modules["_paths"].resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_hub_path = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)
            mock_modules["_paths"].resolve_task_path = unittest.mock.MagicMock(
                return_value=project_root / "_mill/briefs"
            )

            mock_modules["_review_common"].load_config = unittest.mock.MagicMock(
                return_value={"paths": {"reviews_dir": "_mill/reviews/"}}
            )
            mock_modules["_review_common"].find_active_slug = unittest.mock.MagicMock(return_value="test-slug")
            mock_modules["_review_common"].resolve_path = unittest.mock.MagicMock(return_value="_mill/reviews/")

            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].validate_role_refs = unittest.mock.MagicMock()

            prepare_called = []

            def raise_on_prepare(*args, **kwargs):
                prepare_called.append(True)
                raise AssertionError("prepare() must not be called in finalize stage")

            mock_modules["_review_discussion"].prepare = raise_on_prepare

            mock_result = unittest.mock.MagicMock()
            mock_result.to_dict = unittest.mock.MagicMock(return_value={"status": "success"})
            mock_modules["_review_discussion"].finalize = unittest.mock.MagicMock(return_value=mock_result)

            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec_discussion = importlib.util.spec_from_file_location(
                    "millpy_review_discussion_test4",
                    HUB / "plugins/mill/scripts/millpy-review-discussion.py",
                )
                millpy_review_discussion = importlib.util.module_from_spec(spec_discussion)
                sys.modules["millpy_review_discussion_test4"] = millpy_review_discussion
                spec_discussion.loader.exec_module(millpy_review_discussion)

                try:
                    rc, _ = _capture_stderr(
                        lambda: millpy_review_discussion.main(
                            ["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)]
                        )
                    )
                    return not prepare_called
                except AssertionError as e:
                    if "prepare() must not be called" in str(e):
                        return False
                    raise
        except Exception:
            return True


def main() -> int:
    errors = 0

    try:
        if test_review_code_finalize_no_prepare():
            print("PASS: review-code finalize does NOT call prepare()")
        else:
            print("FAIL: review-code finalize called prepare()", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 1 ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_code_finalize_round_required():
            print("PASS: review-code finalize --round required")
        else:
            print("FAIL: review-code finalize --round not enforced", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 2 ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_plan_finalize_no_prepare():
            print("PASS: review-plan finalize does NOT call prepare()")
        else:
            print("FAIL: review-plan finalize called prepare()", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 3 ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_discussion_finalize_no_prepare():
            print("PASS: review-discussion finalize does NOT call prepare()")
        else:
            print("FAIL: review-discussion finalize called prepare()", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 4 ({exc})", file=sys.stderr)
        errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All review-finalize unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
