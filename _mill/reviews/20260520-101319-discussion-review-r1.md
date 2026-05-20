# Review: Replace git subprocess calls with pygit2

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-20
```

## Findings

### [GAP] Error type mismatch in `_capture_head_sha` migration
**Section:** Scope / Technical Context (`_review_common._capture_head_sha`)
**Issue:** The proposed `_pygit2_util.head_sha()` raises `SystemExit` on failure, but `_capture_head_sha()` documents raising `ReviewError`. `worktree_snapshot_guard` explicitly documents that the capture may raise a `ReviewError` from a broken git invocation — replacing the subprocess call with `head_sha()` silently changes the exception type to `SystemExit`, breaking callers that expect `ReviewError` semantics.
**Fix:** Specify whether `_capture_head_sha` wraps `SystemExit` into `ReviewError`, or whether the `_pygit2_util.head_sha()` contract should accept an optional `exc_type` / be allowed to raise `ReviewError` in `_review_common` context. One sentence is enough; the plan writer needs a decision.

### [NOTE] Wiki guard fast-name check omitted from migration spec
**Section:** Technical Context (`resolve_git_root()` wiki guard)
**Issue:** The discussion only describes the samefile check (`repo.workdir` vs `resolve_wiki_path(repo_root)`), but `resolve_git_root` has a second fast guard: `if repo_root.name == "wiki": raise SystemExit(...)` that fires before `resolve_wiki_path` is even called.
**Fix:** Confirm both checks must be preserved — add `if Path(repo.workdir).name == "wiki":` note to the wiki-guard paragraph so the plan writer doesn't miss it.

## Verdict

GAPS_FOUND
One GAP: error type contract for `_capture_head_sha` post-migration is unresolved.