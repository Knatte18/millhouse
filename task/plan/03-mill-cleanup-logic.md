# Batch: mill-cleanup-logic

```yaml
task: "46 (A) — Home.md state machine + split mill-merge teardown into mill-cleanup"
batch: mill-cleanup-logic
number: 3
cards: 8
verify: "python plugins/mill/unit_tests/test-cleanup.py"
depends-on: [1]
```

## Batch Scope

This batch absorbs mill-merge's old teardown into `millpy-cleanup.py` and adds PR-reap for `[pr-pending]` tasks. The work is sequenced as a chain inside one file (`millpy-cleanup.py`) plus its SKILL.md and the unit test. The `CleanupPlan` dataclass grows a `to_reap_pr` field; `build_plan` swaps its `git log` guard for a `git tag -l archive/<slug>` check and learns to read Home.md markers to gate the `phase == "done"` branch; a new `phase == "pr-pending"` branch adds records to `to_reap_pr`; orphan detection extends to `[ready-to-merge]` and `[pr-pending]`; `apply_plan` gains a PR-reap loop. SKILL.md documents the new behaviour. Tests are split into two cards: one for `build_plan` extensions, one for `apply_plan` PR-reap (each existing block in `test-cleanup.py` is one `with tempfile.TemporaryDirectory()` block — the new ones follow that pattern). Card numbering continues at 11 (cards 1–6 were batch 1, cards 7–10 were batch 2).

## Cards

### Card 11: Extend `CleanupPlan` dataclass with `to_reap_pr`

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-cleanup.py`, add a fifth field to the `CleanupPlan` `@dataclass(frozen=True)` (currently lines ~40–46): `to_reap_pr: list[SlugRecord] = field(default_factory=list)`, declared between `to_remove_abandoned` and `to_reset_home`. The `default_factory=list` is mandatory — existing `CleanupPlan(...)` constructions in `test-cleanup.py` pass only the original four fields and would raise `TypeError` without the default. Add `field` to the `from dataclasses import …` line at the top of the file (currently imports only `dataclass`). Update the `build_plan` `return CleanupPlan(...)` call site to pass `to_reap_pr=to_reap_pr` once card 13 declares the list. Update `_print_plan` (currently lines ~193–209) to print a new section between `to_remove_abandoned` and `to_report`: for each record in `plan.to_reap_pr`, print `f"REAP-PR:           {r.slug}  [worktree={r.worktree_path}, branch={r.branch}]"`. Update the `"Nothing to do."` early-return guard to also check `plan.to_reap_pr` (line 194). Do not modify `build_plan` or `apply_plan` logic in this card; those changes land in cards 12–15.
- **Commit:** `feat(cleanup): add to_reap_pr field to CleanupPlan dataclass`

### Card 12: `build_plan` — gate `phase==done` teardown on Home.md marker + archive tag

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-cleanup.py`, rewrite the `if phase == "done":` branch in `build_plan` (currently lines ~131–144). Replace the existing `parent_branch = _status.read_parent_branch(...)` + `git log --oneline {parent_branch}..{record.branch}` guard with the following logic. Read the Home.md marker for this slug from `marker_by_slug` (already computed at the top of the function as `{t.slug: t.phase for t in home_tasks}`):
  - If `marker_by_slug.get(slug) == "done"`: run `_subprocess_util.run(["git", "-C", str(hub_root), "tag", "-l", f"archive/{slug}"])`. If the result's stdout is non-empty, append the record to `to_remove_done`. If the stdout is empty (archive tag absent), append to `to_report`: `f"{slug} — Home.md=[done] but archive tag archive/{slug} absent; run mill-merge first"`.
  - If `marker_by_slug.get(slug) == "ready-to-merge"`: skip silently — the task is live, waiting on mill-merge. Do NOT add to any list. (This is the `pass` branch.)
  - Otherwise (Home.md marker is `active`, `s`, `abandoned`, `None`, or something unexpected): append to `to_report`: `f"{slug} — status.md phase=done but Home.md marker is {marker_by_slug.get(slug)!r}; inspect manually"`. Do NOT add to `to_remove_done`.
  Leave the surrounding `elif phase == "abandoned":` and `elif phase in _LIVE_PHASES:` branches unchanged. Do NOT change `_LIVE_PHASES`; it stays as the live-phase set for status.md.
  
  **Test cleanup (mandatory — stale tests otherwise break `verify:`).** In `plugins/mill/unit_tests/test-cleanup.py`, delete or rewrite the four `guard-slug-1` through `guard-slug-4` test blocks: they mock `git log --oneline parent..branch` and assert against the substring `"unmerged commits"`, which no longer matches the new "archive tag absent" path. Two options per block: (a) delete the block entirely (cards 17–18 supersede the coverage with archive-tag-aware tests); (b) rewrite the mock to return `"archive/<slug>\n"` for the `["git", "-C", ..., "tag", "-l", ...]` invocation and update the assertion to check `to_remove_done`. Use option (a) — simpler and the new tests in Card 17 cover the equivalent scenarios. Also update `_mock_branch_run` (top of file): remove the `"log" in argv and "--oneline" in argv` branch (no production caller uses it anymore) and add a `"tag" in argv and "-l" in argv` branch returning `"archive/<slug>\n"` by default (card 17's tests will override this per-block as needed).
- **Commit:** `refactor(cleanup): gate done-teardown on Home.md marker + archive tag`

### Card 13: `build_plan` — detect `[pr-pending]` tasks for PR-reap

- **Context:**
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-cleanup.py`, declare a local `to_reap_pr: list[SlugRecord] = []` next to the existing `to_remove_done: list[SlugRecord] = []` / `to_remove_abandoned: list[SlugRecord] = []` declarations in `build_plan` (currently lines ~93–96). Inside the per-worktree `for wt_path in active_worktrees:` loop, add a new branch BEFORE the existing `elif phase in _LIVE_PHASES:` line: `elif phase == "pr-pending": to_reap_pr.append(record)`. The `record` variable is already constructed above; reuse it. Update the final `return CleanupPlan(...)` to pass `to_reap_pr=to_reap_pr` in the correct positional slot (as defined by card 11's field ordering). Do NOT add `"pr-pending"` to `_LIVE_PHASES` — pr-pending is its own actionable phase, not live.
- **Commit:** `feat(cleanup): detect [pr-pending] tasks for PR-reap in build_plan`

### Card 14: Extend orphan detection for new Home.md states

- **Context:**
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-cleanup.py`, extend the existing orphan-Home.md-marker check in `build_plan` (currently the `for task in home_tasks:` loop around lines ~176–181, containing `if task.phase == "active" and task.slug not in active_slugs:`). Change the condition to `if task.phase in ("active", "ready-to-merge", "pr-pending") and task.slug not in active_slugs:`. Update the reported message string from `f"orphan Home.md marker: {task.slug} is [active] but has no active worktree"` to `f"orphan Home.md marker: {task.slug} is [{task.phase}] but has no active worktree"` so the operator sees which phase is stranded. Do NOT touch the other two orphan checks in the same block (orphan worktrees under `<container>/wts/` and orphan-active-worktree-with-no-Home.md-entry); they detect different conditions.
- **Commit:** `feat(cleanup): extend orphan Home.md marker detection to new states`

### Card 15: `apply_plan` — PR-reap loop with `gh pr list` resolution

- **Context:**
  - `plugins/mill/scripts/_wiki.py`
  - `plugins/mill/scripts/_tasks_md.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `plugins/mill/scripts/millpy-cleanup.py`, add a new private helper `_apply_pr_reap_record(record, hub_root, wiki_path, junctions_cfg, cfg)` and a loop in `apply_plan` that processes `plan.to_reap_pr` records. The helper sequence per record:
  1. Resolve the PR via `_subprocess_util.run(["gh", "pr", "list", "--head", record.branch, "--state", "all", "--json", "state,mergeCommit,number", "--jq", ".[0]"], cwd=hub_root)`. On non-zero exit or empty stdout, append a `to_report`-style log line to stderr (`print(f"[cleanup] PR-reap {record.slug}: gh pr list failed: {stderr!r}", file=sys.stderr)`) and return early without touching state.
  2. Parse the stdout as JSON via `json.loads`. Extract `state`, `mergeCommit`, `number`.
  3. If `state == "OPEN"`: print `f"[cleanup] PR-reap {record.slug}: PR #{number} still OPEN — skipping"` and return.
  4. If `state == "CLOSED"` (PR closed without merge): print `f"[cleanup] PR-reap {record.slug}: PR #{number} CLOSED without merge — inspect manually (abandon or reopen)"` and return.
  5. If `state == "MERGED"`:
     a. Check for the archive tag: `_subprocess_util.run(["git", "-C", str(hub_root), "tag", "-l", f"archive/{record.slug}"])`. If empty, create the tag. Target SHA selection: first try `_subprocess_util.run(["git", "-C", str(hub_root), "fetch", "origin", record.branch])`; on success, use `record.branch`'s tip. On fetch failure (likely GitHub auto-deleted the branch after merge), use `mergeCommit["oid"]` from the JSON — run `_subprocess_util.run(["git", "-C", str(hub_root), "fetch", "origin", mergeCommit["oid"]])` first to ensure the SHA is local. Create the tag with `git -C <hub_root> tag archive/<slug> <sha>` then push with `git -C <hub_root> push origin archive/<slug>`.
     b. Flip Home.md to `[done]` using `_tasks_md.set_phase` + `(wiki_path / "Home.md").read_text/write_text` and add `"Home.md"` to a `wiki_relative_paths` accumulator the helper returns.
     c. Run the standard worktree teardown — resolve mode via `_resolve_inplace_mode(record, hub_root, wiki_path, cfg)`, then call `_apply_inplace_record(record, hub_root, task_branch)` or `_apply_worktree_record(record, hub_root, wiki_path, junctions_cfg)`. Both `_apply_inplace_record` and `_apply_worktree_record` are existing helpers in this module (lines ~271–396); `_apply_inplace_record` already reads `parent_branch` from `status.md` via `_status.read_parent_branch` internally, so the PR-reap helper does not need to resolve it.
     d. If `record.wiki_active_dir` exists, `shutil.rmtree` it and append `f"active/{record.slug}"` to the helper's wiki_relative_paths return.
  In `apply_plan`, after the existing `for record in plan.to_remove_done + plan.to_remove_abandoned:` loop and BEFORE the `active_link = hub_root / ".active"` dangling-junction block, add a new loop: `for record in plan.to_reap_pr:` calling `_apply_pr_reap_record(...)` and extending `wiki_relative_paths` with the returned list. Import `json` at the top of the module if not already imported. Update the `_wiki.write_commit_push` commit message at the bottom of `apply_plan` to also report PR-reap counts: `f"chore: cleanup — {len(plan.to_remove_done)} done, {len(plan.to_remove_abandoned)} abandoned, {len(plan.to_reap_pr)} pr-reaped"`. Update the final `main()` "Done:" print line to mention pr-reap count too.
- **Commit:** `feat(cleanup): PR-reap loop polls gh pr list and finalises teardown on MERGED`

### Card 16: Update `mill-cleanup` SKILL.md documentation

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `task/discussion.md`
- **Edits:**
  - `plugins/mill/skills/mill-cleanup/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Rewrite `plugins/mill/skills/mill-cleanup/SKILL.md` to document the absorbed teardown plus PR-reap. Replace the current one-sentence description (lines 3 and ~8) with: "Sweeps task artefacts: removes worktrees, branches, portals, and legacy wiki active-dirs for tasks whose Home.md marker is `[done]` (with archive tag confirming the squash landed); polls `gh pr list` for `[pr-pending]` tasks and finalises teardown when the PR merges; reports orphan worktrees and stranded Home.md markers. Runs from the hub, never from a task worktree." Add a `## States handled` table listing:
  | Home.md marker | status.md phase | Action |
  |---|---|---|
  | `[done]` | `done` (+ archive tag present) | Remove worktree, branch, portal, legacy wiki active-dir |
  | `[done]` | `done` (archive tag absent) | Report — squash never landed, run mill-merge first |
  | `[ready-to-merge]` | `done` | Skip — task is live, waiting on mill-merge |
  | `[pr-pending]` | `pr-pending` | Poll `gh pr list`; if MERGED → create archive tag (if absent) + flip `[done]` + teardown; OPEN → skip; CLOSED → report for manual triage |
  | `[active]` / `[ready-to-merge]` / `[pr-pending]` with no active worktree | n/a | Report as orphan Home.md marker |
  Keep the existing "Run it" `uv run …` invocation and the "default is dry-run" sentence. Add a sentence after the table: "Cleanup takes the wiki lock only when `--apply` is set. PR-reap also runs only under `--apply` — dry-run mode reports which `[pr-pending]` tasks WOULD be polled."
- **Commit:** `docs(mill-cleanup): document teardown absorption + PR-reap + state table`

### Card 17: Unit tests — `build_plan` extensions

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_tasks_md.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add five new test blocks to `plugins/mill/unit_tests/test-cleanup.py`'s `main()` function, each following the file's existing `with tempfile.TemporaryDirectory() as tmp:` + `patch("mill_cleanup._subprocess_util.run", side_effect=...)` pattern. Each block ends with a `print("PASS ...")` statement.
  1. **`phase=done + home_marker=done + archive tag present → to_remove_done`** — extend the existing `_mock_branch_run` so the `["git", "-C", ..., "tag", "-l", "archive/<slug>"]` invocation returns stdout `"archive/<slug>\n"`. Build plan with `home_tasks=[_make_task("done-slug", "done")]` and status.md phase=`done`. Assert the record lands in `plan.to_remove_done`, NOT in `plan.to_report`.
  2. **`phase=done + home_marker=done + archive tag absent → to_report`** — mock the tag-list call to return empty stdout. Assert the record lands in `plan.to_report` with substring `"archive tag"` and `"absent"`, NOT in `plan.to_remove_done`.
  3. **`phase=done + home_marker=ready-to-merge → skipped`** — build plan with `_make_task("rtm-slug", "ready-to-merge")` and status.md phase=`done`. Assert `plan.to_remove_done == []` and the slug does NOT appear in `plan.to_report`.
  4. **`phase=pr-pending → to_reap_pr`** — build plan with `_make_task("pr-slug", "pr-pending")` and a status.md whose phase is `pr-pending`. Assert `len(plan.to_reap_pr) == 1` and `plan.to_reap_pr[0].slug == "pr-slug"`.
  5. **`orphan check covers ready-to-merge and pr-pending`** — pass `home_tasks=[_make_task("rtm", "ready-to-merge"), _make_task("pp", "pr-pending"), _make_task("act", "active")]` and `active_worktrees=[]`. Assert exactly three orphan-marker lines in `plan.to_report` (one per slug), each containing the matching `[ready-to-merge]` / `[pr-pending]` / `[active]` substring.
  Use the existing `_make_status_md(phase: str, parent: str = "main")` helper for status.md fixtures; extend it to accept `phase="pr-pending"` if it doesn't already (the helper just substitutes into a yaml template — no special handling needed). Use the existing `_make_task(slug, phase_marker)` helper for Home.md fixtures; pass the new phase strings directly.
- **Commit:** `test(cleanup): cover build_plan extensions for new states + archive tag gate`

### Card 18: Unit tests — `apply_plan` PR-reap

- **Context:**
  - `plugins/mill/scripts/millpy-cleanup.py`
  - `plugins/mill/scripts/_wiki.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-cleanup.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add three new test blocks to `plugins/mill/unit_tests/test-cleanup.py`'s `main()` covering `apply_plan` PR-reap. Each follows the existing block pattern (`with tempfile.TemporaryDirectory() ...`, `with patch(...) ...`).
  1. **`apply_plan PR-MERGED → teardown executed + Home.md flipped to [done]`** — construct a `SlugRecord` for a fake worktree path. Patch `mill_cleanup._subprocess_util.run` so calls matching `["gh", "pr", "list", ...]` return stdout `'{"state": "MERGED", "mergeCommit": {"oid": "abc123"}, "number": 42}'`. Patch `mill_cleanup._subprocess_util.run` for `tag -l archive/<slug>` to return empty stdout (so the helper creates the tag). Patch `_worktree.remove` and `_junction.remove`. Build a `CleanupPlan(to_remove_done=[], to_remove_abandoned=[], to_reap_pr=[record], to_reset_home=[], to_report=[])`. Pre-create a Home.md with `[pr-pending]` for the slug. Call `apply_plan`. Assert: (a) at least one `git tag archive/<slug>` call was made; (b) the Home.md text on disk after the call shows `[done]` for the slug; (c) a worktree-remove call was made.
  2. **`apply_plan PR-OPEN → no-op`** — same setup but mock `gh pr list` returns `'{"state": "OPEN", "number": 42}'`. Assert: (a) no `git tag` call was made; (b) Home.md still shows `[pr-pending]`; (c) no worktree-remove call was made.
  3. **`apply_plan PR-CLOSED-unmerged → reported, no teardown`** — mock returns `'{"state": "CLOSED", "mergeCommit": null, "number": 42}'`. Assert no `git tag` call, no worktree-remove call, and that a stderr message (capture via `capsys` or by patching `print`) includes substring `"CLOSED"` and the slug.
  Use the existing `_fake_run` / `_fake_run2` patterns; extend the side-effect to dispatch on the argv shape (check for `"gh"` / `"pr"` substrings to return the right canned JSON). The `record.wiki_active_dir` field can be `None` for these tests — wiki active-dir handling is exercised by existing tests and reusing those code paths is fine.
- **Commit:** `test(cleanup): cover apply_plan PR-reap MERGED, OPEN, CLOSED paths`

## Batch Tests

`verify: "python plugins/mill/unit_tests/test-cleanup.py"` runs the whole test-cleanup.py suite end-to-end. Cards 11–15's production changes are exercised by the existing tests in `test-cleanup.py` (which must continue to pass) plus the new cards 17–18 tests. Cards 11 (CleanupPlan field) and 14 (orphan detection) are covered by card 17. Cards 12–13 (build_plan logic) are also card 17. Card 15 (apply_plan PR-reap) is card 18. Card 16 (SKILL.md docs) is reviewer-only. The implementer must run `verify:` after every card; the file is small enough that running the full suite per card is cheap.
