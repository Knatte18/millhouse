Now I have everything I need. Let me analyze the implementation against the plan.

Key observations:

1. **Card 1 fix** (`millpy-review-discussion.py:90`): `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")` - correctly uses `git_root` instead of `project_root`/`hub_dir`. This matches the plan exactly.

2. **Shared Decision compliance**: `project_root = hub_dir` (line 69) remains unchanged; only `briefs_dir` is affected. Compliant.

3. **Card 2 test** (`test-review-cli.py:337-426`): The function `test_discussion_prepare_brief_path_uses_git_root` is defined immediately before `main()` at line 337. It matches the plan's spec closely.

4. **main() call** (`test-review-cli.py:437`): `failures += test_discussion_prepare_brief_path_uses_git_root()` is added after `test_review_cli_emits_envelope_on_slug_failure()`. Matches plan requirement #3.

5. **Mock nesting**: The test nests mocks in the correct order matching the plan. However, there is a deviation: the plan specifies using nested `with` blocks, and the implementation uses exactly that structure. The mock for `_review_discussion.prepare` returns `fake_prepare` which has `model: "claude-sonnet-4-6"`. The CLI calls `_agent_dispatch.model_to_tier(prepare_result["model"])` which maps `"claude-sonnet-4-6"` to `"sonnet"` - this call is NOT mocked. `model_to_tier` is a pure function in `_agent_dispatch.py` that handles `claude-sonnet-*` correctly, so this is fine.

6. **`write_brief` is not mocked**: The test calls the real `_agent_dispatch.write_brief` (not mocked). This writes an actual file to `task_root / "_mill" / "briefs" / "review-discussion-holistic-r1.md"`. Since `task_root` is in a `safe_temp_dir()`, this is fine and actually tests the real file creation - which is the point of the test.

7. **`_paths.resolve_task_path`**: Not mocked either. With `git_root = task_root` (which is `tmp / "wts" / "my-slug"`), `resolve_task_path(task_root, "_mill/briefs/")` will look for `task_root / "_mill/briefs/"`. It doesn't exist yet, so it returns `target` directly (no fallback needed). `write_brief` then creates it. Correct.

8. **`cfg_dict` lacks `"paths": {"plan_dir"}`**: The cfg in the test has `plan_dir` and `reviews_dir` but the CLI only uses `cfg` to pass to `prepare()` which is mocked, so this is irrelevant.

9. **Plan spec: module name `"millpy_review_discussion_brief_path"`**: Test at line 345 uses this name. Plan says to use `"millpy_review_discussion_brief_path"`. Matches.

10. **Return early on non-zero exit**: Plan says "return early" with `return failures` at that point. Implementation does this (lines 403-404: increments and returns `failures`). Correct.

11. **Early return on JSON decode error**: Also matches plan.

12. **Plan-spec mock order**: The plan specifies the mock order as `_paths.resolve_git_root` -> `_paths.resolve_hub_path` -> `_paths.resolve_wiki_path` -> `_review_common.load_config` -> `_reviewers.load` -> `_reviewers.validate_role_refs` -> `_review_common.find_active_slug` -> `_review_discussion.prepare`. The implementation nests them in exactly that order (lines 389-397). Correct.

13. **`contextlib.redirect_stdout` placement**: The plan says to apply `redirect_stdout` and call `_mod.main()` inside the innermost `with` block. The implementation redirects stdout *outside* the innermost mock block (line 388 is before the mocks at line 389). The stdout redirect is not inside the mock context - but this doesn't matter for correctness since the mocks are applied via nested `with` and `redirect_stdout` is applied at the same level. The mocks and redirect are all in effect when `_mod.main()` is called at line 397. This is fine.

14. **`_review_discussion` mock target**: The test patches `"_review_discussion.prepare"`. Since the CLI does `from _review_discussion import prepare, finalize, run`, a patch on `"_review_discussion.prepare"` patches the module attribute, but the CLI's local name `prepare` was bound at import time via `exec_module`. Let me check this carefully.

The CLI at lines 61-62 does:
```python
from _review_discussion import prepare, finalize, run
```

Since the CLI module is loaded via `exec_module`, these imports run at that time. The mock patches `_review_discussion.prepare` in the `_review_discussion` module. But the CLI's local `prepare` name was already bound during `exec_module` before the mock is applied. So the mock on `_review_discussion.prepare` would NOT intercept the CLI's call to `prepare(...)` because the CLI is calling its own local `prepare` reference, not `_review_discussion.prepare`.

This is a classic Python mock target bug: patching the source module doesn't help when the name is already imported into the target module's namespace.

Wait - but the CLI module is loaded at line 347 (`_spec.loader.exec_module(_mod)`) BEFORE the `with _mock.patch(...)` context managers. The imports inside `main()` run at call time: looking at the CLI, the imports are inside `main()` function body (lines 55-61). So when `_mod.main(["--stage", "prepare"])` is called inside the mock context, the imports are re-executed fresh at that point. Since `_review_discussion` is already in `sys.modules`, `from _review_discussion import prepare` will re-bind the local `prepare` name from `sys.modules["_review_discussion"].prepare` - which has been patched. So the mock DOES work correctly here because imports are inside `main()`.

Let me verify that imports are indeed inside `main()` by re-checking lines 55-61 of the CLI.

Looking at lines 55-61 of `millpy-review-discussion.py`:
```python
    import _agent_dispatch
    import _paths
    import _reviewers
    from _paths import resolve_git_root, resolve_hub_path, resolve_wiki_path
    from _review_cli import print_error_envelope
    from _review_common import ReviewError, find_active_slug, load_config
    from _review_discussion import prepare, finalize, run
```

These are inside `main()` (indented, after the parser setup). So the mock on `_review_discussion.prepare` at line 396 patches the `_review_discussion` module object, and then when `_mod.main(["--stage", "prepare"])` runs, it does `from _review_discussion import prepare` which gets the patched version. This is correct.

15. **`_review_common.load_config` mock**: Similarly mocked on `"_review_common.load_config"`. The CLI does `from _review_common import ReviewError, find_active_slug, load_config` inside main(). When `load_config(hub_dir, mill_dir)` is called, the local `load_config` name is bound from `_review_common.load_config` which is patched. Correct.

16. **`_reviewers.load` mock**: Patched as `"_reviewers.load"`. The CLI does `import _reviewers` then calls `_reviewers.load(project_root)`. Since this goes through the module namespace, the patch works. Correct.

17. **`_reviewers.validate_role_refs`**: Mocked without a return value, so it just doesn't raise. The CLI calls `_reviewers.validate_role_refs(cfg, registry)`. Correct.

18. **The `briefs_dir` assertion**: When `write_brief` is called with `briefs_dir = _paths.resolve_task_path(git_root, "_mill/briefs/")` where `git_root = task_root = tmp / "wts" / "my-slug"`, it creates the dir and writes the file. `brief_path = task_root / "_mill" / "briefs" / "review-discussion-holistic-r1.md"`. The test checks `str(task_root) in brief_path_str` - which would be true. And `str(hub_root) not in brief_path_str` - `hub_root = tmp / "wts" / "millhouse"` which would not be in the path. Correct.

19. **The `_paths.resolve_hub_path` mock**: Returns `hub_root`. The CLI uses `hub_dir = resolve_hub_path()`. Inside `main()` the import is `from _paths import resolve_git_root, resolve_hub_path, resolve_wiki_path`. This re-binds from `_paths.resolve_hub_path` which is patched. Correct.

20. **`mill_dir = hub_dir / ".millhouse"`**: The CLI sets `mill_dir = hub_dir / ".millhouse"` (line 66). With `hub_dir = hub_root = tmp / "wts" / "millhouse"`, `mill_dir` becomes `tmp / "wts" / "millhouse" / ".millhouse"`. This doesn't need to exist since the test mocks `load_config` to return `cfg_dict` directly.

21. **`wiki_root` in mock**: `_paths.resolve_wiki_path` is patched at the module level but the CLI does `from _paths import ... resolve_wiki_path`. So the local `resolve_wiki_path` in the CLI is bound from `_paths.resolve_wiki_path` which IS being patched via `_mock.patch("_paths.resolve_wiki_path", ...)`. This works.

Everything looks correct. The implementation is clean and matches the plan. No blocking issues found.

MILL_REVIEW_BEGIN
# Review: Fix millpy-review-discussion to write briefs to the task worktree -- holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-09
```

## Verdict

APPROVE
Implementation is correct and complete; plan fully realised.
MILL_REVIEW_END