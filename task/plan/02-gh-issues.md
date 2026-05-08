# Batch: gh-issues

```yaml
task: 32 (A) — Bug-fix batch 2
batch: gh-issues
number: 2
cards: 4
verify: python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Refactor `_gh_issues.py` to remove cwd-sensitivity in `detect_repo`, then update every in-tree caller (mill-autofix and mill-ghissues-to-tasks SKILL.md files) to pass `git_root=` explicitly. Cohesive single batch because the API change and its caller updates must land together — partial application would leave the call sites compiling but cwd-sensitive (still failing the original bug from #202) or non-compiling (calling with a removed positional arg). Card 6 is TDD: write tests against the new signature first, then Card 7 implements it. Cards 8 and 9 update SKILL.md call sites.

## Cards

### Card 6: Add detect_repo unit tests covering git_root parameter and removed gh repo view

- **Context:**
  - `plugins/mill/scripts/_gh_issues.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-gh-issues.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Extend `test-gh-issues.py` with three new test functions, each patching `_gh_issues._subprocess_util.run` (existing pattern in the file): (a) `test_detect_repo_with_explicit_git_root` — passes `git_root=Path("/fake/hub")` and asserts the helper invokes `["git", "-C", "/fake/hub", "remote", "get-url", "origin"]` (NOT `["gh", "repo", "view", ...]`) and returns the parsed `owner/repo` from a stub https URL like `https://github.com/Knatte18/millhouse.git` → `"Knatte18/millhouse"`. (b) `test_detect_repo_with_explicit_git_root_ssh_url` — same as (a) but with stub stdout `git@github.com:Knatte18/millhouse.git` → `"Knatte18/millhouse"`. (c) `test_detect_repo_default_falls_back_to_resolve_git_root` — calls `detect_repo()` with no args, patches `_gh_issues._paths.resolve_git_root` to return `Path("/fake/cwd-root")` (this works because Card 7 makes `_paths` a top-level import in `_gh_issues.py`, so `_gh_issues._paths` is a real attribute on the module object), asserts the same `git -C /fake/cwd-root remote get-url origin` invocation. Each test asserts the patched subprocess was called with the expected `["git", "-C", str(git_root), "remote", "get-url", "origin"]` argv via `mock.assert_called_with` or `mock.call_args`. The tests MUST fail against the unmodified `_gh_issues.py` (which currently calls `gh repo view` first). Register all three in the test-runner driver at the bottom of the file (existing pattern).
- **Commit:** `test(gh-issues): cover detect_repo with explicit git_root`

### Card 7: Add git_root parameter to _gh_issues.detect_repo, fetch, close_with_comment; drop gh repo view

- **Context:**
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_gh_issues.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_gh_issues.py`: (1) Add two top-level imports at the head of the file alongside the existing `import _subprocess_util`: `from pathlib import Path` and `import _paths`. The top-level `import _paths` is load-bearing — Card 6's test patches `_gh_issues._paths.resolve_git_root`, which requires `_paths` to be an attribute of the `_gh_issues` module (a function-body import would only set a function-local name, breaking the patch). (2) Change the signature of `detect_repo` (line 35) to `def detect_repo(git_root: Path | None = None) -> str:`. Inside the function: remove the `gh repo view --json nameWithOwner -q .nameWithOwner` block (lines 41–45) entirely. Resolve the git root: when `git_root is None`, set `git_root = _paths.resolve_git_root()`. Then run `_subprocess_util.run(["git", "-C", str(git_root), "remote", "get-url", "origin"])` and parse the returned URL with the EXISTING two regexes (lines 51–56) — those stay unchanged. Return `""` on any non-zero subprocess exit (preserve existing failure behavior). (3) Update `fetch` (line 89) signature to `def fetch(repo: str | None = None, limit: int = 100, label_filter: list[str] | None = None, git_root: Path | None = None) -> list[dict[str, Any]]:` and change `repo_name = repo or detect_repo()` (line 102) to `repo_name = repo or detect_repo(git_root=git_root)`. (4) Update `close_with_comment` (line 135) signature to `def close_with_comment(number: int, comment: str, repo: str | None = None, git_root: Path | None = None) -> None:` and change `repo_name = repo or detect_repo()` (line 149) to `repo_name = repo or detect_repo(git_root=git_root)`. Update the docstring at the top of the module (lines 1–20) to reflect the new signatures: name `git_root` in the parameter list for all three functions; replace the line about `gh repo view` with a one-line note that `detect_repo` parses `git remote get-url origin`. After this card, Card 6's tests must pass.
- **Commit:** `refactor(gh-issues): accept git_root parameter; drop gh repo view`

### Card 8: Update mill-autofix SKILL.md to pass git_root to _gh_issues calls

- **Context:**
  - `plugins/mill/scripts/_gh_issues.py`
- **Edits:**
  - `plugins/mill/skills/mill-autofix/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Two call-site updates in `mill-autofix/SKILL.md`. (1) Around line 44–46, update the `_gh_issues.fetch(label_filter=['bug'])` example to pass `git_root=` explicitly. The existing snippet is `import _gh_issues, json, sys` followed by `issues = _gh_issues.fetch(label_filter=['bug'])`. Change the call to `issues = _gh_issues.fetch(label_filter=['bug'], git_root=_paths.resolve_git_root())` and add `import _paths` (or merge into the existing import line: `import _gh_issues, _paths, json, sys`). (2) Around line 376–378, update the `_gh_issues.close_with_comment(<issue_number>, ...)` example to pass `git_root=` explicitly. The existing snippet is `import _gh_issues` followed by `_gh_issues.close_with_comment(<issue_number>, 'Autonomously fixed by mill-autofix. Squash commit: <sha>')`. Change to `import _gh_issues, _paths` and `_gh_issues.close_with_comment(<issue_number>, 'Autonomously fixed by mill-autofix. Squash commit: <sha>', git_root=_paths.resolve_git_root())`. Both edits assume the script runs from inside the hub worktree, where `_paths.resolve_git_root()` returns the hub git root — that matches the SKILL.md's existing assumption that mill-autofix runs from the hub. Do NOT change surrounding prose; only the snippet body.
- **Commit:** `docs(mill-autofix): pass git_root to _gh_issues calls`

### Card 9: Update mill-ghissues-to-tasks SKILL.md to pass git_root to _gh_issues calls

- **Context:**
  - `plugins/mill/scripts/_gh_issues.py`
- **Edits:**
  - `plugins/mill/skills/mill-ghissues-to-tasks/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Three call-site updates in `mill-ghissues-to-tasks/SKILL.md`. (1) Around line 25–28, update `_gh_issues.fetch(limit=100)` to `_gh_issues.fetch(limit=100, git_root=_paths.resolve_git_root())`. Add `import _paths` to the same `import` block. (2) Around line 32, the prose currently reads `Read \`.scratch/issues.json\`. Record the repo name (\`_gh_issues.detect_repo()\`) for the close step.` Replace the inline `detect_repo()` call with `detect_repo(git_root=_paths.resolve_git_root())` so the recorded repo name comes from the hub regardless of cwd. (3) Around line 125–128, update `_gh_issues.close_with_comment(<N>, 'Consolidated into wiki task: <slug>')` to `_gh_issues.close_with_comment(<N>, 'Consolidated into wiki task: <slug>', git_root=_paths.resolve_git_root())` and add `import _paths` to that snippet's import block. Do NOT change surrounding prose. The recorded-repo-name flow at line 32 stays — it's still the documented pattern; it just becomes hub-correct under the new signature.
- **Commit:** `docs(mill-ghissues-to-tasks): pass git_root to _gh_issues calls`

## Batch Tests

`python plugins/mill/unit_tests/run-all.py` — covers the new `test-gh-issues.py` cases from Card 6 and the existing test-gh-issues.py fetch/label_filter tests (which call `fetch` without `git_root` and exercise the default-`None` fallback). Cards 8 and 9 are SKILL.md prose updates with no automated test; their correctness is verified by the implementer reading the new signature in `_gh_issues.py` (Card 7) and matching the call sites.
