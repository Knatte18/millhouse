"""Unit tests for plugins/mill/scripts/millpy-ask-thread.py."""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

_spec = importlib.util.spec_from_file_location(
    "millpy_ask_thread", HUB / "plugins" / "mill" / "scripts" / "millpy-ask-thread.py"
)
millpy_ask_thread = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(millpy_ask_thread)


def _run(root: Path, argv: list[str]) -> tuple[int, str]:
    cfg = {"paths": {"status_md": "_mill/status.md"}, "pipeline": {}}
    buffer = io.StringIO()
    with mock.patch.object(millpy_ask_thread._paths, "resolve_git_root", return_value=root), \
            mock.patch.object(millpy_ask_thread._paths, "resolve_hub_path", return_value=root), \
            mock.patch.object(millpy_ask_thread._config, "load_config", return_value=cfg), \
            contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(io.StringIO()):
        code = millpy_ask_thread.main(argv)
    out = buffer.getvalue()
    assert out.isascii()
    return code, out


def _make_worktree(root: Path, with_parent: bool) -> None:
    (root / "_mill").mkdir()
    row = "parent_thread: mh:orch\n" if with_parent else ""
    (root / "_mill" / "status.md").write_text(
        f"# Status\n\n```yaml\nphase: planning\n{row}task: T\nslug: my-slug\n```\n\n"
        "## Timeline\n\n```text\n```\n",
        encoding="utf-8",
    )


PREPARE_ARGS = ["prepare", "--site", "go-batch", "--reason", "stuck", "--actions", "retry,halt"]


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_worktree(root, with_parent=True)
            code, out = _run(root, PREPARE_ARGS)
            assert code == 0
            data = json.loads(out)
            assert data["escalate"] is True
            assert data["parent_thread"] == "mh:orch"
            assert data["reply_path"].endswith("_mill/ask-reply.md")
            assert "my-slug" in data["message"]
            print("PASS: prepare escalates when parent_thread is set")

            code, out = _run(root, ["prepare", "--site", "go-batch", "--reason", "s", "--actions", "approve,halt"])
            assert code == 1 and out == ""
            print("PASS: prepare rejects an action the site does not accept")

            reply = root / "_mill" / "ask-reply.md"
            reply.write_text("```yaml\naction: retry\n```\nfix it\n", encoding="utf-8")
            code, out = _run(root, ["consume", "--actions", "retry,halt"])
            assert code == 0
            assert json.loads(out)["action"] == "retry"
            assert not reply.exists()
            print("PASS: consume prints the parsed action and removes the file")

            code, out = _run(root, ["consume", "--actions", "retry,halt"])
            assert code == 0 and json.loads(out)["action"] == "halt"
            print("PASS: consume with no reply file prints halt")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_worktree(root, with_parent=False)
            code, out = _run(root, PREPARE_ARGS)
            assert code == 0 and json.loads(out)["escalate"] is False
            print("PASS: prepare without parent_thread does not escalate")

        print("All millpy-ask-thread unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
