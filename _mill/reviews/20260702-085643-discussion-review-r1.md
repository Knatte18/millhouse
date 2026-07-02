I have verified all the key claims. The source citations in the discussion are accurate (`_run_verify_gates` signature, the `nits_only` guard, `millpy-implement.py` lines, mill-go delegation line 349, and the four "before reading" callsites). I found several scope/consistency gaps not addressed by the discussion.

MILL_REVIEW_BEGIN
# Review: Fix agent-mode dispatch races and pipeline gaps

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-02
```

## Findings

### [GAP] Liveness-probe fix leaves 3 stale "stopped=terminal" statements
**Section:** Scope / Decision (#587,#595)
**Issue:** Scope names only `## Agent-mode dispatch` step 4, but the "treat stopped/interrupted the same as a raw API error / one-retry transient path" assertion is also stated in step 3 (`mill-go/SKILL.md:125`) and in two "Agent-mode properties" bullets (`:156`, `:158`); editing only step 4 leaves the SKILL internally contradicting the new probe-first rule.
**Fix:** Extend scope to reword `:125`, `:156`, `:158` so the probe-before-terminal rule is stated consistently, not just at step 4.

### [GAP] Baseline worktree may lack gitignored deps/config the verify cmd needs
**Section:** Decision (#590) / Constraints
**Issue:** A bare `git worktree add <parent_sha>` gets a clean tree WITHOUT gitignored state (`.venv`, `.millhouse/config.local.yaml`, `.wiki`/`.active` junctions, node_modules, build caches) that a language-agnostic `verify:` may require; a spurious failure there records `"pre-existing-failures"` and silently disables the module-wide gate for the whole task — defeating #541 in the opposite direction.
**Fix:** State the assumption/mitigation (e.g. how the transient worktree obtains the environment verify needs, or restrict baseline to verify cmds that run self-contained) before plan writing.

### [GAP] #592 carve-out ignores the second unconditional zero-commit rule
**Section:** Decision (#592)
**Issue:** Both templates state the zero-commit prohibition TWICE — once at the "never report success when HEAD equals the baseline" sentence (`:71`/`:65`) AND again at "`commit_sha` MUST be a real new content commit distinct from the housekeeping commit" (`fixer-holistic-brief.md:84`, `fixer-batch-brief.md:78`); the discussion only carves out the first, so the second still contradicts a legitimate nits-only zero-commit `success`.
**Fix:** Have the decision also address the `:84`/`:78` "MUST be a real new content commit" sentence, not just the baseline sentence.

### [GAP] Fixer cannot evaluate the "invoked with --nits-only" antecedent
**Section:** Decision (#592)
**Issue:** The carve-out is conditioned on "when the fix pass was invoked with `--nits-only`," but `millpy-fix.py`'s render token maps (`:319`, `:384`) inject no NITS_ONLY signal — the rendered brief is byte-identical for nits-only and full passes, so the fixer cannot verify the antecedent (only the runtime guard sees `--nits-only`).
**Fix:** Decide the mechanism — add a NITS_ONLY render token, or reword the carve-out to key off a fixer-visible condition ("pushed back on every finding, no code change required").

## Verdict

GAPS_FOUND
Core decisions are sound and well-grounded, but scope under-specifies four consistency/feasibility fixes.
MILL_REVIEW_END