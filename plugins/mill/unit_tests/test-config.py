"""Unit tests for plugins/mill/scripts/_config.py.

Covers:
  - load_config: three-layer merge (plugin template -> repo -> local)
  - load_config: environment variable overrides
  - load_config: unknown-key validation and warnings
  - load_config: legacy wiki/config.yaml fallback
  - load_config: local override wins via deep_merge
  - load_config: repo sources absent -> returns plugin template only (lenient)
  - load_config: subfolder-install layout — stub + real config merged
  - load_config: stub-only (real config absent) — hub_relative_path present
  - deep_merge: scalar in overlay wins over scalar in base
  - deep_merge: nested dicts are merged recursively
  - deep_merge: empty overlay leaves base unchanged
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS_DIR = HUB / "plugins" / "mill" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import yaml  # noqa: E402

import _config  # noqa: E402
import _paths  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(path: Path) -> None:
    """Initialise a minimal git repo so resolve_git_root would accept it."""
    subprocess.run(
        ["git", "init", str(path)],
        check=True,
        capture_output=True,
    )


def _write_yaml(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _setup_plugin_template(tmp_path: Path) -> None:
    """Write a minimal mill-config.yaml template to tmp_path/templates/."""
    template_dir = tmp_path / "templates"
    template_dir.mkdir(parents=True, exist_ok=True)
    template_path = template_dir / "mill-config.yaml"
    template_path.write_text(
        "spawn:\n  branch_prefix: ''\n"
        "roles:\n"
        "  discussion-review:\n"
        "    holistic:\n"
        "      reviewer: sonnetmax_tool\n"
        "  plan-review:\n"
        "    holistic:\n"
        "      reviewer: sonnetmax\n"
        "    batch:\n"
        "      reviewer: sonnetmedium\n"
        "  code-review:\n"
        "    holistic:\n"
        "      reviewer: sonnetmedium\n"
        "    batch:\n"
        "      reviewer: sonnetmedium\n"
        "  implementer:\n"
        "    model: sonnethigh\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


def test_load_config_shared_present() -> None:
    """load_config merges plugin template with repo-layer config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: feat\n")

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "feat", f"Unexpected cfg: {cfg!r}"
    print("PASS load_config — repo config present, overrides plugin template")


def test_load_config_local_override_wins() -> None:
    """load_config deep-merges local override; local values win on conflict."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: repo\n  workers: 2\n")
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "spawn:\n  branch_prefix: local\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "local", (
            f"Local override should win; got {cfg['spawn']['branch_prefix']!r}"
        )
        assert cfg["spawn"]["workers"] == 2, (
            f"Shared key not in local should be preserved; got {cfg['spawn'].get('workers')!r}"
        )
    print("PASS load_config — local override wins; shared-only keys preserved")




def test_load_config_subfolder_install() -> None:
    """load_config merges stub then real config for subfolder-install layout."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "wt"
        wt_root.mkdir()
        # mill-config.yaml at worktree root (not in hub subpath)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: hub_root\n")
        # Stub at worktree root .millhouse
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "hub_relative_path: sub/hub\n",
        )
        # Real config at the declared hub subpath
        _write_yaml(
            wt_root / "sub" / "hub" / ".millhouse" / "config.local.yaml",
            "spawn:\n  branch_prefix: real\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("hub_relative_path") == "sub/hub", (
            f"hub_relative_path from stub should be present; got {cfg.get('hub_relative_path')!r}"
        )
        assert cfg.get("spawn", {}).get("branch_prefix") == "real", (
            f"Real config keys should be in result; got {cfg.get('spawn')!r}"
        )
    print("PASS load_config — subfolder-install: stub + real config merged, both keys present")


def test_load_config_stub_only_real_absent() -> None:
    """load_config returns stub keys when real config is absent (no real hub)."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "wt"
        wt_root.mkdir()
        # mill-config.yaml at worktree root (required, but real config at sub/hub will not exist)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: hub_root\n")
        # Stub only — no real config at sub/hub
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "hub_relative_path: sub/hub\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("hub_relative_path") == "sub/hub", (
            f"hub_relative_path from stub should be present; got {cfg.get('hub_relative_path')!r}"
        )
    print("PASS load_config — stub-only (real config absent): hub_relative_path present, real keys absent")


def test_three_layer_merge() -> None:
    """load_config merges plugin template, repo layer, and local layer."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: repo\n")
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "spawn:\n  workers: 4\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "repo", "Repo value should be present"
        assert cfg["spawn"]["workers"] == 4, "Local value should be present"
    print("PASS load_config — three-layer merge")


def test_env_override_impl() -> None:
    """Environment variable overrides config values."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_IMPLEMENTER"] = "custom_model"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["implementer"]["model"] == "custom_model", (
                f"Env override should apply; got {cfg['roles']['implementer'].get('model')!r}"
            )
        finally:
            os.environ.pop("MILL_IMPLEMENTER", None)
    print("PASS load_config — env override applies")


def test_machine_layer_not_loaded() -> None:
    """load_config does not load machine-layer config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: repo\n")

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg["spawn"]["branch_prefix"] == "repo", "Config should not include machine layer"
    print("PASS load_config — machine layer not loaded")


# ---------------------------------------------------------------------------
# deep_merge
# ---------------------------------------------------------------------------


def test_deep_merge_scalar_wins() -> None:
    """Scalar overlay value wins over scalar base value."""
    result = _config.deep_merge({"a": 1, "b": 2}, {"b": 99})
    assert result == {"a": 1, "b": 99}, f"Unexpected: {result!r}"
    print("PASS deep_merge — scalar overlay wins")


def test_deep_merge_nested_merge() -> None:
    """Nested dicts are merged recursively; disjoint keys from both sides survive."""
    base = {"x": {"p": 1, "q": 2}}
    overlay = {"x": {"q": 99, "r": 3}}
    result = _config.deep_merge(base, overlay)
    assert result == {"x": {"p": 1, "q": 99, "r": 3}}, f"Unexpected: {result!r}"
    print("PASS deep_merge — nested merge, overlay wins on conflict, disjoint keys kept")


def test_deep_merge_empty_overlay() -> None:
    """An empty overlay leaves the base dict unchanged."""
    base = {"a": 1, "b": {"c": 2}}
    result = _config.deep_merge(base, {})
    assert result == base, f"Unexpected: {result!r}"
    # Must be a copy, not the same object.
    assert result is not base, "deep_merge must return a new dict, not the base"
    print("PASS deep_merge — empty overlay returns copy of base")


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# set_local_wiki_overrides
# ---------------------------------------------------------------------------


def test_no_op_when_both_args_none() -> None:
    """Returns False and creates no file when both repo_url and branch are None."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        result = _config.set_local_wiki_overrides(cfg_path, repo_url=None, branch=None)
        assert result is False, f"Expected False, got {result!r}"
        assert not cfg_path.exists(), "File must not be created when both args are None"
    print("PASS set_local_wiki_overrides — no-op when both args are None")


def test_creates_file_when_missing() -> None:
    """Creates the file with wiki.repo_url when file did not exist."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://example.com/x.git", branch=None
        )
        assert result is True, f"Expected True, got {result!r}"
        assert cfg_path.exists(), "File must be created"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data["wiki"]["repo_url"] == "https://example.com/x.git"
        assert "branch" not in data["wiki"], "branch key must be absent"
    print("PASS set_local_wiki_overrides — creates file with repo_url; branch absent")


def test_updates_existing_value() -> None:
    """Updates repo_url in an existing file."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        cfg_path.write_text(
            yaml.safe_dump({"wiki": {"repo_url": "https://old.git"}}, sort_keys=False),
            encoding="utf-8",
        )
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://new.git", branch=None
        )
        assert result is True, f"Expected True, got {result!r}"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data["wiki"]["repo_url"] == "https://new.git"
    print("PASS set_local_wiki_overrides — updates existing repo_url value")


def test_idempotent_when_already_correct() -> None:
    """Returns False without touching the file when content is already up-to-date."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        initial_data = {"wiki": {"repo_url": "https://x.git", "branch": "B"}}
        initial_text = yaml.safe_dump(initial_data, sort_keys=False, allow_unicode=True)
        cfg_path.write_text(initial_text, encoding="utf-8")
        before = cfg_path.read_text(encoding="utf-8")
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://x.git", branch="B"
        )
        assert result is False, f"Expected False (no-op), got {result!r}"
        after = cfg_path.read_text(encoding="utf-8")
        assert before == after, "File contents must be unchanged on no-op"
    print("PASS set_local_wiki_overrides — idempotent when already correct")


def test_partial_update_branch_only_preserves_repo_url() -> None:
    """Updating only branch preserves the existing repo_url."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        cfg_path.write_text(
            yaml.safe_dump(
                {"wiki": {"repo_url": "https://x.git", "branch": "old"}},
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        result = _config.set_local_wiki_overrides(cfg_path, repo_url=None, branch="new")
        assert result is True, f"Expected True, got {result!r}"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data["wiki"]["repo_url"] == "https://x.git", "repo_url must be preserved"
        assert data["wiki"]["branch"] == "new", "branch must be updated"
    print("PASS set_local_wiki_overrides — partial update: branch updated, repo_url preserved")


def test_preserves_other_top_level_keys() -> None:
    """Adds wiki block without removing other top-level keys."""
    with tempfile.TemporaryDirectory() as tmp:
        cfg_path = Path(tmp) / "config.local.yaml"
        cfg_path.write_text(
            yaml.safe_dump({"hub_relative_path": "."}, sort_keys=False),
            encoding="utf-8",
        )
        result = _config.set_local_wiki_overrides(
            cfg_path, repo_url="https://x.git", branch=None
        )
        assert result is True, f"Expected True, got {result!r}"
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        assert data.get("hub_relative_path") == ".", "hub_relative_path must be preserved"
        assert data["wiki"]["repo_url"] == "https://x.git", "wiki.repo_url must be present"
    print("PASS set_local_wiki_overrides — other top-level keys preserved")


def test_env_override_discussion_reviewer() -> None:
    """MILL_DISCUSSION_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_DISCUSSION_REVIEWER"] = "custom_reviewer"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["discussion-review"]["holistic"]["reviewer"] == "custom_reviewer"
        finally:
            os.environ.pop("MILL_DISCUSSION_REVIEWER", None)
    print("PASS load_config — MILL_DISCUSSION_REVIEWER env override")


def test_env_override_plan_reviewer() -> None:
    """MILL_PLAN_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_PLAN_REVIEWER"] = "custom_holistic"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["plan-review"]["holistic"]["reviewer"] == "custom_holistic"
        finally:
            os.environ.pop("MILL_PLAN_REVIEWER", None)
    print("PASS load_config — MILL_PLAN_REVIEWER env override")


def test_env_override_plan_batch_reviewer() -> None:
    """MILL_PLAN_BATCH_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_PLAN_BATCH_REVIEWER"] = "custom_batch"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["plan-review"]["batch"]["reviewer"] == "custom_batch"
        finally:
            os.environ.pop("MILL_PLAN_BATCH_REVIEWER", None)
    print("PASS load_config — MILL_PLAN_BATCH_REVIEWER env override")


def test_env_override_code_reviewer() -> None:
    """MILL_CODE_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_CODE_REVIEWER"] = "custom_code_holistic"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["code-review"]["holistic"]["reviewer"] == "custom_code_holistic"
        finally:
            os.environ.pop("MILL_CODE_REVIEWER", None)
    print("PASS load_config — MILL_CODE_REVIEWER env override")


def test_env_override_code_batch_reviewer() -> None:
    """MILL_CODE_BATCH_REVIEWER env var overrides config."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_CODE_BATCH_REVIEWER"] = "custom_code_batch"
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            assert cfg["roles"]["code-review"]["batch"]["reviewer"] == "custom_code_batch"
        finally:
            os.environ.pop("MILL_CODE_BATCH_REVIEWER", None)
    print("PASS load_config — MILL_CODE_BATCH_REVIEWER env override")


def test_env_override_empty_string_is_noop() -> None:
    """Empty-string env value is treated as unset."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        os.environ["MILL_PLAN_REVIEWER"] = ""
        try:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=tmp_path / "templates" / "mill-config.yaml"
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            # Should use the template value, not empty string
            assert cfg["roles"]["plan-review"]["holistic"]["reviewer"] == "sonnetmax"
        finally:
            os.environ.pop("MILL_PLAN_REVIEWER", None)
    print("PASS load_config — empty-string env value is noop")


def test_list_replace_semantics() -> None:
    """Lists are replaced wholesale, not merged."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "verify:\n  skip_known_broken:\n    - a.py\n    - b.py\n",
        )
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "verify:\n  skip_known_broken:\n    - c.py\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("verify", {}).get("skip_known_broken") == ["c.py"], (
            f"List should be replaced, not merged; got {cfg.get('verify', {}).get('skip_known_broken')!r}"
        )
    print("PASS load_config — list replace semantics")


def test_unknown_key_warning_emitted() -> None:
    """Unknown keys in local config emit warnings to stderr."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")
        _write_yaml(
            wt_root / ".millhouse" / "config.local.yaml",
            "pipeline:\n  autonomous_mode: true\n",
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert "pipeline" in stderr_output, (
            f"Unknown key warning should be in stderr; got {stderr_output!r}"
        )
    print("PASS load_config — unknown-key warning emitted")


def test_deep_merge_none_overlay_dict_base() -> None:
    """None overlay on dict base skips override, preserves base dict."""
    result = _config.deep_merge({"roles": {"k": "v"}}, {"roles": None})
    assert result == {"roles": {"k": "v"}}, f"None overlay must not clobber base dict; got {result!r}"
    print("PASS deep_merge -- None overlay on dict base is skipped, base dict preserved")


def test_deep_merge_none_overlay_scalar_base() -> None:
    """None overlay on scalar base is allowed (reviewer: null semantics)."""
    result = _config.deep_merge({"reviewer": "foo"}, {"reviewer": None})
    assert result == {"reviewer": None}, f"None overlay should override scalar; got {result!r}"
    print("PASS deep_merge -- None overlay on scalar base allowed (reviewer: null semantics)")


def test_resolve_plugin_template_path_stale_root() -> None:
    """resolve_plugin_template_path with stale CLAUDE_PLUGIN_ROOT falls back with warning."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        nonexistent_root = tmp_path / "nonexistent_plugin_root"
        _saved_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
        try:
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(nonexistent_root)
            with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                result = _config.resolve_plugin_template_path("mill-config.yaml")
                stderr_output = mock_stderr.getvalue()
            fallback_path = Path(_config.__file__).resolve().parent.parent / "templates" / "mill-config.yaml"
            assert result == fallback_path, (
                f"Expected fallback path {fallback_path}, got {result}"
            )
            assert "CLAUDE_PLUGIN_ROOT" in stderr_output or str(nonexistent_root) in stderr_output, (
                f"Expected warning about CLAUDE_PLUGIN_ROOT or path in stderr; got {stderr_output!r}"
            )
        finally:
            if _saved_root is not None:
                os.environ["CLAUDE_PLUGIN_ROOT"] = _saved_root
            else:
                os.environ.pop("CLAUDE_PLUGIN_ROOT", None)
    print("PASS resolve_plugin_template_path -- stale CLAUDE_PLUGIN_ROOT falls back to source tree with warning")


def test_load_config_bare_roles_key() -> None:
    """load_config with bare roles: key does not crash; template roles: dict preserved."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        wt_root.mkdir(parents=True)
        _write_yaml(wt_root / "mill-config.yaml", "roles:\n")
        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                result = _config.load_config(wt_root, wt_root)
        assert isinstance(result.get("roles"), dict), (
            f"Expected roles to be a dict; got {result.get('roles')!r}"
        )
    print("PASS load_config -- bare roles: key does not crash; template roles: dict preserved")


def test_load_config_hub_relative_path_no_warning() -> None:
    """load_config with hub_relative_path in config.local.yaml does not emit unknown-key warning."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")
        _write_yaml(wt_root / ".millhouse" / "config.local.yaml", "hub_relative_path: subdir\n")
        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()
        assert "hub_relative_path" not in stderr_output, (
            f"hub_relative_path should not appear in warning; got {stderr_output!r}"
        )
    print("PASS load_config -- hub_relative_path in config.local.yaml does not emit unknown-key warning")


def test_load_config_no_hub_overlay_returns_template() -> None:
    """load_config without hub overlay (mill-config.yaml absent) returns template defaults."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        hub_root = tmp_path / "hub"
        hub_root.mkdir()
        # No mill-config.yaml at hub_root; test that load_config does not raise

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(hub_root, hub_root)

        # Should return template defaults, not raise FileNotFoundError
        assert isinstance(cfg, dict), f"Expected dict, got {type(cfg)!r}"
        assert cfg.get("spawn", {}).get("branch_prefix") == "", (
            f"Template default should be present; got {cfg.get('spawn')!r}"
        )
    print("PASS load_config -- no hub overlay: returns template defaults, does not raise")


def test_load_config_sub_project_hub_overlay() -> None:
    """load_config with sub-project hub overlay merges template + hub overlay."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        # Hub is in a subdirectory (sub-project layout)
        hub_root = tmp_path / "projects" / "sub"
        hub_root.mkdir(parents=True)
        # Hub overlay with non-default value
        _write_yaml(hub_root / "mill-config.yaml", "spawn:\n  branch_prefix: sub_project\n")

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(hub_root, tmp_path)

        # Hub overlay should win over template
        assert cfg.get("spawn", {}).get("branch_prefix") == "sub_project", (
            f"Hub overlay value should win; got {cfg.get('spawn', {}).get('branch_prefix')!r}"
        )
    print("PASS load_config -- sub-project hub overlay: hub value wins over template")


def test_worktree_template_augments_template_cfg() -> None:
    """load_config augments template_cfg with worktree-local template to avoid unknown-key warnings."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Set up cache template without pipeline.max_cards_per_batch
        cache_template_dir = tmp_path / "cache_templates"
        cache_template_dir.mkdir(parents=True, exist_ok=True)
        cache_template_path = cache_template_dir / "mill-config.yaml"
        cache_template_path.write_text(
            "spawn:\n  branch_prefix: ''\n"
            "roles:\n"
            "  discussion-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax_tool\n"
            "  plan-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  code-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmedium\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  implementer:\n"
            "    model: sonnethigh\n",
            encoding="utf-8",
        )

        # Set up worktree with its own template that includes pipeline.max_cards_per_batch
        wt_root = tmp_path / "wt"
        wt_root.mkdir()
        wt_template_dir = wt_root / "plugins" / "mill" / "templates"
        wt_template_dir.mkdir(parents=True, exist_ok=True)
        wt_template_path = wt_template_dir / "mill-config.yaml"
        wt_template_path.write_text(
            "spawn:\n  branch_prefix: ''\n"
            "pipeline:\n  max_cards_per_batch: 10\n"
            "roles:\n"
            "  discussion-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax_tool\n"
            "  plan-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmax\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  code-review:\n"
            "    holistic:\n"
            "      reviewer: sonnetmedium\n"
            "    batch:\n"
            "      reviewer: sonnetmedium\n"
            "  implementer:\n"
            "    model: sonnethigh\n",
            encoding="utf-8",
        )

        # Set up hub config with pipeline.max_cards_per_batch
        hub_config_path = wt_root / "mill-config.yaml"
        hub_config_path.write_text(
            "pipeline:\n  max_cards_per_batch: 10\n",
            encoding="utf-8",
        )
        _git_init(wt_root)

        # Capture stderr to check for unknown-key warnings
        with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
            with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
                with patch.object(
                    _config, "resolve_plugin_template_path",
                    return_value=cache_template_path
                ):
                    cfg = _config.load_config(wt_root, wt_root)

            stderr_output = mock_stderr.getvalue()
            # Check that pipeline.max_cards_per_batch doesn't generate unknown-key warning
            assert "unknown key: pipeline.max_cards_per_batch" not in stderr_output, (
                f"Unexpected unknown-key warning; stderr: {stderr_output!r}"
            )
            # And verify the key is in the result
            assert cfg.get("pipeline", {}).get("max_cards_per_batch") == 10, (
                f"Expected pipeline.max_cards_per_batch in result; got {cfg.get('pipeline')!r}"
            )
    print("PASS load_config -- worktree template augments template_cfg, no unknown-key warning")


def test_same_template_path_skips_augmentation() -> None:
    """load_config skips augmentation when worktree template path resolves to same path."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "wt"
        wt_root.mkdir()

        # Create a worktree but DON'T create plugins/mill/templates/mill-config.yaml
        # (or create it with identical content)
        # This tests the guard: if _worktree_template.exists() is False
        _git_init(wt_root)
        _write_yaml(wt_root / "mill-config.yaml", "spawn:\n  branch_prefix: test\n")

        # When worktree template doesn't exist, augmentation is skipped
        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        # Result should still have the template and repo config merged
        assert cfg.get("spawn", {}).get("branch_prefix") == "test", (
            f"Repo config should be present; got {cfg.get('spawn')!r}"
        )
    print("PASS load_config -- same/missing template path skips augmentation")


def test_dispatch_shim_via_psmux_true_resolves_to_psmux() -> None:
    """dispatch shim converts via_psmux: true to dispatch: psmux."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    psmux:\n      via_psmux: true\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    cfg = _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "psmux", (
            f"Expected dispatch: psmux, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
        assert "[config] llm.claude.psmux.via_psmux is deprecated" in stderr_output, (
            f"Expected deprecation warning in stderr, got {stderr_output!r}"
        )
    print("PASS dispatch shim -- via_psmux: true -> dispatch: psmux with deprecation warning")


def test_dispatch_shim_via_psmux_false_resolves_to_subprocess() -> None:
    """dispatch shim converts via_psmux: false to dispatch: subprocess."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    psmux:\n      via_psmux: false\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "subprocess", (
            f"Expected dispatch: subprocess, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
    print("PASS dispatch shim -- via_psmux: false -> dispatch: subprocess")


def test_dispatch_shim_explicit_dispatch_wins_over_via_psmux() -> None:
    """Explicit dispatch key wins over legacy via_psmux."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    dispatch: agent\n    psmux:\n      via_psmux: true\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                cfg = _config.load_config(wt_root, wt_root)

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "agent", (
            f"Expected dispatch: agent, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
    print("PASS dispatch shim -- explicit dispatch wins over via_psmux")


def test_via_psmux_does_not_trigger_unknown_key_warning() -> None:
    """via_psmux does not trigger generic unknown-key warning."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    psmux:\n      via_psmux: false\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert "unknown key: llm.claude.psmux.via_psmux" not in stderr_output, (
            f"via_psmux should not trigger unknown-key warning, stderr: {stderr_output!r}"
        )
    print("PASS dispatch shim -- via_psmux does not trigger unknown-key warning")


def test_dispatch_shim_unknown_value_falls_back_to_subprocess() -> None:
    """Unknown dispatch value falls back to subprocess with error message."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _setup_plugin_template(tmp_path)
        wt_root = tmp_path / "hub"
        _git_init(wt_root)
        _write_yaml(
            wt_root / "mill-config.yaml",
            "llm:\n  claude:\n    dispatch: invalid_value\n"
        )

        with patch.object(_paths, "resolve_wiki_path", side_effect=SystemExit):
            with patch.object(
                _config, "resolve_plugin_template_path",
                return_value=tmp_path / "templates" / "mill-config.yaml"
            ):
                with patch("sys.stderr", new=io.StringIO()) as mock_stderr:
                    cfg = _config.load_config(wt_root, wt_root)
                    stderr_output = mock_stderr.getvalue()

        assert cfg.get("llm", {}).get("claude", {}).get("dispatch") == "subprocess", (
            f"Expected fallback to subprocess, got {cfg.get('llm', {}).get('claude', {}).get('dispatch')!r}"
        )
        assert "invalid_value" in stderr_output and "falling back" in stderr_output, (
            f"Expected error message in stderr, got {stderr_output!r}"
        )
    print("PASS dispatch shim -- unknown dispatch value falls back to subprocess with error")


def main() -> int:
    tests = [
        test_load_config_shared_present,
        test_load_config_local_override_wins,
        test_load_config_subfolder_install,
        test_load_config_stub_only_real_absent,
        test_three_layer_merge,
        test_env_override_impl,
        test_env_override_discussion_reviewer,
        test_env_override_plan_reviewer,
        test_env_override_plan_batch_reviewer,
        test_env_override_code_reviewer,
        test_env_override_code_batch_reviewer,
        test_env_override_empty_string_is_noop,
        test_list_replace_semantics,
        test_unknown_key_warning_emitted,
        test_machine_layer_not_loaded,
        test_deep_merge_scalar_wins,
        test_deep_merge_nested_merge,
        test_deep_merge_empty_overlay,
        test_deep_merge_none_overlay_dict_base,
        test_deep_merge_none_overlay_scalar_base,
        test_resolve_plugin_template_path_stale_root,
        test_load_config_bare_roles_key,
        test_load_config_hub_relative_path_no_warning,
        test_load_config_no_hub_overlay_returns_template,
        test_load_config_sub_project_hub_overlay,
        test_no_op_when_both_args_none,
        test_creates_file_when_missing,
        test_updates_existing_value,
        test_idempotent_when_already_correct,
        test_partial_update_branch_only_preserves_repo_url,
        test_preserves_other_top_level_keys,
        test_worktree_template_augments_template_cfg,
        test_same_template_path_skips_augmentation,
        test_dispatch_shim_via_psmux_true_resolves_to_psmux,
        test_dispatch_shim_via_psmux_false_resolves_to_subprocess,
        test_dispatch_shim_explicit_dispatch_wins_over_via_psmux,
        test_via_psmux_does_not_trigger_unknown_key_warning,
        test_dispatch_shim_unknown_value_falls_back_to_subprocess,
    ]
    failures: list[str] = []
    for fn in tests:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR [{fn.__name__}]: {exc}", file=sys.stderr)
            failures.append(fn.__name__)
    if failures:
        print(f"\n{len(failures)} test(s) failed: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
