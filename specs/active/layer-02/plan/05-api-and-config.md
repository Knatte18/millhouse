# Batch 05: API scripts + config

```yaml
kind: plan-batch
batch-name: api-and-config
batch-depends: [backends]
approved: false
```

## Batch-Specific Context

Three tiny CLI scripts (one per review type) plus the wiki `config.yaml`
additions. API scripts follow a common template: resolve roots, load config,
find slug, call backend, print JSON or handle error. ~15–25 LOC each.

## Batch Files

- scripts/mill-review-discussion.py
- scripts/mill-review-plan.py
- scripts/mill-review-code.py
- (wiki/config.yaml — lives in the wiki repo, not the hub repo. See Step 13
  for handling.)

## Steps

### Step 12: Add `review:` + `reviewers:` section to wiki `config.yaml`

- **Creates:** none (wiki/config.yaml exists from Layer 01)
- **Modifies:** `../wiki/config.yaml` (wiki repo, accessed via the `.millhouse/wiki` junction)
- **Reads:** `../wiki/config.yaml` (existing state), `specs/active/layer-02/discussion.md`
- **Requirements:**
  - Add top-level `paths:` section:
    ```yaml
    paths:
      discussion_file: active/<SLUG>/discussion.md
      plan_dir:        active/<SLUG>/plan/
      reviews_dir:     active/<SLUG>/reviews/
    ```
  - Add top-level `review:` section:
    ```yaml
    review:
      discussion:
        rounds: 2
        holistic: sonnetmax_tool
      plan:
        rounds: 3
        batch: sonnetmax
        holistic: sonnetmax
      code:
        rounds: 3
        reviewer: sonnetmax
        style: single
    ```
  - Preserve all existing Layer 01 config keys untouched.
  - Commit and push the wiki change. This is a **separate commit** from the
    hub commits in other cards. (Wiki is a separate git repo.)
- **Explore:**
  - `specs/active/layer-02/discussion.md` "Config contract" section — canonical shape.
- **depends-on:** [8]
- **Test approach:** smoke-test — load the file via PyYAML after editing;
  check all keys present and structurally valid.
- **Key test scenarios:**
  - Happy: after commit, `cat .millhouse/wiki/config.yaml | python -c "import yaml,sys; c=yaml.safe_load(sys.stdin); assert 'review' in c"` succeeds.
- **Commit:** `feat(config): add paths + review sections for Layer 02`
  (committed in the wiki repo)

### Step 13: Create the three API CLI scripts

- **Creates:** `scripts/mill-review-discussion.py`, `scripts/mill-review-plan.py`, `scripts/mill-review-code.py`
- **Modifies:** none
- **Reads:** `scripts/_review_common.py`, `scripts/_review_discussion.py`, `scripts/_review_plan.py`, `scripts/_review_code.py`, `scripts/mill-add.py`
- **Requirements:**
  - Each script has a `main()` entry point and `if __name__ == "__main__"` block.
  - Null CLI arguments. `argparse` may be used with no required args (for
    future `--help` support) but no args are required for normal invocation.
  - Each script follows this template:
    ```python
    """mill-review-<type> — CLI entry point for <type> review."""
    import json
    import sys
    from pathlib import Path

    def main(argv: list[str] | None = None) -> int:
        from _review_common import ReviewError, find_active_slug, load_config
        from _review_<type> import run

        project_root = Path.cwd()  # script invoked from project root or hub
        mill_dir = project_root / ".millhouse"
        wiki_root = (mill_dir / "wiki").resolve()
        cfg = load_config(wiki_root, mill_dir)

        try:
            slug = find_active_slug(mill_dir)
            result = run(cfg, slug, mill_dir, wiki_root, project_root)
            print(json.dumps(result.to_dict()))
            return 0
        except ReviewError as exc:
            print(str(exc), file=sys.stderr)
            return 1

    if __name__ == "__main__":
        sys.exit(main())
    ```
  - `load_config()` is imported from `_review_common` (added in Step 8). API
    scripts do NOT define their own config loader — one canonical impl.
- **Explore:**
  - `scripts/mill-add.py` — Layer 01's idiomatic CLI structure (argparse, main, sys.exit).
  - Each corresponding `_review_<type>.py` — confirm the `run()` signature.
- **depends-on:** [9, 10, 11]
- **Test approach:** smoke-test (invoke with `--help`; invoke with a seeded
  fixture and check exit code + JSON validity).
- **Key test scenarios:**
  - Happy: `python mill-review-discussion.py` with a properly seeded
    `.millhouse/` directory exits 0 with JSON on stdout.
  - Error: no `.slug.md` file → exits 1 with stderr message, empty stdout.
  - Error: config missing the `review:` section → exits 1 with clear stderr.
- **Commit:** `feat(review): add mill-review-discussion/-plan/-code API scripts`
