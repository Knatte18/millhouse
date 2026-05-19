"""
Registry loader, name resolver, and role-aware lookup for named reviewer definitions.

Provides the bridge between plugin template mill-agents.yaml (the base registry),
.millhouse/agents.local.yaml (per-hub overrides), and legacy wiki/agents.yaml or
wiki/reviewers.yaml (for in-flight branches before migration).

Public API:
    ReviewerError  — raised on every validation/resolution failure.
    load(hub_dir: Path) -> dict[str, dict]
        Load and validate plugin template + local overlay + legacy wiki fallback.
        Returns name → raw spec dict.
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
import sys
from copy import deepcopy
from pathlib import Path

import yaml

import _paths
from _config import deep_merge, resolve_plugin_template_path

_NAME_REGEX = re.compile(r"^[a-z0-9_-]+$")


class ReviewerError(Exception):
    """Raised on every validation/resolution failure in the reviewer registry."""


def _validate_extends_syntax(raw: dict) -> list[str]:
    """Validate raw-form extends syntax. Returns list of error messages."""
    errors: list[str] = []
    for name, entry in raw.items():
        if not isinstance(entry, dict):
            continue
        if "extends" not in entry:
            continue
        extends_value = entry["extends"]
        if not isinstance(extends_value, str):
            errors.append(f"Reviewer {name!r}: 'extends' must be a string")
            continue
        if extends_value not in raw:
            errors.append(f"Reviewer {name!r}: extends references unknown name {extends_value!r}")
            continue
        target_entry = raw[extends_value]
        if isinstance(target_entry, dict) and target_entry.get("type") == "cluster":
            errors.append(
                f"Reviewer {name!r}: extends references {extends_value!r} which declares"
                " type 'cluster' (clusters cannot be extended)"
            )
        if entry.get("type") == "cluster":
            errors.append(f"Reviewer {name!r}: cluster entries cannot use 'extends'")
    return errors


def _detect_extends_cycles(raw: dict) -> list[str]:
    """DFS cycle detection over extends edges. Returns list of cycle error messages."""
    errors: list[str] = []
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {name: WHITE for name in raw}

    def dfs(node: str, path: list[str]) -> None:
        color[node] = GRAY
        entry = raw.get(node, {})
        if isinstance(entry, dict) and "extends" in entry:
            neighbor = entry["extends"]
            if neighbor not in color:
                pass
            elif color[neighbor] == GRAY:
                cycle_chain = path + [neighbor]
                errors.append(f"Cycle detected in extends chain: {' -> '.join(cycle_chain)}")
            elif color[neighbor] == WHITE:
                dfs(neighbor, path + [neighbor])
        color[node] = BLACK

    for name in list(raw.keys()):
        if color[name] == WHITE:
            dfs(name, [name])
    return errors


def _resolve_extends(raw: dict) -> dict:
    """Top-down extends-chain merge; returns flat dict with no 'extends:' fields."""
    resolved: dict[str, dict] = {}

    def _walk(name: str) -> dict:
        if name in resolved:
            return resolved[name]
        entry = raw[name]
        if "extends" not in entry:
            flat = dict(entry)
        else:
            base = _walk(entry["extends"])
            flat = dict(base)
            for k, v in entry.items():
                if k == "extends":
                    continue
                flat[k] = v
        resolved[name] = flat
        return flat

    for name in raw:
        _walk(name)
    return resolved


def load(hub_dir: Path) -> dict[str, dict]:
    """Load and validate plugin template + local overlay + legacy wiki fallback.

    Returns name → raw spec dict after merging all available layers and validating.

    Validates: all names match [a-z0-9_-]+, no duplicate names in each source file,
    every entry has a known type, required fields per type, cluster use: references
    resolve to type=single only, no cycles in the use: graph, and entries with
    `extends: <name>` are resolved top-down at load time (single-string form only;
    cluster entries may neither extend nor be extended; cycle detection raises
    with the chain).

    Raises ReviewerError listing every problem in a single message.
    """
    # Load plugin template.
    template_path = resolve_plugin_template_path("mill-agents.yaml")
    template_registry = {}
    if template_path.exists():
        template_text = template_path.read_text(encoding="utf-8")
        _validate_source_for_duplicates(template_text, template_path)
        template_registry = yaml.safe_load(template_text) or {}

    # Load local overlay.
    local_path = hub_dir / ".millhouse" / "agents.local.yaml"
    local_registry = {}
    if local_path.exists():
        local_text = local_path.read_text(encoding="utf-8")
        _validate_source_for_duplicates(local_text, local_path)
        local_registry = yaml.safe_load(local_text) or {}

    # Legacy wiki fallback if both layers are empty.
    if not template_registry and not local_registry:
        wiki_path = None
        try:
            wiki_path = _paths.resolve_wiki_path(hub_dir)
            agents_path = wiki_path / "agents.yaml"
            if agents_path.exists():
                sys.stderr.write(
                    f"[reviewers] using legacy wiki agents file at {agents_path}; "
                    "run mill-setup to migrate to plugin template + .millhouse/agents.local.yaml\n"
                )
                wiki_text = agents_path.read_text(encoding="utf-8")
                _validate_source_for_duplicates(wiki_text, agents_path)
                return _validate_and_return(
                    yaml.safe_load(wiki_text) or {}, template_registry
                )
            reviewers_path = wiki_path / "reviewers.yaml"
            if reviewers_path.exists():
                sys.stderr.write(
                    f"[reviewers] using legacy wiki agents file at {reviewers_path}; "
                    "run mill-setup to migrate to plugin template + .millhouse/agents.local.yaml\n"
                )
                wiki_text = reviewers_path.read_text(encoding="utf-8")
                _validate_source_for_duplicates(wiki_text, reviewers_path)
                return _validate_and_return(
                    yaml.safe_load(wiki_text) or {}, template_registry
                )
        except (Exception, SystemExit):
            pass

        # No source found.
        raise ReviewerError(
            f"Missing registry: no plugin template at {template_path}, "
            f"no .millhouse/agents.local.yaml at {local_path}, "
            f"no legacy wiki/agents.yaml or wiki/reviewers.yaml"
        )

    # Merge layers: local overlays template.
    raw = deep_merge(template_registry, local_registry)

    # Per-agent unknown-key validation: local-only agents are allowed.
    for agent_name in local_registry:
        if agent_name in template_registry:
            unknown = _walk_unknown_agent_keys(
                local_registry[agent_name], template_registry[agent_name]
            )
            for key in unknown:
                sys.stderr.write(
                    f"[reviewers] unknown key in {agent_name}: {key} "
                    "(in .millhouse/agents.local.yaml)\n"
                )

    # Run full validation on merged registry.
    return _validate_and_return(raw, template_registry)


def _validate_source_for_duplicates(text: str, source_path: Path) -> None:
    """Check a YAML source for duplicate top-level keys via compose."""
    doc = yaml.compose(text)
    if doc is None or not isinstance(doc, yaml.MappingNode):
        return

    seen_keys: set[str] = set()
    dup_keys: list[str] = []
    for key_node, _ in doc.value:
        k = key_node.value
        if k in seen_keys:
            dup_keys.append(k)
        seen_keys.add(k)
    if dup_keys:
        raise ReviewerError(
            f"Duplicate reviewer names in {source_path}: {sorted(set(dup_keys))!r}"
        )


def _walk_unknown_agent_keys(actual_entry: dict, template_entry: dict) -> list[str]:
    """Walk actual agent entry and return keys not in template_entry."""
    unknown = []
    for key in actual_entry:
        if key not in template_entry:
            unknown.append(key)
    return unknown


def _validate_and_return(raw: dict, template_registry: dict) -> dict[str, dict]:
    """Validate merged registry and return it; raise ReviewerError on any problems."""
    if not isinstance(raw, dict):
        raise ReviewerError("Registry must be a YAML mapping")

    errors: list[str] = []

    errors.extend(_validate_extends_syntax(raw))
    errors.extend(_detect_extends_cycles(raw))
    if errors:
        raise ReviewerError("\n".join(errors))

    raw = _resolve_extends(raw)

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
            lp_reviewer = (scope_cfg.get("large_prompt") or {}).get("reviewer")
            if lp_reviewer is not None:
                try:
                    lp_spec = resolve(registry, lp_reviewer)
                    if lp_spec.get("type") == "cluster":
                        errors.append(
                            f"roles.{role}.{scope}.large_prompt.reviewer={lp_reviewer!r}: "
                            "cluster type not supported for large-prompt override"
                        )
                except ReviewerError as exc:
                    errors.append(
                        f"roles.{role}.{scope}.large_prompt.reviewer={lp_reviewer!r}: {exc}"
                    )

    impl_model = cfg.get("roles", {}).get("implementer", {}).get("model")
    if impl_model is not None:
        try:
            resolve(registry, impl_model)
        except ReviewerError as exc:
            errors.append(f"roles.implementer.model={impl_model!r}: {exc}")

    fixer_model = cfg.get("roles", {}).get("fixer", {}).get("model")
    if fixer_model is not None:
        try:
            resolve(registry, fixer_model)
        except ReviewerError as exc:
            errors.append(f"roles.fixer.model={fixer_model!r}: {exc}")

    if errors:
        raise ReviewerError("\n".join(errors))
