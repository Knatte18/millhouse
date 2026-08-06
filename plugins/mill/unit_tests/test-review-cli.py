"""Unit tests for plugins/mill/scripts/_review_cli.py.

# TODO: CLI subprocess-level tests (running millpy-review-*.py against a tempfile # fixture and
asserting ERROR: on stderr) are deferred to integration_tests/.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _test_helpers  # noqa: E402
from wiki import _client as wiki  # noqa: E402
from _review_cli import print_error, print_error_envelope  # noqa: E402
from _review_common import ReviewError  # noqa: E402


def test_print_error_envelope_shape() -> int:
    """Test print_error_envelope output shape and format."""
    failures = 0

    # Test with review_type="plan"
    stderr_buf = io.StringIO()
    stdout_buf = io.StringIO()
    with contextlib.redirect_stderr(stderr_buf), contextlib.redirect_stdout(stdout_buf):
        print_error_envelope("plan", "some error message")

    stderr_text = stderr_buf.getvalue()
    stdout_text = stdout_buf.getvalue()

    # Check stderr
    if "ERROR: some error message" not in stderr_text:
        print(f"FAIL envelope shape (plan/stderr): {stderr_text!r}", file=sys.stderr)
        failures += 1

    # Check stdout is single JSON line
    stdout_lines = stdout_text.strip().split("\n")
    if len(stdout_lines) != 1:
        print(f"FAIL envelope shape (plan/stdout lines): expected 1 line, got {len(stdout_lines)}", file=sys.stderr)
        failures += 1

    try:
        envelope = json.loads(stdout_lines[0])
    except json.JSONDecodeError as e:
        print(f"FAIL envelope shape (plan/JSON parse): {e}", file=sys.stderr)
        failures += 1
        return failures

    # Check envelope fields
    if envelope.get("type") != "plan":
        print(f"FAIL envelope shape (plan/type): expected 'plan', got {envelope.get('type')!r}", file=sys.stderr)
        failures += 1
    if envelope.get("round") != 0:
        print(f"FAIL envelope shape (plan/round): expected 0, got {envelope.get('round')!r}", file=sys.stderr)
        failures += 1
    if envelope.get("verdict") != "ERROR":
        print(f"FAIL envelope shape (plan/verdict): expected 'ERROR', got {envelope.get('verdict')!r}", file=sys.stderr)
        failures += 1
    if envelope.get("blocking_count") != 0:
        print(f"FAIL envelope shape (plan/blocking_count): expected 0, got {envelope.get('blocking_count')!r}", file=sys.stderr)
        failures += 1

    reviews = envelope.get("reviews", [])
    if len(reviews) != 1:
        print(f"FAIL envelope shape (plan/reviews length): expected 1, got {len(reviews)}", file=sys.stderr)
        failures += 1
    elif reviews[0].get("scope") != "holistic":
        print(f"FAIL envelope shape (plan/scope): expected 'holistic', got {reviews[0].get('scope')!r}", file=sys.stderr)
        failures += 1
    elif reviews[0].get("verdict") != "ERROR":
        print(f"FAIL envelope shape (plan/review verdict): expected 'ERROR', got {reviews[0].get('verdict')!r}", file=sys.stderr)
        failures += 1
    elif reviews[0].get("error") != "some error message":
        print(f"FAIL envelope shape (plan/error message): expected 'some error message', got {reviews[0].get('error')!r}", file=sys.stderr)
        failures += 1

    # Test with review_type="discussion"
    stdout_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf):
        print_error_envelope("discussion", "test msg")
    envelope = json.loads(stdout_buf.getvalue().strip())
    if envelope.get("type") != "discussion":
        print(f"FAIL envelope shape (discussion/type): expected 'discussion', got {envelope.get('type')!r}", file=sys.stderr)
        failures += 1

    # Test with review_type="code"
    stdout_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf):
        print_error_envelope("code", "test msg")
    envelope = json.loads(stdout_buf.getvalue().strip())
    if envelope.get("type") != "code":
        print(f"FAIL envelope shape (code/type): expected 'code', got {envelope.get('type')!r}", file=sys.stderr)
        failures += 1

    return failures


def test_review_cli_emits_envelope_on_config_failure() -> int:
    """Test that CLIs emit envelope when config loading fails."""
    failures = 0
    import importlib.util as _ilu
    import unittest.mock as _mock
    import os as _os

    for cli_name, review_type in [
        ("millpy-review-discussion.py", "discussion"),
        ("millpy-review-plan.py", "plan"),
        ("millpy-review-code.py", "code"),
    ]:
        _cli_path = HUB / "plugins" / "mill" / "scripts" / cli_name
        _spec = _ilu.spec_from_file_location(cli_name, str(_cli_path))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)

        with tempfile.TemporaryDirectory() as _tmpdir:
            _tmp = Path(_tmpdir)

            _orig_cwd = _os.getcwd()
            _os.chdir(_tmp)
            stdout_buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout_buf):
                    with _mock.patch("_paths.resolve_git_root", return_value=_tmp):
                        with _mock.patch("_paths.resolve_wiki_path", side_effect=ValueError("no sibling wiki")):
                            _rc = _mod.main([])
            finally:
                _os.chdir(_orig_cwd)

            if _rc != 1:
                print(f"FAIL config_failure ({cli_name}/exit code): expected 1, got {_rc}", file=sys.stderr)
                failures += 1

            try:
                envelope = json.loads(stdout_buf.getvalue().strip())
            except json.JSONDecodeError as e:
                print(f"FAIL config_failure ({cli_name}/JSON): {e}", file=sys.stderr)
                failures += 1
                continue

            if envelope.get("verdict") != "ERROR":
                print(f"FAIL config_failure ({cli_name}/verdict): expected 'ERROR', got {envelope.get('verdict')!r}", file=sys.stderr)
                failures += 1
            if envelope.get("type") != review_type:
                print(f"FAIL config_failure ({cli_name}/type): expected {review_type!r}, got {envelope.get('type')!r}", file=sys.stderr)
                failures += 1
            if "no sibling wiki" not in str(envelope.get("reviews", [{}])[0].get("error", "")):
                print(f"FAIL config_failure ({cli_name}/error message): no 'no sibling wiki' in {envelope!r}", file=sys.stderr)
                failures += 1

    return failures


def test_review_cli_emits_envelope_on_reviewer_load_failure() -> int:
    """Test that CLIs emit envelope when reviewer loading fails."""
    failures = 0
    import importlib.util as _ilu
    import unittest.mock as _mock
    import os as _os

    # Import _reviewers to get ReviewerError class
    _reviewers = __import__("_reviewers")

    for cli_name, review_type in [
        ("millpy-review-discussion.py", "discussion"),
        ("millpy-review-plan.py", "plan"),
        ("millpy-review-code.py", "code"),
    ]:
        _cli_path = HUB / "plugins" / "mill" / "scripts" / cli_name
        _spec = _ilu.spec_from_file_location(cli_name, str(_cli_path))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)

        with tempfile.TemporaryDirectory() as _tmpdir:
            _tmp = Path(_tmpdir)
            _wiki = _tmp / "wiki"
            _wiki.mkdir()
            (_wiki / "config.yaml").write_text(
                "roles:\n"
                "  discussion-review:\n"
                "    holistic:\n"
                "      rounds: 2\n"
                "      reviewer: sonnetmax\n"
                "  plan-review:\n"
                "    batch:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "    holistic:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "  code-review:\n"
                "    batch:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "    holistic:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "paths:\n"
                "  discussion_file: discussion.md\n"
                "  plan_dir: plan/\n"
                "  reviews_dir: reviews/\n",
                encoding="utf-8",
            )
            _mill = _tmp / ".millhouse"
            _mill.mkdir()

            _orig_cwd = _os.getcwd()
            _os.chdir(_tmp)
            stdout_buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout_buf):
                    with _mock.patch("_paths.resolve_wiki_path", return_value=_wiki):
                        with _mock.patch("_reviewers.load", side_effect=_reviewers.ReviewerError("registry missing")):
                            _rc = _mod.main([])
            finally:
                _os.chdir(_orig_cwd)

            if _rc != 1:
                print(f"FAIL reviewer_load ({cli_name}/exit code): expected 1, got {_rc}", file=sys.stderr)
                failures += 1

            try:
                envelope = json.loads(stdout_buf.getvalue().strip())
            except json.JSONDecodeError as e:
                print(f"FAIL reviewer_load ({cli_name}/JSON): {e}", file=sys.stderr)
                failures += 1
                continue

            if envelope.get("verdict") != "ERROR":
                print(f"FAIL reviewer_load ({cli_name}/verdict): expected 'ERROR', got {envelope.get('verdict')!r}", file=sys.stderr)
                failures += 1
            if envelope.get("type") != review_type:
                print(f"FAIL reviewer_load ({cli_name}/type): expected {review_type!r}, got {envelope.get('type')!r}", file=sys.stderr)
                failures += 1

    return failures


def test_review_cli_emits_envelope_on_slug_failure() -> int:
    """Test that CLIs emit envelope when slug resolution fails."""
    failures = 0
    import importlib.util as _ilu
    import unittest.mock as _mock
    import os as _os

    for cli_name, review_type in [
        ("millpy-review-discussion.py", "discussion"),
        ("millpy-review-plan.py", "plan"),
        ("millpy-review-code.py", "code"),
    ]:
        _cli_path = HUB / "plugins" / "mill" / "scripts" / cli_name
        _spec = _ilu.spec_from_file_location(cli_name, str(_cli_path))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)

        with tempfile.TemporaryDirectory() as _tmpdir:
            _tmp = Path(_tmpdir)
            _wiki = _tmp / "wiki"
            _wiki.mkdir()
            (_wiki / "config.yaml").write_text(
                "roles:\n"
                "  discussion-review:\n"
                "    holistic:\n"
                "      rounds: 2\n"
                "      reviewer: sonnetmax\n"
                "  plan-review:\n"
                "    batch:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "    holistic:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "  code-review:\n"
                "    batch:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "    holistic:\n"
                "      rounds: 1\n"
                "      reviewer: sonnetmax\n"
                "paths:\n"
                "  discussion_file: discussion.md\n"
                "  plan_dir: plan/\n"
                "  reviews_dir: reviews/\n",
                encoding="utf-8",
            )
            (_wiki / "agents.yaml").write_text(
                "sonnetmax:\n"
                "  type: single\n"
                "  provider: claude\n"
                "  model: claude-sonnet-4-6\n",
                encoding="utf-8",
            )
            _mill = _tmp / ".millhouse"
            _mill.mkdir()

            _orig_cwd = _os.getcwd()
            _os.chdir(_tmp)
            stdout_buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(stdout_buf):
                    with _mock.patch("_paths.resolve_git_root", return_value=_tmp):
                        with _mock.patch("_paths.resolve_wiki_path", return_value=_wiki):
                            with _mock.patch("_review_common.find_active_slug", side_effect=ReviewError("branch not present in Home.md")):
                                _rc = _mod.main([])
            finally:
                _os.chdir(_orig_cwd)

            if _rc != 1:
                print(f"FAIL slug_failure ({cli_name}/exit code): expected 1, got {_rc}", file=sys.stderr)
                failures += 1

            try:
                envelope = json.loads(stdout_buf.getvalue().strip())
            except json.JSONDecodeError as e:
                print(f"FAIL slug_failure ({cli_name}/JSON): {e}", file=sys.stderr)
                failures += 1
                continue

            if envelope.get("verdict") != "ERROR":
                print(f"FAIL slug_failure ({cli_name}/verdict): expected 'ERROR', got {envelope.get('verdict')!r}", file=sys.stderr)
                failures += 1
            if envelope.get("type") != review_type:
                print(f"FAIL slug_failure ({cli_name}/type): expected {review_type!r}, got {envelope.get('type')!r}", file=sys.stderr)
                failures += 1
            if "branch not present" not in str(envelope.get("reviews", [{}])[0].get("error", "")):
                print(f"FAIL slug_failure ({cli_name}/error message): no 'branch not present' in {envelope!r}", file=sys.stderr)
                failures += 1

    return failures


def test_discussion_prepare_brief_path_uses_hub_dir() -> int:
    """Test that discussion prepare stage writes briefs under hub_dir.

    ``_paths.resolve_hub_path`` resolves the directory within the CURRENT worktree where
    ``.millhouse/`` actually lives -- for nested sub-project layouts (e.g.
    ``src/csharp/NORCE.Models``) this is a subdirectory of git_root, not git_root itself (see
    _paths.resolve_hub_path docstring). ``_mill/`` lives alongside ``.millhouse/``, so briefs must
    be written under hub_dir; writing them at git_root would miss nested layouts entirely.
    This fixture models that nested relationship (hub_root is a subdirectory of task_root) so the
    assertions hold for both the real-world contract and backward-compatible flat layouts where
    hub_dir == git_root.
    """
    failures = 0
    import importlib.util as _ilu
    import unittest.mock as _mock
    import os as _os

    _cli_path = HUB / "plugins" / "mill" / "scripts" / "millpy-review-discussion.py"
    _spec = _ilu.spec_from_file_location("millpy_review_discussion_brief_path", str(_cli_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    with _test_helpers.safe_temp_dir() as tmp:
        task_root = tmp / "wts" / "my-slug"
        hub_root = task_root / "src" / "proj"
        wiki_root = tmp / "wiki"
        hub_root.mkdir(parents=True)
        wiki_root.mkdir(parents=True)

        cfg_dict = {
            "paths": {
                "discussion_file": "_mill/discussion.md",
                "plan_dir": "_mill/plan/",
                "reviews_dir": "_mill/reviews/",
            },
            "roles": {
                "discussion-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "sonnetmax",
                    }
                }
            },
            "spawn": {
                "branch_prefix": "hanf/",
            },
        }

        fake_prepare = {
            "prompt_text": "# test prompt",
            "model": "claude-sonnet-4-6",
            "round": 1,
            "reviews_dir": hub_root / "_mill" / "reviews",
            "scope": "holistic",
        }

        stdout_buf = io.StringIO()
        _orig_cwd = _os.getcwd()
        _os.chdir(task_root)
        try:
            with contextlib.redirect_stdout(stdout_buf):
                with _mock.patch("_paths.resolve_git_root", return_value=task_root):
                    with _mock.patch("_paths.resolve_hub_path", return_value=hub_root):
                        with _mock.patch("_paths.resolve_wiki_path", return_value=wiki_root):
                            # The hub_dir rebind (Card 15) calls resolve_container_path/ resolve_active_hub for real after slug resolution;
                            # mock both to keep hub_dir at hub_root -- the nested-layout value this test asserts brief_path resolves under -- instead of hitting real git against this fixture's plain (non-git) task_root.
                            with _mock.patch("_paths.resolve_container_path", return_value=tmp / "wts"):
                                with _mock.patch("_paths.resolve_active_hub", return_value=hub_root):
                                    with _mock.patch("_review_common.load_config", return_value=cfg_dict):
                                        with _mock.patch("_reviewers.load", return_value={}):
                                            with _mock.patch("_reviewers.validate_role_refs"):
                                                with _mock.patch("_review_common.find_active_slug", return_value="my-slug"):
                                                    with _mock.patch("_review_discussion.prepare", return_value=fake_prepare):
                                                        _rc = _mod.main(["--stage", "prepare"])
        finally:
            _os.chdir(_orig_cwd)

        if _rc != 0:
            print(f"FAIL brief_path (exit): expected 0, got {_rc}", file=sys.stderr)
            failures += 1
            return failures

        try:
            envelope = json.loads(stdout_buf.getvalue().strip())
        except json.JSONDecodeError as e:
            print(f"FAIL brief_path (JSON): {e}", file=sys.stderr)
            failures += 1
            return failures

        brief_path_str = envelope.get("brief_path", "")

        if str(hub_root) not in brief_path_str:
            print(f"FAIL brief_path: expected path under hub_root {hub_root!r}, got {brief_path_str!r}", file=sys.stderr)
            failures += 1

        if failures == 0:
            print("PASS brief_path: discussion prepare stage writes brief under hub_dir (nested-layout safe)")

        return failures


def test_plan_prepare_brief_path_uses_git_root() -> int:
    """Test that plan prepare stage writes briefs to git_root, not hub_dir."""
    failures = 0
    import importlib.util as _ilu
    import unittest.mock as _mock
    import os as _os

    _cli_path = HUB / "plugins" / "mill" / "scripts" / "millpy-review-plan.py"
    _spec = _ilu.spec_from_file_location("millpy_review_plan_brief_path", str(_cli_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    with _test_helpers.safe_temp_dir() as tmp:
        task_root = tmp / "wts" / "my-slug"
        hub_root = tmp / "wts" / "millhouse"
        wiki_root = tmp / "wiki"
        task_root.mkdir(parents=True)
        hub_root.mkdir(parents=True)
        wiki_root.mkdir(parents=True)

        cfg_dict = {
            "paths": {
                "discussion_file": "_mill/discussion.md",
                "plan_dir": "_mill/plan/",
                "reviews_dir": "_mill/reviews/",
            },
            "roles": {
                "plan-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "sonnetmax",
                    },
                    "batch": {
                        "rounds": 1,
                        "reviewer": "sonnetmax",
                    },
                }
            },
            "spawn": {
                "branch_prefix": "hanf/",
            },
        }

        fake_prepare = {
            "prompt_text": "# test plan prompt",
            "model": "claude-sonnet-4-6",
            "round": 1,
            "reviews_dir": task_root / "_mill" / "reviews",
            "scope": "holistic",
        }

        stdout_buf = io.StringIO()
        _orig_cwd = _os.getcwd()
        _os.chdir(task_root)
        try:
            with contextlib.redirect_stdout(stdout_buf):
                with _mock.patch("_paths.resolve_git_root", return_value=task_root):
                    with _mock.patch("_paths.resolve_hub_path", return_value=hub_root):
                        with _mock.patch("_paths.resolve_wiki_path", return_value=wiki_root):
                            # The project_root rebind (Card 14) calls resolve_container_path/ resolve_active_hub for real after slug resolution;
                            # mock both to keep project_root at task_root -- the corrected value this test asserts brief_path resolves under -- instead of hitting real git against this fixture's plain (non-git) task_root.
                            with _mock.patch("_paths.resolve_container_path", return_value=tmp / "wts"):
                                with _mock.patch("_paths.resolve_active_hub", return_value=task_root):
                                    with _mock.patch("_review_common.load_config", return_value=cfg_dict):
                                        with _mock.patch("_reviewers.load", return_value={}):
                                            with _mock.patch("_reviewers.validate_role_refs"):
                                                with _mock.patch("_review_common.find_active_slug", return_value="my-slug"):
                                                    with _mock.patch("_review_plan.prepare", return_value=fake_prepare):
                                                        # Pass --skip-validate to bypass the pre-review plan validator; mocking _plan_validate.run does not work because the CLI binds it via 'from ...
                                                        # import run' inside the function scope before the mock can intercept.
                                                        _rc = _mod.main(["--stage", "prepare", "--skip-validate"])
        finally:
            _os.chdir(_orig_cwd)

        if _rc != 0:
            print(f"FAIL plan_brief_path (exit): expected 0, got {_rc}", file=sys.stderr)
            failures += 1
            return failures

        try:
            envelope = json.loads(stdout_buf.getvalue().strip())
        except json.JSONDecodeError as e:
            print(f"FAIL plan_brief_path (JSON): {e}", file=sys.stderr)
            failures += 1
            return failures

        brief_path_str = envelope.get("brief_path", "")

        if str(task_root) not in brief_path_str:
            print(
                f"FAIL plan_brief_path: expected path under task_root {task_root!r}, got {brief_path_str!r}",
                file=sys.stderr,
            )
            failures += 1

        if str(hub_root) in brief_path_str:
            print(
                f"FAIL plan_brief_path: brief went to hub_root (regression): {brief_path_str!r}",
                file=sys.stderr,
            )
            failures += 1

        if failures == 0:
            print("PASS plan_brief_path: plan prepare stage writes brief to git_root (task worktree)")

        return failures


def test_code_prepare_brief_path_uses_git_root() -> int:
    """Test that code prepare stage writes briefs to git_root, not hub_dir."""
    failures = 0
    import importlib.util as _ilu
    import unittest.mock as _mock
    import os as _os

    _cli_path = HUB / "plugins" / "mill" / "scripts" / "millpy-review-code.py"
    _spec = _ilu.spec_from_file_location("millpy_review_code_brief_path", str(_cli_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    with _test_helpers.safe_temp_dir() as tmp:
        task_root = tmp / "wts" / "my-slug"
        hub_root = tmp / "wts" / "millhouse"
        wiki_root = tmp / "wiki"
        task_root.mkdir(parents=True)
        hub_root.mkdir(parents=True)
        wiki_root.mkdir(parents=True)

        cfg_dict = {
            "paths": {
                "discussion_file": "_mill/discussion.md",
                "plan_dir": "_mill/plan/",
                "reviews_dir": "_mill/reviews/",
            },
            "roles": {
                "code-review": {
                    "holistic": {
                        "rounds": 1,
                        "reviewer": "sonnetmax",
                    },
                    "batch": {
                        "rounds": 1,
                        "reviewer": "sonnetmax",
                    },
                }
            },
            "spawn": {
                "branch_prefix": "hanf/",
            },
        }

        fake_prepare = {
            "prompt_text": "# test code prompt",
            "model": "claude-sonnet-4-6",
            "round": 1,
            "reviews_dir": task_root / "_mill" / "reviews",
            "scope": "holistic",
        }

        stdout_buf = io.StringIO()
        _orig_cwd = _os.getcwd()
        _os.chdir(task_root)
        try:
            with contextlib.redirect_stdout(stdout_buf):
                with _mock.patch("_paths.resolve_git_root", return_value=task_root):
                    with _mock.patch("_paths.resolve_hub_path", return_value=hub_root):
                        with _mock.patch("_paths.resolve_wiki_path", return_value=wiki_root):
                            # The project_root rebind (Card 13) calls resolve_container_path/ resolve_active_hub for real after slug resolution;
                            # mock both to keep project_root at task_root -- the corrected value this test asserts brief_path resolves under -- instead of hitting real git against this fixture's plain (non-git) task_root.
                            with _mock.patch("_paths.resolve_container_path", return_value=tmp / "wts"):
                                with _mock.patch("_paths.resolve_active_hub", return_value=task_root):
                                    with _mock.patch("_review_common.load_config", return_value=cfg_dict):
                                        with _mock.patch("_reviewers.load", return_value={}):
                                            with _mock.patch("_reviewers.validate_role_refs"):
                                                with _mock.patch("_review_common.find_active_slug", return_value="my-slug"):
                                                    with _mock.patch("_review_code.prepare", return_value=fake_prepare):
                                                        _rc = _mod.main(["--stage", "prepare"])
        finally:
            _os.chdir(_orig_cwd)

        if _rc != 0:
            print(f"FAIL code_brief_path (exit): expected 0, got {_rc}", file=sys.stderr)
            failures += 1
            return failures

        try:
            envelope = json.loads(stdout_buf.getvalue().strip())
        except json.JSONDecodeError as e:
            print(f"FAIL code_brief_path (JSON): {e}", file=sys.stderr)
            failures += 1
            return failures

        brief_path_str = envelope.get("brief_path", "")

        if str(task_root) not in brief_path_str:
            print(
                f"FAIL code_brief_path: expected path under task_root {task_root!r}, got {brief_path_str!r}",
                file=sys.stderr,
            )
            failures += 1

        if str(hub_root) in brief_path_str:
            print(
                f"FAIL code_brief_path: brief went to hub_root (regression): {brief_path_str!r}",
                file=sys.stderr,
            )
            failures += 1

        if failures == 0:
            print("PASS code_brief_path: code prepare stage writes brief to git_root (task worktree)")

        return failures


def test_finalize_actual_model_flag_reflected_in_review_file() -> int:
    """Test that `--stage finalize --actual-model <tier>` overrides the written review file's
    `reviewer_model:` line for each of the three review CLIs.

    Uses an in-process `main(argv)` call against the real `_review_common` and review-backend
    modules (only `_paths`/`_reviewers` are mocked), mirroring the CLI-level real-backend pattern in
    test-review-finalize.py.
    The raw reviewer output always echoes `reviewer_model: sonnetmax`; passing `--actual-model
    haiku` must overwrite that line in the file actually written to disk.
    """
    failures = 0
    import importlib.util as _ilu
    import unittest.mock as _mock
    import _review_common as _rc

    raw_text = (
        "MILL_REVIEW_BEGIN\n"
        "```yaml\n"
        "verdict: APPROVE\n"
        "reviewer_model: sonnetmax\n"
        "```\n"
        "MILL_REVIEW_END\n"
    )

    for cli_name, review_type in [
        ("millpy-review-discussion.py", "discussion"),
        ("millpy-review-plan.py", "plan"),
        ("millpy-review-code.py", "code"),
    ]:
        _cli_path = HUB / "plugins" / "mill" / "scripts" / cli_name
        _spec = _ilu.spec_from_file_location(f"{cli_name}_actual_model", str(_cli_path))
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)

        with tempfile.TemporaryDirectory() as _tmpdir:
            project_root = Path(_tmpdir)
            reviews_dir = project_root / "_mill" / "reviews"
            agent_output_path = project_root / "agent-output.out.md"
            agent_output_path.write_text(raw_text, encoding="utf-8")

            mock_paths = _mock.MagicMock()
            mock_paths.resolve_git_root = _mock.MagicMock(return_value=project_root)
            mock_paths.resolve_hub_path = _mock.MagicMock(return_value=project_root)
            mock_paths.resolve_wiki_path = _mock.MagicMock(return_value=project_root)

            mock_reviewers = _mock.MagicMock()
            mock_reviewers.load = _mock.MagicMock(return_value={})
            mock_reviewers.validate_role_refs = _mock.MagicMock()

            orig_load_config = _rc.load_config
            orig_resolve_path = _rc.resolve_path
            try:
                _rc.load_config = lambda *a, **kw: {"paths": {"reviews_dir": "_mill/reviews/"}}
                _rc.resolve_path = lambda *a, **kw: reviews_dir

                with _mock.patch.dict(sys.modules, {"_paths": mock_paths, "_reviewers": mock_reviewers}):
                    stdout_buf = io.StringIO()
                    with contextlib.redirect_stdout(stdout_buf):
                        rc = _mod.main(
                            [
                                "--slug", "test-slug",
                                "--stage", "finalize",
                                "--round", "1",
                                "--agent-output", str(agent_output_path),
                                "--actual-model", "haiku",
                            ]
                        )
            finally:
                _rc.load_config = orig_load_config
                _rc.resolve_path = orig_resolve_path

            if rc != 0:
                print(f"FAIL actual_model ({cli_name}/exit code): expected 0, got {rc}", file=sys.stderr)
                failures += 1
                continue

            try:
                envelope = json.loads(stdout_buf.getvalue().strip())
            except json.JSONDecodeError as e:
                print(f"FAIL actual_model ({cli_name}/JSON): {e}", file=sys.stderr)
                failures += 1
                continue

            reviews = envelope.get("reviews", [])
            if not reviews:
                print(f"FAIL actual_model ({cli_name}/reviews empty): {envelope!r}", file=sys.stderr)
                failures += 1
                continue

            written_path = Path(reviews[0]["file"])
            if not written_path.exists():
                print(f"FAIL actual_model ({cli_name}/file missing): {written_path}", file=sys.stderr)
                failures += 1
                continue

            written_content = written_path.read_text(encoding="utf-8")
            if "reviewer_model: haiku" not in written_content:
                print(
                    f"FAIL actual_model ({cli_name}/reviewer_model line): expected "
                    f"'reviewer_model: haiku' in written file, got: {written_content!r}",
                    file=sys.stderr,
                )
                failures += 1

    return failures


def main() -> int:
    failures = 0

    # Run new envelope-related tests first
    failures += test_print_error_envelope_shape()
    failures += test_review_cli_emits_envelope_on_config_failure()
    failures += test_review_cli_emits_envelope_on_reviewer_load_failure()
    failures += test_review_cli_emits_envelope_on_slug_failure()
    failures += test_discussion_prepare_brief_path_uses_hub_dir()
    failures += test_plan_prepare_brief_path_uses_git_root()
    failures += test_code_prepare_brief_path_uses_git_root()
    failures += test_finalize_actual_model_flag_reflected_in_review_file()

    # (a) plain message — ERROR: prefix present, hint absent, trailing newline present
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        print_error(ReviewError("plain message"))
    captured = buf.getvalue()
    if not captured.startswith("ERROR: plain message"):
        print(f"FAIL (a) prefix: {captured!r}", file=sys.stderr)
        failures += 1
    if not captured.endswith("\n"):
        print(f"FAIL (a) trailing newline: {captured!r}", file=sys.stderr)
        failures += 1
    if "Hint: check the plan card" in captured:
        print(f"FAIL (a) hint must be absent: {captured!r}", file=sys.stderr)
        failures += 1

    # (b) [resolve_ref_paths] prefix — ERROR: line + hint both present
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        print_error(ReviewError("[resolve_ref_paths] referenced path not found: 'foo.py'"))
    captured = buf.getvalue()
    if "ERROR: [resolve_ref_paths] referenced path not found: 'foo.py'" not in captured:
        print(f"FAIL (b) error line: {captured!r}", file=sys.stderr)
        failures += 1
    if "Hint: check the plan card" not in captured:
        print(f"FAIL (b) hint missing: {captured!r}", file=sys.stderr)
        failures += 1
    if "list it under Deletes:" not in captured:
        print(f"FAIL (b) deletes mention missing: {captured!r}", file=sys.stderr)
        failures += 1

    # (c) [resolve_ref_paths] internal (not at start) — hint must NOT be added
    buf = io.StringIO()
    with contextlib.redirect_stderr(buf):
        print_error(ReviewError("some prefix [resolve_ref_paths] inner"))
    captured = buf.getvalue()
    if "Hint: check the plan card" in captured:
        print(f"FAIL (c) hint must be absent for internal occurrence: {captured!r}", file=sys.stderr)
        failures += 1

    # (d) validate_role_refs failure via millpy-review-discussion CLI mill-config.yaml references "missing_reviewer";
    # reviewers.yaml omits it.
    # main() should exit 1 and write the missing name to stderr.
    import importlib.util as _ilu
    _cli_path = HUB / "plugins" / "mill" / "scripts" / "millpy-review-discussion.py"
    _spec = _ilu.spec_from_file_location("millpy_review_discussion", str(_cli_path))
    _mod = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)

    with _test_helpers.safe_temp_dir() as _tmp:
        _wiki = _tmp / "wiki"
        _test_helpers.init_wiki_repo(_wiki)
        (_tmp / "mill-config.yaml").write_text(
            "roles:\n"
            "  discussion-review:\n"
            "    holistic:\n"
            "      rounds: 2\n"
            "      reviewer: missing_reviewer\n"
            "paths:\n"
            "  discussion_file: discussion.md\n"
            "  plan_dir: plan/\n"
            "  reviews_dir: reviews/\n"
            "spawn:\n"
            "  branch_prefix: 'hanf/'\n",
            encoding="utf-8",
        )
        (_tmp / "agents.yaml").write_text(
            "sonnetmax:\n"
            "  type: single\n"
            "  provider: claude\n"
            "  model: claude-sonnet-4-6\n",
            encoding="utf-8",
        )
        (_wiki / "Home.md").write_text(
            "# Home\n[test-slug] [active]\n",
            encoding="utf-8",
        )
        wiki.upsert_task(_wiki, "test-slug", title="Test", status="active")

        # Initialize _tmp as a real git repo (worktree role)
        import subprocess as _sp
        _sp.run(["git", "init", "--initial-branch=main", str(_tmp)], capture_output=True, check=True)
        _sp.run(["git", "-C", str(_tmp), "config", "user.email", "test@test.com"], capture_output=True, check=True)
        _sp.run(["git", "-C", str(_tmp), "config", "user.name", "Test"], capture_output=True, check=True)
        (_tmp / ".keep").write_text("", encoding="utf-8")
        _sp.run(["git", "-C", str(_tmp), "add", ".keep"], capture_output=True, check=True)
        _sp.run(["git", "-C", str(_tmp), "commit", "-m", "init"], capture_output=True, check=True)
        _sp.run(["git", "-C", str(_tmp), "checkout", "-b", "hanf/test-slug"], capture_output=True, check=True)

        _mill = _tmp / ".millhouse"
        _mill.mkdir()
        (_mill / "discussion.md").write_text("# Discussion\n", encoding="utf-8")

        import unittest.mock as _mock
        import os as _os

        _orig_cwd = _os.getcwd()
        _os.chdir(_tmp)
        _err_buf = io.StringIO()
        try:
            with contextlib.redirect_stderr(_err_buf):
                with _mock.patch("_paths.resolve_git_root", return_value=_tmp):
                    with _mock.patch("_paths.resolve_hub_path", return_value=_tmp):
                        with _mock.patch("_paths.resolve_wiki_path", return_value=_wiki):
                            _rc = _mod.main([])
        finally:
            _os.chdir(_orig_cwd)

        _err_text = _err_buf.getvalue()
        if _rc != 1:
            print(f"FAIL (d) exit code: expected 1, got {_rc}", file=sys.stderr)
            failures += 1
        if "missing_reviewer" not in _err_text:
            print(f"FAIL (d) stderr missing reviewer name: {_err_text!r}", file=sys.stderr)
            failures += 1

    if failures == 0:
        print("test-review-cli: all tests passed (including envelope shape and startup-failure tests)")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
