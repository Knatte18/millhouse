# Batch: Core Python helpers

```yaml
task: 16 (A) — Autonomous bug-fix pipeline (mill-autofix)
batch: Core Python helpers
number: 1
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

This batch adds the two Python helpers the mill-autofix skill depends on — `_autofix.slug_from_title` and the `label_filter` parameter on `_gh_issues.fetch` — together with their unit tests. The external interface consumed by Batch 3 is: `from _autofix import slug_from_title` and `_gh_issues.fetch(label_filter=["bug"])`. No skill files or config files are touched here.

## Cards

### Card 1: Create `_autofix.py` with `slug_from_title`

- **Context:**
  - `plugins/mill/scripts/_gh_issues.py`
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_autofix.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/scripts/_autofix.py` with a single public function `slug_from_title(title: str, existing_slugs: set[str], issue_number: int) -> str`. The algorithm: (1) lowercase the title; (2) replace every character not matching `[a-z0-9]` with `-`; (3) collapse runs of consecutive `-` to a single `-`; (4) strip leading and trailing `-`; (5) truncate to 30 characters — if the 30th character is not `-` and the string is longer than 30 chars, walk left to find the last `-` within the 30-char prefix and truncate there; if no `-` exists in the prefix, truncate hard at 30; (6) if the resulting slug is in `existing_slugs`, append `-<issue_number>` (string). Add module-level docstring describing the public API. No `if __name__ == "__main__":` block.
- **Commit:** `feat(autofix): add _autofix.py with slug_from_title helper`

### Card 2: Add `label_filter` to `_gh_issues.fetch`

- **Context:**
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Edits:**
  - `plugins/mill/scripts/_gh_issues.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_gh_issues.fetch` (currently `def fetch(repo: str | None = None, limit: int = 100) -> list[dict[str, Any]]:`), add a third parameter `label_filter: list[str] | None = None` after `limit`. Update the docstring to document the new parameter. After the existing loop that processes comments (`for issue in issues: issue["body"] = ...`), add a filter step: `if label_filter is not None: issues = [i for i in issues if any(l["name"] in label_filter for l in i.get("labels", []))]`. Update the module-level docstring `Public API:` block for `fetch()` to include `label_filter`. The `gh issue list` call is unchanged — filtering is Python-side post-fetch.
- **Commit:** `feat(gh-issues): add label_filter parameter to fetch()`

### Card 3: Add label_filter tests to `test-gh-issues.py`

- **Context:**
  - `plugins/mill/scripts/_gh_issues.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Import `fetch` is not testable without a real `gh` CLI. Instead, test the filtering logic in isolation by building a small helper or by calling the filter expression directly. The cleanest approach: import `_gh_issues` and monkey-patch `_subprocess_util.run` to return a canned JSON list, then call `fetch(label_filter=...)`. Use `unittest.mock.patch` or a simple monkeypatch of `_gh_issues._subprocess_util.run`. Add these test cases to the existing `main()` function (numbered continuing from case 8): (9) `label_filter=None` → all issues returned; (10) `label_filter=["bug"]` → only issues where at least one label `name == "bug"` returned; (11) `label_filter=["bug", "enhancement"]` → any-of semantics, both-label issues and single-label issues included; (12) `label_filter=["nonexistent"]` → empty list; (13) issue with `labels: []` → excluded when label_filter is set. The mock must return a valid `detect_repo` result and a valid JSON list for the `gh issue list` call. Use `unittest.mock.patch("_gh_issues._subprocess_util.run", side_effect=<mock_fn>)` where `mock_fn` inspects `args[0]` to distinguish `gh repo view` (return `"owner/repo"`) from `gh issue list` (return the canned list).
- **Commit:** `test(gh-issues): add label_filter test cases`

### Card 4: Create `test-autofix.py`

- **Context:**
  - `plugins/mill/scripts/_autofix.py`
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-autofix.py`
- **Deletes:** none
- **Requirements:** Create `plugins/mill/unit_tests/test-autofix.py` following the same structure as `test-gh-issues.py`: `HUB = Path(__file__).resolve().parent.parent.parent.parent`, `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))`, `from _autofix import slug_from_title`. Implement `main() -> int` with these test cases (numbered 1–6): (1) standard title `"Fix NPE in login flow"` → `"fix-npe-in-login-flow"` (all within 30 chars, no collision); (2) special chars `"Bug: crash (v2.0/alpha)"` → `"bug-crash-v2-0-alpha"` (parens, colon, slash stripped); (3) consecutive hyphens `"fix  -- double  space"` → `"fix-double-space"` (collapsed); (4) truncation: a title that produces a slug longer than 30 chars → truncated at the last `-` boundary within 30 chars; (5) collision: slug already in `existing_slugs` → appends `-<issue_number>`; (6) title that starts or ends with non-alpha chars → no leading/trailing hyphens in result. Each case prints `PASS:` or `FAIL:` with a description. Return 0 on all pass, 1 on any failure. Close with `if __name__ == "__main__": sys.exit(main())`.
- **Commit:** `test(autofix): add test-autofix.py for slug_from_title`

## Batch Tests

Verify command: `python plugins/mill/unit_tests/run-all.py`. This runs every file matching `test-*.py` in `plugins/mill/unit_tests/`. The new `test-autofix.py` and the extended `test-gh-issues.py` are both covered. A non-zero exit from any test file causes `run-all.py` to exit non-zero.
