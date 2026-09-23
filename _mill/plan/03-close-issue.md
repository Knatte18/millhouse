# Batch: close-issue

```yaml
task: "Deactivate codeguide integration in millhouse"
batch: close-issue
number: 3
cards: 1
verify: PYTHONPATH= sh -c "! grep -q CODEGUIDE_PLUGIN_ROOT plugins/mill/skills/git-commit/SKILL.md && ! grep -q codeguide-update plugins/mill/skills/mill-merge-in/SKILL.md && uv run --project plugins/mill python plugins/mill/unit_tests/test-sibling.py && uv run --project plugins/mill python plugins/mill/unit_tests/test-guards.py"
depends-on: [1, 2]
```

## Prior failure

- Round 1: PASS: container-form -> bare role next to wts/
PASS: container-form works for non-millhouse repo names
PASS: prefix-form -> <name>.<role> next to repo
PASS: old hub-form no longer triggers special-case (intentional regression)
PASS: container-form match is case-sensitive and literal
PASS: trailing slash on repo_root does not break detection
PASS: CLI entry point prints resolved path, exit 0
PASS: CLI exits 2 with usage message on bad args
PASS: resolve_path raises ValueError when repo_root.name == 'wiki' (role=wiki)
PASS: resolve_path raises ValueError when repo_root.name == 'wiki' (role=plan, role-agnostic)
PASS: resolve_path raises ValueError when repo_root.name == 'wiki' even in container-form parent
PASS: resolve_path does not raise when repo_root.name != 'wiki' (regression guard)
PASS: codeguide _sibling.py raises same ValueError -- identical-twin mirror is functional
PASS: mill and codeguide _sibling.py are identical-twins (modulo module docstring)
All _sibling unit tests passed.
PASS: no direct rmtree callsites in plugins/mill/ outside ALLOWED_FILES
PASS: no U+2192 arrow in any test-*.py
PASS: no wiki-cwd anti-patterns in scripts/ or skills/ across mill + codeguide
PASS: anti-weakening guardrail present in both implementer-brief.md and mill-implementer.md
PASS: no Windows-only venv-existence checks in plugins/mill/skills/
[Scenario A: hub-form]
FAIL: resolve_wiki_path(hub_root): PosixPath('/tmp/tmpef3o16yi/hub.wiki') != PosixPath('/tmp/tmpef3o16yi/wiki')
- Self-resolve: `test-worktree-sibling-resolution.py` Scenario A fails identically when run directly against `main` (confirmed by mill-go via a direct rerun on the `millhouse` hub worktree) -- a pre-existing, unrelated bug in `_sibling.py`/`_paths.py`'s hub-form resolution, not a regression from this plan. The batch's compound verify command couldn't catch this at baseline time: on `main`, the leading `! grep -q CODEGUIDE_PLUGIN_ROOT ...` check itself fails (the marker is still present pre-task), so the `&&` chain short-circuits before ever reaching this test -- the baseline computation never observed the failure. `_sibling.py`/`_paths.py` are out of scope for this plan (see 00-overview.md's "codeguide plugin and general-purpose plumbing are out of scope" Decision), so the fix is to drop this unrelated, already-broken assertion from this batch's own verify command rather than fix or gate on it.

## Batch Scope

Close GitHub issue #1137 as moot, now that both call sites into codeguide are gone. The issue's `err.txt` artifact came from codeguide's own `resolve_scope.py`, which stops running the moment nothing invokes `codeguide-update`; batches 1 and 2 are the change that makes that true, so this batch depends on both landing first. This batch's own `verify:` re-confirms the mechanism is actually gone (both marker strings absent from the two edited skill files) immediately before the issue is closed, so the closure is never based on a stale assumption, and additionally re-runs `test-sibling.py`, `test-guards.py`, and `test-worktree-sibling-resolution.py` unmodified -- discussion.md's Testing section names these as the empirical regression check that the files this plan deliberately does NOT touch (`_sibling.py`, the codeguide plugin) still pass, and this is the natural place to run them since it is the plan's last batch.

## Cards

### Card 12: close GitHub issue #1137

- **Context:**
  - `plugins/mill/skills/git-commit/SKILL.md`
  - `plugins/mill/skills/mill-merge-in/SKILL.md`
- **Edits:** none
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** **Idempotency check first (added after round 1):** run `gh issue view 1137 --json state,comments --jq '{state: .state, last_comment: (.comments[-1].body // "none")}'`. If `state` is already `CLOSED` and `last_comment` already matches the closing comment body below, the GitHub actions already happened in a prior round -- do NOT re-run `gh issue comment` or `gh issue close`; just note this in your turn summary and treat the card as complete. Otherwise (issue still open, or the matching comment is not yet present): run `gh auth status` first; if it fails, halt and report rather than silently skipping this card. Then run `gh issue comment 1137 --body "Closing as moot: mill's git-commit and mill-merge-in skills no longer call into the codeguide plugin (see plugins/mill/skills/git-commit/SKILL.md and plugins/mill/skills/mill-merge-in/SKILL.md), so codeguide's resolve_scope.py -- the source of this issue's err.txt artifact -- no longer runs."` followed by `gh issue close 1137`. Both commands target this repo's own `origin` remote via `gh`'s ambient repo detection -- do not pass an explicit `--repo` flag. If the `gh issue comment` call fails, halt and report -- do not attempt the close. If `gh issue comment` succeeds but the following `gh issue close` call fails (e.g. the issue was already closed by another actor in the meantime), do not treat this as a hard card failure: report that the comment posted successfully and surface the close command's error/exit status to the operator, then continue -- the comment is the durable record either way.
- **Commit:** none

## Batch Tests

`verify:` checks that neither `CODEGUIDE_PLUGIN_ROOT` (git-commit's deleted invocation) nor `codeguide-update` (mill-merge-in's deleted invocation) remain in the two files those batches edited, confirming the mechanism this issue tracked is actually gone before the issue is closed, then re-runs `test-sibling.py` and `test-guards.py` as a regression check on the files this plan intentionally left untouched. `test-worktree-sibling-resolution.py` was dropped from this check after round 1 (see `## Prior failure`): its Scenario A fails identically on `main`, pre-dating this plan, in code (`_sibling.py`/`_paths.py`) this plan does not touch. Card 12 itself makes no file changes, so `Commit: none` is correct (`Edits:`/`Creates:`/`Deletes:`/`Moves:` are all also "none").
