from __future__ import annotations

from pathlib import Path

from tinydb import TinyDB, Query


def _resolve_id_or_slug(db: TinyDB, identifier: int | str) -> int | None:
    if isinstance(identifier, int):
        query = Query()
        doc = db.get(doc_id=identifier)
        return identifier if doc else None
    else:
        query = Query()
        doc = db.get(query.slug == identifier)
        return doc.doc_id if doc else None


class Store:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db = TinyDB(str(db_path))

    def upsert_task(self, task: dict) -> dict:
        slug = task["slug"]
        query = Query()
        existing = self._db.get(query.slug == slug)

        if existing:
            existing.update(task)
            self._db.update(existing, query.slug == slug)
            return self._db.get(doc_id=existing.doc_id)
        else:
            max_id = max([t["id"] for t in self._db.all()], default=-1)
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
            doc_id = self._db.insert(new_task)
            return self._db.get(doc_id=doc_id)

    def get_task(self, identifier: int | str) -> dict | None:
        doc_id = _resolve_id_or_slug(self._db, identifier)
        if doc_id is not None:
            return self._db.get(doc_id=doc_id)
        return None

    def remove_task(self, identifier: int | str) -> None:
        doc_id = _resolve_id_or_slug(self._db, identifier)
        if doc_id is not None:
            self._db.remove(doc_id=doc_id)

    def set_phase(self, identifier: int | str, phase: str | None) -> None:
        doc_id = _resolve_id_or_slug(self._db, identifier)
        if doc_id is not None:
            task = self._db.get(doc_id=doc_id)
            if phase is None:
                task.pop("status", None)
            else:
                task["status"] = phase
            self._db.update(task, doc_ids=[doc_id])

    def list_tasks_brief(self) -> list[dict]:
        result = []
        for doc in self._db.all():
            result.append({
                "id": doc["id"],
                "slug": doc["slug"],
                "title": doc.get("title", ""),
                "group": doc.get("group"),
                "brief": doc.get("brief", ""),
                "status": doc.get("status"),
                "has_proposal": bool(doc.get("body")),
            })
        return result

    def list_tasks_full(self) -> list[dict]:
        return self._db.all()

    def upsert_tasks_batch(self, tasks: list[dict]) -> None:
        for task in tasks:
            slug = task["slug"]
            query = Query()
            existing = self._db.get(query.slug == slug)

            if existing:
                existing.update(task)
                self._db.update(existing, query.slug == slug)
            else:
                max_id = max([t["id"] for t in self._db.all()], default=-1)
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

    def merge_tasks(
        self,
        remove_slugs: list[str],
        upsert: dict,
        set_phase: tuple[str, str | None] | None = None,
    ) -> dict:
        with self._db.write_access():
            for slug in remove_slugs:
                query = Query()
                doc = self._db.get(query.slug == slug)
                if doc:
                    self._db.remove(doc_id=doc.doc_id)

            upserting_slug = upsert["slug"]
            query = Query()
            existing = self._db.get(query.slug == upserting_slug)

            if existing:
                existing.update(upsert)
                self._db.update(existing, query.slug == upserting_slug)
                upserted_doc = self._db.get(doc_id=existing.doc_id)
            else:
                max_id = max([t["id"] for t in self._db.all()], default=-1)
                next_id = max_id + 1

                new_task = {
                    "id": next_id,
                    "slug": upserting_slug,
                    "group": None,
                    "brief": "",
                    "body": "",
                    "status": None,
                }
                new_task.update(upsert)
                doc_id = self._db.insert(new_task)
                upserted_doc = self._db.get(doc_id=doc_id)

            if set_phase is not None:
                phase_identifier, phase_value = set_phase
                doc_id = _resolve_id_or_slug(self._db, phase_identifier)
                if doc_id is not None:
                    task = self._db.get(doc_id=doc_id)
                    if phase_value is None:
                        task.pop("status", None)
                    else:
                        task["status"] = phase_value
                    self._db.update(task, doc_ids=[doc_id])

            return self._db.get(doc_id=upserted_doc.doc_id)

    def reload(self) -> None:
        self._db.close()
        self._db = TinyDB(str(self._db_path))

    def all_tasks(self) -> list[dict]:
        return self._db.all()
