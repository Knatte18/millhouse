MILL_REVIEW_BEGIN
# Review: Fix nit-enforcement gate, Windows verify false-positive, reviewer oscillation, and scope-violation handling — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-06-23
```

## Findings

### [BLOCKING] Card 4 nits-fixed marker cannot hook the success print
**Location:** Batch 2 / Card 4
**Issue:** `main()` in `millpy-fix.py` returns `_forward_output(...)` directly (line 370); `_forward_output` parses status, may demote success→`stuck/verify`, and owns the JSON print. `main()` never sees the final `status`, so "on `status == success`, write marker and inject `nits_applied` before the final JSON print" is not implementable as written — the success decision lives inside `_forward_output`, not the caller.
**Fix:** Thread a `nits_only` flag (and status_path) into `_forward_output`/`finalize_from_output` so the marker write + `nits_applied: true` injection happen at the single point where success is actually emitted, not in `main()`.

### [BLOCKING] Card 4/Card 8 ignore the --stage finalize (agent) path
**Location:** Batch 2 / Card 4; Batch 3 / Card 8
**Issue:** In agent dispatch mode, success is emitted by `--stage finalize` (→ `finalize_from_output` → `_forward_output`), not the `full` stage. Card 4's marker logic and Card 8's derived holistic `verify_cmd` both only describe the `full`/finalize-path in `main()`'s prepare/full branch, but the finalize stage (lines 192-213) computes `verify_cmd` separately and currently forces `None` for holistic. The nit marker and the derived verify gate will silently not fire under `dispatch == agent`.
**Fix:** Apply both behaviours in the `--stage finalize` branch too (derive holistic `verify_cmd` there; pass `--nits-only` through finalize), or centralize in `_forward_output`.

### [BLOCKING] Cards 11-12 don't thread prior_notes through run() (subprocess/psmux path)
**Location:** Batch 4 / Cards 11-12
**Issue:** mill-go's subprocess/psmux code-review dispatch invokes `millpy-review-code.py` with no `--stage`, i.e. `--stage full` → `run()`. `run()` calls `prepare()` internally and does NOT accept/forward a `prior_notes` arg. Cards 11/12 add the param only to the CLI and `prepare()`, so in the dominant (non-agent) path the `--prior-notes` digest is parsed but never reaches `prepare()` — the anti-oscillation digest is silently dropped.
**Fix:** Add `prior_notes` to `run()`'s signature and forward it to its internal `prepare()` call; have the CLI's `full` branch pass `args.prior_notes` into `run()`.

### [NIT] Card 4 re-resolves status_path instead of reusing the computed one
**Location:** Batch 2 / Card 4
**Issue:** Card 4 prescribes `_paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`, but `main()` already holds `status_path = _paths.status_path(project_root, cfg)` (driven by `cfg['paths']['status_md']`). The hard-coded `"_mill/status.md"` can diverge from config and bypasses the `_mill/→task/` compat fallback.
**Fix:** Reuse the existing `status_path` variable.

### [NIT] Batch-2 verify lists test-nit-gate.py before its creating card runs
**Location:** Batch 2 batch-`verify:` / overview Batch Index
**Issue:** Fine within the batch (card 5 creates it, card 7 fills it), but worth confirming `run-all.py --only test-nit-gate.py` is only ever invoked at batch end after card 5/7 — a mid-card verify would error on the unknown name.
**Fix:** No change if verify runs only at batch completion; otherwise gate it.

## Verdict

REQUEST_CHANGES
Three load-bearing hook points (forward_output success, finalize stage, run() threading) are missed.
MILL_REVIEW_END
