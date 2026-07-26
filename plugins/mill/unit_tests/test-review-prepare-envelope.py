"""Unit tests asserting the prepare-envelope invariant introduced by cards 9-11.

The invariant under test: ``output_path`` is present on every brief-emitting
success envelope from the three review CLIs' ``--stage prepare`` branch, and
absent from every envelope that writes no brief (the plan-validator failure
envelope and any ``print_error_envelope`` output).

Mocking discipline: ``_agent_dispatch`` must be the real module here -- if it
were replaced by a ``MagicMock`` (as ``test-review-finalize.py``'s existing
style does), ``write_brief`` and ``output_path_for`` would return
``MagicMock``s, ``str(output_path_for(...))`` would be junk, and the
``.md`` -> ``.out.md`` equality assertion (the entire point of this file)
could not hold. ``_review_cli`` and ``_review_common`` are likewise real
(with ``load_config``/``resolve_path`` patched as attributes on the real
``_review_common`` module, per the ``--slug`` rule below); only ``_paths``,
``_reviewers``, and the review backend itself (``_review_discussion`` /
``_review_plan`` / ``_review_code``) are mocked -- the backend's ``prepare``
returns a static dict, so the real ``write_brief`` and ``output_path_for``
stay in the path.

Each CLI is passed ``--slug <slug>`` explicitly so ``find_active_slug`` is
never called, keeping this test free of real git/branch detection.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

# Real modules -- see the module docstring for why these must not be mocked.
import _agent_dispatch  # noqa: E402
import _review_common  # noqa: E402

# (CLI filename, backend module name to mock, role string the CLI passes to write_brief)
CLI_SPECS = {
    "discussion": ("millpy-review-discussion.py", "_review_discussion", "review-discussion"),
    "plan": ("millpy-review-plan.py", "_review_plan", "review-plan"),
    "code": ("millpy-review-code.py", "_review_code", "review-code"),
}

# Every key the prepare envelope carried before cards 9-11 added output_path.
# The card requires these to still be present and unchanged -- output_path
# is purely additive.
PRE_EXISTING_ENVELOPE_KEYS = (
    "stage",
    "brief_path",
    "subagent_type",
    "model",
    "session_id",
    "role",
    "scope",
    "round",
)


def _mock_paths_and_reviewers(project_root: Path, briefs_dir: Path):
    """Return (mock_paths, mock_reviewers) modules for sys.modules patching."""
    mock_paths = unittest.mock.MagicMock()
    mock_paths.resolve_git_root = unittest.mock.MagicMock(return_value=project_root)
    mock_paths.resolve_hub_path = unittest.mock.MagicMock(return_value=project_root)
    mock_paths.resolve_wiki_path = unittest.mock.MagicMock(return_value=project_root)
    # briefs_dir is where write_brief's real implementation writes the brief +
    # unlinks any stale .out.md; must be a real, writable tempdir path.
    mock_paths.resolve_task_path = unittest.mock.MagicMock(return_value=briefs_dir)

    mock_reviewers = unittest.mock.MagicMock()
    mock_reviewers.load = unittest.mock.MagicMock(return_value={})
    mock_reviewers.validate_role_refs = unittest.mock.MagicMock()
    return mock_paths, mock_reviewers


def _success_prepare_result(scope: str, effort: str | None = None) -> dict:
    """A static backend.prepare() return value for the success-envelope cases.

    model is a real model id (matching the claude-opus-* family) so the real
    _agent_dispatch.model_to_tier resolves it to "opus" instead of raising.

    effort mirrors card 7-9's addition to the real backends' prepare() return
    dicts: present (non-None) when the configured reviewer spec has an
    effort tier, absent (key omitted, matching a spec with no effort key)
    otherwise -- both shapes must round-trip correctly through the CLI's
    conditional envelope inclusion (card 10).
    """
    result = {
        "prompt_text": "irrelevant prompt body for envelope-shape testing",
        "model": "claude-opus-4-1",
        "round": 1,
        "reviews_dir": Path("unused-by-prepare-branch"),
        "scope": scope,
    }
    if effort is not None:
        result["effort"] = effort
    return result


def _run_prepare_stage(
    review_type: str,
    unique_suffix: str,
    argv_extra: list[str],
    backend_prepare: unittest.mock.MagicMock,
    *,
    extra_modules: dict[str, unittest.mock.MagicMock] | None = None,
) -> tuple[int, str]:
    """Run a review CLI's `--stage prepare` with the backend mocked.

    Patches load_config/resolve_path directly on the real, already-imported
    _review_common module (the CLI does `from _review_common import ...`
    inside main(), so attributes set before the call are the ones main()
    picks up). Mocks _paths, _reviewers, and the named backend module in
    sys.modules; extra_modules allows the plan-validator carve-out test to
    additionally mock _plan_validate. _agent_dispatch and _review_cli are
    left genuinely real.

    Returns (return_code, captured_stdout).
    """
    cli_filename, backend_module_name, _role = CLI_SPECS[review_type]
    with tempfile.TemporaryDirectory() as tmpdir:
        project_root = Path(tmpdir)
        briefs_dir = project_root / "_mill" / "briefs"

        orig_load_config = _review_common.load_config
        orig_resolve_path = _review_common.resolve_path
        try:
            _review_common.load_config = lambda *a, **kw: {
                "paths": {"reviews_dir": "_mill/reviews/", "plan_dir": "_mill/plan/"}
            }
            # Only the plan CLI's (unskipped) validator step calls resolve_path
            # in the prepare branch; a fixed tempdir stands in for plan_dir.
            _review_common.resolve_path = lambda *a, **kw: project_root / "_mill" / "plan"

            mock_paths, mock_reviewers = _mock_paths_and_reviewers(project_root, briefs_dir)
            mock_backend = unittest.mock.MagicMock()
            mock_backend.prepare = backend_prepare

            patch_dict = {
                "_paths": mock_paths,
                "_reviewers": mock_reviewers,
                backend_module_name: mock_backend,
            }
            if extra_modules:
                patch_dict.update(extra_modules)

            with unittest.mock.patch.dict(sys.modules, patch_dict):
                unique_name = f"prepare_envelope_test_{review_type}_{unique_suffix}"
                spec = importlib.util.spec_from_file_location(
                    unique_name, HUB / "plugins/mill/scripts" / cli_filename
                )
                module = importlib.util.module_from_spec(spec)
                sys.modules[unique_name] = module
                spec.loader.exec_module(module)

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = module.main(
                        ["--slug", "test-slug", "--stage", "prepare", *argv_extra]
                    )
                return rc, buf.getvalue().strip()
        finally:
            _review_common.load_config = orig_load_config
            _review_common.resolve_path = orig_resolve_path


def _assert_success_envelope_shape(review_type: str) -> bool:
    """Part (a): success envelope carries output_path plus every pre-existing key."""
    _cli_filename, _backend_module_name, role = CLI_SPECS[review_type]
    backend_prepare = unittest.mock.MagicMock(return_value=_success_prepare_result("holistic"))
    # The plan CLI's --stage prepare branch runs the validator by default;
    # skip it here since the success-envelope shape is orthogonal to
    # validator behaviour (the validator-failure envelope has its own test).
    argv_extra = ["--skip-validate"] if review_type == "plan" else []

    rc, stdout_text = _run_prepare_stage(review_type, "success", argv_extra, backend_prepare)
    if rc != 0:
        return False
    try:
        envelope = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False

    if not all(key in envelope for key in PRE_EXISTING_ENVELOPE_KEYS):
        return False

    # Pre-existing keys must be unchanged, not merely present.
    if envelope["stage"] != "prepare":
        return False
    if envelope["subagent_type"] != _agent_dispatch.SUBAGENT_REVIEWER:
        return False
    if envelope["model"] != "opus":
        return False
    if envelope["session_id"] is not None:
        return False
    if envelope["role"] != role:
        return False
    if envelope["scope"] != "holistic":
        return False
    if envelope["round"] != 1:
        return False

    if "output_path" not in envelope:
        return False
    output_path = envelope["output_path"]
    brief_path = envelope["brief_path"]
    if not Path(output_path).is_absolute():
        return False
    expected_output_path = str(Path(brief_path).with_suffix(".out.md"))
    return output_path == expected_output_path


def test_discussion_prepare_envelope_has_output_path() -> bool:
    return _assert_success_envelope_shape("discussion")


def test_plan_prepare_envelope_has_output_path() -> bool:
    return _assert_success_envelope_shape("plan")


def test_code_prepare_envelope_has_output_path() -> bool:
    return _assert_success_envelope_shape("code")


def _assert_effort_envelope(review_type: str, effort: str | None) -> bool:
    """Card 10: effort is forwarded into the prepare envelope only when the
    resolved spec's effort tier (as surfaced by the backend's prepare()
    return dict, per cards 7-9) is non-null.

    When effort is None, the envelope must omit the "effort" key entirely
    (not include it with a null value) -- matching the conditional-inclusion
    convention _implementer_common.emit_prepare already establishes for
    start_sha/effort on the implement/fix CLIs.
    """
    backend_prepare = unittest.mock.MagicMock(
        return_value=_success_prepare_result("holistic", effort=effort)
    )
    argv_extra = ["--skip-validate"] if review_type == "plan" else []

    rc, stdout_text = _run_prepare_stage(
        review_type, f"effort-{effort}", argv_extra, backend_prepare
    )
    if rc != 0:
        return False
    try:
        envelope = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False

    if effort is None:
        return (
            "effort" not in envelope
            and envelope["subagent_type"] == _agent_dispatch.SUBAGENT_REVIEWER
        )
    return (
        envelope.get("effort") == effort
        and envelope["subagent_type"] == f"{_agent_dispatch.SUBAGENT_REVIEWER}-{effort}"
    )


def test_discussion_prepare_envelope_has_effort() -> bool:
    return _assert_effort_envelope("discussion", "high")


def test_discussion_prepare_envelope_omits_effort_when_absent() -> bool:
    return _assert_effort_envelope("discussion", None)


def test_plan_prepare_envelope_has_effort() -> bool:
    return _assert_effort_envelope("plan", "high")


def test_plan_prepare_envelope_omits_effort_when_absent() -> bool:
    return _assert_effort_envelope("plan", None)


def test_code_prepare_envelope_has_effort() -> bool:
    return _assert_effort_envelope("code", "high")


def test_code_prepare_envelope_omits_effort_when_absent() -> bool:
    return _assert_effort_envelope("code", None)


def _assert_error_envelope_has_no_output_path(review_type: str) -> bool:
    """Converse carve-out: print_error_envelope's --stage prepare output
    carries no output_path -- it fires before any brief is rendered."""
    backend_prepare = unittest.mock.MagicMock(
        side_effect=_review_common.ReviewError("synthetic prepare failure for test")
    )
    argv_extra = ["--skip-validate"] if review_type == "plan" else []

    rc, stdout_text = _run_prepare_stage(review_type, "error", argv_extra, backend_prepare)
    if rc != 1:
        return False
    try:
        envelope = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False
    # print_error_envelope's shape: type/round/verdict/blocking_count/reviews.
    if envelope.get("verdict") != "ERROR":
        return False
    return "output_path" not in envelope


def test_discussion_error_envelope_has_no_output_path() -> bool:
    return _assert_error_envelope_has_no_output_path("discussion")


def test_plan_error_envelope_has_no_output_path() -> bool:
    return _assert_error_envelope_has_no_output_path("plan")


def test_code_error_envelope_has_no_output_path() -> bool:
    return _assert_error_envelope_has_no_output_path("code")


def test_plan_validator_failure_envelope_has_no_output_path() -> bool:
    """Converse carve-out: the plan-validator failure envelope
    ({"errors": [...], "summary": ...}, exit 1) fires before any brief
    exists, so it must carry no output_path -- adding one universally would
    be unsatisfiable for this path.
    """
    mock_plan_validate = unittest.mock.MagicMock()
    mock_plan_validate.run = unittest.mock.MagicMock(
        return_value=[
            {
                "batch": "01-setup",
                "check": "synthetic-check",
                "message": "synthetic validator finding for test",
            }
        ]
    )
    # backend.prepare is never reached -- the validator short-circuits first.
    backend_prepare = unittest.mock.MagicMock(
        side_effect=AssertionError("prepare() must not be called when the validator finds errors")
    )

    rc, stdout_text = _run_prepare_stage(
        "plan",
        "validator-failure",
        [],  # no --skip-validate: the validator must run
        backend_prepare,
        extra_modules={"_plan_validate": mock_plan_validate},
    )
    if rc != 1:
        return False
    try:
        envelope = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False
    if "errors" not in envelope or "summary" not in envelope:
        return False
    return "output_path" not in envelope


def main() -> int:
    errors = 0

    checks = [
        ("discussion prepare envelope has output_path + all pre-existing keys", test_discussion_prepare_envelope_has_output_path),
        ("plan prepare envelope has output_path + all pre-existing keys", test_plan_prepare_envelope_has_output_path),
        ("code prepare envelope has output_path + all pre-existing keys", test_code_prepare_envelope_has_output_path),
        ("discussion prepare envelope has effort when spec's effort is non-null", test_discussion_prepare_envelope_has_effort),
        ("discussion prepare envelope omits effort when spec has no effort", test_discussion_prepare_envelope_omits_effort_when_absent),
        ("plan prepare envelope has effort when spec's effort is non-null", test_plan_prepare_envelope_has_effort),
        ("plan prepare envelope omits effort when spec has no effort", test_plan_prepare_envelope_omits_effort_when_absent),
        ("code prepare envelope has effort when spec's effort is non-null", test_code_prepare_envelope_has_effort),
        ("code prepare envelope omits effort when spec has no effort", test_code_prepare_envelope_omits_effort_when_absent),
        ("discussion print_error_envelope carries no output_path", test_discussion_error_envelope_has_no_output_path),
        ("plan print_error_envelope carries no output_path", test_plan_error_envelope_has_no_output_path),
        ("code print_error_envelope carries no output_path", test_code_error_envelope_has_no_output_path),
        ("plan validator-failure envelope carries no output_path", test_plan_validator_failure_envelope_has_no_output_path),
    ]

    for label, fn in checks:
        try:
            if fn():
                print(f"PASS: {label}")
            else:
                print(f"FAIL: {label}", file=sys.stderr)
                errors += 1
        except Exception as exc:
            print(f"FAIL: {label} ({exc})", file=sys.stderr)
            errors += 1

    if errors:
        print(f"\n{errors} test(s) FAILED", file=sys.stderr)
        return 1
    print("All review-prepare-envelope unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
