"""Unit tests for review-plan and review-discussion --round auto-discovery in finalize stage.

Tests the CLI-level --round defaulting path for both millpy-review-plan.py and
millpy-review-discussion.py. Verifies that when --round is absent, discover_round
is called to auto-detect the round number based on existing review files.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest.mock
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _review_common import discover_round  # noqa: E402

# Load millpy_review_plan via importlib (name contains hyphens)
_plan_path = Path(__file__).resolve().parent.parent / "scripts" / "millpy-review-plan.py"
_plan_spec = importlib.util.spec_from_file_location("millpy_review_plan", _plan_path)
millpy_review_plan = importlib.util.module_from_spec(_plan_spec)
_plan_spec.loader.exec_module(millpy_review_plan)

# Load millpy_review_discussion via importlib (name contains hyphens)
_disc_path = Path(__file__).resolve().parent.parent / "scripts" / "millpy-review-discussion.py"
_disc_spec = importlib.util.spec_from_file_location("millpy_review_discussion", _disc_path)
millpy_review_discussion = importlib.util.module_from_spec(_disc_spec)
_disc_spec.loader.exec_module(millpy_review_discussion)


def _make_fixture(tmp: Path) -> tuple[Path, Path]:
    """Create a reviews_dir (empty) and stub_out file for testing."""
    reviews_dir = tmp / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)

    stub_out = tmp / "agent.out.md"
    stub_out.write_text(
        "MILL_REVIEW_BEGIN\n# stub\n\n```yaml\nverdict: APPROVE\n```\nMILL_REVIEW_END\n",
        encoding="utf-8"
    )

    return reviews_dir, stub_out


def _stub_cfg(reviews_dir: Path) -> dict:
    """Return a minimal config dict for testing."""
    return {
        "paths": {
            "reviews_dir": str(reviews_dir),
            "discussion_file": "x",
            "plan_dir": "x",
            "status_md": "x"
        }
    }


def main() -> int:
    """Run all test cases and return 0 on success, 1 on failure."""
    pass_count = 0
    fail_count = 0

    # Test case 1: review-plan-finalize-round-empty
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reviews_dir, stub_out = _make_fixture(tmp)

            stub_review_entry = {
                "scope": "holistic",
                "verdict": "APPROVE",
                "file": str(reviews_dir / "r1.md"),
                "session_id": None,
                "blocking_count": 0,
                "nit_count": 0,
                "round": 1
            }

            with unittest.mock.patch("_paths.resolve_hub_path") as mock_hub:
                with unittest.mock.patch("_paths.resolve_git_root") as mock_git:
                    with unittest.mock.patch("_paths.resolve_wiki_path") as mock_wiki:
                        with unittest.mock.patch("_review_common.load_config") as mock_cfg:
                            with unittest.mock.patch("_review_common.find_active_slug") as mock_slug:
                                with unittest.mock.patch("_reviewers.load") as mock_reviewers_load:
                                    with unittest.mock.patch("_reviewers.validate_role_refs") as mock_validate:
                                        with unittest.mock.patch("_review_common.resolve_path") as mock_resolve:
                                            with unittest.mock.patch("_review_plan.finalize") as mock_finalize:
                                                mock_hub.return_value = tmp
                                                mock_git.return_value = tmp
                                                mock_wiki.return_value = tmp
                                                mock_cfg.return_value = _stub_cfg(reviews_dir)
                                                mock_slug.return_value = "test-slug"
                                                mock_reviewers_load.return_value = {}
                                                mock_resolve.return_value = reviews_dir
                                                mock_finalize.return_value = stub_review_entry

                                                rc = millpy_review_plan.main([
                                                    "--stage", "finalize",
                                                    "--agent-output", str(stub_out)
                                                ])

                                                assert rc != 1, f"expected not 1 (--round is required error), got {rc}"
                                                assert mock_finalize.called, "expected finalize to be called"
                                                call_args = mock_finalize.call_args
                                                assert call_args[1]["round_n"] == 1, \
                                                    f"expected round_n=1 (empty reviews), got {call_args[1]['round_n']}"
                                                print("[case] (a) review-plan-finalize-round-empty")
                                                pass_count += 1
    except Exception as exc:
        print(f"[fail] review-plan-finalize-round-empty: {exc}", file=sys.stderr)
        fail_count += 1

    # Test case 2: review-plan-finalize-round-with-existing
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reviews_dir, stub_out = _make_fixture(tmp)

            # Add existing review file to bump round to 2
            (reviews_dir / "20260618-120000-plan-review-r1.md").write_text("existing", encoding="utf-8")

            stub_review_entry = {
                "scope": "holistic",
                "verdict": "APPROVE",
                "file": str(reviews_dir / "r2.md"),
                "session_id": None,
                "blocking_count": 0,
                "nit_count": 0,
                "round": 2
            }

            with unittest.mock.patch("_paths.resolve_hub_path") as mock_hub:
                with unittest.mock.patch("_paths.resolve_git_root") as mock_git:
                    with unittest.mock.patch("_paths.resolve_wiki_path") as mock_wiki:
                        with unittest.mock.patch("_review_common.load_config") as mock_cfg:
                            with unittest.mock.patch("_review_common.find_active_slug") as mock_slug:
                                with unittest.mock.patch("_reviewers.load") as mock_reviewers_load:
                                    with unittest.mock.patch("_reviewers.validate_role_refs") as mock_validate:
                                        with unittest.mock.patch("_review_common.resolve_path") as mock_resolve:
                                            with unittest.mock.patch("_review_plan.finalize") as mock_finalize:
                                                mock_hub.return_value = tmp
                                                mock_git.return_value = tmp
                                                mock_wiki.return_value = tmp
                                                mock_cfg.return_value = _stub_cfg(reviews_dir)
                                                mock_slug.return_value = "test-slug"
                                                mock_reviewers_load.return_value = {}
                                                mock_resolve.return_value = reviews_dir
                                                mock_finalize.return_value = stub_review_entry

                                                rc = millpy_review_plan.main([
                                                    "--stage", "finalize",
                                                    "--agent-output", str(stub_out)
                                                ])

                                                assert rc != 1, f"expected not 1 (--round is required error), got {rc}"
                                                call_args = mock_finalize.call_args
                                                assert call_args[1]["round_n"] == 2, \
                                                    f"expected round_n=2 (existing r1), got {call_args[1]['round_n']}"
                                                print("[case] (b) review-plan-finalize-round-with-existing")
                                                pass_count += 1
    except Exception as exc:
        print(f"[fail] review-plan-finalize-round-with-existing: {exc}", file=sys.stderr)
        fail_count += 1

    # Test case 3: review-discussion-finalize-round-empty
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reviews_dir, stub_out = _make_fixture(tmp)

            stub_review_entry = unittest.mock.Mock(
                to_dict=unittest.mock.Mock(return_value={
                    "type": "discussion",
                    "round": 1,
                    "verdict": "APPROVE",
                    "blocking_count": 0,
                    "nit_count": 0,
                    "reviews": []
                })
            )

            with unittest.mock.patch("_paths.resolve_git_root") as mock_git:
                with unittest.mock.patch("_paths.resolve_hub_path") as mock_hub:
                    with unittest.mock.patch("_paths.resolve_wiki_path") as mock_wiki:
                        with unittest.mock.patch("_review_common.load_config") as mock_cfg:
                            with unittest.mock.patch("_review_common.find_active_slug") as mock_slug:
                                with unittest.mock.patch("_reviewers.load") as mock_reviewers_load:
                                    with unittest.mock.patch("_reviewers.validate_role_refs") as mock_validate:
                                        with unittest.mock.patch("_review_common.resolve_path") as mock_resolve:
                                            with unittest.mock.patch("_review_discussion.finalize") as mock_finalize:
                                                mock_git.return_value = tmp
                                                mock_hub.return_value = tmp
                                                mock_wiki.return_value = tmp
                                                mock_cfg.return_value = _stub_cfg(reviews_dir)
                                                mock_slug.return_value = "test-slug"
                                                mock_reviewers_load.return_value = {}
                                                mock_resolve.return_value = reviews_dir
                                                mock_finalize.return_value = stub_review_entry

                                                rc = millpy_review_discussion.main([
                                                    "--stage", "finalize",
                                                    "--agent-output", str(stub_out)
                                                ])

                                                assert rc != 1, f"expected not 1 (--round is required error), got {rc}"
                                                assert mock_finalize.called, "expected finalize to be called"
                                                call_args = mock_finalize.call_args
                                                assert call_args[1]["round_n"] == 1, \
                                                    f"expected round_n=1 (empty reviews), got {call_args[1]['round_n']}"
                                                print("[case] (c) review-discussion-finalize-round-empty")
                                                pass_count += 1
    except Exception as exc:
        print(f"[fail] review-discussion-finalize-round-empty: {exc}", file=sys.stderr)
        fail_count += 1

    # Test case 4: review-discussion-finalize-round-with-existing
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            reviews_dir, stub_out = _make_fixture(tmp)

            # Add existing discussion review file to bump round to 2
            (reviews_dir / "20260618-120000-discussion-review-r1.md").write_text("existing", encoding="utf-8")

            stub_review_entry = unittest.mock.Mock(
                to_dict=unittest.mock.Mock(return_value={
                    "type": "discussion",
                    "round": 2,
                    "verdict": "APPROVE",
                    "blocking_count": 0,
                    "nit_count": 0,
                    "reviews": []
                })
            )

            with unittest.mock.patch("_paths.resolve_git_root") as mock_git:
                with unittest.mock.patch("_paths.resolve_hub_path") as mock_hub:
                    with unittest.mock.patch("_paths.resolve_wiki_path") as mock_wiki:
                        with unittest.mock.patch("_review_common.load_config") as mock_cfg:
                            with unittest.mock.patch("_review_common.find_active_slug") as mock_slug:
                                with unittest.mock.patch("_reviewers.load") as mock_reviewers_load:
                                    with unittest.mock.patch("_reviewers.validate_role_refs") as mock_validate:
                                        with unittest.mock.patch("_review_common.resolve_path") as mock_resolve:
                                            with unittest.mock.patch("_review_discussion.finalize") as mock_finalize:
                                                mock_git.return_value = tmp
                                                mock_hub.return_value = tmp
                                                mock_wiki.return_value = tmp
                                                mock_cfg.return_value = _stub_cfg(reviews_dir)
                                                mock_slug.return_value = "test-slug"
                                                mock_reviewers_load.return_value = {}
                                                mock_resolve.return_value = reviews_dir
                                                mock_finalize.return_value = stub_review_entry

                                                rc = millpy_review_discussion.main([
                                                    "--stage", "finalize",
                                                    "--agent-output", str(stub_out)
                                                ])

                                                assert rc != 1, f"expected not 1 (--round is required error), got {rc}"
                                                call_args = mock_finalize.call_args
                                                assert call_args[1]["round_n"] == 2, \
                                                    f"expected round_n=2 (existing r1), got {call_args[1]['round_n']}"
                                                print("[case] (d) review-discussion-finalize-round-with-existing")
                                                pass_count += 1
    except Exception as exc:
        print(f"[fail] review-discussion-finalize-round-with-existing: {exc}", file=sys.stderr)
        fail_count += 1

    # Report results
    total = pass_count + fail_count
    print(f"\n{pass_count}/{total} test case(s) passed")

    if fail_count:
        print(f"{fail_count} test case(s) FAILED", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
