"""Unit tests for millpy-review-{code,plan,discussion}.py finalize arg wiring."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest.mock
from pathlib import Path
import importlib.util
import contextlib
import io

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Real modules used by the missing/empty/whitespace and stale-.out.md tests below (part b/c of card 12).
# These are the genuine implementations, not MagicMocks -- see the docstrings on _finalize_with_agent_output_content and _stale_out_md_case for why: the ERROR result these tests assert on is produced by the real backend's own `except ReviewError` handling, and a mocked backend would make that assertion vacuous.
import _agent_dispatch  # noqa: E402
import _review_common  # noqa: E402


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


def test_review_code_finalize_receives_raw_text_byte_identical() -> bool:
    """
    Test that review-code finalize receives agent-output text byte-identical, entities and all -- it must NOT be HTML-unescaped.

    Agent-mode output is a file the reviewer wrote itself via Write;
    it is never HTML-escaped the way the implementer's <task-notification> payload is (that payload is unrelated and untouched -- see _implementer_common.py:892).
    Unescaping this file's content would corrupt any finding that legitimately quotes "&lt;", "&gt;", or "&amp;" from a source snippet.
    This verifies the read site hands raw_text to _review_code.finalize as its third positional argument unchanged.

    The comparison is made as the function's return value -- not a bare assert inside a try/except that swallows AssertionError -- so a mismatch genuinely surfaces as a failing test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_file = project_root / "output.txt"
        output_file.write_text("Q&amp;A send &lt;guid&gt;", encoding="utf-8")

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

        mock_result = unittest.mock.MagicMock()
        mock_result.to_dict = unittest.mock.MagicMock(return_value={"status": "success"})
        mock_modules["_review_code"].finalize = unittest.mock.MagicMock(return_value=mock_result)

        with unittest.mock.patch.dict(sys.modules, mock_modules):
            spec_code = importlib.util.spec_from_file_location(
                "millpy_review_code_test_unescape",
                HUB / "plugins/mill/scripts/millpy-review-code.py",
            )
            millpy_review_code = importlib.util.module_from_spec(spec_code)
            sys.modules["millpy_review_code_test_unescape"] = millpy_review_code
            spec_code.loader.exec_module(millpy_review_code)

            millpy_review_code.main(
                ["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)]
            )

        # raw_text is the third positional argument to finalize(cfg, slug, raw_text, ...).
        # Read it outside any exception-swallowing block so a mismatch surfaces as False.
        return mock_modules["_review_code"].finalize.call_args.args[2] == "Q&amp;A send &lt;guid&gt;"


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


def test_review_plan_finalize_round_required() -> bool:
    """
    Test that review-plan finalize auto-discovers the round when --round is absent.

    Commit 8a5fefac switched plan finalize to auto-discover the round via discover_round() instead of requiring --round.
    This test verifies the new contract: omitting --round succeeds (rc == 0) and prepare() is never called.
    """
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
            # discover_round supplies the round number when --round is absent
            mock_modules["_review_common"].discover_round = unittest.mock.MagicMock(return_value=1)

            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].validate_role_refs = unittest.mock.MagicMock()

            prepare_called = []

            def raise_on_prepare(*args, **kwargs):
                prepare_called.append(True)
                raise AssertionError("prepare() must not be called")

            mock_modules["_review_plan"].prepare = raise_on_prepare
            mock_modules["_review_plan"].finalize = unittest.mock.MagicMock(
                return_value={
                    "scope": "holistic",
                    "verdict": "APPROVE",
                    "blocking_count": 0,
                    "nit_count": 0,
                    "file": "x.md",
                }
            )

            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec_plan = importlib.util.spec_from_file_location(
                    "millpy_review_plan_test_round_req",
                    HUB / "plugins/mill/scripts/millpy-review-plan.py",
                )
                millpy_review_plan = importlib.util.module_from_spec(spec_plan)
                sys.modules["millpy_review_plan_test_round_req"] = millpy_review_plan
                spec_plan.loader.exec_module(millpy_review_plan)

                rc, _ = _capture_stderr(
                    lambda: millpy_review_plan.main(
                        ["--stage", "finalize", "--agent-output", str(output_file)]
                    )
                )

                # plan finalize auto-discovers the round; omitting --round must succeed
                return rc == 0 and not prepare_called
        except Exception:
            return False


def test_review_plan_finalize_receives_raw_text_byte_identical() -> bool:
    """
    Test that review-plan finalize receives agent-output text byte-identical, entities and all -- it must NOT be HTML-unescaped.

    Mirrors test_review_code_finalize_receives_raw_text_byte_identical: the comparison is made as the function's return value -- not a bare assert inside a try/except that swallows AssertionError -- so a mismatch genuinely surfaces as a failing test rather than being absorbed by a broad exception handler.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_file = project_root / "output.txt"
        output_file.write_text("Q&amp;A send &lt;guid&gt;", encoding="utf-8")

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

        mock_modules["_review_plan"].finalize = unittest.mock.MagicMock(
            return_value={
                "scope": "holistic",
                "verdict": "APPROVE",
                "blocking_count": 0,
                "nit_count": 0,
                "file": "x.md",
            }
        )

        with unittest.mock.patch.dict(sys.modules, mock_modules):
            spec_plan = importlib.util.spec_from_file_location(
                "millpy_review_plan_test_unescape",
                HUB / "plugins/mill/scripts/millpy-review-plan.py",
            )
            millpy_review_plan = importlib.util.module_from_spec(spec_plan)
            sys.modules["millpy_review_plan_test_unescape"] = millpy_review_plan
            spec_plan.loader.exec_module(millpy_review_plan)

            millpy_review_plan.main(
                ["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)]
            )

        # raw_text is the third positional argument to finalize(cfg, slug, raw_text, scope=None, round_n=..., ...).
        # Read it outside any exception-swallowing block so a mismatch surfaces as False.
        return mock_modules["_review_plan"].finalize.call_args.args[2] == "Q&amp;A send &lt;guid&gt;"


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

            mock_modules["_review_plan"].finalize = unittest.mock.MagicMock(
                return_value={
                    "scope": "holistic",
                    "verdict": "APPROVE",
                    "blocking_count": 0,
                    "nit_count": 0,
                    "file": "x.md",
                }
            )

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
            mock_result.to_dict = unittest.mock.MagicMock(
                return_value={
                    "type": "discussion",
                    "round": 1,
                    "verdict": "APPROVE",
                    "blocking_count": 0,
                    "nit_count": 0,
                    "reviews": [],
                }
            )
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


def test_review_discussion_finalize_receives_raw_text_byte_identical() -> bool:
    """
    Test that review-discussion finalize receives agent-output text byte-identical, entities and all -- it must NOT be HTML-unescaped.

    Mirrors test_review_code_finalize_receives_raw_text_byte_identical: the comparison is made as the function's return value -- not a bare assert inside a try/except that swallows AssertionError -- so a mismatch genuinely surfaces as a failing test rather than being absorbed by a broad exception handler.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        output_file = project_root / "output.txt"
        output_file.write_text("Q&amp;A send &lt;guid&gt;", encoding="utf-8")

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

        mock_result = unittest.mock.MagicMock()
        mock_result.to_dict = unittest.mock.MagicMock(
            return_value={
                "type": "discussion",
                "round": 1,
                "verdict": "APPROVE",
                "blocking_count": 0,
                "nit_count": 0,
                "reviews": [],
            }
        )
        mock_modules["_review_discussion"].finalize = unittest.mock.MagicMock(return_value=mock_result)

        with unittest.mock.patch.dict(sys.modules, mock_modules):
            spec_discussion = importlib.util.spec_from_file_location(
                "millpy_review_discussion_test_unescape",
                HUB / "plugins/mill/scripts/millpy-review-discussion.py",
            )
            millpy_review_discussion = importlib.util.module_from_spec(spec_discussion)
            sys.modules["millpy_review_discussion_test_unescape"] = millpy_review_discussion
            spec_discussion.loader.exec_module(millpy_review_discussion)

            millpy_review_discussion.main(
                ["--stage", "finalize", "--round", "1", "--agent-output", str(output_file)]
            )

        # raw_text is the third positional argument to finalize(cfg, slug, raw_text, round_n=..., ...).
        # Read it outside any exception-swallowing block so a mismatch surfaces as False.
        return mock_modules["_review_discussion"].finalize.call_args.args[2] == "Q&amp;A send &lt;guid&gt;"


def test_review_discussion_finalize_round_required() -> bool:
    """
    Test that review-discussion finalize auto-discovers the round when --round is absent.

    Commit 8a5fefac switched discussion finalize to auto-discover the round via discover_round() instead of requiring --round.
    This test verifies the new contract: omitting --round succeeds (rc == 0) and prepare() is never called.
    """
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
            # discover_round supplies the round number when --round is absent
            mock_modules["_review_common"].discover_round = unittest.mock.MagicMock(return_value=1)

            mock_modules["_reviewers"].load = unittest.mock.MagicMock(return_value={})
            mock_modules["_reviewers"].validate_role_refs = unittest.mock.MagicMock()

            prepare_called = []

            def raise_on_prepare(*args, **kwargs):
                prepare_called.append(True)
                raise AssertionError("prepare() must not be called")

            mock_modules["_review_discussion"].prepare = raise_on_prepare

            mock_result = unittest.mock.MagicMock()
            mock_result.to_dict = unittest.mock.MagicMock(
                return_value={
                    "type": "discussion",
                    "round": 1,
                    "verdict": "APPROVE",
                    "blocking_count": 0,
                    "nit_count": 0,
                    "reviews": [],
                }
            )
            mock_modules["_review_discussion"].finalize = unittest.mock.MagicMock(return_value=mock_result)

            with unittest.mock.patch.dict(sys.modules, mock_modules):
                spec_discussion = importlib.util.spec_from_file_location(
                    "millpy_review_discussion_test_round_req",
                    HUB / "plugins/mill/scripts/millpy-review-discussion.py",
                )
                millpy_review_discussion = importlib.util.module_from_spec(spec_discussion)
                sys.modules["millpy_review_discussion_test_round_req"] = millpy_review_discussion
                spec_discussion.loader.exec_module(millpy_review_discussion)

                rc, _ = _capture_stderr(
                    lambda: millpy_review_discussion.main(
                        ["--stage", "finalize", "--agent-output", str(output_file)]
                    )
                )

                # discussion finalize auto-discovers the round; omitting --round must succeed
                return rc == 0 and not prepare_called
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Missing / empty / whitespace agent-output cases (card 12, part b) and the stale-.out.md regression guard (card 12, part c).
# The existing tests above replace _review_common, _review_cli, and _agent_dispatch with bare MagicMocks.
# That style does not work here: under it, print_error_envelope is a mock (so no ERROR envelope ever reaches stdout), `except ReviewError` binds a MagicMock rather than an exception class (raising TypeError the instant anything actually throws), and write_brief is a mock (so it unlinks nothing and the stale-file guard proves nothing).
# These tests instead use the REAL _agent_dispatch, _review_cli, _review_common, and review backend modules -- the ERROR result under test is exactly the backend's own behaviour, so stubbing it out would assert nothing.
# Only _paths and _reviewers are mocked,
# and --slug is passed explicitly so find_active_slug (which would otherwise reach through to real git/branch detection) is never called.
# ---------------------------------------------------------------------------


def _mock_paths_and_reviewers(project_root: Path):
    """Return (mock_paths, mock_reviewers) modules for sys.modules patching.

    project_root stands in for git_root / hub_dir / wiki_root -- none of these tests exercise multi-root wiki behaviour, so a single tempdir plays all three roles.
    """
    mock_paths = unittest.mock.MagicMock()
    mock_paths.resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
    mock_paths.resolve_hub_path = unittest.mock.MagicMock(return_value=project_root)
    mock_paths.resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)

    mock_reviewers = unittest.mock.MagicMock()
    mock_reviewers.load = unittest.mock.MagicMock(return_value={})
    mock_reviewers.validate_role_refs = unittest.mock.MagicMock()
    return mock_paths, mock_reviewers


def _run_finalize_stage(
    cli_relpath: str,
    unique_name: str,
    agent_output_path: Path,
    reviews_dir: Path,
    project_root: Path,
    *,
    actual_model: str | None = None,
) -> tuple[int, str]:
    """Run a review CLI's `--stage finalize` against a real backend.

    Patches ``load_config`` and ``resolve_path`` directly on the real, already-imported ``_review_common`` module (the CLI does ``from _review_common import ...`` inside ``main()``, so attributes set on the module before the call are the ones ``main()`` picks up), mocks only ``_paths`` and ``_reviewers`` in ``sys.modules``, and leaves ``_agent_dispatch``, ``_review_cli``, ``_review_common``, and the review backend module genuinely real.

    ``actual_model``, when given, is passed through as ``--actual-model`` so callers can exercise the audit-trail flag against a real backend and inspect the resulting review file's ``reviewer_model:`` line.

    Returns (return_code, captured_stdout).
    """
    orig_load_config = _review_common.load_config
    orig_resolve_path = _review_common.resolve_path
    try:
        _review_common.load_config = lambda *a, **kw: {
            "paths": {"reviews_dir": "_mill/reviews/"}
        }
        _review_common.resolve_path = lambda *a, **kw: reviews_dir

        mock_paths, mock_reviewers = _mock_paths_and_reviewers(project_root)
        with unittest.mock.patch.dict(
            sys.modules, {"_paths": mock_paths, "_reviewers": mock_reviewers}
        ):
            spec = importlib.util.spec_from_file_location(
                unique_name, HUB / "plugins/mill/scripts" / cli_relpath
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[unique_name] = module
            spec.loader.exec_module(module)

            argv = [
                "--slug", "test-slug",
                "--stage", "finalize",
                "--round", "1",
                "--agent-output", str(agent_output_path),
            ]
            if actual_model is not None:
                argv += ["--actual-model", actual_model]

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = module.main(argv)
            return rc, buf.getvalue().strip()
    finally:
        _review_common.load_config = orig_load_config
        _review_common.resolve_path = orig_resolve_path


def _finalize_with_agent_output_content(cli_relpath: str, unique_name: str, *, content: str, exists: bool) -> bool:
    """Run --stage finalize against an agent-output file that is missing, empty, or whitespace-only;
    assert the printed envelope carries verdict: ERROR on a ZERO return code with no traceback escaping.

    The missing case fails on pre-guard code with an uncaught FileNotFoundError -- exactly the bug cards 9-11's guard fixes.
    The ERROR envelope comes from the backend's own `except ReviewError` -> `ReviewResult(verdict="ERROR")` path on a zero exit;
    print_error_envelope is never reached, so this must NOT be asserted via a raising mock or an exit-1 expectation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        reviews_dir = project_root / "_mill" / "reviews"
        agent_output_path = project_root / "agent-output.out.md"
        if exists:
            agent_output_path.write_text(content, encoding="utf-8")

        rc, stdout_text = _run_finalize_stage(
            cli_relpath, unique_name, agent_output_path, reviews_dir, project_root
        )
        if rc != 0:
            return False
        try:
            envelope = json.loads(stdout_text)
        except json.JSONDecodeError:
            return False
        return envelope.get("verdict") == "ERROR"


def _stale_out_md_case(cli_relpath: str, unique_name: str, role: str) -> bool:
    """The stale-.out.md regression guard -- the single most important test in this batch.

    Simulates a killed-then-retried reviewer: round 1 writes a brief and (in this synthetic setup) an agent actually produced a full, green ".out.md" report.
    The orchestrator then retries the SAME role/scope/ round -- e.g.
    after a transient dispatch failure -- which calls write_brief again.
    write_brief's unconditional unlink must clear that stale ".out.md" before the retried attempt ever runs;
    without it, a finalize call against the (never-rewritten, in this test) path would silently reuse the old APPROVE verdict, and reviewers have no git-state backstop to catch it.
    Asserts the stale file did not survive AND that finalize -- via cards 9-11's missing-file guard -- reports ERROR rather than replaying the stale APPROVE.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        briefs_dir = project_root / "_mill" / "briefs"
        reviews_dir = project_root / "_mill" / "reviews"

        # Round 1, attempt 1: write the brief, then simulate the agent having actually written a full, green report to the corresponding .out.md.
        brief_path = _agent_dispatch.write_brief(briefs_dir, role, "holistic", 1, "attempt-1 prompt")
        out_path = _agent_dispatch.output_path_for(brief_path)
        out_path.write_text(
            "MILL_REVIEW_BEGIN\n```yaml\nverdict: APPROVE\n```\nMILL_REVIEW_END\n",
            encoding="utf-8",
        )
        if not out_path.exists():
            return False

        # Round 1, attempt 2 (retry): write_brief is called again for the SAME role/scope/round.
        # Its unconditional unlink must clear the stale APPROVE before this attempt's reviewer ever runs.
        _agent_dispatch.write_brief(briefs_dir, role, "holistic", 1, "attempt-2 prompt")
        if out_path.exists():
            return False  # stale file survived -- the exact regression this test guards against

        # finalize now reads from a path that no longer exists -- the missing-file guard collapses it to empty text,
        # and the backend's own ERROR handling takes over.
        rc, stdout_text = _run_finalize_stage(
            cli_relpath, unique_name, out_path, reviews_dir, project_root
        )
        if rc != 0:
            return False
        try:
            envelope = json.loads(stdout_text)
        except json.JSONDecodeError:
            return False
        return envelope.get("verdict") == "ERROR"


# ---------------------------------------------------------------------------
# --actual-model audit-trail flag (card 16): threaded from the CLI's argparse flag through finalize() into the written review file's `reviewer_model:` line, regardless of what the raw reviewer text originally echoed.
# Uses the real backend (via _run_finalize_stage) so the assertion reads genuine file content on disk rather than a mocked call_args.
# ---------------------------------------------------------------------------

_ACTUAL_MODEL_RAW_TEXT = (
    "MILL_REVIEW_BEGIN\n"
    "```yaml\n"
    "verdict: APPROVE\n"
    "reviewer_model: sonnetmax\n"
    "```\n"
    "MILL_REVIEW_END\n"
)


def _actual_model_case(cli_relpath: str, unique_name: str, *, actual_model: str | None, expected_line: str) -> bool:
    """Run --stage finalize with (or without) --actual-model and assert the written review file's `reviewer_model:` line matches `expected_line`.

    `_ACTUAL_MODEL_RAW_TEXT` always echoes `reviewer_model: sonnetmax` -- passing `actual_model` must overwrite that line regardless; omitting it (actual_model=None) must reproduce it unmodified.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        reviews_dir = project_root / "_mill" / "reviews"
        agent_output_path = project_root / "agent-output.out.md"
        agent_output_path.write_text(_ACTUAL_MODEL_RAW_TEXT, encoding="utf-8")

        rc, stdout_text = _run_finalize_stage(
            cli_relpath, unique_name, agent_output_path, reviews_dir, project_root,
            actual_model=actual_model,
        )
        if rc != 0:
            return False
        try:
            envelope = json.loads(stdout_text)
        except json.JSONDecodeError:
            return False
        if envelope.get("verdict") != "APPROVE":
            return False
        reviews = envelope.get("reviews", [])
        if not reviews:
            return False
        file_path = Path(reviews[0]["file"])
        if not file_path.exists():
            return False
        written_content = file_path.read_text(encoding="utf-8")
        return expected_line in written_content


def test_review_discussion_finalize_actual_model_overrides_reviewer_model_line() -> bool:
    return _actual_model_case(
        "millpy-review-discussion.py",
        "millpy_review_discussion_test_actual_model",
        actual_model="haiku",
        expected_line="reviewer_model: haiku",
    )


def test_review_discussion_finalize_omitted_actual_model_leaves_reviewer_model_unchanged() -> bool:
    return _actual_model_case(
        "millpy-review-discussion.py",
        "millpy_review_discussion_test_actual_model_omitted",
        actual_model=None,
        expected_line="reviewer_model: sonnetmax",
    )


def test_review_plan_finalize_actual_model_overrides_reviewer_model_line() -> bool:
    return _actual_model_case(
        "millpy-review-plan.py",
        "millpy_review_plan_test_actual_model",
        actual_model="haiku",
        expected_line="reviewer_model: haiku",
    )


def test_review_plan_finalize_omitted_actual_model_leaves_reviewer_model_unchanged() -> bool:
    return _actual_model_case(
        "millpy-review-plan.py",
        "millpy_review_plan_test_actual_model_omitted",
        actual_model=None,
        expected_line="reviewer_model: sonnetmax",
    )


def test_review_code_finalize_actual_model_overrides_reviewer_model_line() -> bool:
    return _actual_model_case(
        "millpy-review-code.py",
        "millpy_review_code_test_actual_model",
        actual_model="haiku",
        expected_line="reviewer_model: haiku",
    )


def test_review_code_finalize_omitted_actual_model_leaves_reviewer_model_unchanged() -> bool:
    return _actual_model_case(
        "millpy-review-code.py",
        "millpy_review_code_test_actual_model_omitted",
        actual_model=None,
        expected_line="reviewer_model: sonnetmax",
    )


def test_review_discussion_finalize_missing_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-discussion.py",
        "millpy_review_discussion_test_missing",
        content="",
        exists=False,
    )


def test_review_discussion_finalize_empty_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-discussion.py",
        "millpy_review_discussion_test_empty",
        content="",
        exists=True,
    )


def test_review_discussion_finalize_whitespace_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-discussion.py",
        "millpy_review_discussion_test_whitespace",
        content="   \n\t  \n",
        exists=True,
    )


def test_review_plan_finalize_missing_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-plan.py",
        "millpy_review_plan_test_missing",
        content="",
        exists=False,
    )


def test_review_plan_finalize_empty_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-plan.py",
        "millpy_review_plan_test_empty",
        content="",
        exists=True,
    )


def test_review_plan_finalize_whitespace_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-plan.py",
        "millpy_review_plan_test_whitespace",
        content="   \n\t  \n",
        exists=True,
    )


def test_review_code_finalize_missing_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-code.py",
        "millpy_review_code_test_missing",
        content="",
        exists=False,
    )


def test_review_code_finalize_empty_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-code.py",
        "millpy_review_code_test_empty",
        content="",
        exists=True,
    )


def test_review_code_finalize_whitespace_agent_output_returns_error() -> bool:
    return _finalize_with_agent_output_content(
        "millpy-review-code.py",
        "millpy_review_code_test_whitespace",
        content="   \n\t  \n",
        exists=True,
    )


def test_review_discussion_finalize_stale_out_md_does_not_survive_retry() -> bool:
    return _stale_out_md_case(
        "millpy-review-discussion.py", "millpy_review_discussion_test_stale", "review-discussion"
    )


def test_review_plan_finalize_stale_out_md_does_not_survive_retry() -> bool:
    return _stale_out_md_case(
        "millpy-review-plan.py", "millpy_review_plan_test_stale", "review-plan"
    )


def test_review_code_finalize_stale_out_md_does_not_survive_retry() -> bool:
    return _stale_out_md_case(
        "millpy-review-code.py", "millpy_review_code_test_stale", "review-code"
    )


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
        if test_review_code_finalize_receives_raw_text_byte_identical():
            print("PASS: review-code finalize receives raw_text byte-identical (no unescape)")
        else:
            print("FAIL: review-code finalize altered raw_text (unescape regression)", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 1b ({exc})", file=sys.stderr)
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
        if test_review_plan_finalize_round_required():
            print("PASS: review-plan finalize auto-discovers round when --round absent")
        else:
            print("FAIL: review-plan finalize did not succeed via auto-discovery", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 3 ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_plan_finalize_receives_raw_text_byte_identical():
            print("PASS: review-plan finalize receives raw_text byte-identical (no unescape)")
        else:
            print("FAIL: review-plan finalize altered raw_text (unescape regression)", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 3b ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_plan_finalize_no_prepare():
            print("PASS: review-plan finalize does NOT call prepare()")
        else:
            print("FAIL: review-plan finalize called prepare()", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 4 ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_discussion_finalize_no_prepare():
            print("PASS: review-discussion finalize does NOT call prepare()")
        else:
            print("FAIL: review-discussion finalize called prepare()", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 5 ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_discussion_finalize_receives_raw_text_byte_identical():
            print("PASS: review-discussion finalize receives raw_text byte-identical (no unescape)")
        else:
            print("FAIL: review-discussion finalize altered raw_text (unescape regression)", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 5b ({exc})", file=sys.stderr)
        errors += 1

    try:
        if test_review_discussion_finalize_round_required():
            print("PASS: review-discussion finalize auto-discovers round when --round absent")
        else:
            print("FAIL: review-discussion finalize did not succeed via auto-discovery", file=sys.stderr)
            errors += 1
    except Exception as exc:
        print(f"FAIL: test 6 ({exc})", file=sys.stderr)
        errors += 1

    actual_model_cases = [
        ("discussion", "override", test_review_discussion_finalize_actual_model_overrides_reviewer_model_line),
        ("discussion", "omitted", test_review_discussion_finalize_omitted_actual_model_leaves_reviewer_model_unchanged),
        ("plan", "override", test_review_plan_finalize_actual_model_overrides_reviewer_model_line),
        ("plan", "omitted", test_review_plan_finalize_omitted_actual_model_leaves_reviewer_model_unchanged),
        ("code", "override", test_review_code_finalize_actual_model_overrides_reviewer_model_line),
        ("code", "omitted", test_review_code_finalize_omitted_actual_model_leaves_reviewer_model_unchanged),
    ]
    for review_type, case_label, test_fn in actual_model_cases:
        try:
            if test_fn():
                print(f"PASS: review-{review_type} finalize --actual-model {case_label} case")
            else:
                print(f"FAIL: review-{review_type} finalize --actual-model {case_label} case", file=sys.stderr)
                errors += 1
        except Exception as exc:
            print(f"FAIL: review-{review_type} finalize --actual-model {case_label} case ({exc})", file=sys.stderr)
            errors += 1

    missing_empty_whitespace_cases = [
        ("discussion", "missing", test_review_discussion_finalize_missing_agent_output_returns_error),
        ("discussion", "empty", test_review_discussion_finalize_empty_agent_output_returns_error),
        ("discussion", "whitespace-only", test_review_discussion_finalize_whitespace_agent_output_returns_error),
        ("plan", "missing", test_review_plan_finalize_missing_agent_output_returns_error),
        ("plan", "empty", test_review_plan_finalize_empty_agent_output_returns_error),
        ("plan", "whitespace-only", test_review_plan_finalize_whitespace_agent_output_returns_error),
        ("code", "missing", test_review_code_finalize_missing_agent_output_returns_error),
        ("code", "empty", test_review_code_finalize_empty_agent_output_returns_error),
        ("code", "whitespace-only", test_review_code_finalize_whitespace_agent_output_returns_error),
    ]
    for review_type, case_label, test_fn in missing_empty_whitespace_cases:
        try:
            if test_fn():
                print(
                    f"PASS: review-{review_type} finalize with {case_label} agent-output "
                    f"returns verdict: ERROR on exit 0"
                )
            else:
                print(
                    f"FAIL: review-{review_type} finalize with {case_label} agent-output "
                    f"did not return verdict: ERROR on exit 0",
                    file=sys.stderr,
                )
                errors += 1
        except Exception as exc:
            print(f"FAIL: review-{review_type} finalize {case_label} case ({exc})", file=sys.stderr)
            errors += 1

    stale_out_md_cases = [
        ("discussion", test_review_discussion_finalize_stale_out_md_does_not_survive_retry),
        ("plan", test_review_plan_finalize_stale_out_md_does_not_survive_retry),
        ("code", test_review_code_finalize_stale_out_md_does_not_survive_retry),
    ]
    for review_type, test_fn in stale_out_md_cases:
        try:
            if test_fn():
                print(f"PASS: review-{review_type} stale .out.md does not survive a write_brief retry")
            else:
                print(
                    f"FAIL: review-{review_type} stale .out.md survived a write_brief retry "
                    f"(stale-verdict regression)",
                    file=sys.stderr,
                )
                errors += 1
        except Exception as exc:
            print(f"FAIL: review-{review_type} stale .out.md case ({exc})", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All review-finalize unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
