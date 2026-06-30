"""
Sandbox-report helper — reads and validates a local sandbox-report.json file.

Sister module to ``_gh_issues.py``: where ``_gh_issues.to_contract()`` maps
``gh``-fetched issues into the triage-report contract, this module reads a
local JSON file already shaped like that contract and validates it strictly
before handing it to ``mill-triage-to-tasks`` (see
``plugins/mill/templates/triage-report.schema.md``). It performs no network
or ``gh`` calls -- the input is an already-resolved ``Path`` on disk.

Public API:
    read(path: Path) -> dict
        Parses and validates ``path`` as a sandbox-report.json file. Raises
        SandboxReportError on any malformed input (bad JSON, wrong
        top-level shape, wrong ``source``, missing/empty item fields,
        duplicate ``ref`` values). On success, returns the full
        triage-report contract envelope with ``ref_prefix=""``,
        ``detail_hint=None``, ``embed_body=True``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class SandboxReportError(RuntimeError):
    """Raised when a sandbox-report.json file fails to parse or validate."""


def read(path: Path) -> dict[str, Any]:
    """Parse and strictly validate ``path`` as a sandbox-report.json file.

    A sandbox-report.json file carries internal QA verdicts produced by an
    external sandbox suite (see ``_mill/discussion.md``). This function
    treats any deviation from the expected shape -- wrong ``source``, a
    malformed item, a duplicate ``ref`` -- as "wrong file passed" and fails
    loudly rather than coercing the input, since a silently-accepted bad
    file would corrupt the decision table inside ``mill-triage-to-tasks``.

    Steps:
        1. Open and parse ``path`` as JSON. Raise on file-not-found or a
           JSON syntax error.
        2. Require the parsed value to be a JSON object, and require its
           ``source`` field to equal ``"sandbox-report"`` exactly.
        3. Require ``items`` to be present and to be a JSON array. An empty
           array is valid -- this function never decides "nothing to do";
           that split belongs to the entry skill (empty array, knowable
           from the file alone) and the shared skill (every item routed to
           skip, only knowable after grouping).
        4. Validate each item has non-empty string ``ref``, ``title``,
           ``body`` fields, and that no ``ref`` repeats across items.
        5. Map ``items`` into the contract's item shape and return the full
           envelope, passing ``meta`` through verbatim from the file (or
           ``{}`` when absent) -- this function never reads or interprets
           ``meta``'s contents.

    Args:
        path: Path to the sandbox-report.json file to read.

    Returns:
        The full triage-report contract envelope: ``{"source":
        "sandbox-report", "meta": <passthrough>, "items": [{"ref": str,
        "title": str, "body": str}, ...], "ref_prefix": "", "detail_hint":
        None, "embed_body": True}``.

    Raises:
        SandboxReportError: ``path`` does not exist, is not valid JSON, is
            not a JSON object, has the wrong (or missing) ``source`` value,
            is missing or has a malformed ``items`` array, has an item
            missing/with an empty ``ref``/``title``/``body``, or has a
            duplicate ``ref`` across items.
    """
    try:
        raw_text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SandboxReportError(f"sandbox-report file not found: {path}") from exc

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise SandboxReportError(f"sandbox-report file at {path} is not valid JSON: {exc}") from exc

    # The top-level value must be a JSON object -- a bare array or string is
    # not a valid sandbox-report file, and calling .get() on it would raise
    # an uncaught AttributeError instead of a clear validation error.
    if not isinstance(data, dict):
        raise SandboxReportError(
            f"sandbox-report file at {path} must contain a JSON object at the top level, got {type(data).__name__}"
        )

    # Reject any file that isn't explicitly stamped as a sandbox-report --
    # this is much more likely to be a wrong-file-passed mistake than
    # something to recover from silently.
    source = data.get("source")
    if source != "sandbox-report":
        raise SandboxReportError(
            f"sandbox-report file at {path} has source={source!r}, expected 'sandbox-report'"
        )

    items = data.get("items")
    if not isinstance(items, list):
        raise SandboxReportError(
            f"sandbox-report file at {path} is missing an 'items' array (or it is not a list)"
        )

    # Validate every item up front and track refs seen so far -- a
    # duplicate ref would corrupt the consumed-items tracking inside
    # mill-triage-to-tasks, so it is rejected outright.
    seen_refs: set[str] = set()
    mapped_items: list[dict[str, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise SandboxReportError(
                f"sandbox-report file at {path}: item at index {index} is not a JSON object"
            )
        for field in ("ref", "title", "body"):
            value = item.get(field)
            if not isinstance(value, str) or not value:
                raise SandboxReportError(
                    f"sandbox-report file at {path}: item at index {index} has a missing or empty '{field}' field"
                )
        ref = item["ref"]
        if ref in seen_refs:
            raise SandboxReportError(
                f"sandbox-report file at {path}: duplicate ref {ref!r} found at item index {index}"
            )
        seen_refs.add(ref)
        mapped_items.append({"ref": ref, "title": item["title"], "body": item["body"]})

    return {
        "source": "sandbox-report",
        "meta": data.get("meta", {}),
        "items": mapped_items,
        "ref_prefix": "",
        "detail_hint": None,
        "embed_body": True,
    }
