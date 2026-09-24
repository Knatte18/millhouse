"""Unit tests for plugins/mill/scripts/_vscode_tasks.py."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

from _vscode_tasks import (  # noqa: E402
    DEFAULT_SESSIONS,
    HUB_TASK_SPECS,
    LABEL_PREFIX,
    MANAGED_MARKER,
    TASK_SPECS,
    render_tasks,
    resolve_sessions,
    session_prefix,
    write_tasks,
)

SLUG = "my-slug"
EXPECTED_KEYS = ["start", "start-auto", "start-orch", "plan", "go", "quick"]


def _parse(rendered: str) -> list[dict]:
    body = rendered.split("\n", 1)[1]
    return json.loads(body)["tasks"]


def _test_render(errors: list[int]) -> None:
    rendered = render_tasks(SLUG)
    assert rendered.startswith(MANAGED_MARKER), "marker FAIL"
    assert rendered.isascii(), "ascii FAIL"
    tasks = _parse(rendered)
    assert [t["label"] for t in tasks] == [LABEL_PREFIX + key for key in EXPECTED_KEYS], tasks
    assert [spec[0] for spec in TASK_SPECS] == EXPECTED_KEYS
    print("PASS: render_tasks output parses, six labelled tasks in order")

    by_key = {t["label"][len(LABEL_PREFIX):]: t["command"] for t in tasks}
    for key, phase, flag in TASK_SPECS:
        command = by_key[key]
        model = DEFAULT_SESSIONS[phase]["model"]
        effort = DEFAULT_SESSIONS[phase]["effort"]
        prompt = f"/mill-{phase}" + (f" {flag}" if flag else "")
        expected = f'claude -n "{SLUG}:{phase}" --model {model} --effort {effort} "{prompt}"'
        assert command == expected, f"{key}: {command!r} != {expected!r}"
    assert by_key["start-auto"].endswith(' --auto"')
    assert by_key["start-orch"].endswith(' --orch"')
    print("PASS: commands carry slug, phase, model, effort and flags")

    assert all("runOptions" not in t for t in tasks)
    assert "runOptions" not in rendered
    print("PASS: no task has runOptions")


def _test_worktree_prefix_render(errors: list[int]) -> None:
    rendered = render_tasks(session_prefix("MH", "my-task"))
    assert "<HUB_TASKS>" not in rendered
    tasks = _parse(rendered)
    assert [t["label"] for t in tasks] == [LABEL_PREFIX + key for key in EXPECTED_KEYS]
    for (key, phase, flag), task in zip(TASK_SPECS, tasks):
        model = DEFAULT_SESSIONS[phase]["model"]
        effort = DEFAULT_SESSIONS[phase]["effort"]
        prompt = f"/mill-{phase}" + (f" {flag}" if flag else "")
        expected = f'claude -n "mh:my-task:{phase}" --model {model} --effort {effort} "{prompt}"'
        assert task["command"] == expected, task["command"]
    print("PASS: worktree render uses lower-cased prefix and has no orch task")


def _test_hub_render(errors: list[int]) -> None:
    rendered = render_tasks(session_prefix("MH"), hub=True)
    assert "<HUB_TASKS>" not in rendered
    tasks = _parse(rendered)
    assert [t["label"] for t in tasks] == [LABEL_PREFIX + spec[0] for spec in HUB_TASK_SPECS]
    assert [t["label"] for t in tasks[:-1]] == [LABEL_PREFIX + key for key in EXPECTED_KEYS]
    assert tasks[0]["command"].startswith('claude -n "mh:start"')
    assert tasks[-1]["label"] == "mill: orch"
    assert tasks[-1]["command"] == 'claude -n "mh:orch" --model opus --effort high'
    print("PASS: hub render adds a prompt-less orch task last")

    override = {"orch": {"model": "sonnet", "effort": "max"}}
    orch = _parse(render_tasks("mh", override, hub=True))[-1]
    assert orch["command"] == 'claude -n "mh:orch" --model sonnet --effort max'
    print("PASS: spawn.sessions.orch override reaches the hub orch command")

    bad = {"orch": {"model": "a b"}}
    try:
        render_tasks("mh", bad, hub=True)
    except ValueError as exc:
        assert "orch.model" in str(exc)
    else:
        raise AssertionError("expected ValueError for hub render with bad orch value")
    render_tasks("mh:slug", bad)
    print("PASS: invalid orch value fails the hub render only")


def _test_session_prefix_and_phases(errors: list[int]) -> None:
    assert session_prefix("MH") == "mh"
    assert session_prefix("MH", "my-task") == "mh:my-task"
    for bad in ("", "M:H", 'M"H'):
        try:
            session_prefix(bad)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for short name {bad!r}")
    print("PASS: session_prefix lower-cases and rejects invalid short names")

    assert resolve_sessions({}, phases=["go"]) == {"go": DEFAULT_SESSIONS["go"]}
    assert resolve_sessions(None) == DEFAULT_SESSIONS
    try:
        resolve_sessions({}, phases=["nope"])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown phase")
    print("PASS: resolve_sessions is phase-scoped")


def _test_sessions(errors: list[int]) -> None:
    assert resolve_sessions(None) == DEFAULT_SESSIONS
    print("PASS: resolve_sessions(None) equals defaults")

    expected = copy.deepcopy(DEFAULT_SESSIONS)
    expected["go"]["effort"] = "max"
    assert resolve_sessions({"go": {"effort": "max"}}) == expected
    assert resolve_sessions({"go": {"effort": " max "}, "plan": None, "quick": {"model": ""}}) == expected
    print("PASS: missing or empty keys fall back per key")

    commands = {t["label"]: t["command"] for t in _parse(render_tasks(SLUG, {"plan": {"model": "haiku", "effort": "low"}}))}
    assert "--model haiku --effort low" in commands["mill: plan"]
    assert "--model opus --effort medium" in commands["mill: start"]
    print("PASS: overridden values are honoured")

    for bad in ({"go": {"model": "a b"}}, {"go": {"model": "-x"}}, {"go": {"model": "a;b"}}):
        try:
            render_tasks(SLUG, bad)
        except ValueError as exc:
            assert "go.model" in str(exc)
        else:
            raise AssertionError(f"expected ValueError for {bad}")
    print("PASS: invalid model value raises ValueError")

    for bad_name in ('a"b', "a$b", "a`b", "a\\b", "a\nb", ""):
        try:
            render_tasks(bad_name)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for name {bad_name!r}")
    print("PASS: unsafe slug raises ValueError")


def _test_write(errors: list[int]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "nested" / "tasks.json"
        assert write_tasks(target, SLUG) == "created"
        assert target.read_text(encoding="utf-8") == render_tasks(SLUG)
        before = (target.read_bytes(), target.stat().st_mtime_ns)
        assert write_tasks(target, SLUG) == "unchanged"
        assert (target.read_bytes(), target.stat().st_mtime_ns) == before
        print("PASS: write_tasks created then unchanged (bytes and mtime preserved)")

        cfg = {"go": {"effort": "max"}}
        assert write_tasks(target, SLUG, cfg) == "updated"
        assert target.read_text(encoding="utf-8") == render_tasks(SLUG, cfg)
        assert not (target.parent / "tasks.json.bak").exists()
        print("PASS: write_tasks updated a managed file without a backup")

    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "tasks.json"
        assert write_tasks(target, "mh", hub=True) == "created"
        assert target.read_text(encoding="utf-8") == render_tasks("mh", hub=True)
        print("PASS: write_tasks(hub=True) writes the hub render")

    with tempfile.TemporaryDirectory() as tmpdir:
        target = Path(tmpdir) / "tasks.json"
        target.write_text('{"version": "2.0.0", "tasks": []}\n', encoding="utf-8")
        assert write_tasks(target, SLUG) == "replaced"
        assert (Path(tmpdir) / "tasks.json.bak").read_text(encoding="utf-8") == '{"version": "2.0.0", "tasks": []}\n'
        assert target.read_text(encoding="utf-8") == render_tasks(SLUG)
        print("PASS: write_tasks replaced an unmanaged file, keeping a .bak")


def _test_template_defaults_consistent(errors: list[int]) -> None:
    template = HUB / "plugins" / "mill" / "templates" / "mill-config.yaml"
    parsed = yaml.safe_load(template.read_text(encoding="utf-8"))
    assert parsed["spawn"]["sessions"] == DEFAULT_SESSIONS
    print("PASS: template spawn.sessions equals DEFAULT_SESSIONS")


def main() -> int:
    errors = [0]
    for test in (_test_render, _test_worktree_prefix_render, _test_hub_render,
                 _test_session_prefix_and_phases, _test_sessions, _test_write, _test_template_defaults_consistent):
        try:
            test(errors)
        except AssertionError as exc:
            errors[0] += 1
            print(f"FAIL: {test.__name__}: {exc}", file=sys.stderr)
    if errors[0]:
        print(f"\n{errors[0]} test(s) FAILED", file=sys.stderr)
        return 1
    print("All _vscode_tasks unit tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
