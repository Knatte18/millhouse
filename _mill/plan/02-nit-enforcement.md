# Batch: nit-enforcement

```yaml
task: "Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling"
batch: nit-enforcement
number: 2
cards: 4
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-nit-gate.py test-millpy-fix.py
depends-on: [1]
```

## Batch Scope

Fixes #515 — make the "always fix nits" rule structurally enforced instead of prose-only. Adds a `--nits-only` flag to `millpy-fix.py` that, on a successful nit-only pass, writes a `nits-fixed-<scope>` status row and emits `nits_applied: true`. Adds a new `_nit_gate.py` helper that recomputes, from the final review file per scope plus the status timeline, which approved scopes had nits but no fix marker. Wires that gate into mill-go's Handoff (block `phase: done` on unfixed nits) and strengthens both APPROVE-with-nits branches with non-skip language. Depends on batch 1 because it also edits `millpy-fix.py` and `test-millpy-fix.py` (shared-file write ordering). External interface consumed downstream: none (batches 3-5 do not touch the nit machinery).

## Cards

### Card 4: --nits-only flag + nits-fixed marker in millpy-fix

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** Add a boolean `--nits-only` argument to `millpy-fix.py`'s argparse (alongside `--scope`, `--review-file`, `--round`). When `--nits-only` is set and the fix pass finalizes with `status == "success"`: (1) resolve `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`; (2) compute `scope = batch_name if scope == "batch" else "holistic"`; (3) call `_status.append_phase(status_path, f"nits-fixed-{scope}", _timestamp.now_utc_iso())`; (4) add `"nits_applied": True` to the JSON envelope before it is printed. The marker write must happen only on success, atomically before the final JSON print. Do NOT change behaviour when `--nits-only` is absent. Keep messages ASCII.
- **Commit:** `feat(fix): --nits-only writes nits-fixed marker and nits_applied flag`

### Card 5: _nit_gate.compute_unfixed_nits helper

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_nit_gate.py`
- **Deletes:** none
- **Requirements:** Create `_nit_gate.py` exposing `compute_unfixed_nits(worktree: Path, reviews_dir: Path, status_path: Path) -> list[str]`. For each approved scope (per-batch scopes named in the status timeline `approved-<batch>` rows, plus `holistic` if a `holistic-approved` row exists), locate that scope's FINAL (latest-timestamp) code-review file under `reviews_dir`, count its `### [NIT]` headings via `_review_common.parse_blocking_count(text, severity="NIT")` (note: `severity` is keyword-only), and include the scope in the returned list when its final review had `nit_count > 0` AND no `nits-fixed-<scope>` row exists in the status timeline at or after the approve row. Read status rows via `_status` helpers; do not hand-parse the YAML block. Return an empty list when every nitted scope has its marker. All paths resolved via `_paths`; never pass a junction. ASCII-only output.
- **Commit:** `feat(nit-gate): add _nit_gate.compute_unfixed_nits`

### Card 6: mill-go Handoff nit gate + non-skip language

- **Context:**
  - `plugins/mill/scripts/_cleanliness.py`
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:** In `mill-go/SKILL.md` Handoff phase, add a nit-enforcement gate step BEFORE `phase: done` that invokes `_nit_gate.compute_unfixed_nits(worktree_root, reviews_dir, status_path)` via a `python -c` block (mirror the existing `_cleanliness.compute_terminal_dirt` terminal-gate invocation pattern in `_cleanliness.py`'s caller). If the returned list is non-empty, BLOCK Handoff with an ASCII message naming the unfixed scopes (e.g. `BLOCKED: unfixed nits in scope(s): <list> -- run the NIT-fix pass before completing`). In both APPROVE-with-nits branches (per-batch and holistic), (a) add `--nits-only` to the `millpy-fix.py` dispatch `<args>`, and (b) add a non-skip clause carrying its own rationale: "NEVER skip the NIT-fix pass, even under time or performance pressure. 'Non-blocking' does NOT mean optional -- deferred nits re-surface as BLOCKING in later rounds and cost more total rounds. Only nits a reviewer explicitly marks 'no action required' may be left." Do not list `_nit_gate.py` in any Context (it is created in card 5 of this batch).
- **Commit:** `feat(mill-go): structural nit gate at Handoff + non-skip language`

### Card 7: tests for the nit gate and marker

- **Context:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-nit-gate.py`
- **Deletes:** none
- **Requirements:** Create `test-nit-gate.py` importing `_nit_gate`. Cover: (a) gate returns empty when every nitted scope has a `nits-fixed-<scope>` row; (b) gate flags a scope whose final review has `### [NIT]` headings and no marker; (c) gate ignores a scope whose final (APPROVE) review has zero nits even if an earlier round had nits; (d) both a per-batch scope and `holistic` handled in one timeline. Build fixtures as synthetic review `.md` files (with `### [NIT]` headings) under a tempdir `reviews_dir` plus a synthetic `status.md` timeline. In `test-millpy-fix.py`, add a case asserting that a `--nits-only` success appends exactly one `nits-fixed-<scope>` row and sets `nits_applied: true` in the envelope (stub the fix subprocess/agent output as the existing fix tests do).
- **Commit:** `test(nit-gate): cover unfixed-nit detection and nits-fixed marker`

## Batch Tests

`verify:` runs `test-nit-gate.py` (new) and `test-millpy-fix.py`. Scope matches the batch's code surface: `_nit_gate.py` and the `--nits-only` path in `millpy-fix.py`. The `mill-go/SKILL.md` edit has no runnable unit surface — it is validated by the plan reviewer. Key scenarios: the four gate cases (a)-(d) and the marker/flag emission.
