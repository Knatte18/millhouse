# Batch: status-gate

```yaml
task: "mill-merge / fixer teardown recovery"
batch: status-gate
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Hardens `mill-go`'s Entry Step 5 phase gate against the case where `_mill/status.md` has already been removed by an aborted `mill-merge` Step 4 cleanup commit (#358). Today the gate crashes with a `ValueError` (from `_status.read`'s `status_path.exists()` check) and the operator is stuck without a recovery hint. This batch adds a `_phase_gate.absent_status_halt_message(task: dict | None, slug: str) -> str` helper that converts a wiki `_client.get_task` result into a halt message, plus a SKILL.md edit that guards the `_status.read_full` call with `if not status_path.exists()` and routes through the helper. The five mapped states are: `ready-to-merge`, `pr-pending`, `done`, task-not-in-wiki (`None`), and any-other-status.

External interface for batches 1/2/4: none.

## Cards

### Card 5: Failing test for `_phase_gate.absent_status_halt_message`

- **Context:**
  - `plugins/mill/unit_tests/test-llm-claude.py`
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/unit_tests/test-mill-go-status-absent.py`
- **Deletes:** none
- **Requirements:** Write `test-mill-go-status-absent.py` exercising `_phase_gate.absent_status_halt_message(task, slug)` across five branches as separate `unittest.TestCase` methods: (1) `test_ready_to_merge_routes_to_mill_merge` — pass `task={"status": "ready-to-merge"}, slug="foo"`; assert returned string contains the literal substring `_mill/status.md` and the literal substring `/mill-merge` and the slug `foo`. (2) `test_pr_pending_routes_to_mill_merge` — `task={"status": "pr-pending"}`; same shape assertions. (3) `test_done_says_already_merged` — `task={"status": "done"}`; assert returned string contains the substring `already merged` and the slug. (4) `test_task_none_says_not_in_home_md` — `task=None`; assert returned string contains the substring `not in Home.md` and the slug. (5) `test_unknown_status_surfaces_value` — `task={"status": "discussing"}`; assert returned string contains the substring `discussing` and `inspect manually`. Use the existing `HUB = Path(__file__).resolve().parent.parent.parent.parent` + `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))` import idiom. No mocking of `_client.get_task` is needed at the helper-test boundary — the helper takes the task dict directly. Run the test before card 6 to confirm it fails with `ModuleNotFoundError: No module named '_phase_gate'`.
- **Commit:** `test(phase-gate): add failing test for absent_status_halt_message`

### Card 6: Implement `_phase_gate.absent_status_halt_message`

- **Context:**
  - `plugins/mill/scripts/wiki/_client.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_phase_gate.py`
- **Deletes:** none
- **Requirements:** Create `_phase_gate.py` exposing `absent_status_halt_message(task: dict | None, slug: str) -> str`. The function is pure — no IO, no subprocess. Logic: if `task is None`: return `f"_mill/status.md is absent and {slug} is not in Home.md -- cannot determine state. Inspect manually."`. Else read `status = task.get("status")`. If `status in ("ready-to-merge", "pr-pending")`: return `f"_mill/status.md is absent and wiki shows {status} for {slug} -- mill-merge has likely run cleanup but not completed. Run /mill-merge to resume teardown."`. If `status == "done"`: return `f"Task {slug} is already merged. Nothing to do."`. Otherwise: return `f"_mill/status.md is absent and wiki state is {status} -- unexpected; inspect manually."`. All messages ASCII only (use `--` not `—`). Add module docstring summarising the helper's role in mill-go's absent-status fallback.
- **Commit:** `feat(phase-gate): add _phase_gate.absent_status_halt_message helper`

### Card 7: Update `mill-go/SKILL.md` Entry Step 5 with absent-status guard

- **Context:**
  - `plugins/mill/scripts/_phase_gate.py`
  - `plugins/mill/scripts/wiki/__init__.py`
  - `plugins/mill/scripts/wiki/_client.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_status.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `skills/mill-go/SKILL.md` Entry Step 5 ("Entry phase gate"), add a guard block immediately before the existing `status = _status.read_full(status_path)` python block. The new block:
  ```python
  if not status_path.exists():
      import sys
      from wiki import _client
      from wiki import WikiStartupError, WikiProtocolError
      import _phase_gate
      try:
          task = _client.get_task(wiki_path, slug)
      except (WikiStartupError, WikiProtocolError) as e:
          print(f"_mill/status.md absent and wiki daemon unavailable: {e} -- inspect manually.", file=sys.stderr)
          raise SystemExit(1)
      print(_phase_gate.absent_status_halt_message(task, slug), file=sys.stderr)
      raise SystemExit(1)
  ```
  Insertion point: between Step 4.5's Path Setup block and the existing Step 5 phase-gate code. Add a one-sentence intro above the new block: "Before reading `status_path`, guard against the merge-interrupted state where `_mill/status.md` has been removed by mill-merge's cleanup commit but teardown did not complete -- mirrors mill-merge's own Step 5 fallback. Wiki daemon errors are caught explicitly so a daemon outage surfaces a readable message instead of a raw traceback." Preserve the existing phase table (`planned`, `implementing`/`reviewing`/`fixing`, `blocked`, `discussed`/`discussing`/`planning`, `done`, other) untouched -- the guard runs BEFORE that table is consulted. Do not modify Step 5's existing branches; do not modify Step 4.5's Path Setup; do not modify any other section of the SKILL.
- **Commit:** `docs(mill-go): guard entry phase gate against absent status.md`

## Batch Tests

`verify:` runs the full unit test suite. `test-mill-go-status-absent.py` covers the five branches of `absent_status_halt_message` and pins each halt message's load-bearing substrings. The SKILL.md edit (card 7) is interpreted text — correctness is verified by integration on the next mill-go invocation that hits a missing-status scenario.
