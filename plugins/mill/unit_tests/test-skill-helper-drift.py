"""Unit tests for SKILL.md helper-reference drift and nested-hub regression locks.

Batch: drift-guard-and-regression-locks

Card 1: Drift-guard scan
  Every mill-SKILL.md helper reference (pattern `_<module>.<fn>(`) resolves to a real
  shipped function in plugins/mill/scripts.

Card 2: Regression locks
  #495: millpy-review-plan.py resolves project_root via _paths.resolve_hub_path()
  #496: mill-go SKILL.md resolves reviews_dir = hub / '_mill/reviews'
  #504/#505: drift guard asserts _cleanliness.revert_out_of_scope_drift resolves

Card 3: Extract-unit checks and mill-start body/brief lock
  Directly asserts _extract_helper_references behaviour: the negative case
  (gate_cmd.lower() produces no matches) and the positive case
  (_paths.resolve_git_root() produces one match). Also locks mill-start/SKILL.md
  against losing the task['body'] and task['brief'] field-name guidance.
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
# The negative lookbehind in _extract_helper_references now suppresses every former
# identifier-tail false positive (e.g. gate_cmd.lower(), env_block.get(), path.exists()),
# so this set is intentionally empty. Reserve it only for future true module-qualified
# (_module.func() where the leading _ is preceded by a non-identifier character) exemptions.
ALLOWLIST: set[tuple[str, str]] = set()


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
    The regex matches an underscore-prefixed module identifier, a dot, a function
    identifier, and an opening parenthesis. The negative lookbehind
    `(?<![A-Za-z0-9_])` requires the leading `_` to be preceded by a
    non-identifier character, so identifier tails such as `_cmd` in
    `gate_cmd.lower()` are not mis-extracted as `_cmd` module references.
    The underscore is matched but not captured; the captured module stem does
    not include it.
    """
    pattern = r"(?<![A-Za-z0-9_])_([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)\("
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

    # mill-start body/brief lock: confirm the SKILL instructs agents to read both fields
    mill_start_skill_path = SKILLS / "mill-start" / "SKILL.md"
    try:
        mill_start_skill_text = mill_start_skill_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        failures.append(f"FAIL: {mill_start_skill_path}: could not read {e}")
        return failures

    if "task['body']" not in mill_start_skill_text:
        failures.append(
            f"FAIL: mill-start body/brief lock: {mill_start_skill_path} does not "
            f"contain the literal string task['body'] -- field-name guidance was removed"
        )

    if "task['brief']" not in mill_start_skill_text:
        failures.append(
            f"FAIL: mill-start body/brief lock: {mill_start_skill_path} does not "
            f"contain the literal string task['brief'] -- field-name guidance was removed"
        )

    return failures


def _run_extract_unit_checks() -> list[str]:
    """
    Assert _extract_helper_references behaviour directly for the negative and positive cases.

    Negative case: an identifier tail like gate_cmd.lower() must produce no matches,
    confirming the lookbehind suppresses false positives from within-identifier underscores.

    Positive case: a genuine module-qualified call like _paths.resolve_git_root() must
    produce exactly one match, confirming real helper references are still extracted.

    Returns a list of FAIL: messages; an empty list means both cases passed.
    """
    failures: list[str] = []

    # Negative case: the _cmd tail of gate_cmd.lower() must not be extracted
    negative_result = _extract_helper_references("gate_cmd.lower()")
    if negative_result != []:
        failures.append(
            f"FAIL: extract-unit negative case: expected [], got {negative_result!r} "
            f"for input 'gate_cmd.lower()'"
        )

    # Positive case: a real module-qualified call must be extracted with the correct tuple
    positive_result = _extract_helper_references("_paths.resolve_git_root()")
    expected_positive = [("paths", "resolve_git_root")]
    if positive_result != expected_positive:
        failures.append(
            f"FAIL: extract-unit positive case: expected {expected_positive!r}, "
            f"got {positive_result!r} for input '_paths.resolve_git_root()'"
        )

    return failures


def main() -> int:
    """
    Run all three check groups: drift guard (Card 1), regression locks (Card 2),
    and extract-unit checks (Card 3).

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
        print("PASS: #495/#496 and mill-start body/brief locks are in place")

        print("--- Card 3: Extract-unit checks ---")
        extract_failures = _run_extract_unit_checks()
        if extract_failures:
            for msg in extract_failures:
                print(msg, file=sys.stderr)
            print(f"FAIL: {len(extract_failures)} extract-unit check(s) failed", file=sys.stderr)
            return 1
        print("PASS: _extract_helper_references correctly handles negative and positive cases")

        print("All test-skill-helper-drift checks passed.")
        return 0

    except Exception as e:
        print(f"FAIL: unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
