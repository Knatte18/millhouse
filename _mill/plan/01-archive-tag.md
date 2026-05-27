# Batch: archive-tag

```yaml
task: "mill-merge / fixer teardown recovery"
batch: archive-tag
number: 1
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Implements idempotent + safe conflict resolution for `mill-merge` Step 6's archive-tag creation (#356). Today `git tag archive/<slug> $CHILD_BRANCH` fails when the tag already exists from a prior aborted attempt; the operator has to manually delete the tag. This batch adds a `_archive_tag.create_or_resolve(worktree, slug, child_branch)` helper that picks one of three actions based on the existing tag's relationship to the new SHA — same-SHA no-op, ancestor force-update, or move-aside with numeric suffix — and a SKILL.md edit that invokes the helper via inline `$MILL_PYTHON -c "..."`.

The helper's external interface: returns `{"action": "noop"|"force_update"|"moved_aside"|"created", "tag": "archive/<slug>"|"archive/<slug>-NN", "moved_aside_to": "archive/<slug>-NN" | None}`. The helper handles all git tag CRUD + `--force-with-lease` push internally; callers do not need to follow up with git commands.

External interface for batch 2/3/4: none — this batch is self-contained.

## Cards

### Card 1: Failing test for `_archive_tag.create_or_resolve`

- **Context:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/unit_tests/test-config.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-archive-tag-conflict.py`
- **Deletes:** none
- **Requirements:** Write `test-archive-tag-conflict.py` exercising `_archive_tag.create_or_resolve(worktree, slug, child_branch)` against a tmp git repo created with `subprocess.run(["git", "init"], cwd=tmp)`. Cover exactly these scenarios as separate `unittest.TestCase` methods: (1) `test_no_existing_tag_creates` — no prior tag; assert result `{"action": "created", "tag": "archive/<slug>", "moved_aside_to": None}` and `git tag -l "archive/<slug>"` lists the tag. (2) `test_same_sha_is_noop` — tag exists pointing at child_branch HEAD; assert result `{"action": "noop", ...}` and the tag SHA is unchanged. (3) `test_ancestor_sha_force_updates` — tag exists pointing at an ancestor commit of child_branch HEAD; assert result `{"action": "force_update", "tag": "archive/<slug>", "moved_aside_to": None}` and the tag now points at child_branch HEAD. (4) `test_divergent_sha_moves_aside_to_01` — tag exists pointing at a divergent commit (on a different branch, not an ancestor); assert result `{"action": "moved_aside", "tag": "archive/<slug>", "moved_aside_to": "archive/<slug>-01"}` and both tags exist with the expected SHAs. (5) `test_second_divergence_moves_aside_to_02` — `archive/<slug>` AND `archive/<slug>-01` both exist with divergent histories; assert the new move-aside target is `archive/<slug>-02`. Skip the `--force-with-lease` push assertion in these tests (no remote in tmp repo); push is exercised via a separate code path the helper itself owns. Use `HUB = Path(__file__).resolve().parent.parent.parent.parent` + `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))` to import `_archive_tag` (matches `test-llm-claude.py` import idiom). Run the test before card 2 to confirm it fails with `ModuleNotFoundError: No module named '_archive_tag'`.
- **Commit:** `test(archive-tag): add failing test for create_or_resolve`

### Card 2: Implement `_archive_tag.create_or_resolve`

- **Context:**
  - `plugins/mill/scripts/_subprocess_util.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_archive_tag.py`
- **Deletes:** none
- **Requirements:** Create `_archive_tag.py` exposing `create_or_resolve(worktree: Path, slug: str, child_branch: str) -> dict`. Algorithm: (a) Resolve `target_sha = subprocess.run(["git", "-C", str(worktree), "rev-parse", child_branch], ...)`. (b) Resolve `tag_name = f"archive/{slug}"`. (c) Query existing tag: `git -C <worktree> rev-parse --verify --quiet refs/tags/<tag_name>`. If exit non-zero → tag doesn't exist → run `git -C <worktree> tag <tag_name> <child_branch>` then `git -C <worktree> push origin <tag_name>` and return `{"action": "created", "tag": tag_name, "moved_aside_to": None}`. (d) If exit zero → `existing_sha = stdout.strip()`. If `existing_sha == target_sha` → return `{"action": "noop", "tag": tag_name, "moved_aside_to": None}` (no git commands, no push). (e) Otherwise check ancestor: `git -C <worktree> merge-base --is-ancestor <existing_sha> <child_branch>`. Exit code 0 = ancestor → run `git -C <worktree> tag -f <tag_name> <child_branch>` then `git -C <worktree> push --force-with-lease origin <tag_name>` and return `{"action": "force_update", "tag": tag_name, "moved_aside_to": None}`. (f) Else (exit code 1 = divergent) → find lowest unused suffix: list existing `archive/<slug>-NN` tags via `git -C <worktree> tag -l "archive/<slug>-*"`, parse the two-digit suffixes (regex `^archive/{re.escape(slug)}-(\d{{2}})$`), compute `next_n = min({1..99} - existing_suffixes)`, format as `f"{next_n:02d}"`. Run `git -C <worktree> tag archive/<slug>-<NN> <existing_sha>` (the OLD sha), then `git -C <worktree> tag -f <tag_name> <child_branch>` (NEW sha), then push both tags (the moved-aside with plain push, the new tag with `--force-with-lease`). Return `{"action": "moved_aside", "tag": tag_name, "moved_aside_to": f"archive/{slug}-{next_n:02d}"}`. Use `_subprocess_util.run` for every git invocation. Do not check the push return code — push failure is treated as a non-fatal warning (the helper returns the result dict regardless of push outcome) so tests can exercise the tag-resolution branches against tmp repos with no remote. Print one-line ASCII status message to stderr per non-trivial action (`[archive-tag] noop -- tag matches`, `[archive-tag] force-update -- ancestor`, `[archive-tag] moved aside -- archive/<slug>-NN; new tag created`). Add module docstring matching repo style.
- **Commit:** `feat(archive-tag): add _archive_tag.create_or_resolve helper`

### Card 3: Update `mill-merge/SKILL.md` Step 6 to invoke helper

- **Context:**
  - `plugins/mill/scripts/_archive_tag.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/skills/mill-merge/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Replace the two-line Bash block at `### 6. Archive tag` in `skills/mill-merge/SKILL.md` (currently `git tag archive/<slug> "$CHILD_BRANCH"` + `git push origin "archive/<slug>"`) with an inline Python invocation matching the idiom at `### 7. Home.md -- mark [done]` in the same skill:
  ```bash
  PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "
  from pathlib import Path
  import _paths, _archive_tag
  worktree = _paths.resolve_git_root()
  result = _archive_tag.create_or_resolve(worktree, '<slug>', '$CHILD_BRANCH')
  print(f'[mill-merge] archive-tag action: {result[\"action\"]} -- tag: {result[\"tag\"]}')
  if result['moved_aside_to']:
      print(f'[mill-merge] prior tag preserved as {result[\"moved_aside_to\"]}')
  "
  ```
  Update the surrounding prose: replace the existing paragraph beginning "Tags the cleanup-commit tip..." with: "Idempotently tags the cleanup-commit tip of the task branch. The helper handles the three conflict cases — same-SHA no-op, ancestor force-update, divergent move-aside — so re-running `/mill-merge` after a partial teardown never fails at this step. See `_archive_tag.py` for the resolution logic." Preserve the existing "**Recovery note:**" callout block immediately above Step 4 untouched. Do not modify any other section of the SKILL.
- **Commit:** `docs(mill-merge): invoke _archive_tag helper from Step 6`

## Batch Tests

`verify:` runs the full unit test suite via `run-all.py`. The new `test-archive-tag-conflict.py` covers the five conflict scenarios called out in card 1. SKILL.md is interpreted text — no automated test for card 3; correctness is verified by integration in subsequent mill-merge runs and by the SKILL's inline-Python invocation being syntactically valid Python (the implementer should `python -c` the embedded snippet once before committing to confirm import paths resolve).
