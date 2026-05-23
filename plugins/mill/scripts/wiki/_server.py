"""Wiki daemon server — handles read/write requests with in-process caching and git operations."""
import logging
import logging.handlers
import os
import time
from pathlib import Path
import sys

from _daemon import DaemonBase
from wiki import (
    FIELD_OP,
    OP_READ,
    OP_WRITE,
    FIELD_OK,
    FIELD_CONTENT,
    FIELD_HASH,
    FIELD_ERROR_TYPE,
    FIELD_ERROR,
    FIELD_PATH,
    FIELD_FILES,
    FIELD_MESSAGE,
    FIELD_BASE_HASH,
    FIELD_NEW_CONTENT,
    ERR_NOT_FOUND,
    ERR_CONFLICT,
    ERR_PUSH_FAILED,
    ERR_PROTOCOL,
    ERR_PATH,
    WikiPathError,
    WikiPushError,
)
from wiki._render import render
from wiki._store import Store
from wiki._sync import path_guard, pull, atomic_write, commit_push


class WikiServer(DaemonBase):
    """Wiki daemon server — in-process cache, lazy refresh, CAS writes."""

    _protocol_version = 1

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

        # Set up rotating file logger
        handler = logging.handlers.RotatingFileHandler(
            wiki_path / ".wiki-daemon.log",
            maxBytes=1_000_000,
            backupCount=2,
            mode="w",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        self._log = logging.getLogger("wiki-server")
        self._log.addHandler(handler)
        self._log.setLevel(logging.INFO)
        self._log.propagate = False

    def on_start(self, port: int, token: str) -> None:
        """Log startup and ensure gitignore."""
        self._log.info("wiki-server started pid=%d port=%d" % (os.getpid(), port))
        self._ensure_gitignore()

    def on_stop(self) -> None:
        """Log shutdown."""
        self._log.info("wiki-server stopping")

    def handle_request(self, msg: dict) -> dict:
        """Dispatch request on operation type."""
        op = msg.get(FIELD_OP)
        if op == OP_READ:
            return self._handle_read(msg)
        elif op == OP_WRITE:
            return self._handle_write(msg)
        else:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PROTOCOL,
                FIELD_ERROR: "unknown op",
            }

    def _handle_read(self, msg: dict) -> dict:
        """Handle read request with lazy refresh and caching."""
        rel_path = msg.get(FIELD_PATH, "")

        try:
            path_guard(rel_path)
        except WikiPathError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PATH,
                FIELD_ERROR: str(e),
            }

        # Lazy refresh: check if we should pull
        now = time.monotonic()
        if now - self._last_pull > self._refresh_interval:
            try:
                pull(self._wiki_path)
                # Repopulate TinyDB from pulled state
                try:
                    disk_content = (self._wiki_path / "Home.md").read_text("utf-8")
                    self._store.set("Home.md", disk_content)
                except FileNotFoundError:
                    pass
                self._last_pull = time.monotonic()
            except WikiPushError as e:
                self._log.warning("lazy refresh failed, serving cache: %s" % str(e))

        # Try cache hit
        hit = self._store.get(rel_path)
        if hit is not None:
            return {
                FIELD_OK: True,
                FIELD_CONTENT: hit[0],
                FIELD_HASH: hit[1],
            }

        # Cache miss: read from disk
        try:
            content = (self._wiki_path / rel_path).read_text("utf-8")
        except FileNotFoundError:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_NOT_FOUND,
                FIELD_ERROR: rel_path,
            }

        # Store in cache and return
        self._store.set(rel_path, content)
        result = self._store.get(rel_path)
        if result is None:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_NOT_FOUND,
                FIELD_ERROR: rel_path,
            }
        return {
            FIELD_OK: True,
            FIELD_CONTENT: result[0],
            FIELD_HASH: result[1],
        }

    def _handle_write(self, msg: dict) -> dict:
        """Handle write request with CAS checking and TinyDB integration."""
        files_payload = msg.get(FIELD_FILES, {})
        message = msg.get(FIELD_MESSAGE, "wiki: update")

        # Step 1: Pull before write
        try:
            pull(self._wiki_path)
        except WikiPushError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                FIELD_ERROR: str(e),
            }

        # Step 2: Repopulate TinyDB from pulled state
        if "Home.md" in files_payload or self._store.get("Home.md") is None:
            try:
                disk_content = (self._wiki_path / "Home.md").read_text("utf-8")
                self._store.set("Home.md", disk_content)
            except FileNotFoundError:
                pass
            self._last_pull = time.monotonic()

        # Step 3: CAS check for each file
        for rel_path, entry in files_payload.items():
            try:
                path_guard(rel_path)
            except WikiPathError as e:
                return {
                    FIELD_OK: False,
                    FIELD_ERROR_TYPE: ERR_PATH,
                    FIELD_ERROR: str(e),
                }

            # Compute current_hash
            if rel_path == "Home.md":
                home_cached = self._store.get("Home.md")
                current_hash = home_cached[1] if home_cached is not None else ""
            else:
                cached = self._store.get(rel_path)
                if cached is not None:
                    current_hash = cached[1]
                else:
                    full_path = self._wiki_path / rel_path
                    try:
                        disk_content = full_path.read_text("utf-8")
                        current_hash = Store.content_hash(disk_content)
                    except FileNotFoundError:
                        current_hash = ""

            # CAS check
            base_hash = entry.get(FIELD_BASE_HASH, "")
            if base_hash != current_hash:
                return {
                    FIELD_OK: False,
                    FIELD_ERROR_TYPE: ERR_CONFLICT,
                    FIELD_ERROR: f"conflict on {rel_path}",
                }

        # Step 4: atomic_write each client file
        for rel_path, entry in files_payload.items():
            new_content = entry.get(FIELD_NEW_CONTENT, "")
            try:
                atomic_write(self._wiki_path, rel_path, new_content)
            except OSError as e:
                return {
                    FIELD_OK: False,
                    FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                    FIELD_ERROR: str(e),
                }

        # Step 5: Update TinyDB
        for rel_path, entry in files_payload.items():
            new_content = entry.get(FIELD_NEW_CONTENT, "")
            self._store.set(rel_path, new_content)

        # Step 6: Render
        rendered = render(self._store.all_tasks())
        for rel_path, content in rendered.items():
            try:
                atomic_write(self._wiki_path, rel_path, content)
            except OSError as e:
                return {
                    FIELD_OK: False,
                    FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                    FIELD_ERROR: str(e),
                }

        # Step 7: Commit
        commit_paths = list(files_payload.keys()) + list(rendered.keys()) + ["tasks.json"]
        commit_paths = list(dict.fromkeys(commit_paths))
        try:
            commit_push(self._wiki_path, commit_paths, message)
        except WikiPushError as e:
            return {
                FIELD_OK: False,
                FIELD_ERROR_TYPE: ERR_PUSH_FAILED,
                FIELD_ERROR: str(e),
            }

        # Step 8: Invalidate non-Home.md cache entries
        for rel_path in files_payload.keys():
            if rel_path != "Home.md":
                self._store.invalidate(rel_path)

        return {FIELD_OK: True}

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

        # Try to commit (non-fatal on failure)
        try:
            commit_push(self._wiki_path, [".gitignore"], "chore(wiki): gitignore daemon artifacts")
        except Exception as e:
            self._log.warning("failed to commit .gitignore: %s" % str(e))


if __name__ == "__main__":
    wiki_path = Path(sys.argv[1])
    idle_timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    refresh_interval = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0
    WikiServer(wiki_path, idle_timeout=idle_timeout, refresh_interval=refresh_interval).run()
