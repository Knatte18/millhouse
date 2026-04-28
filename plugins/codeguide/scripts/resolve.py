"""
Path resolution for codeguide hooks.

Resolve chain
-------------
1. **Inline walk** — from cwd up to (and including) git-toplevel, look
   for ``_codeguide/<filename>``.
2. **.codeguide-root override** — if inline fails, read the first line of
   ``<git-toplevel>/.codeguide-root`` and use it as the sibling anchor
   (absolute path, or relative to toplevel).
3. **Sibling default** — otherwise compute the anchor via
   ``_sibling.resolve_path("codeguide", git_toplevel)``.
4. **Sibling walk** — mirror the inline walk under the anchor: for each
   level from cwd up to toplevel, check
   ``<anchor>/<rel>/_codeguide/<filename>``.

Routing files (Overview.md, modules/) resolve from cwd — each folder with
a _codeguide/ is a self-contained routing node.
Metadata files (config.yaml, local-rules.md, DocumentationGuide.md)
resolve via the chain above.
"""

import os
import pathlib
import subprocess
import sys

METADATA_ANCHOR = "config.yaml"


def routing_root(cwd: str | None = None) -> pathlib.Path:
    """Return the cwd-level _codeguide/ directory (routing context)."""
    return pathlib.Path(cwd or os.getcwd()) / "_codeguide"


def _find_git_toplevel(start: pathlib.Path) -> pathlib.Path | None:
    current = start.resolve()
    while True:
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _walk_levels(cwd: pathlib.Path, toplevel: pathlib.Path) -> list[pathlib.Path]:
    """Levels from cwd up to and including toplevel."""
    levels: list[pathlib.Path] = []
    current = cwd.resolve()
    toplevel = toplevel.resolve()
    while True:
        levels.append(current)
        if current == toplevel:
            return levels
        parent = current.parent
        if parent == current:
            return levels
        current = parent


def _inline_walk(filename: str, cwd: pathlib.Path, toplevel: pathlib.Path) -> pathlib.Path | None:
    for level in _walk_levels(cwd, toplevel):
        candidate = level / "_codeguide" / filename
        if candidate.exists():
            return candidate
    return None


def _sibling_walk(filename: str, cwd: pathlib.Path, toplevel: pathlib.Path, anchor: pathlib.Path) -> pathlib.Path | None:
    toplevel = toplevel.resolve()
    for level in _walk_levels(cwd, toplevel):
        rel = level.relative_to(toplevel)
        candidate = anchor / rel / "_codeguide" / filename
        if candidate.exists():
            return candidate
    return None


def _read_override(toplevel: pathlib.Path) -> pathlib.Path | None:
    override = toplevel / ".codeguide-root"
    if not override.exists():
        return None
    raw = override.read_text(encoding="utf-8").strip().splitlines()
    if not raw:
        return None
    anchor = pathlib.Path(raw[0].strip())
    if not anchor.is_absolute():
        anchor = (toplevel / anchor).resolve()
    return anchor


def _resolve_main_worktree_root(toplevel: pathlib.Path) -> pathlib.Path:
    result = subprocess.run(
        ["git", "-C", str(toplevel), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"git rev-parse --git-common-dir failed for {toplevel}: "
            f"{result.stderr.strip()!r}"
        )
    common_dir = pathlib.Path(result.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = (toplevel / common_dir).resolve()
    return common_dir.parent


def _sibling_anchor_default(toplevel: pathlib.Path) -> pathlib.Path:
    main_root = _resolve_main_worktree_root(toplevel)
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
    from _sibling import resolve_path
    return resolve_path("codeguide", main_root)


def resolve(cwd: str | None = None, filename: str = METADATA_ANCHOR) -> dict:
    """Full resolution: inline walk, then .codeguide-root, then sibling default.

    Returns a dict with keys:
        mode: "inline" | "sibling" | None
        cg_root: Path | None — the _codeguide/ directory that contains <filename>
        sibling_anchor: Path | None — the sibling-repo root (only meaningful when mode == "sibling")
        found: bool
    """
    cwd_path = pathlib.Path(cwd or os.getcwd()).resolve()
    toplevel = _find_git_toplevel(cwd_path)
    if toplevel is None:
        return {"mode": None, "cg_root": None, "sibling_anchor": None, "found": False}

    hit = _inline_walk(filename, cwd_path, toplevel)
    if hit is not None:
        return {"mode": "inline", "cg_root": hit.parent, "sibling_anchor": None, "found": True}

    anchor = _read_override(toplevel) or _sibling_anchor_default(toplevel)
    hit = _sibling_walk(filename, cwd_path, toplevel, anchor)
    if hit is not None:
        return {"mode": "sibling", "cg_root": hit.parent, "sibling_anchor": anchor, "found": True}

    return {"mode": None, "cg_root": None, "sibling_anchor": anchor, "found": False}


def find_metadata(filename: str, cwd: str | None = None) -> pathlib.Path | None:
    """Find <filename> under any _codeguide/ (inline or sibling chain)."""
    r = resolve(cwd, filename)
    return r["cg_root"] / filename if r["found"] else None


def config_path(cwd: str | None = None) -> pathlib.Path | None:
    return find_metadata(METADATA_ANCHOR, cwd)


def metadata_root(cwd: str | None = None) -> pathlib.Path | None:
    r = resolve(cwd)
    return r["cg_root"] if r["found"] else None


def load_config_flag(flag: str, cwd: str | None = None) -> bool:
    path = config_path(cwd)
    if path is None:
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{flag}:"):
                    value = line.split(":", 1)[1].strip().lower()
                    return value == "true"
    except FileNotFoundError:
        pass
    return False


def load_source_extensions(cwd: str | None = None) -> list[str]:
    path = config_path(cwd)
    if path is None:
        return []
    extensions = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("- ."):
                    extensions.append(line[2:].strip())
    except FileNotFoundError:
        pass
    return extensions


def _cli(argv: list[str]) -> int:
    import json
    as_json = "--json" in argv[1:]
    result = resolve()
    if as_json:
        payload = {
            "mode": result["mode"],
            "cg_root": str(result["cg_root"]) if result["cg_root"] else None,
            "sibling_anchor": str(result["sibling_anchor"]) if result["sibling_anchor"] else None,
            "found": result["found"],
        }
        print(json.dumps(payload))
        return 0 if result["found"] else 1
    if result["found"]:
        print(result["cg_root"])
        return 0
    print(
        "ERROR: no _codeguide/ with config.yaml found — run /codeguide-setup first [--sibling]",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(_cli(sys.argv))
