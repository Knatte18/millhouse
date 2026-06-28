This is interesting. In the mill-go SKILL.md Entry section (line 25), the pattern for loading config uses `_review_common.load_config(hub_path, hub_path/.millhouse)`. The done_gate snippet at line 724 uses `_config.load_config(hub_root, git_root)` — passing `git_root` as the second argument. But this is in an inline Python snippet that is documentation guidance for how the operator's done_gate command is run, not actual framework code. The function signature states `worktree_root` for the second arg, and the intended use is `git_root`. In nested layouts, `git_root != hub_root`, so `worktree_root / ".millhouse" / "config.local.yaml"` would look for the local stub at `git_root/.millhouse/config.local.yaml`. However, for mill-go itself, the call is through `_review_common.load_config(hub_dir, mill_dir)` where `mill_dir = hub_dir / ".millhouse"`.

The discrepancy is minor and only impacts augmentation logic, not the primary `done_gate` key reading (which comes from the plugin template). This is in a SKILL.md snippet that will be copied by an LLM, not framework code. It's a potential NIT but not a correctness bug since `_config.load_config` is lenient about missing paths.

Now I have enough information to generate the full review.

MILL_REVIEW_BEGIN
# Review: Fix review finding-count parser, nested-layout brief path, verify cwd, process leaks, and missing done-gate — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewed_file: plan/ + source
date: 2026-06-28
```

## Verdict

APPROVE
All eleven cards are implemented correctly; no blocking issues found across three batches.
MILL_REVIEW_END