"""
Registry loader, name resolver, and role-aware lookup for named reviewer definitions.

Provides the bridge between wiki/reviewers.yaml (the registry of named reviewer
specs) and wiki/config.yaml (the role configuration that references those specs).

Public API:
    ReviewerError  — raised on every validation/resolution failure.
    load(wiki_root: Path) -> dict[str, dict]
        Load and validate wiki_root/reviewers.yaml. Returns name → raw spec dict.
    resolve(registry: dict, name: str) -> dict
        Resolve a reviewer name to a fully-flattened spec dict.
        Special case: "test_stub" returns a synthetic spec without consulting the registry.
    resolve_role(cfg: dict, registry: dict, role: str, scope: str) -> dict | None
        Read cfg.roles.<role>.<scope>.reviewer and resolve via registry.
        Returns None if reviewer is null or rounds is 0.
    validate_role_refs(cfg: dict, registry: dict) -> None
        Walk cfg.roles.<role>.<scope>.reviewer for every (role, scope) pair;
        confirm each non-null name resolves. Raises ReviewerError listing all failures.
"""
from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

import yaml

_NAME_REGEX = re.compile(r"^[a-z0-9_-]+$")


class ReviewerError(Exception):
    """Raised on every validation/resolution failure in the reviewer registry."""


def load(wiki_root: Path) -> dict[str, dict]:
    """Load wiki_root/reviewers.yaml, validate structure, return name → raw spec.

    Validates: all names match [a-z0-9_-]+, no duplicate names, every entry has
    a known type, required fields per type, cluster use: references resolve to
    type=single only, and no cycles in the use: graph.

    Raises ReviewerError listing every problem in a single message.
    """
    path = wiki_root / "reviewers.yaml"
    if not path.exists():
        raise ReviewerError(f"Missing registry at {path}")

    text = path.read_text(encoding="utf-8")

    # Use yaml.compose to detect duplicate top-level keys before construction.
    doc = yaml.compose(text)
    if doc is None:
        return {}
    if not isinstance(doc, yaml.MappingNode):
        raise ReviewerError(f"Registry at {path} must be a YAML mapping")

    errors: list[str] = []

    # Duplicate key detection via AST node pairs.
    seen_keys: set[str] = set()
    dup_keys: list[str] = []
    for key_node, _ in doc.value:
        k = key_node.value
        if k in seen_keys:
            dup_keys.append(k)
        seen_keys.add(k)
    if dup_keys:
        errors.append(f"Duplicate reviewer names: {sorted(set(dup_keys))!r}")

    raw = yaml.safe_load(text) or {}
    if not isinstance(raw, dict):
        raise ReviewerError(f"Registry at {path} must be a YAML mapping")

    # Per-entry validation; track valid types for cross-ref checks.
    valid_types: dict[str, str] = {}
    for name, entry in raw.items():
        if not isinstance(name, str) or not _NAME_REGEX.match(str(name)):
            errors.append(f"Invalid reviewer name {name!r}: must match [a-z0-9_-]+")
            continue
        if not isinstance(entry, dict):
            errors.append(f"Reviewer {name!r}: entry must be a YAML mapping")
            continue
        entry_type = entry.get("type")
        if entry_type not in ("single", "cluster"):
            errors.append(f"Reviewer {name!r}: unknown type {entry_type!r}")
            continue
        if entry_type == "single":
            if not isinstance(entry.get("provider"), str):
                errors.append(f"Reviewer {name!r} (single): missing or invalid 'provider'")
            if not isinstance(entry.get("model"), str):
                errors.append(f"Reviewer {name!r} (single): missing or invalid 'model'")
        elif entry_type == "cluster":
            workers = entry.get("workers")
            if not isinstance(workers, dict):
                errors.append(
                    f"Reviewer {name!r} (cluster): 'workers' must be a mapping with 'use' and 'count'"
                )
            else:
                if "use" not in workers:
                    errors.append(f"Reviewer {name!r} (cluster): 'workers.use' is required")
                count = workers.get("count")
                if not isinstance(count, int) or count <= 0:
                    errors.append(
                        f"Reviewer {name!r} (cluster): 'workers.count' must be a positive integer"
                    )
            handler = entry.get("handler")
            if not isinstance(handler, dict):
                errors.append(
                    f"Reviewer {name!r} (cluster): 'handler' must be a mapping with 'use'"
                )
            elif "use" not in handler:
                errors.append(f"Reviewer {name!r} (cluster): 'handler.use' is required")
        valid_types[name] = entry_type

    # Cross-ref validation: cluster use: values must resolve to type=single.
    for name in list(valid_types.keys()):
        if valid_types[name] != "cluster":
            continue
        entry = raw[name]
        workers = entry.get("workers") or {}
        handler = entry.get("handler") or {}
        for use_name, label in [
            (workers.get("use"), "workers.use"),
            (handler.get("use"), "handler.use"),
        ]:
            if use_name is None:
                continue
            if use_name not in valid_types:
                errors.append(
                    f"Reviewer {name!r}: {label} references unknown name {use_name!r}"
                )
            elif valid_types[use_name] != "single":
                errors.append(
                    f"Reviewer {name!r}: {label} references {use_name!r}"
                    f" which is not type 'single' (no nested clusters)"
                )

    # Cycle detection DFS over use: edges (defensive; unreachable given no-nested-cluster rule).
    _detect_cycles(raw, valid_types, errors)

    if errors:
        raise ReviewerError("\n".join(errors))

    return raw


def _detect_cycles(
    registry: dict,
    valid_types: dict[str, str],
    errors: list[str],
) -> None:
    """DFS cycle detection over cluster use: edges. Appends cycle messages to errors."""
    adjacency: dict[str, list[str]] = {}
    for name, entry_type in valid_types.items():
        if entry_type == "cluster":
            entry = registry.get(name, {})
            refs: list[str] = []
            workers_use = (entry.get("workers") or {}).get("use")
            handler_use = (entry.get("handler") or {}).get("use")
            if workers_use:
                refs.append(workers_use)
            if handler_use:
                refs.append(handler_use)
            adjacency[name] = refs
        else:
            adjacency[name] = []

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in valid_types}

    def dfs(node: str) -> None:
        color[node] = GRAY
        for neighbor in adjacency.get(node, []):
            if neighbor not in color:
                continue
            if color[neighbor] == GRAY:
                errors.append(f"Cycle detected: {node!r} → {neighbor!r}")
            elif color[neighbor] == WHITE:
                dfs(neighbor)
        color[node] = BLACK

    for name in list(valid_types.keys()):
        if color[name] == WHITE:
            dfs(name)


def resolve(registry: dict, name: str) -> dict:
    """Resolve a reviewer name to a fully-flattened spec.

    Special case: name == "test_stub" returns
    {"type": "single", "provider": "test_stub", "tooluse": False}
    without consulting the registry.

    For type=single: returns a copy of the entry with tooluse defaulted to False.
    For type=cluster: returns a deep copy with workers.use and handler.use replaced
    by their fully-resolved single-spec dicts (bounded at depth 1 by load validation).

    Raises ReviewerError on missing name or unknown type.
    """
    if name == "test_stub":
        return {"type": "single", "provider": "test_stub", "tooluse": False}

    if name not in registry:
        raise ReviewerError(f"Unknown reviewer: {name!r}")

    spec = dict(registry[name])

    if spec["type"] not in ("single", "cluster"):
        raise ReviewerError(f"Unknown reviewer type: {spec['type']!r}")

    if spec["type"] == "single":
        if "tooluse" not in spec:
            spec["tooluse"] = False
        return spec

    # cluster: flatten use: references to their resolved single-specs.
    spec = deepcopy(spec)
    workers = spec.get("workers", {})
    handler = spec.get("handler", {})
    if isinstance(workers, dict) and "use" in workers:
        workers["use"] = resolve(registry, workers["use"])
    if isinstance(handler, dict) and "use" in handler:
        handler["use"] = resolve(registry, handler["use"])
    return spec


def resolve_role(
    cfg: dict,
    registry: dict,
    role: str,
    scope: str,
) -> dict | None:
    """Read cfg.roles.<role>.<scope>.reviewer; resolve via registry.

    Returns None if reviewer is null or rounds is 0.
    Raises ReviewerError if the role or scope key is absent from cfg.
    """
    if role not in cfg.get("roles", {}) or scope not in cfg["roles"][role]:
        raise ReviewerError(f"Missing roles.{role}.{scope} in config")

    subsection = cfg["roles"][role][scope]
    reviewer = subsection.get("reviewer")
    rounds = subsection.get("rounds", 0)

    if reviewer is None or rounds == 0:
        return None

    return resolve(registry, reviewer)


def validate_role_refs(cfg: dict, registry: dict) -> None:
    """Walk cfg.roles.<role>.<scope>.reviewer for every (role, scope) pair.

    Confirms each non-null name resolves in the registry.
    Raises ReviewerError with all missing names listed in the message.
    """
    errors: list[str] = []
    for role, role_cfg in cfg.get("roles", {}).items():
        if not isinstance(role_cfg, dict):
            continue
        for scope, scope_cfg in role_cfg.items():
            if not isinstance(scope_cfg, dict):
                continue
            reviewer = scope_cfg.get("reviewer")
            if reviewer is None:
                continue
            try:
                resolve(registry, reviewer)
            except ReviewerError as exc:
                errors.append(f"roles.{role}.{scope}.reviewer={reviewer!r}: {exc}")

    if errors:
        raise ReviewerError("\n".join(errors))
