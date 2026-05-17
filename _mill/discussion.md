# Discussion: 59 (A) -- Small infra fixes batch 8

```yaml
task: 59 (A) -- Small infra fixes batch 8
slug: mill-misc-fixes-8
status: discussing
parent: main
```

## Problem

A batch of nine unrelated infrastructure bugs has accumulated from recent task runs (issues #295, #296, #303, #305, #307, #309, #311, #314, #318). None of them is large enough to warrant a dedicated task and none belongs to either the review-pipeline-fixes (#61) or branch-slug-fixes (#60) task scopes. They share the property that each is a small, localised correction to existing helpers, SKILL.md prose, a unit test, marketplace config, or the merge-in subagent.

Why now: these defects keep surfacing in concurrent task runs. #295 / #296 make helper APIs unintuitive (callers guess shapes and fail). #303 produced an actual mis-planned task whose batches 3/4 had `depends-on: []` instead of `[1,2]` / `[3]` and the validator did not catch it. #305 means the Windows unit-test runner fails on every push. #307 silently routes plugin commands at the dev tree on directory-source marketplaces. #309/#311 make the discussion and code review loops slightly wrong. #314 silently undid an intentional file deletion in a live task and required manual cleanup. #318 is already fixed in main; included only to document the design principle.

## Scope

**In:**

- `_status.py` -- add `read(status_path) -> dict` returning the parsed top YAML block as a plain dict (#295).
- `_paths.py` -- give `resolve_git_root` an optional `start: Path | None = None` argument (#296).
- `_plan_validate.py` -- add a `depends-on-batch-mismatch` cross-check verifying per-batch frontmatter `depends-on:` matches the overview Batch Index `depends-on:` for the same batch (#303).
- `plugins/mill/unit_tests/test-vscode-processes.py` -- guard the posix-only assertions with `os.name != "nt"` and print `SKIP` on Windows (#305).
- `plugins/mill/templates/marketplace.json` / `update-plugins.ps1` / `mill-setup` and supporting docs -- investigate how `CLAUDE_PLUGIN_ROOT` resolves with `source: directory` marketplaces and apply or document the fix (#307).
- `plugins/mill/skills/mill-start/SKILL.md` -- in Phase: Discussion Review step 5 (GAPS_FOUND), change `git -C <worktree> add <discussion_path>` to `git -C <worktree> add <discussion_path> <reviews_dir>/` so review files are committed (#309).
- `plugins/mill/skills/mill-go/SKILL.md` -- remove `mill-receiving-review` load instructions from the Builder flow (Execute step 3, Holistic step 5, Resume step 4 cross-references); reaffirm in Principles that only the dispatched implementer loads it (#311).
- `plugins/mill/scripts/millpy-merge-in-subagent.py` + `plugins/mill/templates/merge-in-conflict-brief.md` -- include relevant task-intent excerpts (current plan files + `discussion.md`) in the conflicts-mode subagent prompt so the model can recognize an intentional deletion (#314).
- Unit tests for the three new behaviours that materially change code paths (#295, #296, #303).

**Out:**

- #318 -- already fixed in main as part of the `config-move-to-hub` squash. Documented in this discussion only as a design-principle note; no code change in this task.
- Splitting this batch into smaller per-issue tasks. The whole point of the "batch 8" pattern is to take one trip through plan / review / merge for nine small fixes.
- Re-architecting `_status` summary helpers, or unifying `read_status` and `read_full`. The new `read()` is additive; existing helpers are untouched.
- Changing the `--auto` GAPS_FOUND interaction shape; only the git-add pathspec changes in #309.
- Generalising the merge-in conflict resolver to also surface DU conflicts to the operator (option (b)). Option (a) -- intent-aware prompt -- is sufficient and avoids adding an operator-interaction path.
- Migrating the unit-test runner to `pytest` to "properly" solve #305; the inline `if/print` pattern is acceptable for now.

## Decisions

### `_status.read()` shape (#295)

- Decision: Add a new top-level `read(status_path: Path) -> dict` that parses the top fenced YAML block and returns its keys as a dict (`phase`, `task`, `slug`, `branch`, `parent`, `plan`, `task_description`, plus any future fields). On a missing file, raise `ValueError(f"status file not found: {status_path}")`; on malformed YAML, raise `ValueError`.
- Rationale: This is the exact behaviour the proposal text describes ("parser fensed yaml-blokk og returnerer dict"). The existing `read_status()` returns a slim, derivation-heavy summary (`current_batch`, `last_timeline_entry`) and `read_full()` returns the wrapper `{"yaml": ..., "timeline": ...}`. Callers that just want the YAML block keys keep falling back to inline `yaml.safe_load` because neither existing helper matches that shape.
- Rejected:
  - Aliasing to `read_status()` -- the slim summary intentionally drops fields; callers needing `branch:` or `task_description:` still cannot use it.
  - Aliasing to `read_full()` -- forces every caller to write `read(...)["yaml"]["phase"]`, which is exactly the unwrapping callers complain about.
- API exposure: add `read` to the public-API docstring; mention it in mill-plan's SKILL.md (signature line) per proposal.

### `_paths.resolve_git_root` optional start (#296)

- Decision: Change signature to `resolve_git_root(start: Path | None = None) -> Path`. When `start is None`, behaviour is unchanged (`git rev-parse --show-toplevel` from cwd). When `start` is provided, run `git -C <start> rev-parse --show-toplevel`. Existing wiki-cwd guards and resolver downstream remain unchanged.
- Rationale: Multiple callers already write `resolve_git_root(some_path)` and crash with `TypeError`. The addition is backwards-compatible. The wiki-cwd guard already operates on the resolved `repo_root`; passing `start` changes only the `cwd` of the `git rev-parse` call, not the guard.
- Rejected: Renaming the helper or adding a sibling `resolve_git_root_from(start)` -- callers expect the same name; the optional argument is the path of least surprise.
- API exposure: add a signature line in mill-plan and mill-start SKILL.md per proposal.

### `_plan_validate` depends-on cross-check (#303)

- Decision: Add `_check_depends_on_batch_mismatch(batch_files, overview_text)` in `_plan_validate.py`, called from `run()`. Behaviour:
  - Parse overview batch index via `extract_batch_index`.
  - Build a `number_to_name` map from the overview entries (same construction `resolve_deps_as_names` does internally).
  - For each batch entry whose `file:` resolves to a file in `batch_files`, read that file's top fenced-YAML block and parse the `depends-on:` field.
  - Normalise both sides to a set of batch-name strings: for each `depends-on` list (overview side and per-batch side), translate `int` entries through `number_to_name` and pass `str` entries through unchanged. `resolve_deps_as_names` itself takes the full overview batch-dict list and returns the overview-side normalisation in one call; the per-batch-file side is a list of raw ints/strs that needs the inline translation (we cannot pass it to `resolve_deps_as_names` because that function expects `[{"name": ..., "depends-on": [...]}, ...]` dicts).
  - Emit a `depends-on-batch-mismatch` finding per mismatched batch with a `message` naming both sets (sorted, comma-joined).
- Severity: BLOCKING (consistent with the other structural checks).
- Rationale: Mirrors the proposal exactly; matches the existing per-check shape (one function, registered in `run()`).
- Rejected:
  - Folding into `_check_depends_on_unknown` -- conflates two semantically distinct checks ("unknown ref" vs. "ref disagrees with overview"); they'd share no code.
  - Treating the per-batch frontmatter as the source of truth and "fixing" the overview -- the overview's DAG is authoritative because mill-go reads it; emitting a finding is the correct response.
- Skip-key: `--skip-check depends-on-batch-mismatch` (existing skip mechanism applies).

### test-vscode-processes posix mocks on Windows (#305)

- Decision: Guard the two posix-mocked tests (`posix_parser_basic`, `posix_parser_no_code_processes`) with `if os.name != "nt":`; otherwise emit `print("SKIP: posix_parser_basic (Windows)")` and `print("SKIP: posix_parser_no_code_processes (Windows)")`. Uses the same `os.name` idiom the file already uses at line 273 (`path_match_helper_windows_case_insensitive`), inverted. The Windows-mocked tests still run on Linux/macOS CI.
- Rationale: The root cause is that `os.path` on Windows is `ntpath`, and patching `os.name = "posix"` does not switch path semantics. Re-engineering the mock to also swap `os.path` would require touching `_vscode_processes` to import `ntpath`/`posixpath` indirectly -- out of scope. The SKIP path matches the existing inline-test convention (`SKIP: path_match_helper_windows_case_insensitive (not Windows)` is already in the file).
- Rejected:
  - Patching `os.path.basename` etc. -- pulls test setup into product code (or fragile monkey-patching).
  - Converting the file to `pytest` with `@pytest.mark.skipif` -- creates a runner inconsistency vs. the rest of `plugins/mill/unit_tests/`.

### directory-source marketplace + CLAUDE_PLUGIN_ROOT (#307)

- Decision: Investigate concretely. The deliverable has two parts:
  1. Locate where `CLAUDE_PLUGIN_ROOT` is resolved. Suspected sites: `~/.claude/plugins/known_marketplaces.json`, the source-of-truth `marketplace.json` shipped under `plugins/`, and `update-plugins.ps1`. If any of these contains an `installLocation` field or equivalent that points at the dev tree on `source: directory` marketplaces, change the materialisation to point at the cache instead (`~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`).
  2. If no in-repo config controls this (i.e. the resolution is a Claude Code internal), document the workaround in `CLAUDE.md` and `update-plugins.ps1` header comments: on directory-source installs operators must point CC at the cache, not the source, or accept that intra-plugin paths resolve to the dev tree.
- Rationale: The proposal is explicitly an investigation. The discussion locks the deliverable as "in-repo fix if available, otherwise documented finding"; mill-plan will produce a card structured around investigation -> fix-or-document.
- Rejected: Hard-coding `CLAUDE_PLUGIN_ROOT` in scripts -- that breaks every other plugin install layout.

### mill-start GAPS_FOUND review-file commit (#309)

- Decision: In `plugins/mill/skills/mill-start/SKILL.md`, Phase: Discussion Review step 5: change the git-add command from `git -C <worktree> add <discussion_path>` to `git -C <worktree> add <discussion_path> <reviews_dir>/`. Keep the commit message and message format unchanged.
- Rationale: APPROVE-with-NOTE (step 4b) already commits `<reviews_dir>/`; the GAPS_FOUND branch is the only path that leaves them untracked. Single-line edit in one file.
- Rejected: Auto-`.gitignore` of `_mill/reviews/` -- the reviews are part of the per-task history and belong on the branch (mill-merge strips them at the squash-cleanup commit).

### mill-go Builder vs Implementer mill-receiving-review (#311)

- Decision: In `plugins/mill/skills/mill-go/SKILL.md`:
  - Execute step 3 (line ~203): remove the "Before reading any review file, load the `mill-receiving-review` skill" instruction. Replace with: "The Builder only reads the verdict from the JSON envelope -- never the findings. Loading `mill-receiving-review` is the dispatched implementer's job."
  - Execute step 4 (`NEED_CONTEXT`): the Builder reads only the `## Missing context` bullets, which is structured plumbing, not a finding -- no skill load required. Leave a one-line clarification: "Reading the missing-context bullet list does not require `mill-receiving-review`."
  - Holistic step 5 (line ~343): remove "Load `mill-receiving-review` before reading any finding"; the holistic-fix CLI dispatches a fresh implementer that loads the skill itself (the fix-prompt already instructs this). Add a one-line cross-reference to Principles.
  - Resume step 4 (line ~282): rewrite to "When resume lands you at any point that reads review findings, the dispatched implementer loads the skill. Builder still does not read findings."
  - Principles bullet on `Implementer owns receive-review` stays as the canonical statement.
- Rationale: The skill governs how to handle findings (push back vs. fix). Builder consumes only the structured verdict (`APPROVE` / `REQUEST_CHANGES` / `NEED_CONTEXT` / `ERROR`) and -- for `NEED_CONTEXT` -- a bulleted file list. Neither requires the receive-review decision tree.
- Rejected: Keep the Builder-loads-skill instruction and rewrite Principles to match -- contradicts the design intent ("Lean Builder. You never read card bodies, diffs, or source files") and inflates Builder context.

### merge-in subagent intent-awareness for DU conflicts (#314)

- Decision: In conflicts mode, before rendering `templates/merge-in-conflict-brief.md`, the dispatcher gathers task-intent excerpts and passes them as a new template token `<TASK_INTENT>`:
  - Read `_mill/discussion.md` if present (whole file -- it is small).
  - Read every batch file in `_mill/plan/` (overview + per-batch) if present, but only the YAML frontmatter block plus the `## Cards` section's `- **Edits:**` / `- **Creates:**` / `- **Deletes:**` bullets, not the prose. This caps token cost.
  - Concatenate with section dividers; place at the top of the brief above `## Conflicting files`.
- Template change: add `<TASK_INTENT>` token to `merge-in-conflict-brief.md`. Add Instructions language: "If a file is listed under a batch's `Deletes:` and the merge introduces a modified version of that file from the parent, the resolution is to delete the file (your branch's intent overrides). Stage the deletion with `git -C <PROJECT_ROOT> rm <file>`."
- Token-budget note: discussion.md is typically < 4k tokens. Batch frontmatter/bullets per batch ~ 200 tokens. Worst case ~ 10k tokens added to the conflict brief; well within Sonnet's window.
- If neither `_mill/discussion.md` nor `_mill/plan/` exists (e.g. running merge-in outside a mill-managed branch), `<TASK_INTENT>` renders empty and the subagent behaves as before.
- Rationale: The naive resolver re-introduced an intentionally deleted file because it had no signal about intent. Surfacing intent in the prompt is the minimal automated fix; the alternative (option b -- surface DU to operator) adds a new operator-interaction path and goes against the broader autonomous-pipeline direction.
- Rejected: Option (b) -- adds an operator-interaction path with no automation gain.
- Rejected: Including the full batch prose -- exceeds the value/cost ratio; the per-card path bullets carry the intent signal.

### #318 is already fixed; document the principle only

- Decision: No code change. Add a one-line entry in `CLAUDE.md` `## Path invariants` (or the closest existing section) capturing the principle: "Helpers that take a path argument MUST NOT consult cwd for config; route the path through to any inner config lookup."
- Rationale: The fix landed in main during config-move-to-hub. The proposal is documentation-only.
- Rejected: Skipping entirely -- the principle is generalisable and prevents the next instance.

### Unit tests

- Decision: Add three test functions:
  - `test-status-read.py` (new) -- verifies `_status.read()` returns a dict containing the expected keys for a typical status.md fixture (including `branch:` after the recent additions) and raises `ValueError` on a missing path.
  - Extend `plugins/mill/unit_tests/test-paths.py` (if it exists) or create it -- verifies `_paths.resolve_git_root()` returns the same path with and without `start=<repo_dir>` argument, using a real temp git repo via `git init`.
  - Extend `plugins/mill/unit_tests/test-plan-validate.py` -- new case `depends_on_batch_mismatch_emits_finding`: write an overview with `depends-on: [1]` for batch 2 and a batch-2 frontmatter with `depends-on: []`; assert the validator emits one `depends-on-batch-mismatch` finding.
- Rationale: New behaviour ships with tests; the rest of the changes (SKILL.md prose, marketplace docs, conflict brief template) are not behaviour-bearing in a way unit tests would meaningfully cover.

## Technical context

- `_status.py`: existing helpers `read_status` (slim summary), `read_full` (raw yaml+timeline), and the splitter `_split_fences` already exist. New `read()` is a thin function that calls `_split_fences(text, _YAML_FENCE)` and `yaml.safe_load` on the body. Returns the dict as-is.

- `_paths.resolve_git_root` (line 115): currently no argument. The change is one parameter and one `git -C` extension. The wiki-cwd safety guards (lines 121-141) already operate on the resolved `repo_root` and need no change.

- `_plan_validate.run()` (line 715): registers checks in linear order. The new `_check_depends_on_batch_mismatch` slots in after `_check_depends_on_unknown` and before `_check_parallel_modifies_overlap`. The helper imports `extract_batch_index` from `_plan_dag` (already used by `_check_depends_on_unknown` and `_compute_transitive_ancestors`). The number-to-name translation is built inline from the overview's batch list (`{entry["number"]: entry["name"] for entry in batches if "number" in entry}`) — mirrors the construction inside `resolve_deps_as_names` (`_plan_dag.py:158`). `resolve_deps_as_names` itself is called on the overview-side dict list to get its normalised view in one step; the per-batch-file side reads the raw `depends-on:` ints/strs from the file's YAML block and applies the same `number_to_name` lookup inline.

- `test-vscode-processes.py` -- the existing `path_match_helper_windows_case_insensitive` test already uses the `if os.name != "nt": SKIP` pattern (lines 273-274). The same shape applies to the two posix tests, inverted.

- Marketplace research entry points to investigate (#307): `marketplace.json` (in repo root), `update-plugins.ps1` (top-level), `mill-setup` Phase 4.x where it materialises CLAUDE_PLUGIN_ROOT references. The user-side file `~/.claude/plugins/known_marketplaces.json` is not in this repo; treat it as opaque and infer behaviour from the script side.

- mill-start SKILL.md (line 124) -- single edit in step 5 of Phase: Discussion Review.

- mill-go SKILL.md -- four edits across Execute step 3, Holistic step 5, Resume step 4, plus a touch-up in Principles to remove the residual ambiguity. The Principles bullet already says the right thing; the redundant "Builder loads the skill" instructions in the body are what create the contradiction.

- `millpy-merge-in-subagent.py` -- `_run_conflicts` (line 108) renders `merge-in-conflict-brief.md` with two tokens today (`CONFLICTING_FILES`, `PROJECT_ROOT`). Adding `TASK_INTENT` requires:
  - A new local function `_collect_task_intent(project_root: Path) -> str` reading `_mill/discussion.md` and the YAML/header-bullet portion of each `_mill/plan/*.md`.
  - Passing the string through to `_render.render`.
  - Updating the template to include `<TASK_INTENT>` between the title and `## Conflicting files`.

- Template / plan file paths assume the worktree's `_mill/` layout (CLAUDE.md `## Path invariants` -- working state on the task branch). `project_root` is `Path.cwd()` per the script (line 71); when called from a task branch checkout, `_mill/` is sibling to `plugins/`.

- `mill-receiving-review` skill (`plugins/mill/skills/mill-receiving-review/SKILL.md`): the decision tree distinguishes FIX vs. PUSH BACK and is solely consumed when reading review findings. The Builder reads only the JSON envelope and the structured missing-context bullets, neither of which is a "finding".

## Constraints

- ASCII-only stdout/stderr (CLAUDE.md `## Conventions worth carrying`). All new `print()` strings use plain ASCII (`-`, `->`, `--`).
- `${CLAUDE_PLUGIN_ROOT}` for intra-plugin paths in SKILL.md and shell commands. New text in mill-go / mill-start follows this.
- Junctions are IDE convenience only; new code resolves real paths via `_paths` (CLAUDE.md `## Path invariants`). The conflict-subagent's `_mill/` lookup uses `project_root / "_mill"`, not any junction.
- `_status.read()` must NOT introduce a circular import. `_status` currently imports only `yaml` and `_yaml_writer`; the new function adds no imports.
- Tests in `plugins/mill/unit_tests/` use in-memory / `tempfile` fixtures, no real git unless inside the test scope, and no real LLM (CLAUDE.md `## Repo layout pointers`). The new `resolve_git_root(start=...)` test does require a real `git init` in a tempdir -- acceptable because it isolates fully to `tempfile.TemporaryDirectory()`.

## Testing

- TDD candidates:
  - `_status.read()` -- write the test first (fixture status.md, assert dict keys), then implement.
  - `_paths.resolve_git_root(start=...)` -- write the test first (tempdir + `git init`, assert `start=tempdir` returns `tempdir.resolve()`), then implement.
  - `_check_depends_on_batch_mismatch` -- write the test first (synthetic overview + batch files in a tempdir), then implement.

- Non-TDD changes (no logic shift):
  - SKILL.md edits (#309, #311) -- prose only; no test possible. Manual verification: run mill-start --auto on a discussion that triggers GAPS_FOUND, confirm `git status` shows reviews/ committed; for mill-go, the contradiction is documentation-only.
  - merge-in conflict brief template change (#314) -- behaviour test is end-to-end (real merge-in run with intent-aware prompt). Acceptable to verify manually on a synthetic DU conflict reproduction.
  - test-vscode-processes (#305) -- run the file on Windows; the SKIP lines must appear and the file must exit 0.
  - Marketplace docs (#307) -- no automated test; verification is operator-side (run a fresh install, observe `CLAUDE_PLUGIN_ROOT`).
  - #318 doc-only -- no test.

- Regression coverage: existing `_status` / `_paths` / `_plan_validate` tests must continue to pass with no modifications. The new tests are additions, not rewrites.

## Q&A log

- **Q:** For `_status.read()` (#295), what should it return? **A:** [auto-pick] Add `read(status_path) -> dict` returning the parsed top YAML block as a dict. **Why:** Matches the proposal's "parser fensed yaml-blokk og returnerer dict" verbatim; existing `read_status`/`read_full` have incompatible shapes.
- **Q:** Where to put the per-batch depends-on cross-check (#303)? **A:** [auto-pick] New `_check_depends_on_batch_mismatch` function called from `run()`. **Why:** Matches the per-check structural pattern; conflating with `_check_depends_on_unknown` shares no code and obscures intent.
- **Q:** How to fix the posix test on Windows (#305)? **A:** [auto-pick] Guard with `sys.platform != "win32"` and print SKIP on Windows. **Why:** Matches the existing inline-skip pattern in the same file (`path_match_helper_windows_case_insensitive`); patching `os.path` would push test mock concerns into product code.
- **Q:** Scope for the marketplace investigation (#307)? **A:** [auto-pick] Investigate, apply in-repo fix if available, otherwise document workaround. **Why:** The proposal is explicitly investigative; capping at "document-only" would skip the cheap fix if one exists.
- **Q:** Resolve mill-go mill-receiving-review contradiction (#311) by? **A:** [auto-pick] Remove Builder load instruction; only Implementer loads it. **Why:** Aligns with the Lean Builder principle and the actual data flow (Builder reads only the JSON envelope).
- **Q:** merge-in DU conflict approach (#314)? **A:** [auto-pick] Option (a) -- include plan/discussion excerpts in subagent prompt. **Why:** Keeps merge-in autonomous; option (b) adds an operator-interaction path with no automation gain.
- **Q:** Add unit tests for new behaviours? **A:** [auto-pick] Yes -- minimal tests for `_status.read`, `resolve_git_root(start=...)`, and the depends-on cross-check. **Why:** New behaviour ships with tests; SKILL.md/template prose changes are not behaviour-bearing in a way unit tests cover.
- **Q:** Bundle all nine fixes into one task? **A:** [auto-pick] Bundle. **Why:** The "batch 8" task pattern is designed to amortise one plan/review/merge trip across multiple small fixes; splitting nine ways multiplies overhead without changing risk.
