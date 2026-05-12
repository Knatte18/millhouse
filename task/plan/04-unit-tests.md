# Batch: unit tests

```yaml
task: '40 (B) — mill-finalize: lift PR decision out of mill-merge'
batch: unit tests
number: 4
cards: 1
verify: python plugins/mill/unit_tests/test-mill-finalize-dispatch.py
depends-on: [1]
```

## Batch Scope

Create `plugins/mill/unit_tests/test-mill-finalize-dispatch.py`. This file tests the dispatch evaluation logic that mill-finalize's Dispatch section implements: reading `git.require_pr_to_base` and `git.base_branch` from a deep-merged config dict and comparing `parent_branch` to `base_branch`. Tests are self-contained in-memory dict fixtures — no git, no LLM, no file I/O. The test file is executable directly: `python plugins/mill/unit_tests/test-mill-finalize-dispatch.py`.

Note: `plugins/mill/unit_tests/test-mill-merge-inplace.py` is unchanged (confirmed to contain only `_inplace` module smoke tests with no PR-path tests to remove).

## Cards

### Card 7: Create test-mill-finalize-dispatch.py

- **Context:**
  - `plugins/mill/skills/mill-finalize/SKILL.md`
  - `plugins/mill/unit_tests/test-mill-merge-inplace.py`
  - `task/discussion.md`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-mill-finalize-dispatch.py`
- **Deletes:** none
- **Requirements:**

  Create `plugins/mill/unit_tests/test-mill-finalize-dispatch.py` as a standalone executable test file (no test framework import required — plain `assert` + `print("PASS: ...")` + `sys.exit(1)` on failure is the project convention, matching `test-mill-merge-inplace.py`'s style).

  The file must implement all five scenarios from `task/discussion.md` Testing section, plus a helper for the deep-merge logic. Exact scenarios:

  **Scenario 1 — require_pr_to_base: true, parent == base_branch → PR mode:**
  ```python
  cfg = {"git": {"require_pr_to_base": True, "base_branch": "main"}}
  parent_branch = "main"
  require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
  base_branch = cfg.get("git", {}).get("base_branch", "main")
  assert require_pr and parent_branch == base_branch, "expected PR mode"
  print("PASS: require_pr_to_base=true, parent==base_branch → PR mode")
  ```

  **Scenario 2 — require_pr_to_base: true, parent != base_branch → direct mode:**
  ```python
  cfg = {"git": {"require_pr_to_base": True, "base_branch": "main"}}
  parent_branch = "develop"
  require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
  base_branch = cfg.get("git", {}).get("base_branch", "main")
  assert not (require_pr and parent_branch == base_branch), "expected direct mode"
  print("PASS: require_pr_to_base=true, parent!=base_branch → direct mode")
  ```

  **Scenario 3 — require_pr_to_base absent → direct mode:**
  ```python
  cfg = {}
  require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
  assert not require_pr, "expected direct mode when key absent"
  print("PASS: require_pr_to_base absent → direct mode")
  ```

  **Scenario 4 — old kebab-case key not recognised (breaking change documented):**
  ```python
  cfg = {"git": {"require-pr-to-base": True, "base-branch": "main"}}
  require_pr = bool(cfg.get("git", {}).get("require_pr_to_base", False))
  assert not require_pr, "old kebab-case key must not be recognised"
  print("PASS: old kebab-case key require-pr-to-base not recognised → direct mode (breaking change)")
  ```

  **Scenario 5 — config deep-merge: local override of require_pr_to_base wins over wiki:**
  ```python
  import copy
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
  ```

  **File structure:** import section (`import sys, copy`) at top; five scenario blocks executed sequentially; on any `AssertionError` catch and `sys.exit(1)` with the error message; final `print("All tests passed.")` + `sys.exit(0)`.

  Use a `try/except AssertionError` guard around each scenario so that a failure in scenario N does not suppress N+1..5. Print all failures before exiting. Use a `failures = []` list; append `(scenario_name, str(e))` on each catch; after all scenarios, if `failures`: print each, `sys.exit(1)`.

- **Commit:** `test(mill-finalize): add dispatch evaluation unit tests`

## Batch Tests

`python plugins/mill/unit_tests/test-mill-finalize-dispatch.py` — expected output: five PASS lines + "All tests passed." Exit code 0. Run from the repo root.
