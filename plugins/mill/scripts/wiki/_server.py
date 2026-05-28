"""Wiki daemon server — handles structured task operations with TinyDB and git integration."""
import logging
import logging.handlers
import os
import time
from pathlib import Path
import sys

from _daemon import DaemonBase
from wiki import (
    FIELD_OP,
    OP_UPSERT_TASK,
    OP_UPSERT_TASKS_BATCH,
    OP_SET_PHASE,
    OP_REMOVE_TASK,
    OP_MERGE_TASKS,
    OP_GET_TASK,
    OP_LIST_TASKS_BRIEF,
    OP_LIST_TASKS_FULL,
    OP_HEALTH,
    OP_RERENDER,
    OP_SHUTDOWN,
    FIELD_OK,
    FIELD_ERROR_TYPE,
    FIELD_ERROR,
    ERR_NOT_FOUND,
    ERR_PUSH_FAILED,
    ERR_PROTOCOL,
    WikiPushError,
)
from wiki._render import render
from wiki._store import Store
from wiki._sync import pull, atomic_write, commit_push


class WikiServer(DaemonBase):
    """Wiki daemon server — structured task operations with TinyDB."""

    _protocol_version = 2

    def __init__(
        self,
        wiki_path: Path,
        *,
        idle_timeout: int = 600,
        refresh_interval: float = 10.0,
    ) -> None:
        """Initialize wiki server.

        Args:
            wiki_path: Path to wiki clone root.
            idle_timeout: Seconds before idle-exit.
            refresh_interval: Seconds between lazy pulls.
        """
        super().__init__("wiki", wiki_path / ".wiki-daemon.json", idle_timeout)
        self._wiki_path = wiki_path
        self._refresh_interval = refresh_interval
        self._store = Store(wiki_path / "tasks.json")
        self._last_pull: float = 0.0

        self._log = logging.getLogger("wiki-server")
        for h in list(self._log.handlers):
            try:
                h.close()
            except Exception:
                pass
            self._log.removeHandler(h)
        self._log.setLevel(logging.INFO)
        self._log.propagate = False
        if os.environ.get("WIKI_DAEMON_SKIP_GIT") == "1":
            self._log.addHandler(logging.NullHandler())
        else:
            handler = logging.handlers.RotatingFileHandler(
                wiki_path / ".wiki-daemon.log",
                maxBytes=1_000_000,
                backupCount=2,
                mode="w",
            )
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            )
            self._log.addHandler(handler)

    def on_start(self, port: int, token: str) -> None:
        """Log startup and ensure gitignore."""
        self._log.info("wiki-server started pid=%d port=%d" % (os.getpid(), port))
        self._ensure_gitignore()

    def on_stop(self) -> None:
        """Log shutdown, close the store, release log handlers."""
        self._log.info("wiki-server stopping")
        try:
            self._store.close()
        except Exception:
            pass
        for handler in list(self._log.handlers):
            try:
                handler.close()
            except Exception:
                pass
            self._log.removeHandler(handler)

    def handle_request(self, msg: dict) -> dict:
        """Dispatch request on operation type."""
        op = msg.get(FIELD_OP)
        payload = msg.get("payload", {})

        if op == OP_UPSERT_TASK:
            return self._handle_upsert_task(payload)
        elif op == OP_UPSERT_TASKS_BATCH:
            return self._handle_upsert_tasks_batch(payload)
        elif op == OP_SET_PHASE:
            return self._handle_set_phase(payload)
        elif op == OP_REMOVE_TASK:
            return self._handle_remove_task(payload)
        elif op == OP_GET_TASK:
            return self._handle_get_task(payload)
        elif op == OP_LIST_TASKS_BRIEF:
            return self._handle_list_tasks_brief(payload)
        elif op == OP_LIST_TASKS_FULL:
            return self._handle_list_tasks_full(payload)
        elif op == OP_MERGE_TASKS:
            return self._handle_merge_tasks(payload)
        elif op == OP_HEALTH:
            return self._handle_health(payload)
        elif op == OP_RERENDER:
            return self._handle_rerender(payload)
        elif op == OP_SHUTDOWN:
            return self._handle_shutdown(payload)
        else:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: f"unknown op: {op}",
            }

    def _handle_upsert_task(self, payload: dict) -> dict:
        """Handle upsert_task operation."""
        try:
            task = self._store.upsert_task(payload)
            self._render_and_commit_all(slug_for_msg=payload.get("slug", "task"))
            return {FIELD_OK: True, "task": task}
        except WikiPushError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                FIELD_ERROR: str(e),
            }
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _handle_upsert_tasks_batch(self, payload: dict) -> dict:
        """Handle upsert_tasks_batch operation."""
        try:
            tasks = payload.get("tasks", [])
            message = payload.get("message")
            self._store.upsert_tasks_batch(tasks)
            msg = message if message else "batch"
            self._render_and_commit_all(slug_for_msg=msg)
            return {FIELD_OK: True, "count": len(tasks)}
        except WikiPushError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                FIELD_ERROR: str(e),
            }
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _handle_set_phase(self, payload: dict) -> dict:
        """Handle set_phase operation."""
        try:
            id_or_slug = payload.get("id_or_slug")
            phase = payload.get("phase")

            self._store.set_phase(id_or_slug, phase)
            self._render_and_commit_all(slug_for_msg=str(id_or_slug))
            return {FIELD_OK: True}
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_NOT_FOUND,
                FIELD_ERROR: str(e),
            }

    def _handle_remove_task(self, payload: dict) -> dict:
        """Handle remove_task operation."""
        try:
            id_or_slug = payload.get("id_or_slug")
            task = self._store.get_task(id_or_slug)
            if task is None:
                return {
                    FIELD_OK: False,
                    FIELD_ERROR_TYPE: ERR_NOT_FOUND,
                    FIELD_ERROR: f"task not found: {id_or_slug}",
                }
            self._store.remove_task(id_or_slug)
            self._render_and_commit_all(slug_for_msg=str(id_or_slug))
            return {FIELD_OK: True}
        except WikiPushError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                FIELD_ERROR: str(e),
            }
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _handle_get_task(self, payload: dict) -> dict:
        """Handle get_task operation."""
        try:
            id_or_slug = payload.get("id_or_slug")
            task = self._store.get_task(id_or_slug)
            return {FIELD_OK: True, "task": task}
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _handle_list_tasks_brief(self, payload: dict) -> dict:
        """Handle list_tasks_brief operation."""
        try:
            tasks = self._store.list_tasks_brief()
            return {FIELD_OK: True, "tasks": tasks}
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _handle_list_tasks_full(self, payload: dict) -> dict:
        """Handle list_tasks_full operation."""
        try:
            tasks = self._store.list_tasks_full()
            return {FIELD_OK: True, "tasks": tasks}
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _handle_health(self, payload: dict) -> dict:
        """Handle health check operation."""
        return {FIELD_OK: True}

    def _handle_rerender(self, payload: dict) -> dict:
        """Re-render derived files (Home.md, _Sidebar.md, proposal-*.md) from tasks.json.

        Commits and pushes only if the render output differs from on-disk content;
        a no-op render returns OK without producing a commit.
        """
        try:
            self._render_and_commit_all(slug_for_msg="rerender")
            return {FIELD_OK: True}
        except WikiPushError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                FIELD_ERROR: str(e),
            }
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _handle_shutdown(self, payload: dict) -> dict:
        """Request a clean daemon shutdown. The accept loop exits after this reply is sent."""
        self.request_shutdown()
        return {FIELD_OK: True}

    def _handle_merge_tasks(self, payload: dict) -> dict:
        """Handle merge_tasks operation."""
        try:
            remove_slugs = payload.get("remove_slugs", [])
            upsert = payload.get("upsert", {})
            set_phase_tuple = payload.get("set_phase")

            task = self._store.merge_tasks(
                remove_slugs=remove_slugs,
                upsert=upsert,
                set_phase=set_phase_tuple,
            )
            self._render_and_commit_all(slug_for_msg=upsert.get("slug", "merge"))
            return {FIELD_OK: True, "task": task}
        except WikiPushError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                FIELD_ERROR: str(e),
            }
        except Exception as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: str(e),
            }

    def _render_and_commit_all(self, slug_for_msg: str) -> None:
        """Pull, reload, render, write, and commit all files.

        This is the canonical sequence for all mutating operations.

        Two test-only env vars trim the git workload:
        - ``WIKI_DAEMON_SKIP_GIT=1`` — skip pull, commit, and push entirely.
          Renders + writes files only. Use when no test asserts on git state.
        - ``WIKI_DAEMON_SKIP_PUSH=1`` — pull + commit run, push is skipped.
          Use when a test asserts on commit log content.

        SKIP_GIT takes precedence. Production callers leave both unset.
        """
        skip_git = os.environ.get("WIKI_DAEMON_SKIP_GIT") == "1"
        skip_push = os.environ.get("WIKI_DAEMON_SKIP_PUSH") == "1"

        # Pull before render
        if not skip_git and not skip_push:
            try:
                pull(self._wiki_path)
                self._store.reload()
                self._last_pull = time.monotonic()
            except WikiPushError:
                pass

        # Render all tasks
        rendered = render(self._store.all_tasks())

        # Atomic write each rendered file
        for rel_path, content in rendered.items():
            atomic_write(self._wiki_path, rel_path, content)

        if skip_git:
            return

        # Commit and push
        commit_paths = list(rendered.keys()) + ["tasks.json"]
        commit_paths = list(dict.fromkeys(commit_paths))
        message = f"wiki: {slug_for_msg}"

        try:
            commit_push(self._wiki_path, commit_paths, message)
            # Reload after successful push to pick up any cross-host changes from rebase
            self._store.reload()
        except WikiPushError:
            raise

    def _ensure_gitignore(self) -> None:
        """Ensure .gitignore contains daemon artifact entries."""
        gitignore_path = self._wiki_path / ".gitignore"

        # Read existing content
        try:
            content = gitignore_path.read_text("utf-8")
        except FileNotFoundError:
            content = ""

        # Check if both entries are present as lines
        lines = content.splitlines()
        has_json = any(line.strip() == ".wiki-daemon.json" for line in lines)
        has_log = any(line.strip() == ".wiki-daemon.log" for line in lines)

        if has_json and has_log:
            return

        # Append missing entries
        lines = content.rstrip("\n").split("\n") if content.strip() else []
        if not has_json:
            lines.append(".wiki-daemon.json")
        if not has_log:
            lines.append(".wiki-daemon.log")

        new_content = "\n".join(lines) + "\n"
        gitignore_path.write_text(new_content, "utf-8")

        # Skip the commit entirely under WIKI_DAEMON_SKIP_GIT (test mode).
        if os.environ.get("WIKI_DAEMON_SKIP_GIT") == "1":
            return

        # Try to commit (non-fatal on failure). commit_push internally honors
        # WIKI_DAEMON_SKIP_PUSH and stops after the local commit when set.
        try:
            commit_push(self._wiki_path, [".gitignore"], "chore(wiki): gitignore daemon artifacts")
        except Exception as e:
            self._log.warning("failed to commit .gitignore: %s" % str(e))


if __name__ == "__main__":
    wiki_path = Path(sys.argv[1])
    idle_timeout = 600
    try:
        env_idle = os.environ.get("WIKI_DAEMON_IDLE_TIMEOUT")
        if env_idle:
            idle_timeout = int(env_idle)
    except (ValueError, TypeError):
        pass
    if idle_timeout == 600 and len(sys.argv) > 2:
        idle_timeout = int(sys.argv[2])
    refresh_interval = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
    WikiServer(wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval).run()
