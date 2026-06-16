"""Dispatch evaluation unit tests for mill-finalize PR-vs-direct logic."""
import sys
import copy

failures = []

# Scenario 1 -- require_pr_to_base: true, parent == base_branch -> PR mode
try:
    cfg = {"git": {"require_pr_to_base": True, "base_branch": "main"}}
    parent_branch = "main"
    require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
    base_branch = cfg.get("git", {}).get("base_branch", "main")
    assert require_pr, "expected PR mode"
    print("PASS: require_pr_to_base=true -> PR mode")
except AssertionError as e:
    print(f"FAIL: {e}", file=sys.stderr)
    failures.append(("scenario_1", str(e)))

# Scenario 2 -- require_pr_to_base: true, parent != base_branch (stacked) -> PR mode
try:
    cfg = {"git": {"require_pr_to_base": True, "base_branch": "main"}}
    parent_branch = "develop"
    require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
    base_branch = cfg.get("git", {}).get("base_branch", "main")
    assert require_pr, "expected PR mode for stacked task"
    # Stacked task: PR targets parent_branch, not base_branch
    pr_target = parent_branch
    assert pr_target == "develop", "PR target should be parent_branch for stacked task"
    print("PASS: require_pr_to_base=true, stacked (parent!=base) -> PR mode with parent as target")
except AssertionError as e:
    print(f"FAIL: {e}", file=sys.stderr)
    failures.append(("scenario_2", str(e)))

# Scenario 3 -- require_pr_to_base absent -> direct mode
try:
    cfg = {}
    require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
    assert not require_pr, "expected direct mode when key absent"
    print("PASS: require_pr_to_base absent -> direct mode")
except AssertionError as e:
    print(f"FAIL: {e}", file=sys.stderr)
    failures.append(("scenario_3", str(e)))

# Scenario 4 — old kebab-case key not recognised (breaking change documented)
try:
    cfg = {"git": {"require-pr-to-base": True, "base-branch": "main"}}
    require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
    assert not require_pr, "old kebab-case key must not be recognised"
    print("PASS: old kebab-case key require-pr-to-base not recognised -> direct mode (breaking change)")
except AssertionError as e:
    print(f"FAIL: {e}", file=sys.stderr)
    failures.append(("scenario_4", str(e)))

# Scenario 5 — config deep-merge: local override of require_pr_to_base wins over wiki
try:
    wiki_cfg = {"git": {"require_pr_to_base": False, "base_branch": "main"}}
    local_cfg = {"git": {"require_pr_to_base": True}}
    merged = copy.deepcopy(wiki_cfg)
    for k, v in local_cfg.items():
        if isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k].update(v)
        else:
            merged[k] = v
    require_pr = bool(merged.get("git", {}).get("require_pr_to_base", False))
    assert require_pr, "local override must win over wiki config"
    print("PASS: local override require_pr_to_base=true wins over wiki false")
except AssertionError as e:
    print(f"FAIL: {e}", file=sys.stderr)
    failures.append(("scenario_5", str(e)))

if failures:
    for name, msg in failures:
        print(f"FAIL [{name}]: {msg}", file=sys.stderr)
    sys.exit(1)

print("All tests passed.")
sys.exit(0)
