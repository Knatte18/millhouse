from __future__ import annotations

from pathlib import Path

import tinydb.operations
from tinydb import TinyDB, Query


def _resolve_id_or_slug(db: TinyDB, identifier: int | str) -> int | None:
    query = Query()
    if isinstance(identifier, int):
        doc = db.get(query.id == identifier)
        return doc.doc_id if doc else None
    else:
        doc = db.get(query.slug == identifier)
        return doc.doc_id if doc else None


class Store:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db = TinyDB(str(db_path), indent=2, sort_keys=True)

    def _validate_write(self, tasks_snapshot: list[dict], incoming: dict) -> None:
        # Type validation
        if "group" in incoming:
            raise ValueError("group key is not allowed; use depends_on, isolated, deferred instead")

        depends_on = incoming.get("depends_on", [])
        if not isinstance(depends_on, list) or not all(isinstance(s, str) for s in depends_on):
            raise ValueError("depends_on must be a list of strings")

        isolated = incoming.get("isolated", False)
        if not isinstance(isolated, bool):
            raise ValueError("isolated must be a boolean")

        deferred = incoming.get("deferred", False)
        if not isinstance(deferred, bool):
            raise ValueError("deferred must be a boolean")

        # Build slug set from snapshot
        snapshot_by_slug = {t["slug"]: t for t in tasks_snapshot}
        incoming_slug = incoming["slug"]

        # Dangling dependency check
        for dep_slug in depends_on:
            if dep_slug not in snapshot_by_slug:
                raise ValueError(f"dangling dependency: {dep_slug!r} not found")

        # Target-not-schedulable check: can't depend on isolated or deferred tasks
        for dep_slug in depends_on:
            target = snapshot_by_slug[dep_slug]
            if target.get("isolated", False):
                raise ValueError(f"cannot depend on isolated task {dep_slug!r}")
            if target.get("deferred", False):
                raise ValueError(f"cannot depend on deferred task {dep_slug!r}")

        # Cycle detection using DFS
        def has_cycle_from(start_slug: str, current_slug: str, visited: set, rec_stack: set, path: list) -> bool:
            visited.add(current_slug)
            rec_stack.add(current_slug)
            path.append(current_slug)

            current = snapshot_by_slug.get(current_slug)
            if current:
                for dep in current.get("depends_on", []):
                    if dep not in visited:
                        if has_cycle_from(start_slug, dep, visited, rec_stack, path):
                            return True
                    elif dep in rec_stack:
                        # Found a cycle
                        return True

            rec_stack.remove(current_slug)
            path.pop()
            return False

        # Check for cycles starting from incoming task's dependencies
        for dep_slug in depends_on:
            visited = set()
            rec_stack = set()
            path = []
            if has_cycle_from(incoming_slug, dep_slug, visited, rec_stack, path):
                raise ValueError(f"cycle detected: {incoming_slug} -> {' -> '.join(path)}")

        # Reverse-isolate check: can't make a task isolated if others depend on it
        if isolated:
            reverse_deps = [t["slug"] for t in tasks_snapshot if incoming_slug in t.get("depends_on", [])]
            if reverse_deps:
                raise ValueError(f"cannot isolate {incoming_slug!r}: depended on by {reverse_deps}")

        # Reverse-defer check: can't make a task deferred if non-deferred tasks depend on it
        if deferred:
            reverse_deps = [t["slug"] for t in tasks_snapshot
                          if incoming_slug in t.get("depends_on", []) and not t.get("deferred", False)]
            if reverse_deps:
                raise ValueError(f"cannot defer {incoming_slug!r}: depended on by non-deferred {reverse_deps}")

    def upsert_task(self, task: dict) -> dict:
        slug = task["slug"]
        query = Query()
        existing = self._db.get(query.slug == slug)

        # Build snapshot: all current records, merged with the incoming task
        all_records = self._db.all()
        snapshot = [r for r in all_records if r["slug"] != slug]  # exclude existing

        # Prepare the incoming task with defaults
        if existing:
            incoming = {**existing, **task}
        else:
            max_id = max([t["id"] for t in all_records], default=-1)
            next_id = max_id + 1
            incoming = {
                "id": next_id,
                "slug": slug,
                "depends_on": [],
                "isolated": False,
                "deferred": False,
                "brief": "",
                "body": "",
                "status": None,
                **task
            }

        # Validate before any mutation
        self._validate_write(snapshot + [incoming], incoming)

        if existing:
            existing.update(task)
            self._db.update(existing, query.slug == slug)
            return self._db.get(doc_id=existing.doc_id)
        else:
            doc_id = self._db.insert(incoming)
            return self._db.get(doc_id=doc_id)

    def get_task(self, identifier: int | str) -> dict | None:
        doc_id = _resolve_id_or_slug(self._db, identifier)
        if doc_id is not None:
            return self._db.get(doc_id=doc_id)
        return None

    def remove_task(self, identifier: int | str) -> None:
        doc_id = _resolve_id_or_slug(self._db, identifier)
        if doc_id is not None:
            self._db.remove(doc_ids=[doc_id])

    def set_phase(self, identifier: int | str, phase: str | None) -> None:
        doc_id = _resolve_id_or_slug(self._db, identifier)
        if doc_id is not None:
            task = dict(self._db.get(doc_id=doc_id))
            if phase is None:
                task.pop("status", None)
            else:
                task["status"] = phase
            self._db.remove(doc_ids=[doc_id])
            self._db.insert(task)

    def list_tasks_brief(self) -> list[dict]:
        result = []
        for doc in self._db.all():
            result.append({
                "id": doc["id"],
                "slug": doc["slug"],
                "title": doc.get("title", ""),
                "depends_on": doc.get("depends_on", []),
                "isolated": doc.get("isolated", False),
                "deferred": doc.get("deferred", False),
                "brief": doc.get("brief", ""),
                "status": doc.get("status"),
                "has_proposal": bool(doc.get("body")),
            })
        return result

    def list_tasks_full(self) -> list[dict]:
        return self._db.all()

    def set_deps(self, slug: str, depends_on: list[str]) -> None:
        query = Query()
        existing = self._db.get(query.slug == slug)
        if not existing:
            raise ValueError(f"task not found: {slug!r}")

        # Build incoming record with updated depends_on
        incoming = {**existing, "depends_on": depends_on}

        # Build snapshot: all records with this one replaced
        all_records = self._db.all()
        snapshot = [r for r in all_records if r["slug"] != slug] + [incoming]

        # Validate before mutation
        self._validate_write(snapshot, incoming)

        # Update the database
        self._db.update({"depends_on": depends_on}, query.slug == slug)

    def migrate_group_to_deps(self) -> None:
        for doc in self._db.all():
            if "group" in doc:
                # Drop the group key
                self._db.update(tinydb.operations.delete("group"), doc_ids=[doc.doc_id])
                # Set the new fields
                is_isolated = doc.get("group") == "Z"
                self._db.update(
                    {
                        "depends_on": [],
                        "isolated": is_isolated,
                        "deferred": False
                    },
                    doc_ids=[doc.doc_id]
                )

    def upsert_tasks_batch(self, tasks: list[dict]) -> None:
        # Build full projected snapshot first: current store merged with all incoming tasks
        all_records = self._db.all()
        incoming_slugs = {t["slug"] for t in tasks}

        # Start with current records not being upserted
        base = [r for r in all_records if r["slug"] not in incoming_slugs]

        # Project incoming tasks with defaults
        max_id = max([t["id"] for t in all_records], default=-1)
        projected_incoming = []
        next_id = max_id + 1

        for task in tasks:
            slug = task["slug"]
            query = Query()
            existing = self._db.get(query.slug == slug)

            if existing:
                incoming_task = {**existing, **task}
            else:
                incoming_task = {
                    "id": next_id,
                    "slug": slug,
                    "depends_on": [],
                    "isolated": False,
                    "deferred": False,
                    "brief": "",
                    "body": "",
                    "status": None,
                    **task
                }
                next_id += 1

            projected_incoming.append(incoming_task)

        # Build full snapshot
        snapshot = base + projected_incoming

        # Validate each incoming task
        for incoming in projected_incoming:
            self._validate_write(snapshot, incoming)

        # All validations passed, perform mutations
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
                    "depends_on": [],
                    "isolated": False,
                    "deferred": False,
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
        # Validate upsert payload BEFORE any mutation
        if not isinstance(upsert, dict) or not upsert.get("slug"):
            raise ValueError("merge_tasks requires upsert with non-empty 'slug'")

        # Build projected snapshot: current records minus removals, merged with upsert
        all_records = self._db.all()
        upserting_slug = upsert["slug"]

        # Remove records that will be deleted
        base = [t for t in all_records if t["slug"] not in set(remove_slugs)]

        # Prepare the upserted record
        query = Query()
        existing = self._db.get(query.slug == upserting_slug)

        if existing:
            incoming = {**existing, **upsert}
        else:
            max_id = max([t["id"] for t in all_records], default=-1)
            next_id = max_id + 1
            incoming = {
                "id": next_id,
                "slug": upserting_slug,
                "depends_on": [],
                "isolated": False,
                "deferred": False,
                "brief": "",
                "body": "",
                "status": None,
                **upsert
            }

        # Build snapshot: base + incoming (incoming replaces any existing with same slug)
        snapshot = [r for r in base if r["slug"] != upserting_slug] + [incoming]

        # Validate before any mutation
        self._validate_write(snapshot, incoming)

        # All validations passed, perform mutations
        remove_slugs_set = set(remove_slugs)
        for slug in remove_slugs_set:
            query = Query()
            doc = self._db.get(query.slug == slug)
            if doc:
                self._db.remove(doc_ids=[doc.doc_id])

        if existing:
            existing.update(upsert)
            self._db.update(existing, query.slug == upserting_slug)
            upserted_doc = self._db.get(doc_id=existing.doc_id)
        else:
            doc_id = self._db.insert(incoming)
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

    def close(self) -> None:
        self._db.close()

    def reload(self) -> None:
        self._db.close()
        self._db = TinyDB(str(self._db_path), indent=2, sort_keys=True)

    def all_tasks(self) -> list[dict]:
        return self._db.all()
