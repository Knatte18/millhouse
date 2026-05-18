I have enough to write the review. The Technical Context has a wrong `_config.load_config` argument name (confirmed against source), the integration test path is slightly off, and one test case has a "(or None)" that contradicts the guaranteed non-null design.

---

# Review: 58 (D) — Activate psmux-based claude subprocess routing

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-18
```

## Findings

### [NOTE] Technical Context states wrong first arg for load_config
**Section:** Technical Context
**Issue:** "Config loading: `_config.load_config(wiki_path, worktree_root)`" — the actual signature is `load_config(repo_root: Path, worktree_root: Path)` (confirmed at `_config.py:148`). The Decisions section correctly uses `git_root` and explicitly rejects `wiki_path` under "Rejected", but the contradiction in Technical Context could confuse a first-pass reader.
**Fix:** Change `wiki_path` to `repo_root` in the Technical Context sentence.

### [NOTE] Integration test path is wrong
**Section:** Testing — Integration test
**Issue:** Path written as `integration_tests/test-claude-psmux.py`; actual location is `plugins/mill/integration_tests/test-claude-psmux.py`.
**Fix:** Correct the path to `plugins/mill/integration_tests/test-claude-psmux.py`.

### [NOTE] Test case 8 says "or None" but design guarantees non-null session_id
**Section:** Testing — `via_psmux=true`, wrapper exits 0
**Issue:** "session_id is the value passed in (or `None`)" conflicts with the `response-extraction-psmux` decision that guarantees `_invoke` always generates and returns a UUID when session_id is None.
**Fix:** Remove "(or `None`)"; the test should assert that a UUID string is returned when `session_id=None` is passed into `_invoke`.

## Verdict

APPROVE
Three NOTEs, all minor; no information is missing that would block plan writing.