# Discussion: millpy-implement finalize/resume fixes and the red integration suites

```yaml
task: millpy-implement finalize/resume fixes and the red integration suites
slug: implement-recovery-and-integration-tests
status: discussing
parent_branch: main
```

## Problem

Three consolidated GitHub issues (#1163, #1162, #1160).

1. #1163: `millpy-implement --stage finalize` infers batch completeness by comparing the content-commit count with the number of cards.
   A card whose `Commit:` field is `none` (verification-only) never produces a commit, so a fully finished batch is reported as `stuck_type: incomplete` ("2 content commit(s) since start but 3 card(s) in batch") when the implementer ends without a JSON line.
   The recovery cost an extra agent turn.
2. #1162: `--stage prepare <batch> --resume-incomplete` re-renders the tracked brief `_mill/briefs/implement-<batch>-r1.md` but makes no housekeeping commit (deliberately, see below), so finalize's in-scope dirty gate can fail with `stuck_type: logic` "success reported but in-scope working tree dirty", listing only the brief and its `.out.md`.
   Separately, `mill-go-base/SKILL.md`'s "resuming a blocked batch after external fix" procedure never says to use `--resume-incomplete` when `preserve_start_sha=True`, so the normal prepare discards the preserved `start_sha`.
3. #1160: five integration suites fail on main: `test-spawn`, `test-plan-assets`, `test-merge`, `test-go-assets`, `test-agent-mode-commit-target`.
   Two of them (`test-go-assets`, `test-agent-mode-commit-target`) exercise the implementer/finalize machinery, so they are the verification vehicle for the code fixes.

Why now: the two millpy-implement bugs cost real orchestrator turns in a live run, and the red integration suites mean the fixes cannot be verified by the existing integration tier.

## Scope

**In:**

- Make the count-only completeness heuristic ignore `Commit: none` cards (#1163).
- Stop the resume-prepare re-rendered brief from tripping the finalize dirty gate (#1162).
- Add the `preserve_start_sha=True` -> `--resume-incomplete` instruction to `plugins/mill/skills/mill-go-base/SKILL.md` (#1162 related note).
- Repair the five integration suites (#1160), fixing test fixtures/callers where the tests are stale, and product code only where the test exposes a real bug.
- Add unit tests for the two code fixes in `plugins/mill/unit_tests/test-implementer-common.py`.

**Out:**

- Reworking the completeness gate beyond the `Commit: none` subtraction (the `cards_done` path already handles it).
- Making `--resume-incomplete` create a housekeeping commit (rejected, see Decisions).
- Any change to the other integration suites (only `test-baseline-waiver` is known green; do not touch it).
- Wiki/`_mill` path conventions.

## Decisions

### commit-none-recount

- Decision: `_cards_incomplete_reason` in `plugins/mill/scripts/_implementer_common.py` gains a keyword `commit_none_card_ids: set[int] | None = None`.
  Its count-only fallback (`_count_only_reason`, used when `cards_done` is absent or malformed) compares `content` against `len(card_ids - commit_none_card_ids)` instead of `len(card_ids)`; the message reports the adjusted expected count.
  The `cards_done` set-difference path is unchanged.
  Thread the parameter from every caller: `_batch_completeness_stuck` (new keyword `commit_none_card_ids`), `_reclassify_verify_failure` (already receives it), and the four `_batch_completeness_stuck` call sites in `finalize_from_output` / `_forward_output` (which already hold `commit_none_card_ids`, computed from the batch file on disk).
- Rationale: matches the issue's stated expectation and the existing code-derived carve-out (`_cards_done_all_commit_none`, issue #664); the set is computed from the batch file, never from the implementer's self-report.
- Rejected: trusting only `cards_done` (absent in exactly the failure case); treating any batch containing a `Commit: none` card as always complete (hides genuinely stopped-early batches).

### resume-brief-dirty

- Decision: fix the finalize side, not the prepare side.
  In `_in_scope_dirty_stuck`, the `_mill/briefs/` exclusion is `line.startswith("_mill/briefs/")` on repo-relative paths from `git diff --name-only`.
  Broaden it so a briefs path is excluded wherever the task dir sits inside the repo (a `/_mill/briefs/` path component, or equivalently a path relative to the resolved task dir), covering both the brief and its `.out.md`.
  The plan-writer must first reproduce the failure with a unit test using a tracked, re-rendered brief (including a nested/hub-relative layout) and only then adjust the predicate, so the fix targets the real cause; if the unit test shows the current predicate already excludes the reported paths, the remaining fix is whatever the reproduction shows (e.g. the `.out.md` naming or a different path root) -- do not ship a fix without a failing-then-passing test.
- Rationale: `--resume-incomplete` must not make a second `mill-go: start batch` commit, because `_content_commit_count` subtracts only commits whose subject starts with `mill-go: start batch` and a differently-named commit would be over-counted as content, while a same-named one is deliberately avoided (see the comment in `millpy-implement.py`'s resume branch).
  Briefs are already declared Builder-owned bookkeeping in `_in_scope_dirty_stuck`'s docstring (#885), so excluding them is the consistent fix.
- Rejected: committing the brief in the resume branch (breaks the recount as above); committing with a new subject and teaching `_content_commit_count` about it (more moving parts, two places to keep in sync).
- Autonomous assumption: this was an open design call; the finalize-side exclusion was chosen as the lower-risk option.

### resume-doc

- Decision: in `mill-go-base/SKILL.md`, the "resuming a blocked batch after external fix" procedure (around step 5, "Re-run `/mill-go`") gets an explicit note: when step 2 decided `preserve_start_sha = True`, the batch's prepare must be run as `--stage prepare <batch_name> --resume-incomplete` (so the preserved `start_sha` is not overwritten); when `False`, normal prepare.
  Cross-reference the existing step 5.5 `--resume-incomplete` description rather than restating its mechanics.
- Rationale: the routing from Resume into Execute's normal prepare currently discards the preserved SHA.
  Check `plugins/mill/skills/mill-go-base/resume.md` for the same routing and add the pointer there only if the routing is defined there.
- Rejected: making prepare auto-detect the preserved SHA (behaviour change to a stage other skills depend on).

### integration-suite-repairs

Root causes found by running each suite (`PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/<file>.py`):

- `test-plan-assets`: `plugins/mill/templates/plan-overview.md` and `plan-batch.md` now use `<TASK_TITLE_YAML>` (and `<BATCH_NAME_YAML>` in the batch template); the test's token dicts lack them.
  Fix: add `TASK_TITLE_YAML` (and `BATCH_NAME_YAML`) to the test's render calls via `_yaml_writer.quote_scalar`, as `mill-plan/SKILL.md` documents.
- `test-go-assets`: `_review_code.run` now requires keyword-only `git_root`.
  Fix: pass `git_root=` in the test call (`millpy-review-code.py` shows the calling convention).
  Check the sibling review-discussion/review-plan calls in the same file for the same drift.
- `test-agent-mode-commit-target`: `_forward_output` with only a `mill-go: start batch` commit since `start_sha` now correctly returns `stuck/logic` "success reported but no content commit".
  The test premise is stale: it simulates prepare with a housekeeping commit only.
  Fix: after the housekeeping commit, add a real content commit on the task branch before calling `_forward_output`, keeping the assertions that the recorded SHA is the task HEAD and not on main.
  Note `_forward_output` also emits `scope_violations` for untracked test files; the test must not assert their absence.
- `test-merge`: the two-hop chain scenario (#817) fails because `check_liveness` (since #879) counts a local `refs/heads/<branch>` as live, and the fixture leaves `test/task-c` (and `test/task-b`) as local branches after tagging `archive/<slug>`.
  Fix: in the fixture, delete the local branches (`git branch -D`) after creating each archive tag, matching what `mill-cleanup` does to a torn-down parent.
  Check the earlier dead-parent sub-scenarios for the same assumption.
  Product code is correct; do not change `_parent_branch.py`.
- `test-spawn`: `millpy-spawn.py` exits 1 with "Wiki not found at <container>/hub.wiki".
  The fixture builds `<container>/hub` and `<container>/wiki`, which is neither container form (`wts/<slug>` + sibling `wiki/`) nor prefix form (`<hub>.wiki`).
  Fix: make the fixture resolvable, preferably by writing `paths: {wiki: <abs wiki path>}` into the hub's `.millhouse/config.local.yaml` (the documented override in `_paths.resolve_wiki_path`), or by rebuilding it as `<container>/wts/hub` with sibling `<container>/wiki`.
  Further failures may follow once the wiki resolves (worktree location assertions, junction names, the docstring's `worktrees/<slug>` and `.millhouse/wiki` expectations); iterate until the suite passes, updating assertions to current behaviour when the current behaviour is the documented one (see `CLAUDE.md` container layout).
  If a remaining failure reveals a genuine spawn bug rather than fixture drift, fix the product code and record it.
- Autonomous assumption: tests are stale, not the product, in all five cases unless a reproduction proves otherwise.
  The plan must run each suite after its fix and the final batch must run all five plus the unit suite.

## Technical context

- `plugins/mill/scripts/_implementer_common.py`: `_content_commit_count` (subtracts commits with subject prefix `mill-go: start batch`), `_cards_incomplete_reason`, `_batch_completeness_stuck`, `_reclassify_verify_failure`, `_cards_done_all_commit_none`, `_in_scope_dirty_stuck`, `finalize_from_output`, `_forward_output`.
  `commit_none_card_ids` is already computed in `plugins/mill/scripts/millpy-implement.py` `main()` from the batch file and passed to finalize.
- `plugins/mill/scripts/millpy-implement.py`: the `args.resume_incomplete` branch intentionally skips `capture_snapshot`, `set_batch_fields`, and the housekeeping commit; `emit_prepare` then re-renders the brief via `_agent_dispatch.write_brief`.
- Existing unit tests for these helpers: `plugins/mill/unit_tests/test-implementer-common.py` (many `_batch_completeness_stuck` and `_reclassify_verify_failure` cases); follow its fixture style.
- Integration tests live in `plugins/mill/integration_tests/`; run singly with `PYTHONPATH= uv run --project plugins/mill python plugins/mill/integration_tests/<file>.py`.
  They write fixtures under `.scratch/`.
- The plugin cache (`${CLAUDE_PLUGIN_ROOT}`) may diverge from this worktree; verify against the worktree sources.
  Plan `verify:` commands must start with `PYTHONPATH=`.

## Constraints

- Never use `sed`; use Edit/Read/Write.
- `print()`/log output ASCII only.
- No changes to the parent worktree; this task is isolated.
- Unit tests use in-memory/tempfile fixtures, no real git or LLM.
- Skill-file edits: the change to `mill-go-base/SKILL.md` is a single-file, one-paragraph edit.

## Testing

- TDD candidates: `_cards_incomplete_reason` with `commit_none_card_ids` (batch of 3 cards, one `none`, 2 commits, `cards_done=None` -> complete; 1 commit -> incomplete with adjusted count; malformed `cards_done` falls back the same way); `_batch_completeness_stuck` and `_reclassify_verify_failure` threading; `_in_scope_dirty_stuck` with a modified tracked `_mill/briefs/` brief and `.out.md` (flat and nested layout) returning None while a real in-scope dirty file still returns the stuck dict.
- Integration: each of the five suites must pass individually; `test-go-assets` and `test-agent-mode-commit-target` additionally cover the finalize path.
- Run the full unit suite (`plugins/mill/unit_tests/run-all.py` via `uv run --project plugins/mill`) after the code batch.

## Q&A log

- **Q:** Where should the #1162 fix live: prepare-side commit or finalize-side exclusion? **A:** [auto-pick] Finalize-side exclusion of orchestrator-owned brief artifacts. **Why:** a second housekeeping-style commit would corrupt `_content_commit_count`, and briefs are already documented as Builder-owned in the dirty gate.
- **Q:** Fix stale integration tests or product code? **A:** [auto-pick] Fix the tests, except where a reproduction proves a product bug. **Why:** each failure traced to a deliberate later product change (#879 liveness, `git_root` param, `*_YAML` tokens, no-content-commit gate, wiki path resolution).
- **Q:** How to make `test-spawn` find the wiki? **A:** [auto-pick] Set `paths.wiki` in the fixture's `config.local.yaml`. **Why:** the documented override, smallest change; layout rebuild is the fallback if further drift appears.
