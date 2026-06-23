# Batch: implementer-finalize-contract

```yaml
task: "Fix agent-dispatch cwd guard, implementer self-termination, and false-success contracts"
batch: implementer-finalize-contract
number: 2
cards: 5
verify: "PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-implementer-common.py test-millpy-implement.py"
depends-on: [1]
```

## Batch Scope

Closes the two false-success holes in the implementer finalize path and
strengthens the implementer brief. Adds two mechanical gates to
`_implementer_common._forward_output` — a batch-completeness gate (raw
commit count vs `### Card N` count, #521) and an in-scope dirty-tree gate
(#516) — wired through both `_forward_output` and its agent-dispatch entry
`finalize_from_output`, fed by new params resolved in `millpy-implement.py`.
In parallel, hardens `implementer-brief.md` with an anti-yield directive, a
mandatory `git status --porcelain` self-check, and sharper Test Integrity
Guardrail wording (#519). Depends on batch 1 because it also edits
`millpy-implement.py`'s setup/finalize block.

Batch-local decisions: the completeness gate emits `stuck_type: transient`
(mill-go's one-shot retry gives a free continuation; a fresh re-dispatch
resumes because committed cards and `start_sha` persist in status.md). The
dirty-tree gate emits `stuck_type: logic`. New helper params are keyword-only
with `None` defaults so existing callers/tests are unaffected; when a param
is `None` the corresponding gate is a no-op (backward compatible).

## Cards

### Card 6: Add completeness + dirty-tree gates and thread params through the finalize helpers

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/scripts/_subprocess_util.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** (1) Add two module-level helpers to `_implementer_common.py`:
  `_batch_completeness_stuck(project_root, start_sha, card_count, session_id) -> dict | None` — returns `None` (no-op) when `start_sha is None`, when `card_count is None`, OR when `card_count <= 0` (a falsy/zero card count means the batch file had no `### Card N:` headings — e.g. a test fixture or a docs-only batch — and the gate must not fire). Otherwise runs `git rev-list --count {start_sha}..HEAD` via `_subprocess_util.run(..., cwd=project_root)` (mirror the existing usage at `millpy-implement.py` ~line 295). **Guard the parse:** if the subprocess returncode is non-zero, OR `stdout.strip()` is not a base-10 integer (wrap `int(...)` in `try/except ValueError`), return `None` — never let a non-numeric stdout raise (existing tests such as `test-millpy-implement.py` mock `_subprocess_util.run` to return a non-numeric sha for all git calls, so an unguarded `int()` would crash the success path). Only when a numeric `count` is obtained and `count < card_count` return `{"status":"stuck","stuck_type":"transient","reason": f"batch incomplete: {count} commit(s) since start but {card_count} card(s) in batch -- implementer stopped before finishing all cards","session_id": session_id or "unknown"}`, else `None`.
  `_in_scope_dirty_stuck(project_root, task_dir, parent_branch, session_id) -> dict | None` — returns `None` when `task_dir is None or parent_branch is None`; otherwise calls `_cleanliness.compute_terminal_dirt(project_root, task_dir, parent_branch)` and if the returned list is non-empty returns `{"status":"stuck","stuck_type":"logic","reason": f"success reported but in-scope working tree dirty: {dirt}","session_id": session_id or "unknown"}`, else `None`. **Wrap the `compute_terminal_dirt` call in `try/except Exception` and return `None` on any failure** — `compute_terminal_dirt` calls `_pygit2_util.status_porcelain`, which raises `GitOpsError` when `project_root` is not a real git repo (e.g. the non-git fixture in `test-millpy-implement.py`). A finalize-time git failure must be a no-op here, never a crash: the authoritative mill-go 2b cleanliness gate still runs afterward. Keep all reason strings ASCII. Both helpers must be fully self-defensive (no exception escapes); the new calls in the self-reported-success branch sit outside the inferred-path `except Exception` wrapper, so the helpers themselves own their error handling.
  (2) Add keyword-only params `card_count: int | None = None`, `task_dir: Path | None = None`, `parent_branch: str | None = None` to BOTH `_forward_output` (line 311) and `finalize_from_output` (line 255); `finalize_from_output` forwards all three to its `_forward_output` call (line 270).
  (3) In `_forward_output`'s self-reported-success branch, immediately AFTER the existing no-content-commit check (the `HEAD == start_sha` block ending ~line 359) and BEFORE the success-enrich `git rev-parse HEAD` at ~line 361: call `_batch_completeness_stuck(project_root, start_sha, card_count, session_id or parsed.get("session_id"))`; if non-`None`, `print(json.dumps(...))` and `return 0`. Then call `_in_scope_dirty_stuck(project_root, task_dir, parent_branch, session_id or parsed.get("session_id"))`; if non-`None`, `print(json.dumps(...))` and `return 0`.
- **Commit:** `feat(implementer-common): add completeness and in-scope dirty-tree finalize gates (#521, #516)`

### Card 7: Apply the completeness gate to the inferred-success emit points

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `_forward_output`'s inferred-success fallback (the `try` block at lines ~374-451), guard each of the three points that emit `{"status":"success", ..., "inferred":True}` (currently lines ~416, ~431, ~448) with the completeness gate so an incomplete batch that produced commits but no JSON report is never inferred as success. Immediately before each such success `print`, call `_batch_completeness_stuck(project_root, start_sha, card_count, session_id)` and if it returns non-`None`, `print(json.dumps(...))` and `return 0` instead of the success line. Do not alter the existing dirty-tree / formatter-drift logic on these paths (the inferred branch already rejects a dirty tree at ~line 419); only add the completeness short-circuit ahead of each success emit. The `except Exception: pass` wrapper at ~450 must continue to cover the new calls.
- **Commit:** `fix(implementer-common): gate inferred-success on batch completeness (#521)`

### Card 8: Resolve and thread card_count, task_dir, parent_branch in millpy-implement.py

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_parent_branch.py`
  - `plugins/mill/scripts/_plan_dag.py`
  - `plugins/mill/scripts/_cleanliness.py`
  - `plugins/mill/unit_tests/test-millpy-implement.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-implement.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Compute the three gate inputs in `main()` and pass them to the finalize helpers. (1) `card_count`: read `batch_file.read_text(encoding="utf-8")` and count card headings by matching the heading shape `_plan_validate` uses — `^###\s+Card\s+\d+\s*:` in multiline mode. In the actual Python source use a single-backslash raw string: `len(re.findall(r"(?m)^###\s+Card\s+\d+\s*:", text))`. (Any doubled backslashes appearing in this plan's markdown are escaping artifacts only — the implemented regex must use single backslashes, or it will match nothing and silently disable the gate.) Add `import re` at the top if not already imported. (2) `task_dir`: use `status_path.parent` (the `_mill/` dir), matching mill-go's 2b cleanliness gate. (3) `parent_branch`: `_parent_branch.resolve(status_path, interactive=False)` — non-interactive because finalize has no operator; add `import _parent_branch` if not already imported. Wrap the `parent_branch` resolution in `try/except` and fall back to `None` on failure (a `None` param makes the dirty gate a safe no-op rather than crashing finalize). Pass `card_count=card_count, task_dir=status_path.parent, parent_branch=parent_branch` to BOTH the `finalize_from_output(...)` call in the finalize stage (lines ~195-202) and the `_forward_output(...)` call in the full stage (line ~308). Compute `card_count`/`parent_branch` in a location reachable by both stages (e.g. after `batch_file` is known at line ~175, before the finalize-stage branch).
- **Commit:** `feat(implement): thread card_count/task_dir/parent_branch into finalize gates (#521, #516)`

### Card 9: Harden implementer-brief.md with anti-yield, self-check, and guardrail wording

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Three edits to `implementer-brief.md`. (1) Anti-yield directive: at the top of `## Implementation discipline` (before the numbered list at line ~44), add a bolded paragraph instructing the implementer to complete the ENTIRE batch in a single turn and to never end its turn between cards — a per-card commit is NOT a stopping point; only stop once every `## Cards` entry is committed, `## Verify` has run, and the JSON report is emitted. (2) Pre-report self-check: in `## Report` (before the final-turn JSON discussion, after line ~82), add a mandatory step: before emitting the success JSON, run `git status --porcelain --untracked-files=no` via `git -C <PROJECT_ROOT>`; if it shows ANY tracked in-scope modification, commit it via the `git-commit` skill (or report `stuck_type: logic`) — never report `success` with an uncommitted tracked change, because `millpy-implement` finalize now rejects a success with a dirty in-scope tree. (3) Test Integrity Guardrail (#519): extend the `## Test Integrity Guardrail` paragraph (line ~60) to explicitly forbid dropping, skipping, renaming-away, or omitting any pre-existing test during a migration/refactor (the post-change test set must include every pre-change test), and to forbid shared-decision-violating shortcuts to make verify pass — calling out `git remote set-url` as a concrete banned example where the plan's Shared Decision required a plain text edit. Keep all added text ASCII.
- **Commit:** `docs(implementer-brief): forbid mid-batch yield, require clean-tree self-check, sharpen test guardrail (#521, #516, #519)`

### Card 10: Unit-test the completeness and dirty-tree gates

- **Context:**
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-implementer-common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add unit tests reusing the existing real-git tempfile fixture pattern in `test-implementer-common.py` (`_setup_fixture`, `_capture_stdout`). This file has NO per-test functions and no `run-all`-discovered test list: it runs inline numbered cases inside `main()` and increments an `errors` counter (see the final case ~"case 26"). Add the new cases inside the existing `main()` body, continuing the case numbering and `errors`-counter pattern; do not add standalone `test_*` functions (they would never run). Cover the completeness gate via `_forward_output` with a self-reported `{"status":"success",...}` output: (a) `card_count` greater than the number of content commits since `start_sha` demotes to `stuck` with `stuck_type: transient`; (b) `card_count` equal to (or less than) the commit count still yields `success`. Cover the dirty-tree gate: (c) with `task_dir`/`parent_branch` set and an uncommitted in-scope tracked modification present, a self-reported success demotes to `stuck` with `stuck_type: logic`; (d) a clean in-scope tree yields `success`. Also assert (e) that omitting the new kwargs (`card_count=None`, `task_dir=None`, `parent_branch=None`) preserves the pre-existing behavior (no demotion) — this guards backward compatibility. Set `verify_cmd=None` (or a trivially-passing command) in these tests so the verify gate does not interfere. Follow the file's `run-all.py` discovery convention.
- **Commit:** `test(implementer-common): cover completeness and dirty-tree finalize gates`

## Batch Tests

`verify` runs `test-implementer-common.py` (the new gate tests, Card 10, plus the existing inference-path tests as regression coverage for Cards 6-7) and `test-millpy-implement.py` (regression-guards the Card 8 threading change to `millpy-implement.py`). `implementer-brief.md` (Card 9) is template prose with no runnable surface; it is validated by code review, not by `verify`. Scope is intentionally two test files because only the implementer finalize path and its CLI threading are exercised.
