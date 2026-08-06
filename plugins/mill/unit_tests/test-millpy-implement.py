"""Unit tests for millpy-implement.py CLI main().

Loads the module under test via importlib and calls main(argv) in-process.
All external I/O (git, LLM, path resolution) is patched in setUp.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import uuid
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _implementer_common  # noqa: E402
import _safe_rmtree  # noqa: E402
import _verify_baseline  # noqa: E402

_IMPLEMENT_PATH = HUB / "plugins" / "mill" / "scripts" / "millpy-implement.py"

_spec = importlib.util.spec_from_file_location("millpy_implement", str(_IMPLEMENT_PATH))
millpy_implement = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_implement)


def _make_fixture(tmp_path: Path) -> None:
    """Create the fake worktree directory tree in tmp_path."""
    plan_dir = tmp_path / "task" / "plan"
    plan_dir.mkdir(parents=True, exist_ok=True)

    overview_text = (
        "# Plan: Test Task\n\n"
        "```yaml\n"
        "task: Test Task\n"
        "slug: test-slug\n"
        "approved: true\n"
        "```\n\n"
        "## Batch Index\n\n"
        "```yaml\n"
        "batches:\n"
        "  - name: test-batch\n"
        "    file: 01-test-batch.md\n"
        "    depends-on: []\n"
        "    verify: null\n"
        "```\n"
    )
    (plan_dir / "00-overview.md").write_text(overview_text, encoding="utf-8")
    (plan_dir / "01-test-batch.md").write_text("# Batch: test-batch\n", encoding="utf-8")

    status_text = (
        "```yaml\n"
        "phase: implementing\n"
        "slug: test-slug\n"
        "task: Test Task\n"
        "branch: test-branch\n"
        "parent: main\n"
        "```\n\n"
        "## Timeline\n\n"
        "```text\n"
        "implementing  2026-01-01T00:00:00Z\n"
        "```\n\n"
        "## Batches\n\n"
        "```yaml\n"
        "batches:\n"
        "  - name: test-batch\n"
        "    state: pending\n"
        "```\n"
    )
    (tmp_path / "task" / "status.md").write_text(status_text, encoding="utf-8")

    millhouse_dir = tmp_path / ".millhouse"
    millhouse_dir.mkdir(parents=True, exist_ok=True)
    (millhouse_dir / "config.local.yaml").write_text("{}", encoding="utf-8")

    wiki_dir = tmp_path / "wiki"
    wiki_dir.mkdir(parents=True, exist_ok=True)
    (wiki_dir / "config.yaml").write_text(
        "roles:\n  implementer:\n    self_fix_rounds: 2\n", encoding="utf-8"
    )

    (tmp_path / "reviews").mkdir(parents=True, exist_ok=True)


class TestMillpyImplement(unittest.TestCase):

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)

        _make_fixture(self.tmp_path)

        self.original_cwd = os.getcwd()
        os.chdir(self.tmp_path)
        self.addCleanup(os.chdir, self.original_cwd)

        def _p(target, attr, **kwargs):
            patcher = unittest.mock.patch.object(target, attr, **kwargs)
            mock_obj = patcher.start()
            self.addCleanup(patcher.stop)
            return mock_obj

        self.mock_resolve_git_root = _p(
            millpy_implement._paths, "resolve_git_root",
            return_value=self.tmp_path,
        )
        self.mock_resolve_hub_path = _p(
            millpy_implement._paths, "resolve_hub_path",
            return_value=self.tmp_path,
        )
        self.mock_resolve_container_path = _p(
            millpy_implement._paths, "resolve_container_path",
            return_value=self.tmp_path.parent,
        )
        self.mock_resolve_active_hub = _p(
            millpy_implement._paths, "resolve_active_hub",
            return_value=self.tmp_path,
        )
        self.mock_resolve_wiki = _p(
            millpy_implement._paths, "resolve_wiki_path",
            return_value=self.tmp_path / "wiki",
        )
        self.mock_load_config = _p(
            millpy_implement._review_common, "load_config",
            return_value={
                "paths": {"status_md": "_mill/status.md"},
                "roles": {"implementer": {"self_fix_rounds": 2, "model": "sonnethigh"}},
                # dispatch is pinned to "subprocess" (not the _agent_dispatch.resolve_dispatch_mode default of "agent") so every pre-existing bare/full-stage test in this file -- none of which has an opinion on dispatch mode -- keeps exercising the non-agent path unaffected by the fail-fast guard added in Card 1. Agent-mode-specific tests override this per-test.
                "llm": {"claude": {"dispatch": "subprocess"}, "implementer_timeout": 1800},
            },
        )
        self.mock_slug_from_branch = _p(
            millpy_implement._marker, "slug_from_branch",
            return_value="test-slug",
        )
        self.mock_read_branch = _p(
            millpy_implement._status, "read_branch",
            return_value="test-branch",
        )
        self.mock_subprocess_run = _p(
            millpy_implement._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="abc1234\n", stderr=""
            ),
        )
        self.mock_uuid4 = _p(
            millpy_implement.uuid, "uuid4",
            return_value=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        )
        self.mock_capture_snapshot = _p(
            millpy_implement._cleanliness, "capture_snapshot",
        )
        self.mock_reviewers_load = _p(
            millpy_implement._reviewers, "load",
            return_value={
                "sonnethigh": {
                    "type": "single",
                    "provider": "claude",
                    "model": "claude-sonnet-4-6",
                    "effort": "high",
                }
            },
        )
        self.mock_reviewers_resolve = _p(
            millpy_implement._reviewers, "resolve",
            return_value={
                "type": "single",
                "provider": "claude",
                "model": "claude-sonnet-4-6",
                "effort": "high",
            },
        )
        self.mock_compute_scope_violations = _p(
            _implementer_common._cleanliness, "compute_scope_violations",
            return_value=[],
        )

    def _run_main(self, argv):
        """Run main(argv) with stdout captured. Returns (rc, captured_stdout)."""
        buf = io.StringIO()
        with unittest.mock.patch("sys.stdout", buf):
            rc = millpy_implement.main(argv)
        return rc, buf.getvalue()

    def test_1_initial_dispatch_success(self):
        """Initial dispatch: pending batch -> success JSON, batch state running."""
        status_path = self.tmp_path / "task" / "status.md"

        # Route rev-parse HEAD to differ between the start_sha capture (first call) and the post-implementation HEAD, so the no-content-commit guard in _forward_output sees HEAD != start_sha and accepts the success report.
        rev_parse_calls = []

        def routing_fn(argv, **kw):
            if argv[1] == "rev-parse":
                rev_parse_calls.append(1)
                # Full 40-char hex SHAs: _is_valid_commit_sha rejects short/non-hex values.
                sha = "0" * 40 if len(rev_parse_calls) == 1 else "1" * 40
                return subprocess.CompletedProcess(args=argv, returncode=0, stdout=sha + "\n", stderr="")
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "success")

        batches = millpy_implement._status.read_batches(status_path)
        self.assertEqual(batches[0]["state"], "running")
        self.assertEqual(batches[0]["implementer_session"], "00000000-0000-0000-0000-000000000001")

    def test_2_initial_dispatch_running_batch(self):
        """Crash-recovery: batch already running -> re-dispatches with new UUID."""
        status_path = self.tmp_path / "task" / "status.md"
        millpy_implement._status.set_batch_field(status_path, "test-batch", "state", "running")

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        batches = millpy_implement._status.read_batches(status_path)
        self.assertEqual(batches[0]["state"], "running")
        self.assertEqual(batches[0]["implementer_session"], "00000000-0000-0000-0000-000000000001")

    def test_3_initial_dispatch_stuck(self):
        """Initial dispatch: implementer returns stuck -> exit 0, stuck JSON."""
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"stuck","stuck_type":"verify","reason":"tests failed"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")

    def test_6_batch_not_found(self):
        """Unknown batch name -> exit 1, no JSON on stdout."""
        rc, out = self._run_main(["nonexistent-batch"])
        self.assertEqual(rc, 1)
        self.assertEqual(out.strip(), "")

    def test_7_malformed_json_from_implementer(self):
        """Implementer output with no valid JSON -> exit 0, stuck/logic JSON."""
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=("implementer output with no json\n", "sess"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")

    def test_agent_mode_full_stage_guard_bare_invocation(self):
        """dispatch: agent + bare invocation (implicit --stage full) -> fail-fast guard fires."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "sonnethigh"}},
            "llm": {"claude": {"dispatch": "agent"}, "implementer_timeout": 1800},
        }
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run"
        ) as mock_run:
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        mock_run.assert_not_called()

    def test_agent_mode_full_stage_guard_explicit_full(self):
        """dispatch: agent + explicit --stage full -> fail-fast guard fires."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "sonnethigh"}},
            "llm": {"claude": {"dispatch": "agent"}, "implementer_timeout": 1800},
        }
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run"
        ) as mock_run:
            rc, out = self._run_main(["test-batch", "--stage", "full"])

        self.assertEqual(rc, 1)
        mock_run.assert_not_called()

    def test_agent_mode_prepare_stage_not_guarded(self):
        """dispatch: agent + --stage prepare -> guard does not fire; prepare proceeds normally."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "sonnethigh"}},
            "llm": {"claude": {"dispatch": "agent"}, "implementer_timeout": 1800},
        }
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_implement._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")

    def test_subprocess_mode_full_stage_not_guarded(self):
        """dispatch: subprocess (setUp's shared default) + bare invocation -> guard does not fire."""
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ) as mock_run:
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        mock_run.assert_called_once()

    def test_9_model_and_effort_from_config(self):
        """Initial dispatch: model and effort read from config and passed to implementer."""
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ) as mock_run:
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        call_kwargs = mock_run.call_args.kwargs
        self.assertEqual(call_kwargs.get("model"), "claude-sonnet-4-6")
        self.assertEqual(call_kwargs.get("effort"), "high")

    def test_10_model_default_fallback(self):
        """When roles.implementer.model is absent, defaults to 'sonnethigh'."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2}},
            # dispatch pinned to "subprocess" (see setUp's own default) so this model-default-fallback test -- which has no opinion on dispatch mode -- is not tripped up by the agent-mode full-stage fail-fast guard.
            "llm": {"claude": {"dispatch": "subprocess"}, "implementer_timeout": 1800},
        }
        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # _reviewers.resolve was called with 'sonnethigh' (the default)
        self.mock_reviewers_resolve.assert_called_with(
            self.mock_reviewers_load.return_value, "sonnethigh"
        )

    def test_11_brief_size_guard_fires(self):
        """Brief exceeds max_implementer_prompt_chars -> stuck/transient, no LLM call."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "haiku"}},
            # dispatch pinned to "subprocess" (see setUp's own default) so this brief-size-guard test -- which has no opinion on dispatch mode -- is not tripped up by the agent-mode full-stage fail-fast guard.
            "llm": {
                "claude": {"dispatch": "subprocess"},
                "implementer_timeout": 1800,
                "max_implementer_prompt_chars": 10,
            },
        }
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="x" * 20):
            with unittest.mock.patch.object(millpy_implement._implementer_claude, "run") as mock_run:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertIn("max_implementer_prompt_chars", data["reason"])
        mock_run.assert_not_called()

    def test_12_brief_size_guard_disabled(self):
        """max_implementer_prompt_chars = 0 (disabled) -> guard does not fire."""
        self.mock_load_config.return_value = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "haiku"}},
            # dispatch pinned to "subprocess" (see setUp's own default) so this brief-size-guard test -- which has no opinion on dispatch mode -- is not tripped up by the agent-mode full-stage fail-fast guard.
            "llm": {
                "claude": {"dispatch": "subprocess"},
                "implementer_timeout": 1800,
                "max_implementer_prompt_chars": 0,
            },
        }
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="x" * 20):
            with unittest.mock.patch.object(
                millpy_implement._implementer_claude, "run",
                return_value=(
                    '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                    "fake-session",
                ),
            ) as mock_run:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # Verify that _implementer_claude.run was called (the guard did not fire)
        mock_run.assert_called_once()

    def test_13_stage_prepare_emits_brief_and_envelope(self):
        """--stage prepare: renders brief, calls emit_prepare, no LLM call."""
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_implement._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        # LLM should not be called in prepare stage
        mock_run.assert_not_called()
        # Output should be prepare JSON envelope
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["role"], "implement")
        self.assertEqual(data["scope"], "test-batch")
        self.assertEqual(data["round"], 1)
        self.assertTrue(data["brief_path"])

    def test_project_root_rebind_uses_resolve_active_hub_not_resolve_hub_path(self):
        """project_root rebinds to resolve_active_hub's value, not resolve_hub_path's escaped one.

        Simulates resolve_hub_path()'s main-worktree-fallback escape: resolve_hub_path still returns
        self.tmp_path (the stale/escaped value),
        but resolve_active_hub -- called after slug resolution, per the rebind fix -- returns a
        distinct decoy directory standing in for the corrected active task worktree.
        briefs_dir (surfaced via --stage prepare's brief_path in the envelope) must resolve under
        the decoy, proving project_root was rebound to resolve_active_hub's return value and not
        left at resolve_hub_path's original, escaped one.
        """
        corrected_root = self.tmp_path / "corrected-worktree"
        corrected_root.mkdir(parents=True, exist_ok=True)
        _make_fixture(corrected_root)
        self.mock_resolve_active_hub.return_value = corrected_root

        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_implement._implementer_claude, "run"
            ) as mock_run:
                rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        data = json.loads(out.strip())
        brief_path = Path(data["brief_path"])
        self.assertEqual(brief_path.parent, corrected_root / "_mill" / "briefs")
        self.assertFalse(brief_path.is_relative_to(self.tmp_path / "_mill" / "briefs"))

    def test_load_config_uses_hub_root_when_hub_in_subdirectory(self):
        """#728 repro: hub lives in a subdirectory of the outer git repo.

        load_config must be invoked with the resolved hub root (project_root / resolve_active_hub's
        corrected root), never the outer git-repo root -- otherwise the hub's own mill-config.yaml
        is silently missed in favor of a template/primary-clone fallback found by walking from
        git_root.
        """
        hub_dir = self.tmp_path / "sub" / "hub"
        hub_dir.mkdir(parents=True, exist_ok=True)
        _make_fixture(hub_dir)
        self.mock_resolve_hub_path.return_value = hub_dir
        self.mock_resolve_active_hub.return_value = hub_dir
        # self.mock_resolve_git_root keeps returning self.tmp_path (the outer root), which must never be passed as load_config's hub_root argument.

        observed_cfgs = []

        def _fake_load_config(hub_root, mill_dir):
            if hub_root == hub_dir:
                cfg = {
                    "paths": {"status_md": "_mill/status.md"},
                    "spawn": {"branch_prefix": "hub-own-prefix"},
                    "roles": {"implementer": {"self_fix_rounds": 2, "model": "sonnethigh"}},
                    "llm": {"claude": {"dispatch": "subprocess"}, "implementer_timeout": 1800},
                }
            else:
                # Stand-in for the template/primary-clone fallback the pre-fix code would silently pick up when passed the outer git-repo root.
                cfg = {
                    "spawn": {"branch_prefix": "template-fallback-prefix"},
                    "llm": {"claude": {"dispatch": "subprocess"}},
                }
            observed_cfgs.append((hub_root, cfg))
            return cfg

        self.mock_load_config.side_effect = _fake_load_config

        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(millpy_implement._implementer_claude, "run") as mock_run:
                rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        self.assertTrue(observed_cfgs)
        for hub_root_arg, cfg in observed_cfgs:
            self.assertEqual(hub_root_arg, hub_dir)
            self.assertEqual(cfg["spawn"]["branch_prefix"], "hub-own-prefix")

    def test_cfg_reload_after_resolve_active_hub_used_for_downstream_values(self):
        """Bootstrap cfg and the resolve_active_hub-corrected reload can genuinely differ.
    Downstream values that read cfg -- self_fix_rounds baked into the rendered brief,
    and the model name passed to _reviewers.resolve -- must come from the reloaded config, not the
        stale bootstrap one.
        """
        corrected_root = self.tmp_path / "corrected-worktree"
        corrected_root.mkdir(parents=True, exist_ok=True)
        _make_fixture(corrected_root)
        self.mock_resolve_active_hub.return_value = corrected_root

        bootstrap_cfg = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 2, "model": "bootstrap-model"}},
            "llm": {"claude": {"dispatch": "subprocess"}, "implementer_timeout": 1800},
        }
        reloaded_cfg = {
            "paths": {"status_md": "_mill/status.md"},
            "roles": {"implementer": {"self_fix_rounds": 9, "model": "reloaded-model"}},
            "llm": {"claude": {"dispatch": "subprocess"}, "implementer_timeout": 1800},
        }

        def _fake_load_config(hub_root, mill_dir):
            return reloaded_cfg if hub_root == corrected_root else bootstrap_cfg

        self.mock_load_config.side_effect = _fake_load_config

        rendered_tokens = {}

        def _capture_render(template_path, tokens):
            rendered_tokens.update(tokens)
            return "Brief text"

        with unittest.mock.patch.object(millpy_implement._render, "render", side_effect=_capture_render):
            with unittest.mock.patch.object(millpy_implement._implementer_claude, "run") as mock_run:
                rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        mock_run.assert_not_called()
        # self_fix_rounds baked into the brief must come from the reloaded config (9), never the bootstrap config's value (2).
        self.assertEqual(rendered_tokens.get("SELF_FIX_ROUNDS"), "9")
        # model_name passed to _reviewers.resolve must come from the reloaded config too.
        self.mock_reviewers_resolve.assert_called_with(
            self.mock_reviewers_load.return_value, "reloaded-model"
        )

    def test_14_stage_finalize_reads_agent_output(self):
        """--stage finalize: reads agent output file, calls finalize_from_output."""
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        # _forward_output re-derives commit_sha via `git rev-parse HEAD` and validates it (_is_valid_commit_sha);
        # the setUp default ("abc1234") is too short/non-hex.
        self.mock_subprocess_run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="a" * 40 + "\n", stderr=""
        )

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run"
        ) as mock_run:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        # LLM should not be called in finalize stage
        mock_run.assert_not_called()
        # Output should be the agent output processed by _forward_output
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "success")

    def test_commits_made_nonzero_on_llm_error(self):
        """LLMError with commits made: rev-list returns 3 -> stuck JSON includes commits_made=3."""
        def routing_fn(argv, **kw):
            if argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="3\n", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            side_effect=millpy_implement._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertEqual(data["commits_made"], 3)

    def test_commits_made_zero_on_llm_error_no_commits(self):
        """LLMError with no commits made: rev-list returns 0 -> stuck JSON includes commits_made=0."""
        def routing_fn(argv, **kw):
            if argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="0\n", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            side_effect=millpy_implement._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertEqual(data["commits_made"], 0)

    def test_commits_made_zero_on_rev_list_failure(self):
        """LLMError with rev-list failure: returncode=1 -> commits_made defaults to 0."""
        def routing_fn(argv, **kw):
            if argv[1] == "rev-list":
                return subprocess.CompletedProcess(
                    args=argv, returncode=1, stdout="", stderr="error"
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            side_effect=millpy_implement._llm_claude.LLMError("timeout"),
        ):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        data = json.loads(out.strip().splitlines()[-1])
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "transient")
        self.assertEqual(data["commits_made"], 0)

    def test_skip_start_commit_on_refire(self):
        """Re-fire with empty staged diff: staged-emptiness check skips the start-batch commit.

        Guards the atomic-commit mechanics (#563): when git diff --cached --quiet exits 0 (nothing
        staged), git_commit must not be called.
        This happens when prepare already ran once and all state is committed -- the snapshot and
        status.md are unchanged.
        """

        def routing_fn(argv, **kw):
            if argv[1] == "diff":
                # git diff --cached --quiet: exit 0 means nothing new is staged.
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ) as mock_impl_run:
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit"
            ) as mock_git_commit:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # git_commit must NOT be called when the staged diff is empty.
        mock_git_commit.assert_not_called()
        # The implementer session must still be dispatched.
        mock_impl_run.assert_called_once()

    def test_no_skip_start_commit_on_fresh_fire(self):
        """Fresh fire with non-empty staged diff: staged-emptiness check commits and pushes.

        Guards the atomic-commit mechanics (#563): when git diff --cached --quiet exits non-zero
        (changes staged), git_commit must be called exactly once, followed by push.
        """
        def routing_fn(argv, **kw):
            if argv[1] == "diff":
                # git diff --cached --quiet: exit 1 means changes are staged.
                return subprocess.CompletedProcess(
                    args=argv, returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ) as mock_git_commit:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # git_commit must be called exactly once when the staged diff is non-empty.
        mock_git_commit.assert_called_once()

    def test_16_stage_finalize_accepts_round_flag(self):
        """--stage finalize accepts --round flag with no argparse error, ignores CLI value.

        Mirrors test_15_stage_finalize_accepts_session_and_start_sha_flags for #568: the --round
        flag is accepted for CLI-shape parity with millpy-fix.py but is ignored;
        the finalize branch reads start_sha and implementer_session from status.md.
        """
        status_path = self.tmp_path / "task" / "status.md"
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        # Write sentinel values to status.md that differ from the CLI flags.
        millpy_implement._status.set_batch_field(status_path, "test-batch", "start_sha", "STATUS_SHA")
        millpy_implement._status.set_batch_field(status_path, "test-batch", "implementer_session", "STATUS_SESSION")

        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
                "--round", "1",
                "--session-id", "CLI_SESSION",
                "--start-sha", "CLI_SHA",
            ])

        # rc==0 confirms argparse did not raise for --round (no "unrecognized arguments").
        self.assertEqual(rc, 0)
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        # Finalize must use status.md values, not the CLI --round/--session-id/--start-sha args.
        self.assertEqual(call_kwargs.get("start_sha"), "STATUS_SHA")
        self.assertEqual(call_kwargs.get("session_id"), "STATUS_SESSION")

    def test_prepare_retry_dirty_staged_commits(self):
        """Re-fire with non-empty staged diff (regenerated session): git_commit IS called.

        Covers the atomicity fix (#563): on a retry, the fresh implementer_session UUID written to
        status.md dirtied the file;
        git diff --cached --quiet exits non-zero, so git_commit must fire and the commit message
        must use the expected start-batch format.
        """
        batch_name = "test-batch"

        def routing_fn(argv, **kw):
            if argv[1] == "diff":
                # Simulate status.md dirtied by the new session UUID -- something is staged.
                return subprocess.CompletedProcess(
                    args=argv, returncode=1, stdout="", stderr=""
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = routing_fn

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="", stderr=""
                ),
            ) as mock_git_commit:
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        # git_commit must be called -- the atomic retry must commit the session write.
        mock_git_commit.assert_called_once()
        # The commit message must match the start-batch format so the finalize commit detection in _implementer_common still recognises it.
        commit_msg = mock_git_commit.call_args[0][1]
        self.assertEqual(commit_msg, f"mill-go: start batch {batch_name}")

    def test_15_stage_finalize_accepts_session_and_start_sha_flags(self):
        """--stage finalize accepts --session-id and --start-sha flags, still uses status.md values."""
        status_path = self.tmp_path / "task" / "status.md"
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        # Set distinct sentinel values in status.md
        millpy_implement._status.set_batch_field(status_path, "test-batch", "start_sha", "STATUS_SHA")
        millpy_implement._status.set_batch_field(status_path, "test-batch", "implementer_session", "STATUS_SESSION")

        # Patch finalize_from_output to capture the call
        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
                "--session-id", "CLI_SESSION",
                "--start-sha", "CLI_SHA",
            ])

        # Verify argparse succeeded (rc == 0)
        self.assertEqual(rc, 0)

        # Verify finalize_from_output was called once
        mock_finalize.assert_called_once()

        # Verify the kwargs passed to finalize_from_output contain status.md values, NOT CLI args
        call_kwargs = mock_finalize.call_args.kwargs
        self.assertEqual(call_kwargs.get("start_sha"), "STATUS_SHA")
        self.assertEqual(call_kwargs.get("session_id"), "STATUS_SESSION")

    def test_finalize_stage_resolves_batch_verify_command(self):
        """--stage finalize: batch verify command is resolved and passed to finalize_from_output."""
        # Update the batch file to include a verify command in frontmatter
        plan_dir = self.tmp_path / "task" / "plan"
        batch_file = plan_dir / "01-test-batch.md"
        batch_file.write_text(
            "```yaml\n"
            "task: Test Task\n"
            "verify: exit 0\n"
            "```\n\n"
            "# Batch: test-batch\n",
            encoding="utf-8"
        )

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        # Patch finalize_from_output to capture the verify_cmd argument
        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0,
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        # Verify that finalize_from_output was called with the resolved verify_cmd
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        self.assertEqual(call_kwargs.get("verify_cmd"), "exit 0")

    def test_parent_branch_token_in_render_map(self):
        """PARENT_BRANCH token is present in the render map with the resolved parent value."""
        # Patch _parent_branch.resolve to return a known string
        with unittest.mock.patch.object(
            millpy_implement._parent_branch, "resolve",
            return_value="main",
        ):
            captured_tokens: dict = {}

            def capture_render(template_path, tokens):
                captured_tokens.update(tokens)
                # Return a minimal rendered string to avoid token-missing KeyError
                return "rendered"

            with unittest.mock.patch.object(millpy_implement._render, "render", side_effect=capture_render):
                with unittest.mock.patch.object(
                    millpy_implement._implementer_claude, "run",
                    return_value=(
                        '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                        "fake-session",
                    ),
                ):
                    # Use --stage prepare so the render call fires without needing a real LLM
                    rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        # The key must be present and equal to the resolved parent value
        self.assertIn("PARENT_BRANCH", captured_tokens)
        self.assertEqual(captured_tokens["PARENT_BRANCH"], "main")

    def test_parent_branch_token_empty_string_when_unresolvable(self):
        """PARENT_BRANCH token is empty string (not None) when parent_branch cannot be resolved."""
        # Patch _parent_branch.resolve to raise so parent_branch falls back to None
        with unittest.mock.patch.object(
            millpy_implement._parent_branch, "resolve",
            side_effect=Exception("no parent"),
        ):
            captured_tokens: dict = {}

            def capture_render(template_path, tokens):
                captured_tokens.update(tokens)
                return "rendered"

            with unittest.mock.patch.object(millpy_implement._render, "render", side_effect=capture_render):
                with unittest.mock.patch.object(
                    millpy_implement._implementer_claude, "run",
                    return_value=(
                        '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                        "fake-session",
                    ),
                ):
                    rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        # When parent is unresolvable the token must be "" (empty string), never None
        self.assertIn("PARENT_BRANCH", captured_tokens)
        self.assertEqual(captured_tokens["PARENT_BRANCH"], "")
        self.assertIsNotNone(captured_tokens["PARENT_BRANCH"])

    def test_overview_verify_threaded_as_module_wide(self):
        """Overview with non-null top-level verify: threads it as module_wide_verify_cmd."""
        plan_dir = self.tmp_path / "task" / "plan"
        # Write an overview with a non-null top-level verify command
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_with_verify, encoding="utf-8")

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0,
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        # The overview-level verify command must be threaded as module_wide_verify_cmd
        self.assertEqual(call_kwargs.get("module_wide_verify_cmd"), "exit 0")

    def test_overview_verify_null_passes_none_as_module_wide(self):
        """Overview with null top-level verify: passes None as module_wide_verify_cmd."""
        # The default fixture already has verify: null in the overview (via _make_fixture)
        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with unittest.mock.patch.object(
            millpy_implement, "finalize_from_output",
            return_value=0,
        ) as mock_finalize:
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        # A null overview verify must produce None (not the string "null")
        self.assertIsNone(call_kwargs.get("module_wide_verify_cmd"))

    def test_finalize_stage_batch_verify_cwd_hub_resolves_nested_project_root(self):
        """Nested layout: batch verify: {cwd: hub, command: ...} resolves cwd_override to project_root."""
        nested_hub = self.tmp_path / "hub"
        nested_hub.mkdir(parents=True, exist_ok=True)
        _make_fixture(nested_hub)

        plan_dir = nested_hub / "task" / "plan"
        batch_file = plan_dir / "01-test-batch.md"
        batch_file.write_text(
            "```yaml\n"
            "task: Test Task\n"
            "verify:\n"
            "  cwd: hub\n"
            "  command: exit 0\n"
            "```\n\n"
            "# Batch: test-batch\n",
            encoding="utf-8"
        )

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with (
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_hub_path", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_git_root", return_value=self.tmp_path
            ),
            # The rebind (Card 9) supersedes resolve_hub_path's value with resolve_active_hub's for project_root -- override it here too so this nested-hub simulation still resolves project_root to nested_hub.
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_active_hub", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement, "finalize_from_output", return_value=0
            ) as mock_finalize,
        ):
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        self.assertEqual(call_kwargs.get("verify_cmd"), "exit 0")
        self.assertEqual(call_kwargs.get("cwd_override"), nested_hub)

    def test_overview_verify_cwd_hub_resolves_module_wide_cwd_override(self):
        """Nested layout: overview verify: {cwd: hub, command: ...} resolves module_wide_cwd_override to project_root."""
        nested_hub = self.tmp_path / "hub"
        nested_hub.mkdir(parents=True, exist_ok=True)
        _make_fixture(nested_hub)

        plan_dir = nested_hub / "task" / "plan"
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify:\n"
            "  cwd: hub\n"
            "  command: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_with_verify, encoding="utf-8")

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            '{"status":"success","commit_sha":"xyz","session_id":"fake"}\n',
            encoding="utf-8"
        )

        with (
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_hub_path", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_git_root", return_value=self.tmp_path
            ),
            # The rebind (Card 9) supersedes resolve_hub_path's value with resolve_active_hub's for project_root -- override it here too so this nested-hub simulation still resolves project_root to nested_hub.
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_active_hub", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement, "finalize_from_output", return_value=0
            ) as mock_finalize,
        ):
            rc, out = self._run_main([
                "test-batch",
                "--stage", "finalize",
                "--agent-output", str(agent_output_path),
            ])

        self.assertEqual(rc, 0)
        mock_finalize.assert_called_once()
        call_kwargs = mock_finalize.call_args.kwargs
        self.assertEqual(call_kwargs.get("module_wide_verify_cmd"), "exit 0")
        self.assertEqual(call_kwargs.get("module_wide_cwd_override"), nested_hub)

    def test_baseline_stage_cwd_hub_derives_relative_fragment_for_compute_baseline(self):
        """Nested layout: overview verify: {cwd: hub, ...} makes _run_baseline_stage pass a hub-relative cwd_override_relative to compute_baseline."""
        nested_hub = self.tmp_path / "hub"
        nested_hub.mkdir(parents=True, exist_ok=True)
        _make_fixture(nested_hub)

        plan_dir = nested_hub / "task" / "plan"
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify:\n"
            "  cwd: hub\n"
            "  command: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_with_verify, encoding="utf-8")

        with (
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_hub_path", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_git_root", return_value=self.tmp_path
            ),
            # The rebind (Card 9) supersedes resolve_hub_path's value with resolve_active_hub's for project_root -- override it here too so this nested-hub simulation still resolves project_root to nested_hub.
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_active_hub", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement._status, "get_module_verify_baseline", return_value=None
            ),
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "compute_baseline", return_value="clean"
            ) as mock_compute_baseline,
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        mock_compute_baseline.assert_called_once()
        call_args, call_kwargs = mock_compute_baseline.call_args
        self.assertEqual(call_args[0], nested_hub)
        self.assertEqual(call_args[1], self.tmp_path)
        self.assertEqual(call_args[3], "exit 0")
        self.assertEqual(call_kwargs.get("cwd_override_relative"), Path("hub"))

    def test_baseline_stage_cwd_git_root_passes_none_relative_fragment(self):
        """Nested layout: overview verify: {cwd: git_root, ...} makes _run_baseline_stage pass cwd_override_relative=None."""
        nested_hub = self.tmp_path / "hub"
        nested_hub.mkdir(parents=True, exist_ok=True)
        _make_fixture(nested_hub)

        plan_dir = nested_hub / "task" / "plan"
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify:\n"
            "  cwd: git_root\n"
            "  command: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_with_verify, encoding="utf-8")

        with (
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_hub_path", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_git_root", return_value=self.tmp_path
            ),
            # The rebind (Card 9) supersedes resolve_hub_path's value with resolve_active_hub's for project_root -- override it here too so this nested-hub simulation still resolves project_root to nested_hub.
            unittest.mock.patch.object(
                millpy_implement._paths, "resolve_active_hub", return_value=nested_hub
            ),
            unittest.mock.patch.object(
                millpy_implement._status, "get_module_verify_baseline", return_value=None
            ),
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "compute_baseline", return_value="clean"
            ) as mock_compute_baseline,
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        mock_compute_baseline.assert_called_once()
        _, call_kwargs = mock_compute_baseline.call_args
        self.assertIsNone(call_kwargs.get("cwd_override_relative"))

    def test_baseline_stage_plain_string_verify_passes_none_relative_fragment(self):
        """Flat layout: plain-string overview verify: makes _run_baseline_stage pass cwd_override_relative=None."""
        # Uses the default fixture (verify: null in the batch, flat layout hub == git_root), but with a non-null plain-string overview verify.
        plan_dir = self.tmp_path / "task" / "plan"
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (plan_dir / "00-overview.md").write_text(overview_with_verify, encoding="utf-8")

        with (
            unittest.mock.patch.object(
                millpy_implement._status, "get_module_verify_baseline", return_value=None
            ),
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "compute_baseline", return_value="clean"
            ) as mock_compute_baseline,
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        mock_compute_baseline.assert_called_once()
        _, call_kwargs = mock_compute_baseline.call_args
        self.assertIsNone(call_kwargs.get("cwd_override_relative"))

    def _write_two_batch_fixture(self, batch_a_verify_baseline=None, batch_b_verify_baseline=None):
        """
        Write a plan/status fixture with two batches (batch-a, batch-b), each declaring its own
        plain-string `verify:` frontmatter command, and an overview with `verify: null` (no
        module-wide command configured).

        `batch_a_verify_baseline`/`batch_b_verify_baseline`, when not None, seed that batch's
        `verify_baseline_failures` field in status.md's `## Batches` section -- simulating a prior
        invocation that already computed a baseline for that batch.
        """
        plan_dir = self.tmp_path / "task" / "plan"
        (plan_dir / "01-batch-a.md").write_text(
            "```yaml\nbatch: batch-a\nverify: echo a\n```\n\n# Batch: batch-a\n",
            encoding="utf-8",
        )
        (plan_dir / "02-batch-b.md").write_text(
            "```yaml\nbatch: batch-b\nverify: echo b\n```\n\n# Batch: batch-b\n",
            encoding="utf-8",
        )

        def _batch_yaml(name, baseline):
            if baseline is None:
                return f"  - name: {name}\n    state: pending\n"
            return (
                f"  - name: {name}\n    state: pending\n"
                f"    verify_baseline_failures: {baseline!r}\n"
            )

        status_path = self.tmp_path / "task" / "status.md"
        status_path.write_text(
            "```yaml\n"
            "phase: implementing\n"
            "slug: test-slug\n"
            "task: Test Task\n"
            "branch: test-branch\n"
            "parent: main\n"
            "```\n\n"
            "## Timeline\n\n"
            "```text\n"
            "implementing  2026-01-01T00:00:00Z\n"
            "```\n\n"
            "## Batches\n\n"
            "```yaml\n"
            "batches:\n"
            + _batch_yaml("batch-a", batch_a_verify_baseline)
            + _batch_yaml("batch-b", batch_b_verify_baseline)
            + "```\n",
            encoding="utf-8",
        )

    def test_baseline_stage_prints_exactly_two_lines_module_wide_then_per_batch(self):
        """Module-wide + per-batch both need computing -> exactly two JSON lines, module_wide first."""
        self._write_two_batch_fixture()
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (self.tmp_path / "task" / "plan" / "00-overview.md").write_text(
            overview_with_verify, encoding="utf-8"
        )

        with (
            unittest.mock.patch.object(
                millpy_implement._status, "get_module_verify_baseline", return_value=None
            ),
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "_checkout_parent_branch",
                return_value=self.tmp_path / "checkout",
            ),
            unittest.mock.patch.object(millpy_implement._verify_baseline, "_link_dependency_dirs"),
            unittest.mock.patch.object(millpy_implement._worktree, "remove_safe"),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "_run_module_wide_verify_algorithm",
                return_value="clean",
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "compute_batch_baselines",
                side_effect=lambda commands, checkout_path, project_root: {commands[0][0]: []},
            ),
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 2)
        module_wide = json.loads(lines[0])
        per_batch = json.loads(lines[1])
        self.assertEqual(module_wide, {"stage": "baseline", "substage": "module_wide", "result": "computed", "value": "clean"})
        self.assertEqual(per_batch["substage"], "per_batch")
        self.assertEqual(sorted(per_batch["computed"]), ["batch-a", "batch-b"])
        self.assertEqual(per_batch["cached"], [])
        self.assertEqual(per_batch["errored"], {})

    def test_baseline_stage_per_batch_idempotency_skips_already_cached_batch(self):
        """batch-a already has a stored baseline -> not recomputed; batch-b computed."""
        self._write_two_batch_fixture(batch_a_verify_baseline=[])

        with (
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "_checkout_parent_branch",
                return_value=self.tmp_path / "checkout",
            ),
            unittest.mock.patch.object(millpy_implement._verify_baseline, "_link_dependency_dirs"),
            unittest.mock.patch.object(millpy_implement._worktree, "remove_safe"),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "compute_batch_baselines"
            ) as mock_compute,
        ):
            mock_compute.side_effect = lambda commands, checkout_path, project_root: {
                commands[0][0]: ["failure-b"]
            }
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        mock_compute.assert_called_once()
        lines = out.strip().splitlines()
        module_wide = json.loads(lines[0])
        per_batch = json.loads(lines[1])
        # No module-wide verify configured in this fixture's overview.
        self.assertEqual(module_wide["result"], "skipped")
        self.assertEqual(per_batch["computed"], ["batch-b"])
        self.assertEqual(per_batch["cached"], ["batch-a"])
        self.assertEqual(per_batch["errored"], {})

        status_path = self.tmp_path / "task" / "status.md"
        batches = {b["name"]: b for b in millpy_implement._status.read_batches(status_path)}
        # batch-a's stored value is untouched.
        self.assertEqual(batches["batch-a"]["verify_baseline_failures"], [])
        self.assertEqual(batches["batch-b"]["verify_baseline_failures"], ["failure-b"])

    def test_baseline_stage_per_batch_failure_isolation(self):
        """One batch's computation raises -> sibling batch still computed and persisted."""
        self._write_two_batch_fixture()

        def _side_effect(commands, checkout_path, project_root):
            name = commands[0][0]
            if name == "batch-a":
                raise RuntimeError("boom")
            return {name: ["failure-b"]}

        with (
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "_checkout_parent_branch",
                return_value=self.tmp_path / "checkout",
            ),
            unittest.mock.patch.object(millpy_implement._verify_baseline, "_link_dependency_dirs"),
            unittest.mock.patch.object(millpy_implement._worktree, "remove_safe"),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "compute_batch_baselines",
                side_effect=_side_effect,
            ),
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        module_wide = json.loads(lines[0])
        per_batch = json.loads(lines[1])
        # Module-wide sub-step is unaffected (no module-wide verify configured here).
        self.assertEqual(module_wide["result"], "skipped")
        self.assertEqual(per_batch["computed"], ["batch-b"])
        self.assertEqual(per_batch["errored"], {"batch-a": "boom"})

        status_path = self.tmp_path / "task" / "status.md"
        batches = {b["name"]: b for b in millpy_implement._status.read_batches(status_path)}
        self.assertNotIn("verify_baseline_failures", batches["batch-a"])
        self.assertEqual(batches["batch-b"]["verify_baseline_failures"], ["failure-b"])

    def test_baseline_stage_shared_checkout_failure_module_wide_unaffected(self):
        """Checkout fails, no module-wide work needed this round -> module-wide line unaffected, all batches errored."""
        self._write_two_batch_fixture()
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (self.tmp_path / "task" / "plan" / "00-overview.md").write_text(
            overview_with_verify, encoding="utf-8"
        )

        with (
            # Module-wide baseline already cached -- module-wide has nothing to compute this round.
            unittest.mock.patch.object(
                millpy_implement._status, "get_module_verify_baseline", return_value="clean"
            ),
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "_checkout_parent_branch",
                side_effect=RuntimeError("worktree add failed"),
            ),
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        module_wide = json.loads(lines[0])
        per_batch = json.loads(lines[1])
        # Unaffected: reports its own cached value exactly as it would without the failure.
        self.assertEqual(module_wide, {"stage": "baseline", "substage": "module_wide", "result": "cached", "value": "clean"})
        self.assertEqual(per_batch["computed"], [])
        self.assertIn("batch-a", per_batch["errored"])
        self.assertIn("batch-b", per_batch["errored"])

    def test_baseline_stage_shared_checkout_failure_module_wide_also_errored(self):
        """Checkout fails, module-wide ALSO needed computing this round -> module-wide line also reports error."""
        self._write_two_batch_fixture()
        overview_with_verify = (
            "# Plan: Test Task\n\n"
            "```yaml\n"
            "task: Test Task\n"
            "slug: test-slug\n"
            "approved: true\n"
            "verify: exit 0\n"
            "```\n\n"
            "## Batch Index\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: test-batch\n"
            "    file: 01-test-batch.md\n"
            "    depends-on: []\n"
            "    verify: null\n"
            "```\n"
        )
        (self.tmp_path / "task" / "plan" / "00-overview.md").write_text(
            overview_with_verify, encoding="utf-8"
        )

        with (
            unittest.mock.patch.object(
                millpy_implement._status, "get_module_verify_baseline", return_value=None
            ),
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "_checkout_parent_branch",
                side_effect=RuntimeError("worktree add failed"),
            ),
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        lines = out.strip().splitlines()
        module_wide = json.loads(lines[0])
        per_batch = json.loads(lines[1])
        self.assertEqual(module_wide["substage"], "module_wide")
        self.assertEqual(module_wide["result"], "error")
        self.assertEqual(per_batch["computed"], [])
        self.assertIn("batch-a", per_batch["errored"])
        self.assertIn("batch-b", per_batch["errored"])

    def test_baseline_stage_enumerates_batch_own_verify_despite_later_deletes(self):
        """A batch whose own verify: names a path a LATER batch's Deletes: removes still gets a baseline."""
        plan_dir = self.tmp_path / "task" / "plan"
        (plan_dir / "01-batch-a.md").write_text(
            "```yaml\nbatch: batch-a\nverify: test tools/x\n```\n\n"
            "# Batch: batch-a\n\n"
            "- **Deletes:** none\n",
            encoding="utf-8",
        )
        (plan_dir / "02-batch-b.md").write_text(
            "```yaml\nbatch: batch-b\nverify: echo b\n```\n\n"
            "# Batch: batch-b\n\n"
            "- **Deletes:** `tools/x`\n",
            encoding="utf-8",
        )
        status_path = self.tmp_path / "task" / "status.md"
        status_path.write_text(
            "```yaml\n"
            "phase: implementing\n"
            "slug: test-slug\n"
            "task: Test Task\n"
            "branch: test-branch\n"
            "parent: main\n"
            "```\n\n"
            "## Timeline\n\n"
            "```text\n"
            "implementing  2026-01-01T00:00:00Z\n"
            "```\n\n"
            "## Batches\n\n"
            "```yaml\n"
            "batches:\n"
            "  - name: batch-a\n"
            "    state: pending\n"
            "  - name: batch-b\n"
            "    state: pending\n"
            "```\n",
            encoding="utf-8",
        )

        with (
            unittest.mock.patch.object(
                millpy_implement._parent_branch, "resolve", return_value="main"
            ),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "_checkout_parent_branch",
                return_value=self.tmp_path / "checkout",
            ),
            unittest.mock.patch.object(millpy_implement._verify_baseline, "_link_dependency_dirs"),
            unittest.mock.patch.object(millpy_implement._worktree, "remove_safe"),
            unittest.mock.patch.object(
                millpy_implement._verify_baseline, "compute_batch_baselines",
                side_effect=lambda commands, checkout_path, project_root: {commands[0][0]: []},
            ),
        ):
            rc, out = self._run_main(["--stage", "baseline"])

        self.assertEqual(rc, 0)
        per_batch = json.loads(out.strip().splitlines()[1])
        # Unlike `_plan_dag.iter_batch_verifies` (which would suppress batch-a's verify since batch-b's Deletes: names the same path), direct frontmatter enumeration still computes batch-a's baseline.
        self.assertIn("batch-a", per_batch["computed"])
        self.assertIn("batch-b", per_batch["computed"])

    def test_real_brief_renders_parent_branch_token(self):
        """Rendering the real implementer-brief.md substitutes <PARENT_BRANCH> with the parent value."""
        plugin_root = HUB / "plugins" / "mill"
        template_path = plugin_root / "templates" / "implementer-brief.md"

        # Build a minimal token map that satisfies all required tokens in the brief, including START_SHA which was added in batch 2.
        tokens = {
            "TASK_TITLE": "Test Task",
            "SLUG": "test-slug",
            "BATCH_NAME": "test-batch",
            "BATCH_FILE": "/path/to/batch.md",
            "OVERVIEW_FILE": "/path/to/overview.md",
            "PROJECT_ROOT": "/path/to/root",
            "WIKI_PATH": "/path/to/wiki",
            "SELF_FIX_ROUNDS": "2",
            "ROUND": "1",
            "SESSION_ID": "test-session-uuid",
            "LANGUAGE_SKILLS": "",
            "PARENT_BRANCH": "main",
            "START_SHA": "",
        }

        import _render
        rendered = _render.render(template_path, tokens)
        # The rendered text must contain the substituted parent value, not the raw token
        self.assertIn("main", rendered)
        self.assertNotIn("<PARENT_BRANCH>", rendered)

    def test_real_brief_renders_parent_branch_empty_when_unresolvable(self):
        """Rendering the real implementer-brief.md with empty PARENT_BRANCH substitutes empty string."""
        plugin_root = HUB / "plugins" / "mill"
        template_path = plugin_root / "templates" / "implementer-brief.md"

        tokens = {
            "TASK_TITLE": "Test Task",
            "SLUG": "test-slug",
            "BATCH_NAME": "test-batch",
            "BATCH_FILE": "/path/to/batch.md",
            "OVERVIEW_FILE": "/path/to/overview.md",
            "PROJECT_ROOT": "/path/to/root",
            "WIKI_PATH": "/path/to/wiki",
            "SELF_FIX_ROUNDS": "2",
            "ROUND": "1",
            "SESSION_ID": "test-session-uuid",
            "LANGUAGE_SKILLS": "",
            "PARENT_BRANCH": "",
            "START_SHA": "",
        }

        import _render
        rendered = _render.render(template_path, tokens)
        # The raw token placeholder must not appear in the output
        self.assertNotIn("<PARENT_BRANCH>", rendered)
        # The literal string "None" must not appear where the token was
        self.assertNotIn("None", rendered)


    def test_resume_incomplete_preserves_start_sha(self):
        """--resume-incomplete: prepare reads start_sha from status.md, skips set_batch_fields and
        capture_snapshot.

        Verifies that the resume path does not re-capture HEAD or overwrite the original
        start_sha/implementer_session in status.md.
        The original start_sha must survive unchanged so that finalize can count content commits
        from the correct baseline.
        Also verifies that capture_snapshot is NOT called, preserving the original new-dirt baseline
        snapshot written during the first dispatch.
        """
        status_path = self.tmp_path / "task" / "status.md"

        # Write the original start_sha and implementer_session into status.md so the resume path can read them.
        original_start_sha = "original_start_sha_abc123"
        original_session = "original-session-uuid-1234"
        millpy_implement._status.set_batch_fields(
            status_path,
            "test-batch",
            {
                "state": "running",
                "start_sha": original_start_sha,
                "implementer_session": original_session,
            },
        )

        # Patch set_batch_fields to detect whether it is called on the resume path.
        with unittest.mock.patch.object(
            millpy_implement._status, "set_batch_fields"
        ) as mock_set_batch_fields:
            with unittest.mock.patch.object(
                millpy_implement._render, "render", return_value="Brief text"
            ):
                rc, out = self._run_main(
                    ["test-batch", "--stage", "prepare", "--resume-incomplete"]
                )

        self.assertEqual(rc, 0)
        # capture_snapshot must NOT be called on the resume path.
        self.mock_capture_snapshot.assert_not_called()
        # set_batch_fields must NOT be called on the resume path (the original start_sha and implementer_session must remain untouched in status.md).
        mock_set_batch_fields.assert_not_called()

        # Confirm the original start_sha is still intact in status.md.
        batches = millpy_implement._status.read_batches(status_path)
        batch_entry = next(b for b in batches if b["name"] == "test-batch")
        self.assertEqual(batch_entry["start_sha"], original_start_sha)
        self.assertEqual(batch_entry["implementer_session"], original_session)

    def test_resume_incomplete_start_sha_token_in_render_dict(self):
        """--resume-incomplete: START_SHA token equals preserved sha;
SESSION_ID equals retained session.

        On a resume dispatch the rendered brief must receive the original start_sha as START_SHA so
        the implementer can identify already-committed cards.
        The SESSION_ID token must match the retained implementer_session from status.md (not a fresh
        UUID) so the finalize-reported session_id is consistent with the brief.
        On a normal (non-resume) dispatch START_SHA must be the empty string.
        """
        status_path = self.tmp_path / "task" / "status.md"
        original_start_sha = "original_sha_for_token_test"
        original_session = "retained-session-uuid-5678"
        millpy_implement._status.set_batch_fields(
            status_path,
            "test-batch",
            {
                "state": "running",
                "start_sha": original_start_sha,
                "implementer_session": original_session,
            },
        )

        # Capture the token dict passed to _render.render on the resume path.
        captured_resume_tokens: dict = {}

        def capture_render(template_path, tokens):
            captured_resume_tokens.update(tokens)
            return "Brief text"

        with unittest.mock.patch.object(
            millpy_implement._render, "render", side_effect=capture_render
        ):
            rc, _ = self._run_main(
                ["test-batch", "--stage", "prepare", "--resume-incomplete"]
            )

        self.assertEqual(rc, 0)
        # START_SHA must be the preserved sha from status.md, not empty string.
        self.assertIn("START_SHA", captured_resume_tokens)
        self.assertEqual(captured_resume_tokens["START_SHA"], original_start_sha)
        # SESSION_ID must match the retained implementer_session from status.md.
        self.assertIn("SESSION_ID", captured_resume_tokens)
        self.assertEqual(captured_resume_tokens["SESSION_ID"], original_session)

        # On a normal (non-resume) dispatch START_SHA must be empty string.
        captured_normal_tokens: dict = {}

        def capture_render_normal(template_path, tokens):
            captured_normal_tokens.update(tokens)
            return "Brief text"

        with unittest.mock.patch.object(
            millpy_implement._render, "render", side_effect=capture_render_normal
        ):
            rc2, _ = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc2, 0)
        self.assertIn("START_SHA", captured_normal_tokens)
        self.assertEqual(captured_normal_tokens["START_SHA"], "")

    def test_resume_incomplete_finalize_success_when_complete(self):
        """Finalize after resume emits success when content commits >= card_count.

        Sets up a batch file with one card heading so card_count=1.
        Mocks git to return two commits since start_sha (one housekeeping + one content), so
        _content_commit_count returns 1. The agent output reports success;
        finalize must emit success, not incomplete.
        """
        status_path = self.tmp_path / "task" / "status.md"
        plan_dir = self.tmp_path / "task" / "plan"
        original_start_sha = "original_sha_for_finalize_test"
        original_session = "finalize-session-uuid-9999"

        # Write a batch file with one card heading so card_count=1.
        batch_file = plan_dir / "01-test-batch.md"
        batch_file.write_text(
            "```yaml\ntask: Test\nverify: null\n```\n\n"
            "### Card 1: the only card\n\n"
            "- **Requirements:** Implement it.\n"
            "- **Commit:** feat(card1): implement\n",
            encoding="utf-8",
        )

        # Write start_sha into status.md so finalize reads it.
        millpy_implement._status.set_batch_fields(
            status_path,
            "test-batch",
            {
                "state": "running",
                "start_sha": original_start_sha,
                "implementer_session": original_session,
            },
        )

        agent_output_path = self.tmp_path / "agent-output.txt"
        agent_output_path.write_text(
            f'{{"status":"success","commit_sha":"end_sha","session_id":"{original_session}"}}\n',
            encoding="utf-8",
        )

        def routing_fn(argv, **kw):
            # rev-parse HEAD: return a SHA different from start_sha so no-content guard passes.
            # Full 40-char hex: _is_valid_commit_sha rejects the short "end_sha" placeholder.
            if len(argv) >= 2 and argv[1] == "rev-parse":
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout=("e" * 40) + "\n", stderr=""
                )
            # rev-list --count: return 2 (1 housekeeping + 1 content commit).
            if "rev-list" in argv and "--count" in argv:
                return subprocess.CompletedProcess(
                    args=argv, returncode=0, stdout="2\n", stderr=""
                )
            # git log --pretty=%s: return subjects showing one housekeeping + one content commit.
            if "log" in argv and "--pretty=%s" in argv:
                return subprocess.CompletedProcess(
                    args=argv,
                    returncode=0,
                    stdout="feat(card1): implement\nmill-go: start batch test-batch\n",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=argv, returncode=0, stdout="abc1234\n", stderr=""
            )

        self.mock_subprocess_run.side_effect = routing_fn

        rc, out = self._run_main([
            "test-batch",
            "--stage", "finalize",
            "--agent-output", str(agent_output_path),
        ])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip().splitlines()[-1])
        # With card_count=1 and content_commits=1 the batch is complete; must be success.
        self.assertEqual(data["status"], "success")
        self.assertNotEqual(data.get("stuck_type"), "incomplete")

    def test_card_ids_extraction_non_contiguous_headings(self):
        """card_ids extraction reads literal Card numbers, not a 1..N range (#660 repro).

        Writes a batch file whose only headings are "### Card 7:" and "### Card 8:" -- mirroring
        mill-plan's global-across-batches card numbering, where a later batch's cards are not
        assumed to start at 1. main() must extract card_ids={7, 8}, not {1, 2}, and thread it to
        _forward_output.
        """
        batch_file = self.tmp_path / "task" / "plan" / "01-test-batch.md"
        batch_file.write_text(
            "```yaml\ntask: Test\nverify: null\n```\n\n"
            "### Card 7: first card\n\n"
            "- **Requirements:** Implement it.\n"
            "- **Commit:** feat(card7): implement\n\n"
            "### Card 8: second card\n\n"
            "- **Requirements:** Implement it too.\n"
            "- **Commit:** feat(card8): implement\n",
            encoding="utf-8",
        )

        captured_kwargs = {}

        def _fake_forward_output(output, project_root, **kwargs):
            captured_kwargs.update(kwargs)
            return 0

        with unittest.mock.patch.object(
            millpy_implement._implementer_claude, "run",
            return_value=(
                '{"status":"success","commit_sha":"abc","session_id":"fake"}\n',
                "fake-session",
            ),
        ):
            with unittest.mock.patch.object(
                millpy_implement, "_forward_output", side_effect=_fake_forward_output,
            ):
                rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 0)
        self.assertEqual(captured_kwargs.get("card_ids"), {7, 8})
        # card_count itself is no longer a callee kwarg -- the stale keyword was dropped once finalize_from_output/_forward_output's signature was renamed.
        self.assertNotIn("card_count", captured_kwargs)

    def test_prepare_stage_envelope_includes_start_sha_matching_head(self):
        """--stage prepare on a fresh (pending) batch: envelope start_sha matches the captured HEAD.

        Card 2 (#625, #635, #643): the prepare envelope must carry start_sha so the next batch's
        effort-tier work (which threads start_sha through the same emit_prepare call) has a real
        value to build on, and so a re-dispatched prepare has something to reuse.
        """
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        # The patched _subprocess_util.run default (set in setUp) returns "abc1234\n" for every call, including the fresh-mint branch's `git rev-parse HEAD` capture.
        self.assertEqual(data["start_sha"], "abc1234")

    def test_prepare_stage_envelope_includes_effort_from_implementer_spec(self):
        """--stage prepare envelope carries the resolved implementer spec's effort tier.

        #628/#633: the effort-tier-implementer batch threads impl_effort (already resolved from the
        implementer registry spec, here "sonnethigh" -> effort "high" per setUp's
        mock_reviewers_resolve) into the same emit_prepare call Card 2's start_sha fix already
        extended.
        """
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertEqual(data["effort"], "high")

    def test_prepare_stage_reuses_session_on_rerun_of_running_batch(self):
        """Second --stage prepare call against a batch already 'running' with a session reuses it.

        Card 2 (#625, #635, #643): a re-dispatched prepare (e.g.
        after a transient dispatch failure) must not re-mint state.md fields nor re-run
        capture_snapshot/commit/push -- only the fresh-mint (first) prepare call does that
        state-mutating work.
        """
        status_path = self.tmp_path / "task" / "status.md"
        original_start_sha = "reuse_start_sha_123"
        original_session = "reuse-session-uuid-456"
        millpy_implement._status.set_batch_fields(
            status_path,
            "test-batch",
            {
                "state": "running",
                "start_sha": original_start_sha,
                "implementer_session": original_session,
            },
        )

        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit"
            ) as mock_git_commit:
                rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["session_id"], original_session)
        self.assertEqual(data["start_sha"], original_start_sha)

        # No state-mutating work: capture_snapshot and git_commit must record zero calls,
        # and no "git push" subprocess call may appear among the (still-patched) generic runs.
        self.mock_capture_snapshot.assert_not_called()
        mock_git_commit.assert_not_called()
        push_calls = [
            call for call in self.mock_subprocess_run.call_args_list
            if call.args and list(call.args[0])[:2] == ["git", "push"]
        ]
        self.assertEqual(push_calls, [], "git push must not be invoked on the prepare-reuse path")

        # The original values must remain untouched in status.md (no set_batch_fields call).
        batches = millpy_implement._status.read_batches(status_path)
        batch_entry = next(b for b in batches if b["name"] == "test-batch")
        self.assertEqual(batch_entry["start_sha"], original_start_sha)
        self.assertEqual(batch_entry["implementer_session"], original_session)

    def test_prepare_stage_push_failure_nonfatal_but_commit_failure_still_fatal(self):
        """Card 3 (#626): a failed git push is non-fatal (warning + envelope still emitted);
    a failed git commit remains fatal (return 1, no envelope).
        """
        status_path = self.tmp_path / "task" / "status.md"

        # Sub-case 1: git push returns non-zero -> warning on stderr, envelope still printed. `git diff --cached --quiet` must return non-zero (staged) so the fresh-mint branch actually reaches the commit/push sequence, mirroring test_no_skip_start_commit_on_fresh_fire.
        def push_fails_routing(argv, **kw):
            if argv[1] == "diff":
                return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="")
            if argv[1] == "push":
                return subprocess.CompletedProcess(
                    args=argv, returncode=1, stdout="", stderr="push failed: connection reset"
                )
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = push_fails_routing

        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit",
                return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            ):
                stderr_buf = io.StringIO()
                with unittest.mock.patch("sys.stderr", stderr_buf):
                    rc, out = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["stage"], "prepare")
        self.assertIn("push failed", stderr_buf.getvalue())
        self.assertIn("warning", stderr_buf.getvalue().lower())

        # Reset the batch back to "pending" so the next prepare call takes the fresh-mint branch again (rather than the running-batch reuse path exercised above).
        millpy_implement._status.set_batch_field(status_path, "test-batch", "state", "pending")

        # Sub-case 2: git commit fails -> still fatal, returns 1, never reaches emit_prepare. `git diff --cached --quiet` must again return non-zero (staged) so the fresh-mint branch reaches the commit step where the patched failure below fires.
        def commit_fails_routing(argv, **kw):
            if argv[1] == "diff":
                return subprocess.CompletedProcess(args=argv, returncode=1, stdout="", stderr="")
            return subprocess.CompletedProcess(args=argv, returncode=0, stdout="abc1234\n", stderr="")

        self.mock_subprocess_run.side_effect = commit_fails_routing
        with unittest.mock.patch.object(millpy_implement._render, "render", return_value="Brief text"):
            with unittest.mock.patch.object(
                millpy_implement._subprocess_util, "git_commit",
                return_value=subprocess.CompletedProcess(
                    args=[], returncode=1, stdout="", stderr="commit failed"
                ),
            ):
                rc2, out2 = self._run_main(["test-batch", "--stage", "prepare"])

        self.assertEqual(rc2, 1)
        self.assertEqual(out2.strip(), "")

    def test_main_reports_clean_message_on_exhausted_wiki_startup_error(self):
        """slug_from_branch exhausting the cold-daemon retry -> clean stderr message, exit 1, no traceback."""
        self.mock_slug_from_branch.side_effect = millpy_implement.WikiStartupError(
            "daemon did not start within timeout"
        )

        stderr_buf = io.StringIO()
        with unittest.mock.patch("sys.stderr", stderr_buf):
            rc, out = self._run_main(["test-batch"])

        self.assertEqual(rc, 1)
        stderr_output = stderr_buf.getvalue()
        # A clean except clause must have caught this -- no raw unhandled traceback.
        self.assertNotIn("Traceback (most recent call last)", stderr_output)


class TestClassifyStuckType(unittest.TestCase):

    def test_classify_command_not_found(self):
        """'command not found' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("command not found: go")
        self.assertEqual(stuck_type, "verify")

    def test_classify_no_such_file(self):
        """'no such file' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("No such file or directory")
        self.assertEqual(stuck_type, "verify")

    def test_classify_not_found(self):
        """'not found' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("Binary not found")
        self.assertEqual(stuck_type, "verify")

    def test_classify_cannot_find(self):
        """'cannot find' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("cannot find the specified file")
        self.assertEqual(stuck_type, "verify")

    def test_classify_errno_2(self):
        """'[errno 2]' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("[Errno 2] No such file")
        self.assertEqual(stuck_type, "verify")

    def test_classify_winerror_2(self):
        """'winerror 2' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("WinError 2: The system cannot find")
        self.assertEqual(stuck_type, "verify")

    def test_classify_cannot_run_program(self):
        """'cannot run program' in reason -> stuck_type=verify."""
        stuck_type = millpy_implement.classify_stuck_type("cannot run program go")
        self.assertEqual(stuck_type, "verify")

    def test_classify_timeout(self):
        """'timeout' in reason -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("Claude CLI timed out after 1800s")
        self.assertEqual(stuck_type, "transient")

    def test_classify_dead_session(self):
        """'dead session' in reason -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("claude --resume abc exited 1: dead session")
        self.assertEqual(stuck_type, "transient")

    def test_classify_rate_limit(self):
        """'rate limit' in reason -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("claude rate-limited (exit 429)")
        self.assertEqual(stuck_type, "transient")

    def test_classify_generic_error(self):
        """Generic error with no known signal -> stuck_type=transient."""
        stuck_type = millpy_implement.classify_stuck_type("claude exited 1: unknown error")
        self.assertEqual(stuck_type, "transient")


class TestForwardOutput(unittest.TestCase):

    def _call(self, output: str) -> tuple[int, str]:
        buf = io.StringIO()
        with unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=unittest.mock.MagicMock(returncode=0, stdout="a" * 40 + "\n"),
        ):
            with unittest.mock.patch.object(
                _implementer_common._cleanliness, "compute_scope_violations",
                return_value=[],
            ):
                with unittest.mock.patch("sys.stdout", buf):
                    rc = millpy_implement._forward_output(output, Path("/fake"))
        return rc, buf.getvalue()

    def test_fo_1_bare_json_on_last_line(self):
        """Bare JSON with status key on last line -> printed verbatim (commit_sha corrected), exit 0."""
        json_str = '{"status":"success","commit_sha":"abc"}'
        rc, out = self._call(f"some preamble\n{json_str}")
        self.assertEqual(rc, 0)
        expected = json.loads(json_str)
        expected["commit_sha"] = "a" * 40
        self.assertEqual(json.loads(out.strip()), expected)

    def test_fo_2_json_in_fence(self):
        """JSON inside ```json fence -> extracted and printed (commit_sha corrected), exit 0."""
        json_str = '{"status":"success","commit_sha":"abc"}'
        output = f"```json\n{json_str}\n```"
        rc, out = self._call(output)
        self.assertEqual(rc, 0)
        expected = json.loads(json_str)
        expected["commit_sha"] = "a" * 40
        self.assertEqual(json.loads(out.strip()), expected)

    def test_fo_3_json_in_fence_trailing_blank_lines(self):
        """JSON in fence with trailing blank lines -> extracted correctly (commit_sha corrected), exit 0."""
        json_str = '{"status":"success","commit_sha":"abc"}'
        output = f"```json\n{json_str}\n```\n\n\n"
        rc, out = self._call(output)
        self.assertEqual(rc, 0)
        expected = json.loads(json_str)
        expected["commit_sha"] = "a" * 40
        self.assertEqual(json.loads(out.strip()), expected)

    def test_fo_4_multiple_json_lines_last_wins(self):
        """Multiple lines with status JSON -> last one printed (commit_sha corrected)."""
        first = '{"status":"stuck","stuck_type":"verify","reason":"oops"}'
        last = '{"status":"success","commit_sha":"def"}'
        rc, out = self._call(f"{first}\n{last}")
        self.assertEqual(rc, 0)
        expected = json.loads(last)
        expected["commit_sha"] = "a" * 40
        self.assertEqual(json.loads(out.strip()), expected)

    def test_fo_5_no_json_anywhere(self):
        """No JSON-like pattern in output -> stuck/logic sentinel printed, exit 0."""
        rc, out = self._call("implementer ran but produced no report")
        self.assertEqual(rc, 0)
        data = json.loads(out.strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")
        self.assertIn("no structured report", data["reason"])

    def test_fo_6_malformed_json_last_valid_earlier(self):
        """Unclosed brace last (regex miss) + valid JSON earlier -> earlier valid one printed (commit_sha corrected)."""
        valid = '{"status":"success","commit_sha":"x"}'
        output = f'{valid}\n{{"status":"broken"'
        rc, out = self._call(output)
        self.assertEqual(rc, 0)
        expected = json.loads(valid)
        expected["commit_sha"] = "a" * 40
        self.assertEqual(json.loads(out.strip()), expected)

    def test_fo_7_sha_normalized(self):
        """git rev-parse success -> commit_sha in output replaced with HEAD sha."""
        sha = "a" * 40
        buf = io.StringIO()
        with unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=unittest.mock.MagicMock(returncode=0, stdout=sha + "\n"),
        ):
            with unittest.mock.patch.object(
                _implementer_common._cleanliness, "compute_scope_violations",
                return_value=[],
            ):
                with unittest.mock.patch("sys.stdout", buf):
                    rc = millpy_implement._forward_output(
                        '{"status":"success","commit_sha":"abc1234","session_id":"x"}',
                        Path("/fake"),
                    )
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(buf.getvalue().strip())["commit_sha"], sha)

    def test_fo_8_sha_git_failure(self):
        """git rev-parse failure -> fails safe with stuck/logic, never passes an unvalidated self-reported commit_sha (#744)."""
        buf = io.StringIO()
        with unittest.mock.patch.object(
            _implementer_common._subprocess_util, "run",
            return_value=unittest.mock.MagicMock(returncode=1, stdout=""),
        ):
            with unittest.mock.patch.object(
                _implementer_common._cleanliness, "compute_scope_violations",
                return_value=[],
            ):
                with unittest.mock.patch("sys.stdout", buf):
                    rc = millpy_implement._forward_output(
                        '{"status":"success","commit_sha":"abc1234","session_id":"x"}',
                        Path("/fake"),
                    )
        self.assertEqual(rc, 0)
        data = json.loads(buf.getvalue().strip())
        self.assertEqual(data["status"], "stuck")
        self.assertEqual(data["stuck_type"], "logic")
        self.assertNotIn("commit_sha", data)


class TestVerifyBaselineCwdOverrideRelative(unittest.TestCase):
    """_verify_baseline.compute_baseline's cwd_override_relative re-anchoring (#604).

    Exercises compute_baseline directly (not through millpy-implement.py's CLI), mocking git and
    subprocess so only the dependency-junction targets and the verify subprocess's cwd are observed.
    """

    def setUp(self):
        self.tmp_path = Path(tempfile.mkdtemp())
        self.addCleanup(_safe_rmtree.safe_rmtree, self.tmp_path, allowed_root=self.tmp_path, ignore_errors=True)

        self.project_root = self.tmp_path / "project"
        self.git_root = self.tmp_path / "git"
        self.project_root.mkdir(parents=True, exist_ok=True)
        self.git_root.mkdir(parents=True, exist_ok=True)
        # A single gitignored dependency dir to exercise the junction loop.
        (self.project_root / ".venv").mkdir()

        def _p(target, attr, **kwargs):
            patcher = unittest.mock.patch.object(target, attr, **kwargs)
            mock_obj = patcher.start()
            self.addCleanup(patcher.stop)
            return mock_obj

        # git rev-parse / git worktree add both succeed with a fixed sha.
        self.mock_subprocess_util_run = _p(
            _verify_baseline._subprocess_util, "run",
            return_value=subprocess.CompletedProcess(
                args=[], returncode=0, stdout="deadbeef\n", stderr=""
            ),
        )
        # Deterministic transient-worktree path: fix uuid4 so tmp_path is known.
        fixed_uuid = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
        _p(_verify_baseline.uuid, "uuid4", return_value=fixed_uuid)
        self.mock_junction_create = _p(_verify_baseline._junction, "create")
        _p(_verify_baseline._worktree, "remove_safe")
        self.expected_tmp_path = (
            self.project_root / ".scratch" / f"verify-baseline-{fixed_uuid.hex[:12]}"
        )

    def test_junction_and_verify_cwd_reanchored_when_cwd_override_relative_set(self):
        """cwd_override_relative set: junction target and verify cwd both re-anchor under it."""
        with unittest.mock.patch.object(
            _verify_baseline.subprocess, "run",
            return_value=unittest.mock.MagicMock(returncode=0, stdout="", stderr=""),
        ) as mock_verify_run:
            result = _verify_baseline.compute_baseline(
                self.project_root,
                self.git_root,
                "main",
                "exit 0",
                cwd_override_relative=Path("hub"),
            )

        self.assertEqual(result, "clean")
        self.mock_junction_create.assert_called_once_with(
            self.project_root / ".venv", self.expected_tmp_path / "hub" / ".venv"
        )
        self.assertEqual(
            mock_verify_run.call_args.kwargs.get("cwd"), self.expected_tmp_path / "hub"
        )

    def test_junction_and_verify_cwd_unchanged_when_cwd_override_relative_none(self):
        """cwd_override_relative=None: junction target and verify cwd stay at tmp_path directly (flat layout)."""
        with unittest.mock.patch.object(
            _verify_baseline.subprocess, "run",
            return_value=unittest.mock.MagicMock(returncode=0, stdout="", stderr=""),
        ) as mock_verify_run:
            result = _verify_baseline.compute_baseline(
                self.project_root, self.git_root, "main", "exit 0",
            )

        self.assertEqual(result, "clean")
        self.mock_junction_create.assert_called_once_with(
            self.project_root / ".venv", self.expected_tmp_path / ".venv"
        )
        self.assertEqual(
            mock_verify_run.call_args.kwargs.get("cwd"), self.expected_tmp_path
        )


if __name__ == "__main__":
    unittest.main()
