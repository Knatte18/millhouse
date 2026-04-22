"""
Validate the Batch Index DAG in a plan overview file.

mill-plan writes ``<WIKI_PATH>/active/<slug>/plan/00-overview.md`` with a
fenced ``yaml`` block declaring every batch and its ``depends-on:``
edges. Before handing the plan off for review, the skill must
self-validate that block — catching obvious cycles and dangling
references cheaply, rather than paying for a round of reviewer tokens
to discover the same.

The reviewer still does its own check (see ``review-plan-holistic.md``
criteria). This module is the pre-check; it is not authoritative.

Public API:
    PlanDAGError — raised on any structural failure
    extract_batch_index(overview_text) -> list[dict]
        Parse the first ``batches:`` fenced-yaml block out of the
        overview text. Raises on malformed input.
    validate(batches, batch_files) -> None
        Run all structural checks. Raises on the first problem.
        ``batch_files`` is the list of batch filenames present in the
        plan dir (relative names, e.g. ``["01-foundation.md", ...]``),
        used to check ``file:`` references resolve.

Structure expected inside the fenced block:

    batches:
      - name: foundation
        file: 01-foundation.md
        depends-on: []
        verify: pytest tests/foundation/ -q
      - name: reviewers
        file: 02-reviewers.md
        depends-on: [foundation]
        verify: null

``verify:`` may be null. ``depends-on:`` may be ``[]``. ``name:`` and
``file:`` are required per batch.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml


class PlanDAGError(Exception):
    """Raised by :func:`validate` on any structural failure.

    Callers (mill-plan skill) catch this, surface the message to the
    user, and abort before committing the plan. The message names the
    failing batch/edge so the LLM can self-correct in the same session.
    """


# Match a ``yaml`` fenced block whose first non-blank inner line is
# ``batches:``. This is how we distinguish the Batch Index block from
# any other ``yaml`` block (e.g. the overview frontmatter).
_BATCHES_BLOCK_RE = re.compile(
    r"```yaml\s*\n(?P<body>(?:\s*\n)*batches:[\s\S]*?)```",
    re.MULTILINE,
)


def extract_batch_index(overview_text: str) -> list[dict]:
    """Return the list of batch entries from the first ``batches:`` block.

    Args:
        overview_text: Contents of ``00-overview.md``.

    Returns:
        The ``batches`` list from the yaml block, as plain dicts.

    Raises:
        PlanDAGError: No ``batches:`` block is present, the yaml is
            malformed, or the block contains no ``batches:`` key at the
            top level.
    """
    match = _BATCHES_BLOCK_RE.search(overview_text)
    if match is None:
        raise PlanDAGError(
            "Batch Index DAG missing: no ```yaml ... batches: ... ``` block in 00-overview.md"
        )
    body = match.group("body")
    try:
        data = yaml.safe_load(body) or {}
    except yaml.YAMLError as exc:
        raise PlanDAGError(f"Batch Index yaml parse error: {exc}") from exc
    if not isinstance(data, dict) or "batches" not in data:
        raise PlanDAGError("Batch Index block lacks top-level `batches:` key")
    batches = data["batches"]
    if not isinstance(batches, list):
        raise PlanDAGError("`batches:` must be a list")
    return batches


def _check_shapes(batches: list[dict]) -> None:
    """Verify each batch entry has ``name:`` and ``file:`` strings.

    ``depends-on:`` defaults to ``[]`` if absent. ``verify:`` may be
    any string or null — we do not enforce the shape of verify commands
    here; that is a reviewer concern.
    """
    seen_names: set[str] = set()
    for i, entry in enumerate(batches):
        if not isinstance(entry, dict):
            raise PlanDAGError(f"Batch entry #{i} is not a mapping: {entry!r}")
        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise PlanDAGError(f"Batch entry #{i} missing `name:` string")
        if name in seen_names:
            raise PlanDAGError(f"Duplicate batch name: {name!r}")
        seen_names.add(name)
        file_ref = entry.get("file")
        if not isinstance(file_ref, str) or not file_ref:
            raise PlanDAGError(f"Batch {name!r} missing `file:` string")
        deps = entry.get("depends-on", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            raise PlanDAGError(
                f"Batch {name!r} `depends-on:` must be a list of strings"
            )


def _check_file_refs(batches: list[dict], batch_files: list[str]) -> None:
    """Verify every ``file:`` exists in ``batch_files`` and vice versa.

    Both directions are errors:
    - a declared batch whose file is missing on disk → planner skipped a
      write.
    - a file on disk that no batch entry references → planner left an
      orphan file.
    """
    declared = {entry["file"] for entry in batches}
    actual = set(batch_files)
    missing = declared - actual
    if missing:
        raise PlanDAGError(
            f"Batch Index references file(s) not on disk: {sorted(missing)}"
        )
    orphaned = actual - declared
    if orphaned:
        raise PlanDAGError(
            f"Batch file(s) on disk not listed in Batch Index: {sorted(orphaned)}"
        )


def _check_deps(batches: list[dict]) -> None:
    """Verify every ``depends-on:`` entry names a known batch."""
    names = {entry["name"] for entry in batches}
    for entry in batches:
        for dep in entry.get("depends-on", []):
            if dep not in names:
                raise PlanDAGError(
                    f"Batch {entry['name']!r} depends on unknown batch {dep!r}"
                )
            if dep == entry["name"]:
                raise PlanDAGError(f"Batch {entry['name']!r} depends on itself")


def _check_acyclic(batches: list[dict]) -> None:
    """Kahn's-algorithm topological sort; raise if any node remains.

    A remaining node after the queue drains means it is inside a cycle
    (never had zero in-degree). We report all remaining nodes so the
    planner sees the whole cycle, not one edge at a time.
    """
    indegree: dict[str, int] = {entry["name"]: 0 for entry in batches}
    adj: dict[str, list[str]] = {entry["name"]: [] for entry in batches}
    for entry in batches:
        for dep in entry.get("depends-on", []):
            adj[dep].append(entry["name"])
            indegree[entry["name"]] += 1

    queue = [n for n, d in indegree.items() if d == 0]
    visited = 0
    while queue:
        n = queue.pop(0)
        visited += 1
        for m in adj[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                queue.append(m)
    if visited != len(batches):
        remaining = [n for n, d in indegree.items() if d > 0]
        raise PlanDAGError(
            f"Cycle detected in Batch Index DAG; batches still in cycle: {sorted(remaining)}"
        )


_FRONTMATTER_BLOCK_RE = re.compile(
    r"```yaml\s*\n(?P<body>[\s\S]*?)```",
    re.MULTILINE,
)


def _read_batch_frontmatter(batch_path: Path) -> dict:
    """Return the first fenced-yaml block of a batch file as a dict.

    Returns ``{}`` on any structural problem — the caller (typically
    the verify-iterator) treats a malformed batch as "no verify
    command" rather than escalating. A batch with a broken frontmatter
    would have been rejected by the plan-reviewer long before a merge
    is attempted.
    """
    try:
        text = batch_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    match = _FRONTMATTER_BLOCK_RE.search(text)
    if match is None:
        return {}
    try:
        data = yaml.safe_load(match.group("body")) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def iter_batch_verifies(plan_dir: Path) -> list[tuple[str, str]]:
    """Return ``(batch_name, verify_cmd)`` pairs in DAG execution order.

    mill-merge-in's Verify step replays exactly the checks that ran
    during implementation: each batch's ``verify:`` from its
    frontmatter, in the same order mill-go dispatched them
    (``topo_order``). Batches whose ``verify:`` is ``null`` or missing
    are skipped silently — pure-docs batches have no runnable surface
    and forcing a sentinel command there would be noise.

    If the plan overview is missing or malformed, returns ``[]`` and
    the caller falls back to "nothing to verify".
    """
    overview = plan_dir / "00-overview.md"
    if not overview.exists():
        return []
    try:
        batches = extract_batch_index(overview.read_text(encoding="utf-8"))
    except PlanDAGError:
        return []

    try:
        order = topo_order(batches)
    except PlanDAGError:
        return []

    file_by_name = {entry["name"]: entry.get("file") for entry in batches}

    commands: list[tuple[str, str]] = []
    for name in order:
        file_ref = file_by_name.get(name)
        if not file_ref:
            continue
        frontmatter = _read_batch_frontmatter(plan_dir / file_ref)
        verify = frontmatter.get("verify")
        if isinstance(verify, str) and verify.strip():
            commands.append((name, verify.strip()))
    return commands


def topo_order(batches: list[dict]) -> list[str]:
    """Return a topological ordering of batch names.

    mill-go consumes this to decide execution order: batches appear in
    an order compatible with every ``depends-on:`` edge. Among batches
    that share a dependency level we break ties by the order they
    appear in the input — which matches the authored order in the
    overview and gives a predictable execution timeline.

    Assumes ``validate(batches, ...)`` has already been called so the
    input is structurally sound (no cycles, no dangling refs). If the
    graph contains a cycle this function raises ``PlanDAGError`` — a
    safety net in case the caller skipped validation.
    """
    indegree: dict[str, int] = {entry["name"]: 0 for entry in batches}
    adj: dict[str, list[str]] = {entry["name"]: [] for entry in batches}
    for entry in batches:
        for dep in entry.get("depends-on", []):
            adj[dep].append(entry["name"])
            indegree[entry["name"]] += 1

    # Stable-priority queue: preserve authored order among zero-indegree
    # nodes by draining them in batch-list sequence.
    order_hint = {entry["name"]: i for i, entry in enumerate(batches)}
    queue: list[str] = sorted(
        [n for n, d in indegree.items() if d == 0],
        key=lambda n: order_hint[n],
    )

    result: list[str] = []
    while queue:
        n = queue.pop(0)
        result.append(n)
        new_ready: list[str] = []
        for m in adj[n]:
            indegree[m] -= 1
            if indegree[m] == 0:
                new_ready.append(m)
        if new_ready:
            queue.extend(sorted(new_ready, key=lambda n: order_hint[n]))
    if len(result) != len(batches):
        raise PlanDAGError(
            "Cycle detected during topological sort; call validate() first"
        )
    return result


def validate(batches: list[dict], batch_files: list[str]) -> None:
    """Run every structural check on ``batches`` against ``batch_files``.

    On success returns ``None``. On failure raises ``PlanDAGError`` with
    a message naming the first problem encountered — order matters
    because later checks assume earlier invariants hold (e.g. the cycle
    check assumes dep-refs are valid).
    """
    _check_shapes(batches)
    _check_file_refs(batches, batch_files)
    _check_deps(batches)
    _check_acyclic(batches)


if __name__ == "__main__":
    # Minimal good plan
    good = """
```yaml
batches:
  - name: foundation
    file: 01-foundation.md
    depends-on: []
    verify: pytest tests/foundation/ -q
  - name: reviewers
    file: 02-reviewers.md
    depends-on: [foundation]
    verify: null
  - name: templates
    file: 03-templates.md
    depends-on: [foundation]
    verify: null
  - name: integration
    file: 04-integration.md
    depends-on: [reviewers, templates]
    verify: pytest tests/integration/ -q
```
"""
    batches = extract_batch_index(good)
    validate(batches, ["01-foundation.md", "02-reviewers.md", "03-templates.md", "04-integration.md"])
    print("PASS: good plan accepted")

    # Cycle
    cycle = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: [b]
  - name: b
    file: 02-b.md
    depends-on: [a]
```
"""
    batches = extract_batch_index(cycle)
    try:
        validate(batches, ["01-a.md", "02-b.md"])
    except PlanDAGError as exc:
        assert "Cycle" in str(exc), str(exc)
        print(f"PASS: cycle rejected -- {exc}")
    else:
        raise AssertionError("cycle was not rejected")

    # Unknown dep
    unknown = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: [ghost]
```
"""
    batches = extract_batch_index(unknown)
    try:
        validate(batches, ["01-a.md"])
    except PlanDAGError as exc:
        assert "unknown batch" in str(exc), str(exc)
        print(f"PASS: unknown dep rejected -- {exc}")
    else:
        raise AssertionError("unknown dep was not rejected")

    # Orphan file on disk
    orphan = """
```yaml
batches:
  - name: a
    file: 01-a.md
    depends-on: []
```
"""
    batches = extract_batch_index(orphan)
    try:
        validate(batches, ["01-a.md", "99-orphan.md"])
    except PlanDAGError as exc:
        assert "not listed" in str(exc), str(exc)
        print(f"PASS: orphan file rejected -- {exc}")
    else:
        raise AssertionError("orphan file was not rejected")

    # Missing block
    try:
        extract_batch_index("no yaml here")
    except PlanDAGError as exc:
        assert "missing" in str(exc), str(exc)
        print(f"PASS: missing block rejected -- {exc}")
    else:
        raise AssertionError("missing block was not rejected")

    # topo_order
    order = topo_order([
        {"name": "foundation", "depends-on": []},
        {"name": "reviewers", "depends-on": ["foundation"]},
        {"name": "templates", "depends-on": ["foundation"]},
        {"name": "integration", "depends-on": ["reviewers", "templates"]},
    ])
    assert order.index("foundation") < order.index("reviewers")
    assert order.index("foundation") < order.index("templates")
    assert order.index("reviewers") < order.index("integration")
    assert order.index("templates") < order.index("integration")
    # Authored-order tie-break: reviewers (2nd authored) precedes templates (3rd).
    assert order.index("reviewers") < order.index("templates")
    print(f"PASS: topo_order respects dependencies and authored order -- {order}")

    # iter_batch_verifies
    import tempfile as _tmp
    with _tmp.TemporaryDirectory() as td:
        plan_dir = Path(td)
        (plan_dir / "00-overview.md").write_text(
            "```yaml\n"
            "batches:\n"
            "  - name: foundation\n"
            "    file: 01-foundation.md\n"
            "    depends-on: []\n"
            "  - name: reviewers\n"
            "    file: 02-reviewers.md\n"
            "    depends-on: [foundation]\n"
            "  - name: docs\n"
            "    file: 03-docs.md\n"
            "    depends-on: [foundation]\n"
            "```\n",
            encoding="utf-8",
        )
        (plan_dir / "01-foundation.md").write_text(
            "# Batch: foundation\n\n"
            "```yaml\n"
            "batch: foundation\n"
            "verify: pytest tests/foundation -q\n"
            "```\n",
            encoding="utf-8",
        )
        (plan_dir / "02-reviewers.md").write_text(
            "# Batch: reviewers\n\n"
            "```yaml\n"
            "batch: reviewers\n"
            "verify: pytest tests/reviewers -q\n"
            "```\n",
            encoding="utf-8",
        )
        (plan_dir / "03-docs.md").write_text(
            "# Batch: docs\n\n"
            "```yaml\n"
            "batch: docs\n"
            "verify: null\n"
            "```\n",
            encoding="utf-8",
        )
        commands = iter_batch_verifies(plan_dir)
        assert commands == [
            ("foundation", "pytest tests/foundation -q"),
            ("reviewers", "pytest tests/reviewers -q"),
        ], commands
        print(f"PASS: iter_batch_verifies yields verify commands in DAG order, skips null -- {commands}")

    print("All _plan_dag smoke tests passed.")
