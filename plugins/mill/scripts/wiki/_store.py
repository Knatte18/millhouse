from __future__ import annotations

import hashlib
from pathlib import Path

from tinydb import TinyDB, Query

from wiki._parse import parse_home_md
from wiki._render import render


class Store:
    def __init__(self, db_path: Path) -> None:
        self._db = TinyDB(str(db_path))
        self._file_cache: dict[str, tuple[str, str]] = {}
        self._initialized = False

    @staticmethod
    def content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def set(self, rel_path: str, content: str) -> None:
        if rel_path == "Home.md":
            tasks = parse_home_md(content)
            for task in tasks:
                self.upsert_task(task)
            self._initialized = True
        else:
            hash_value = Store.content_hash(content)
            self._file_cache[rel_path] = (content, hash_value)

    def get(self, rel_path: str) -> tuple[str, str] | None:
        if rel_path == "Home.md":
            if not self._initialized:
                return None
            rendered = render(self.all_tasks())
            home_content = rendered["Home.md"]
            return (home_content, Store.content_hash(home_content))
        else:
            return self._file_cache.get(rel_path)

    def invalidate(self, rel_path: str) -> None:
        if rel_path == "Home.md":
            self._initialized = False
        else:
            self._file_cache.pop(rel_path, None)

    def upsert_task(self, task: dict) -> None:
        slug = task["slug"]
        slug_query = Query()
        existing = self._db.get(slug_query.slug == slug)

        if existing:
            existing.update(task)
            self._db.update(existing, slug_query.slug == slug)
        else:
            max_id = 0
            for doc in self._db.all():
                if isinstance(doc.get("id"), int) and doc["id"] > max_id:
                    max_id = doc["id"]
            next_id = max_id + 1

            new_task = {
                "id": next_id,
                "slug": slug,
                "group": None,
                "brief": "",
                "body": "",
                "status": None,
            }
            new_task.update(task)
            self._db.insert(new_task)

    def all_tasks(self) -> list[dict]:
        return self._db.all()

    def get_by_slug(self, slug: str) -> dict | None:
        slug_query = Query()
        return self._db.get(slug_query.slug == slug)
