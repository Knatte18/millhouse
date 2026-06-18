"""Unit tests for SKILL.md helper-reference drift and nested-hub regression locks.

Batch: drift-guard-and-regression-locks

Card 1: Drift-guard scan
  Every mill-SKILL.md helper reference (pattern `_<module>.<fn>(`) resolves to a real
  shipped function in plugins/mill/scripts.

Card 2: Regression locks
  #495: millpy-review-plan.py resolves project_root via _paths.resolve_hub_path()
  #496: mill-go SKILL.md resolves reviews_dir = hub / '_mill/reviews'
  #504/#505: drift guard asserts _cleanliness.revert_out_of_scope_drift resolves
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parent.parent.parent.parent
SCRIPTS = HUB / "plugins" / "mill" / "scripts"
SKILLS = HUB / "plugins" / "mill" / "skills"

sys.path.insert(0, str(SCRIPTS))


# Allowlist of (module_stem, function_name) pairs exempt from the drift check.
# These are intentionally exempt items: local variable method calls (not module functions).
# Examples: cfg.get(...) where cfg is a dict, path.exists() where path is a Path instance.
ALLOWLIST: set[tuple[str, str]] = {
    # Local dict/object method calls (not module functions)
    ("block", "get"),        # env_block.get(...) - local variable
    ("gap_titles", "isdisjoint"),  # local variable method
    ("ts_str", "strip"),     # local variable method
    # Path object method calls (not module functions)
    ("path", "exists"),      # path.exists()
    ("path", "glob"),        # path.glob(...)
    ("path", "read_text"),   # path.read_text(...)
    ("path", "write_text"),  # path.write_text(...)
    ("path", "stat"),        # path.stat()
    ("path", "unlink"),      # path.unlink(...)
    ("dir", "exists"),       # directory path method
    ("dir", "glob"),         # directory path method
}


def _collect_shipped_helpers() -> dict[str, set[str]]:
    """
    Scan plugins/mill/scripts recursively for module-level functions.

    Returns a mapping: module_stem -> set of function names.
    The module stem is the bare filename without .py and without leading underscore
    (e.g., "client", "paths"), which matches how the regex extracts _<module> references
    from SKILLs (the underscore is matched but not captured in the regex).
    """
    helpers: dict[str, set[str]] = {}

    for py_file in SCRIPTS.rglob("*.py"):
        # Skip non-module files (executables like millpy-*.py are not helpers)
        if py_file.name.startswith("millpy-"):
            continue

        module_stem = py_file.stem  # bare filename, e.g., "_client", "_paths"
        # Strip leading underscore to match what the regex extracts
        if module_stem.startswith("_"):
            module_stem = module_stem[1:]

        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"FAIL: could not parse {py_file}: {e}", file=sys.stderr)
            return {}

        # Collect only top-level function definitions
        top_level_functions = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                top_level_functions.add(node.name)

        if top_level_functions:
            helpers[module_stem] = helpers.get(module_stem, set()) | top_level_functions

    return helpers


def _extract_helper_references(skill_md_text: str) -> list[tuple[str, str]]:
    """
    Extract all _<module>.<fn>( references from a SKILL.md text.

    Returns list of (module_stem, function_name) tuples.
    Regex matches underscore-prefixed module identifier, dot, function identifier, then (.
    The underscore is matched but not captured; the captured module name does not include it.
    """
    pattern = r"_([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\("
    matches = re.findall(pattern, skill_md_text)
    return [(module, fn) for module, fn in matches]


def _run_drift_guard() -> list[str]:
    """
    Scan all mill SKILLs and assert every _<module>.<fn>( reference resolves.

    Returns list of failure messages (empty list = all passed).
    """
    failures: list[str] = []

    # Build the set of available helpers
    helpers = _collect_shipped_helpers()
    if not helpers:
        failures.append("FAIL: could not parse any helper modules")
        return failures

    # Scan every SKILL.md in plugins/mill/skills/
    skill_files = sorted(SKILLS.rglob("SKILL.md"))
    for skill_file in skill_files:
        try:
            skill_text = skill_file.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            failures.append(f"FAIL: {skill_file}: could not read {e}")
            continue

        references = _extract_helper_references(skill_text)

        for module_stem, fn in references:
            # Check allowlist first
            if (module_stem, fn) in ALLOWLIST:
                continue

            # Check if the helper is shipped
            if module_stem not in helpers:
                failures.append(
                    f"FAIL: {skill_file}: unresolved module '{module_stem}' "
                    f"(referenced as _{module_stem}.{fn}()"
                )
            elif fn not in helpers[module_stem]:
                failures.append(
                    f"FAIL: {skill_file}: unresolved function '_{module_stem}.{fn}()' "
                    f"(module exists but function is not defined)"
                )

    return failures


def _run_regression_locks() -> list[str]:
    """
    Assert the already-fixed #495/#496 source state against regression.

    #495: millpy-review-plan.py uses _paths.resolve_hub_path() for project_root
    #496: mill-go SKILL.md resolves reviews_dir = hub / '_mill/reviews'

    Note: #504/#505 (SKILL.md helper reference mismatches) are already covered by
    Card 1's drift-guard scan, which asserts _cleanliness.revert_out_of_scope_drift
    (referenced by mill-go SKILL.md) resolves to a shipped function.

    Returns list of failure messages (empty list = all passed).
    """
    failures: list[str] = []

    # #495 lock: check millpy-review-plan.py
    review_plan_path = SCRIPTS / "millpy-review-plan.py"
    try:
        review_plan_text = review_plan_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        failures.append(f"FAIL: {review_plan_path}: could not read {e}")
        return failures

    if "project_root = _paths.resolve_hub_path()" not in review_plan_text:
        failures.append(
            f"FAIL: #495 regression: {review_plan_path} does not use "
            f"'project_root = _paths.resolve_hub_path()' for hub resolution"
        )

    if "project_root = Path.cwd()" in review_plan_text:
        failures.append(
            f"FAIL: #495 regression: {review_plan_path} uses bare 'Path.cwd()' "
            f"which is not cwd-independent (should use _paths.resolve_hub_path())"
        )

    # #496 lock: check mill-go SKILL.md
    mill_go_skill_path = SKILLS / "mill-go" / "SKILL.md"
    try:
        mill_go_skill_text = mill_go_skill_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        failures.append(f"FAIL: {mill_go_skill_path}: could not read {e}")
        return failures

    if "reviews_dir = hub / '_mill/reviews'" not in mill_go_skill_text:
        failures.append(
            f"FAIL: #496 regression: {mill_go_skill_path} does not use "
            f"'reviews_dir = hub / '_mill/reviews'' for holistic crash-recovery"
        )

    return failures


def main() -> int:
    """
    Run both check groups: drift guard (Card 1) and regression locks (Card 2).

    Returns 0 on all passes, 1 on any failure.
    """
    try:
        print("--- Card 1: Drift-guard scan ---")
        drift_failures = _run_drift_guard()
        if drift_failures:
            for msg in drift_failures:
                print(msg, file=sys.stderr)
            print(f"FAIL: {len(drift_failures)} unresolved helper reference(s)", file=sys.stderr)
            return 1
        print("PASS: all mill-SKILL.md helper references resolve to shipped functions")

        print("--- Card 2: Regression locks ---")
        regression_failures = _run_regression_locks()
        if regression_failures:
            for msg in regression_failures:
                print(msg, file=sys.stderr)
            print(f"FAIL: {len(regression_failures)} regression lock(s) failed", file=sys.stderr)
            return 1
        print("PASS: #495/#496 source fixes are in place and locked against regression")

        print("All test-skill-helper-drift checks passed.")
        return 0

    except Exception as e:
        print(f"FAIL: unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
