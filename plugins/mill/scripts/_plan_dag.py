"""
Validate the Batch Index DAG in a plan overview file.

mill-plan writes ``<WIKI_PATH>/active/<slug>/plan/00-overview.md`` with a fenced ``yaml`` block declaring every batch and its ``depends-on:`` edges.
Before handing the plan off for review, the skill must self-validate that block — catching obvious cycles and dangling references cheaply, rather than paying for a round of reviewer tokens to discover the same.

The reviewer still does its own check (see ``review-plan-holistic.md`` criteria).
This module is the pre-check;
it is not authoritative.

Public API:
    PlanDAGError — raised on any structural failure extract_batch_index(overview_text) -> list[dict] Parse the first ``batches:`` fenced-yaml block out of the overview text.
    Raises on malformed input.
    validate(batches, batch_files) -> None Run all structural checks.
    Raises on the first problem. ``batch_files`` is the list of batch filenames present in the plan dir (relative names, e.g. ``["01-foundation.md", ...]``), used to check ``file:`` references resolve.
    parse_commit_none_card_ids(batch_text) -> set[int] Return the card numbers in a batch file whose ``Commit:`` field is the literal ``none`` sentinel (verification-only cards).

Structure expected inside the fenced block:

    batches:
      - number: NN name: foundation file: 01-foundation.md depends-on: [] verify: pytest tests/foundation/ -q
      - name: reviewers file: 02-reviewers.md depends-on: [1] verify: null

``number:`` (optional positive int) labels the batch for human navigation. ``depends-on:`` accepts a list of integers (referencing ``number:`` values) or strings (referencing ``name:`` values; legacy format).
Mixed types in one list are rejected. ``verify:`` may be null. ``depends-on:`` may be ``[]``. ``name:`` and ``file:`` are required per batch.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path

import yaml

import _status
from _review_common import parse_deletes, parse_moves


class PlanDAGError(Exception):
    """Raised by :func:`validate` on any structural failure.

    Callers (mill-plan skill) catch this, surface the message to the user, and abort before committing the plan.
    The message names the failing batch/edge so the LLM can self-correct in the same session.
    """


# Match a ``yaml`` fenced block whose first non-blank inner line is ``batches:``.
# This is how we distinguish the Batch Index block from any other ``yaml`` block (e.g.
# the overview frontmatter).
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
        PlanDAGError: No ``batches:`` block is present, the yaml is malformed, or the block contains no ``batches:`` key at the top level.
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


# Matches a card-start line, e.g. "### Card 9: Add a helper".
# Used both to split card blocks and (via re.findall elsewhere, e.g.
# millpy-implement.py) to collect the plain set of declared card numbers.
_CARD_START_RE = re.compile(r"^###\s+Card\s+(\d+)\s*:")

# Matches the inline value of a card's ``Commit:`` field bullet, mirroring _plan_validate.py's `_RE_REFS_HEADER`-style card-field bullets but scoped to this one field.
_CARD_COMMIT_RE = re.compile(r"^-\s*\*\*Commit:\*\*(?P<inline>.*)$", re.MULTILINE)


def parse_commit_none_card_ids(batch_text: str) -> set[int]:
    """Return card numbers whose ``Commit:`` field is the literal ``none``.

    ``Commit: none`` marks a verification-only card (issue #664): a card whose sole job is confirming earlier work (e.g.
    a grep-and-confirm gate) rather than producing its own diff.
    Both this module's callers need to identify these cards without depending on each other:

    - ``_plan_validate.py``'s ``commit-none-with-content`` check uses this to find which cards must have zero content in Edits:/Creates:/ Deletes:/Moves:.
    - ``millpy-implement.py``'s no-content-commit gate uses this as the carve-out signal that a zero-commit turn for these specific cards is expected, not a stuck implementer.

    Card blocks are split the same way ``_plan_validate._parse_cards`` bounds them: from a ``### Card N:`` line up to the next ``### `` heading or end of file.
    This is re-implemented here (rather than imported from ``_plan_validate``) because this module's own docstring states callers import ``_plan_dag``, never the reverse.

    Args:
        batch_text: Full contents of a batch markdown file.

    Returns:
        The set of card numbers (as declared in ``### Card N:``, not batch-relative indices) whose ``Commit:`` field, stripped and lowercased, equals ``"none"``.
        A card with no ``Commit:`` line at all is NOT included -- that omission is ``_plan_validate``'s ``card-missing-field`` check's job, not this function's.
    """
    # Split the batch text into card blocks: each runs from its "### Card N:" line up to (but not including) the next "### " heading.
    lines = batch_text.splitlines()
    none_card_ids: set[int] = set()
    current_num: int | None = None
    current_lines: list[str] = []
    card_blocks: list[tuple[int, str]] = []
    for line in lines:
        m = _CARD_START_RE.match(line)
        if m:
            if current_num is not None:
                card_blocks.append((current_num, "\n".join(current_lines)))
            current_num = int(m.group(1))
            current_lines = [line]
        elif current_num is not None:
            if line.startswith("### "):
                card_blocks.append((current_num, "\n".join(current_lines)))
                current_num = None
                current_lines = []
            else:
                current_lines.append(line)
    if current_num is not None:
        card_blocks.append((current_num, "\n".join(current_lines)))

    for card_num, card_block_text in card_blocks:
        commit_match = _CARD_COMMIT_RE.search(card_block_text)
        if commit_match and commit_match.group("inline").strip().lower() == "none":
            none_card_ids.add(card_num)
    return none_card_ids


def _check_shapes(batches: list[dict]) -> None:
    """Verify each batch entry has ``name:`` and ``file:`` strings.

    ``depends-on:`` defaults to ``[]`` if absent. ``verify:`` may be any string or null — we do not enforce the shape of verify commands here;
    that is a reviewer concern.
    """
    seen_names: set[str] = set()
    seen_numbers: set[int] = set()
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
        number = entry.get("number")
        if number is not None:
            if not isinstance(number, int) or number < 1:
                raise PlanDAGError(
                    f"Batch {name!r} `number:` must be a positive integer, got {number!r}"
                )
            if number in seen_numbers:
                raise PlanDAGError(f"Duplicate batch number: {number}")
            seen_numbers.add(number)
        deps = entry.get("depends-on", [])
        if not isinstance(deps, list):
            raise PlanDAGError(
                f"Batch {name!r} `depends-on:` must be a list of strings"
            )
        if deps:
            types = {type(d) for d in deps}
            if types - {int, str}:
                raise PlanDAGError(
                    f"Batch {name!r} `depends-on:` must be a list of strings"
                )
            if len(types) > 1:
                raise PlanDAGError(
                    f"Batch {name!r} `depends-on:` must not mix int and str entries"
                )


def resolve_deps_as_names(batches: list[dict]) -> dict[str, list[str]]:
    """Map each batch's ``depends-on:`` entries to names.

    Integer entries are translated to names via the ``number:`` field.
    String entries pass through unchanged.
    Unresolved integer entries (no matching ``number:`` in any batch) are silently dropped — ``_check_deps`` is the authoritative check for dangling deps.
    """
    number_to_name = {
        entry["number"]: entry["name"]
        for entry in batches
        if "number" in entry
    }
    result: dict[str, list[str]] = {}
    for entry in batches:
        name = entry["name"]
        deps: list[str] = []
        for dep in entry.get("depends-on", []):
            if isinstance(dep, int):
                resolved = number_to_name.get(dep)
                if resolved is not None:
                    deps.append(resolved)
            else:
                deps.append(dep)
        result[name] = deps
    return result


def _check_file_refs(batches: list[dict], batch_files: list[str]) -> None:
    """Verify every ``file:`` exists in ``batch_files`` and vice versa.

    Both directions are errors:
    - a declared batch whose file is missing on disk → planner skipped a write.
    - a file on disk that no batch entry references → planner left an orphan file.
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
    numbers = {entry["number"] for entry in batches if "number" in entry}
    for entry in batches:
        for dep in entry.get("depends-on", []):
            if isinstance(dep, int):
                if dep not in numbers:
                    raise PlanDAGError(
                        f"Batch {entry['name']!r} depends on unknown batch number {dep}"
                    )
                if entry.get("number") == dep:
                    raise PlanDAGError(
                        f"Batch {entry['name']!r} (number {dep}) depends on itself"
                    )
            else:
                if dep not in names:
                    raise PlanDAGError(
                        f"Batch {entry['name']!r} depends on unknown batch {dep!r}"
                    )
                if dep == entry["name"]:
                    raise PlanDAGError(f"Batch {entry['name']!r} depends on itself")


def _check_acyclic(batches: list[dict]) -> None:
    """Kahn's-algorithm topological sort;
raise if any node remains.

    A remaining node after the queue drains means it is inside a cycle (never had zero in-degree).
    We report all remaining nodes so the planner sees the whole cycle, not one edge at a time.
    """
    indegree: dict[str, int] = {entry["name"]: 0 for entry in batches}
    adj: dict[str, list[str]] = {entry["name"]: [] for entry in batches}
    deps_by_name = resolve_deps_as_names(batches)
    for name, deps in deps_by_name.items():
        for dep in deps:
            adj[dep].append(name)
            indegree[name] += 1

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

    Returns ``{}`` on any structural problem — the caller (typically the verify-iterator) treats a malformed batch as "no verify command" rather than escalating.
    A batch with a broken frontmatter would have been rejected by the plan-reviewer long before a merge is attempted.
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


def parse_verify_field(
    frontmatter: dict, hub_root: Path, git_root: Path
) -> tuple[str | None, Path | None]:
    """Normalize a batch/overview frontmatter's ``verify:`` value.

    ``verify:`` supports two shapes, per the "verify cwd field schema" Shared Decision:

    1. A plain string (today's format) — the command runs in whatever cwd the caller already defaults to.
        Returned as ``(command, None)``;
        the ``None`` cwd is the signal to the caller "use your existing default", which preserves pre-#604 behavior byte-for-byte for every flat-layout plan.
    2. A ``{cwd: hub|git_root, command: <string>}`` mapping — used by nested-layout plans (``hub_root != git_root``) that need to pin the verify command to a specific root.
        Unlike the string form, the mapping form has no implicit default: ``cwd`` is required and must be exactly ``"hub"`` or ``"git_root"``.

    This is the single normalizer for the ``verify:`` field;
    every other read site (implementer, fixer, baseline, merge-in, plan-validate) must route through this function rather than re-implementing the string-vs-mapping branch.

    Args:
        frontmatter: The parsed fenced-yaml frontmatter dict of a batch file or the plan overview.
        hub_root: The mill project root (``_paths.resolve_hub_path()``).
            Used when the mapping form specifies ``cwd: hub``.
        git_root: The git repository toplevel (``_paths.resolve_git_root()``).
            Used when the mapping form specifies ``cwd: git_root``.

    Returns:
        ``(command, cwd)``. ``command`` is ``None`` when ``verify`` is absent, ``None``, or an empty/whitespace-only string — "nothing to run".
        Otherwise ``command`` is the stripped command string. ``cwd`` is ``None`` for the string form (caller's existing default applies) or the resolved ``Path`` for the mapping form.

    Raises:
        ValueError: ``verify`` is a mapping without a non-empty ``command``, a mapping with an unrecognized (or missing) ``cwd``, or any type other than ``None``/string/mapping (e.g.
            a list or int).
            This is a deliberate fail-loud policy: a malformed ``verify:`` field is a plan-authoring bug and must surface immediately rather than silently defaulting to "no verify" or the wrong cwd.
    """
    verify = frontmatter.get("verify")
    # Absent, explicit null, or blank string all mean "nothing to run" -- the common case for pure-docs batches.
    if verify is None:
        return (None, None)
    if isinstance(verify, str):
        if not verify.strip():
            return (None, None)
        # Plain-string form: no cwd opinion, caller keeps its default.
        return (verify.strip(), None)
    if isinstance(verify, dict):
        command = verify.get("command")
        if not isinstance(command, str) or not command.strip():
            raise ValueError("verify mapping missing a non-empty `command:` string")
        cwd_key = verify.get("cwd")
        if cwd_key == "hub":
            return (command.strip(), hub_root)
        if cwd_key == "git_root":
            return (command.strip(), git_root)
        # The mapping form always requires an explicit cwd -- unlike the string form, there is no implicit default to fall back to.
        raise ValueError(f"verify mapping has unrecognized `cwd:` value: {cwd_key!r}")
    raise ValueError(f"verify must be null, a string, or a mapping; got {verify!r}")


def _normalize_removal_token(token: str) -> str:
    """Normalize a ``Deletes:``/``Moves:`` source token for exact-match comparison.

    Strips one leading ``"./"`` and any trailing ``"/"`` so that the plan-authoring variations ``"tools/x/"``, ``"./tools/x"``, and ``"tools/x"`` all collapse to the same comparison key.
    This is purely lexical string normalization -- no filesystem resolution and no awareness of ``cwd``/``root`` coordinate spaces.
    """
    if token.startswith("./"):
        token = token[2:]
    return token.rstrip("/")


def _is_path_candidate_verify_token(token: str) -> bool:
    """Return whether a shlex-split ``verify:`` command token could name a path.

    Deliberately conservative, to avoid false-positive suppressions: excludes flag-form tokens (``-o``, ``--dir=x``), tokens with no path separator (bare subcommand names like ``go`` or ``build``), and globby/ellipsis tokens (``./...``, ``./pkg/...``, ``*.go``) that are Go-style wildcard build targets a ``Deletes:``/``Moves:`` entry could never name verbatim.
    """
    if token.startswith("-"):
        return False
    if "/" not in token:
        return False
    if "*" in token or "?" in token or "..." in token:
        return False
    return True


def _verify_command_targets_later_removal(
    command: str,
    later_batch_names: list[str],
    removed_by_batch: dict[str, set[str]],
) -> bool:
    """Return whether ``command`` names a target one of ``later_batch_names`` removes.

    Tokenizes ``command`` with ``shlex.split`` and checks every path-candidate token (see :func:`_is_path_candidate_verify_token`), normalized the same way as the removal-map tokens, for an exact match against any later batch's declared removal set.
    The check is existential and all-or-nothing over the whole command: a single matching token is enough to report the command as stale, even when the command also names other targets that remain valid.
    """
    tokens = shlex.split(command)
    for token in tokens:
        if not _is_path_candidate_verify_token(token):
            continue
        normalized = _normalize_removal_token(token)
        for later_name in later_batch_names:
            if normalized in removed_by_batch.get(later_name, set()):
                return True
    return False


def iter_batch_verifies(
    plan_dir: Path, hub_root: Path, git_root: Path, *, status_path: Path | None = None
) -> list[tuple[str, str, Path | None]]:
    """Return ``(batch_name, verify_cmd, cwd)`` triples in DAG order.

    mill-merge-in's Verify step (and ``millpy-fix.py``'s holistic prepare/finalize) replays exactly the checks that still matter given the plan's current state: each surviving batch's ``verify:`` from its frontmatter, in the same order mill-go dispatched them (``topo_order``).
    Three independent reasons drop a batch's verify out of the returned list:

    1. ``verify:`` is ``null`` or missing -- pure-docs batches have no runnable surface and forcing a sentinel command there would be noise (pre-existing behavior).
    2. A strictly-later batch (higher index in ``order``) declares, via its own ``Deletes:``/``Moves:`` bullets, that it removes a path this batch's ``verify:`` command references -- replaying the command would just fail on a target the plan itself says is gone.
        Detection matches normalized command tokens against normalized ``Deletes:``/``Moves:``-source tokens (never live filesystem state -- see the "metadata-driven cross-batch verify suppression" Shared Decision).
        A batch's own removals,
        and any earlier batch's, never suppress it -- only strictly-later removals count, so a batch never suppresses itself even when it deletes a path its own ``verify:`` references.
    3. When ``status_path`` is given: the batch itself has not reached ``"approved"`` state yet (its verify hasn't actually been validated/settled),
        or the only later batch that would otherwise suppress it (reason 2) has not reached ``"approved"`` either (that later batch has not actually executed its declared removal yet, so the target still exists and this batch's verify still runs).

    Known limitations of reason 2's matching (accepted trade-offs, see
    ``_mill/discussion.md`` Decision 2):
    - Exact-match only, no directory-containment: ``Deletes: tools/x/`` does NOT suppress a verify referencing ``tools/x/cmd/app``.
    - All-or-nothing per command: a multi-target command is fully suppressed if any single target matches.
    - Purely lexical, no ``cwd``/``root`` coordinate resolution: a verify authored in a different coordinate space than the ``Deletes:``/``Moves:`` tokens may fail to match and will simply keep running -- it is never falsely suppressed.
    - ``shlex.split`` uses its default ``posix=True`` tokenization, which treats backslash as an escape character regardless of host OS.
        A verify command containing a Windows-style backslash path may have its tokens corrupted before the path-candidate check runs, so such a command will not be reliably suppressed even when its target is genuinely removed later.

    Each batch's raw ``verify:`` value is routed through :func:`parse_verify_field` to resolve the plain-string vs. ``{cwd, command}`` mapping forms;
    ``cwd`` in the returned triple is ``None`` for the string form (caller uses its existing default) or the resolved ``hub_root``/``git_root`` for the mapping form.

    Args:
        plan_dir: Directory containing ``00-overview.md`` and the batch files it references.
        hub_root: The mill project root, passed through to ``parse_verify_field`` for ``cwd: hub`` resolution.
        git_root: The git repository toplevel, passed through to ``parse_verify_field`` for ``cwd: git_root`` resolution.
        status_path: Optional path to the task's ``status.md``.
            When ``None`` (the default), reason 3 above never applies and this function's behavior is byte-for-byte identical to before this parameter existed -- strictly additive, per the "``status_path`` kwarg is strictly additive" Shared Decision.
            When provided, batch states are read via ``_status.read_batches``;
            a ``ValueError`` from a malformed ``## Batches`` block degrades to returning ``[]`` (mirroring the malformed-overview branch below) rather than raising.

    Returns:
        A list of ``(batch_name, command, cwd)`` triples, one per batch that survives all three filters above.

    If the plan overview is missing or malformed, returns ``[]`` and the caller falls back to "nothing to verify".
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

    # Resolve per-batch approval state up front (reason 3).
    # Left as None when status_path is omitted so the filters below skip that reason entirely -- the strictly-additive contract from the Shared Decision.
    states: dict[str, str] | None = None
    if status_path is not None:
        states = {}
        try:
            for b in _status.read_batches(status_path):
                states[b.get("name")] = b.get("state")
        except ValueError:
            # Malformed `## Batches` block (missing/unterminated fenced yaml, or bad yaml) -- degrade to "nothing to verify" rather than let the corruption propagate to the caller.
            return []

    # Build a per-batch removal map (reason 2) from each batch's own Deletes:/Moves: declarations, so the main loop below can look up "what did batch X declare gone" without re-parsing per lookup.
    # Iterates every batch in `batches`, not just `order`, per contract.
    removed_by_batch: dict[str, set[str]] = {}
    for entry in batches:
        name = entry["name"]
        file_ref = file_by_name.get(name)
        if not file_ref:
            continue
        batch_path = plan_dir / file_ref
        removed = {_normalize_removal_token(t) for t in parse_deletes(batch_path)}
        removed |= {
            _normalize_removal_token(src) for src, _dst in parse_moves(batch_path)
        }
        removed_by_batch[name] = removed

    commands: list[tuple[str, str, Path | None]] = []
    for index, name in enumerate(order):
        # Reason 3a: this batch itself hasn't reached "approved" yet.
        if states is not None and states.get(name) != "approved":
            continue
        file_ref = file_by_name.get(name)
        if not file_ref:
            continue
        frontmatter = _read_batch_frontmatter(plan_dir / file_ref)
        command, cwd = parse_verify_field(frontmatter, hub_root, git_root)
        if command is None:
            continue
        # Reason 2 (narrowed by reason 3b when status_path is given): only a strictly-later batch that has actually executed its removal (state == "approved", when states is tracked) counts as a remover -- a later batch still pending has not removed anything yet, so its declared target still exists.
        later_batch_names = [
            later_name
            for later_name in order[index + 1 :]
            if states is None or states.get(later_name) == "approved"
        ]
        if _verify_command_targets_later_removal(
            command, later_batch_names, removed_by_batch
        ):
            continue
        commands.append((name, command, cwd))
    return commands


def topo_order(batches: list[dict]) -> list[str]:
    """Return a topological ordering of batch names.

    mill-go consumes this to decide execution order: batches appear in an order compatible with every ``depends-on:`` edge.
    Among batches that share a dependency level we break ties by the order they appear in the input — which matches the authored order in the overview and gives a predictable execution timeline.

    Assumes ``validate(batches, ...)`` has already been called so the input is structurally sound (no cycles, no dangling refs).
    If the graph contains a cycle this function raises ``PlanDAGError`` — a safety net in case the caller skipped validation.
    """
    indegree: dict[str, int] = {entry["name"]: 0 for entry in batches}
    adj: dict[str, list[str]] = {entry["name"]: [] for entry in batches}
    deps_by_name = resolve_deps_as_names(batches)
    for name, deps in deps_by_name.items():
        for dep in deps:
            adj[dep].append(name)
            indegree[name] += 1

    # Stable-priority queue: preserve authored order among zero-indegree nodes by draining them in batch-list sequence.
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

    On success returns ``None``.
    On failure raises ``PlanDAGError`` with a message naming the first problem encountered — order matters because later checks assume earlier invariants hold (e.g.
    the cycle check assumes dep-refs are valid).
    """
    _check_shapes(batches)
    _check_file_refs(batches, batch_files)
    _check_deps(batches)
    _check_acyclic(batches)
