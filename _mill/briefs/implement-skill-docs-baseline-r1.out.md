Batch 07-skill-docs-baseline complete: 2 of 2 cards committed.

- Card 34: `plugins/mill/skills/mill-go-base/SKILL.md` — rewrote the "0.5. Baseline pre-flight" section: narrowed the speculative-early-launch exit branch's completeness claim to the module-wide half only, switched JSON-line extraction to select by `substage` key (documenting the per-batch result vocabulary computed/cached/deferred/skipped/error), dropped the stale `baseline_parent_sha` pin and on-demand-computation sentences, and restated the eager-before-batch-1 rationale inline instead of citing `_mill/discussion.md`. Commit `f49a73c1`.
- Card 35: `plugins/mill/skills/mill-merge-in/SKILL.md` — rewrote the "3.5. Baseline recompute" step: described `--recompute-baseline` as running the same `compute_baseline` algorithm with its own asymmetric verdict mapping (pre-existing-failures left unset vs. cached verbatim), documented the new batch-clearing side effect, and restated the merge-in rationale inline instead of citing `_mill/discussion.md`. Commit `84c3a2ae`.

Verified both edits against the actual landed code in `plugins/mill/scripts/millpy-implement.py` (`_run_module_wide_standalone`/`_run_per_batch_baseline_standalone`) and `plugins/mill/scripts/millpy-merge-in-subagent.py` (`--recompute-baseline` handler) before writing the prose, since this batch depends on batches 3 and 5.

`verify: null` for this batch (prose-only, no runnable test surface) — skipped straight to report per the brief. Working tree is clean.

{"status":"success","commit_sha":"84c3a2aef1b5d011e8abb42ab4d10fe6fcc71239","session_id":"7010d82e-3723-4dd3-b5a9-e14dd96297d3","cards_done":[34,35]}
