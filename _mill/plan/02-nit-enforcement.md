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

Fixes #515 — make the "always fix nits" rule structurally enforced instead of prose-only. Adds a `--nits-only` flag to `millpy-fix.py` that, on a successful nit-only pass, writes a `nits-fixed-<scope>` status row and emits `nits_applied: true`. Adds a new `_nit_gate.py` helper that recomputes, from the final review file per scope plus the status timeline, which approved scopes had nits but no fix marker. Wires that gate into mill-go's Handoff (block `phase: done` on unfixed nits) and strengthens both APPROVE-with-nits branches with non-skip language. The marker/flag emission lives inside `_implementer_common._forward_output` (the single success-emit point), so it fires in both agent (`--stage finalize`) and subprocess/psmux dispatch. Depends on batch 1 because it also edits `millpy-fix.py`, `_implementer_common.py`, and `test-millpy-fix.py` (shared-file write ordering). External interface consumed downstream: none (batches 3-5 do not touch the nit machinery).

## Cards

### Card 4: --nits-only flag + nits-fixed marker (emitted inside _forward_output)

- **Context:**
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
  - `plugins/mill/scripts/_timestamp.py`
- **Edits:**
  - `plugins/mill/scripts/millpy-fix.py`
  - `plugins/mill/scripts/_implementer_common.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:** The success verdict is emitted *inside* `_implementer_common._forward_output` (it owns the JSON print and may demote success→`stuck/verify`); `millpy-fix.main()` returns `finalize_from_output(...)`/`_forward_output(...)` directly and never sees the final status. So thread the nit behaviour into that function, not into `main()`:
  1. Add a boolean `--nits-only` argument to `millpy-fix.py`'s argparse (alongside `--scope`, `--review-file`, `--round`).
  2. Add two keyword-only params to BOTH `_forward_output(...)` and `finalize_from_output(...)` in `_implementer_common.py`: `nits_only: bool = False` and `status_path: Path | None = None` (the latter forwarded straight through `finalize_from_output` → `_forward_output`).
  3. Add a third keyword-only param `nits_scope: str | None = None` to both `_forward_output(...)` and `finalize_from_output(...)`. Inside `_forward_output`, on the **parsed-success emit path** (where a fixer's own reported `status == "success"` JSON is about to be printed — NOT a demoted `stuck/*` path, and NOT the inferred-success / no-JSON fallback paths, which a `--nits-only` fixer success never takes), when `nits_only` is True and `status_path` and `nits_scope` are not None: add `"nits_applied": True` to the dict before printing, and call `_status.append_phase(status_path, f"nits-fixed-{nits_scope}", _timestamp.now_utc_iso())`. On any `stuck` outcome, write no marker and no flag.
  4. In `millpy-fix.main()`, pass `nits_only=args.nits_only`, `status_path=status_path` (reuse the existing `status_path = _paths.status_path(project_root, cfg)` at line 146 — do NOT re-resolve via a hard-coded `"_mill/status.md"`), and `nits_scope = args.batch_name if args.scope == "batch" else "holistic"` into the call in BOTH the `--stage finalize` branch (via `finalize_from_output`) AND the full-stage dispatch (via `_forward_output`), so the marker fires under `dispatch == agent` (which uses `--stage finalize`) as well as subprocess/psmux.
  Do NOT change behaviour when `--nits-only` is absent. Keep messages ASCII.
- **Commit:** `feat(fix): --nits-only writes nits-fixed marker via _forward_output`

### Card 5: _nit_gate.compute_unfixed_nits helper

- **Context:**
  - `plugins/mill/scripts/_review_common.py`
  - `plugins/mill/scripts/_status.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:** none
- **Creates:**
  - `plugins/mill/scripts/_nit_gate.py`
- **Deletes:** none
- **Requirements:** Create `_nit_gate.py` exposing `compute_unfixed_nits(worktree: Path, reviews_dir: Path, status_path: Path) -> list[str]`. For each approved scope (per-batch scopes named in the status timeline `approved-<batch>` rows, plus `holistic` if a `holistic-approved` row exists), locate that scope's FINAL (latest-timestamp) code-review file under `reviews_dir` by matching filenames with `_review_common.RE_BATCH` (per-batch: `type=code`, `batch=<scope>`) and `_review_common.RE_SIMPLE` (holistic: `type=code`) rather than a hand-rolled glob, count its `### [NIT]` headings via `_review_common.parse_blocking_count(text, severity="NIT")` (note: `severity` is keyword-only), and include the scope in the returned list when its final review had `nit_count > 0` AND no `nits-fixed-<scope>` row exists ANYWHERE in the status timeline. Do NOT impose any positional ("at or after the approve row") constraint: mill-go writes the `nits-fixed-<scope>` marker during the NIT-fix dispatch, which runs BEFORE it appends `approved-<batch>` / `holistic-approved`, so the marker normally PRECEDES the approve row — a positional check would false-flag every fixed scope. Read the timeline via `_status.read_full(status_path)["timeline"]` (a list of `"<phase>  <timestamp>"` strings) — split each row on whitespace to get the phase token; do NOT hand-parse the YAML block and do NOT assume a row-iterator helper exists. Return an empty list when every nitted scope has its marker. Cross-card contract: the three phase tokens this gate matches — `approved-<batch>`, `holistic-approved`, and `nits-fixed-<scope>` — are authored by card 4 (`_forward_output` writes `nits-fixed-<scope>`) and card 6 (mill-go writes the approve rows); keep all three string literals identical across cards 4/5/6. All paths resolved via `_paths`; never pass a junction. ASCII-only output.
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
  - `plugins/mill/scripts/_implementer_common.py`
  - `plugins/mill/scripts/_review_common.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-millpy-fix.py`
- **Creates:**
  - `plugins/mill/unit_tests/test-nit-gate.py`
- **Deletes:** none
- **Requirements:** Create `test-nit-gate.py` importing `_nit_gate`. Cover: (a) gate returns empty when every nitted scope has a `nits-fixed-<scope>` row; (b) gate flags a scope whose final review has `### [NIT]` headings and no marker; (c) gate ignores a scope whose final (APPROVE) review has zero nits even if an earlier round had nits; (d) both a per-batch scope and `holistic` handled in one timeline. Build fixtures as synthetic review `.md` files (with `### [NIT]` headings) under a tempdir `reviews_dir` plus a synthetic `status.md` timeline. In `test-millpy-fix.py`, add a case asserting that a `--nits-only` success appends exactly one `nits-fixed-<scope>` row and sets `nits_applied: true` in the envelope (stub the fix subprocess/agent output as the existing fix tests do).
- **Commit:** `test(nit-gate): cover unfixed-nit detection and nits-fixed marker`

## Batch Tests

`verify:` runs `test-nit-gate.py` (new) and `test-millpy-fix.py`. Scope matches the batch's code surface: `_nit_gate.py`, the `--nits-only` path through `_forward_output`, and the marker. The `mill-go/SKILL.md` edit has no runnable unit surface — it is validated by the plan reviewer. Key scenarios: the four gate cases (a)-(d) and the marker/flag emission. Note: `verify:` (including the `--only test-nit-gate.py` term) runs only at batch completion, after every card in the batch has been implemented — so `test-nit-gate.py` always exists by the time `run-all.py --only` names it; it is never invoked mid-card.
