"""Unit tests for plugins/mill/scripts/_ask_parent.py."""
from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

HUB = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))

import _ask_parent  # noqa: E402

NOW = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def _make_worktree(root: Path, with_parent: bool) -> Path:
    mill = root / "_mill"
    mill.mkdir()
    row = "parent_thread: mh:orch\n" if with_parent else ""
    status = mill / "status.md"
    status.write_text(
        f"# Status\n\n```yaml\nphase: planning\n{row}task: T\n```\n\n## Timeline\n\n```text\n```\n",
        encoding="utf-8",
    )
    return status


def _prepare(root: Path, status: Path, cfg: dict, reason: str = "batch stuck") -> dict:
    return _ask_parent.prepare(
        status_path=status,
        worktree_root=root,
        cfg=cfg,
        slug="my-slug",
        site="go-holistic-cap",
        reason=reason,
        actions=["approve", "retry", "halt"],
        now=NOW,
    )


def _write_reply(root: Path, text: str) -> Path:
    reply = _ask_parent.reply_path(root)
    reply.write_text(text, encoding="utf-8")
    return reply


def main() -> int:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = _make_worktree(root, with_parent=False)
            stale = _write_reply(root, "stale")
            result = _prepare(root, status, {})
            assert result == {"escalate": False, "reason": "no parent_thread"}, result
            assert not stale.exists()
            print("PASS: prepare without parent_thread does not escalate and deletes stale reply")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            status = _make_worktree(root, with_parent=True)
            cfg = {"pipeline": {"parent_escalation_timeout_minutes": 0}}
            stale = _write_reply(root, "stale")
            assert _prepare(root, status, cfg) == {"escalate": False, "reason": "disabled"}
            assert not stale.exists()
            print("PASS: prepare with timeout 0 is disabled")

            stale = _write_reply(root, "stale")
            result = _prepare(root, status, {}, reason="café broke\nsecond line")
            assert not stale.exists()
            assert result["escalate"] is True
            assert result["giveup_s"] == 3600
            assert result["parent_thread"] == "mh:orch"
            assert result["unreachable_suffix"] == " (parent_thread mh:orch unreachable)"
            message = result["message"]
            assert message.isascii()
            for needle in ("my-slug", "go-holistic-cap", "caf? broke second line", result["reply_path"],
                           "- approve:", "- retry:", "- halt:", "2026-01-02T04:04:05Z UTC"):
                assert needle in message, f"{needle!r} missing from message"
            print("PASS: prepare escalates with a self-describing ASCII message and 3600s give-up")

            cfg_none = {"pipeline": {"parent_escalation_timeout_minutes": None}}
            assert _ask_parent.timeout_minutes(cfg_none) == 60
            assert _ask_parent.timeout_minutes({"pipeline": {"parent_escalation_timeout_minutes": "x"}}) == 60
            assert _ask_parent.timeout_minutes({"pipeline": {"parent_escalation_timeout_minutes": 5}}) == 5
            print("PASS: timeout_minutes defaults and coerces")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "_mill").mkdir()
            accepted = ["retry", "approve", "halt"]
            for action in accepted:
                reply = _write_reply(root, f"```yaml\naction: {action}\n```\n  do the thing  \n")
                result = _ask_parent.consume(reply, accepted)
                assert result["action"] == action, result
                assert result["guidance"] == "do the thing"
                assert not reply.exists()
            print("PASS: consume returns each accepted action with stripped guidance and deletes the file")

            reply = _write_reply(root, "```yaml\naction: approve\n```\nok")
            assert _ask_parent.consume(reply, ["retry", "halt"])["action"] == "halt"
            print("PASS: consume maps an unaccepted action to halt")

            missing = _ask_parent.reply_path(root)
            assert _ask_parent.consume(missing, accepted) == {"action": "halt", "guidance": "", "halt_suffix": ""}
            print("PASS: consume of a missing file is halt")

            for text in ("just prose", "```yaml\naction: [unclosed\n```\nx", "```yaml\nother: 1\n```\nx"):
                reply = _write_reply(root, text)
                result = _ask_parent.consume(reply, accepted)
                assert result["action"] == "halt", (text, result)
                assert not reply.exists()
            print("PASS: consume degrades to halt without a usable action")

        long_guidance = "\n  \nfirst " + "x" * 300 + "\nsecond"
        suffix = _ask_parent.halt_suffix(long_guidance)
        assert suffix == " -- parent: " + ("first " + "x" * 300)[:200]
        assert "second" not in suffix
        assert _ask_parent.halt_suffix("  \n ") == ""
        print("PASS: halt_suffix truncates and uses the first non-blank line")

        assert _ask_parent.unreachable_suffix("mh:orch") == " (parent_thread mh:orch unreachable)"
        print("PASS: unreachable_suffix")

        assert _ask_parent.parse_actions("retry, halt,retry", "go-batch") == ["retry", "halt"]
        for args in (("bogus",), ("",), ("retry", "nope"), ("approve", "go-batch")):
            try:
                _ask_parent.parse_actions(*args)
                assert False, f"expected ValueError for {args!r}"
            except ValueError:
                pass
        print("PASS: parse_actions rejects bad input")

        for path in (HUB / "mill-config.yaml", HUB / "plugins" / "mill" / "templates" / "mill-config.yaml"):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert (
                data["pipeline"]["parent_escalation_timeout_minutes"] == _ask_parent.DEFAULT_TIMEOUT_MINUTES
            ), path
        print("PASS: hub and template configs carry the default timeout key")

        print("All _ask_parent unit tests passed.")
        return 0
    except AssertionError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
