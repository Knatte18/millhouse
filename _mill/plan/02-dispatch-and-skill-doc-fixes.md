# Batch: dispatch-and-skill-doc-fixes

```yaml
task: "Fix agent-mode dispatch gaps: HTML escaping, missing flags, timeouts, and stale skill content"
batch: "dispatch-and-skill-doc-fixes"
number: 2
cards: 3
verify: null
depends-on: []
```

## Batch Scope

Four documentation-only SKILL.md fixes, none touching executable code: #606 and #599 both land in mill-go's `## Agent-mode dispatch` step 6 (same section, bundled into one card since they're adjacent edits to the same paragraph); #598 adds a Step 0 to mill-start's `## Entry`; #596 adds a third anti-pattern item to `mill:workflow`'s `## Anti-patterns`. No shared context between the three cards' target files — each is independent. `verify: null` per the Shared Decision `documentation-only edits carry no test surface` in the overview.

## Cards

### Card 5: Document `--review-file` re-pass and extended finalize timeout in mill-go's Agent-mode dispatch

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Agent-mode dispatch`, step 6 ("Run finalize stage"), immediately after the existing paragraph that ends "...for review CLIs, pass `--round <round>`.", insert a new paragraph covering both #606 and #599:
  - #606: state explicitly that for `millpy-fix.py`, "the same standard arguments" means re-passing `--scope`, `--batch-name` (batch scope only), and `--review-file <path>` exactly as given to the prepare-stage call — `millpy-fix.py` requires `--review-file` unconditionally at every `--stage`, not just `prepare` (its argparse validates `--review-file is None` before branching on `--stage`).
  - #599: state that `millpy-fix.py --stage finalize` calls should be given an extended Bash-tool timeout — recommend 600000ms (10 minutes) — because finalize replays every batch's `verify:` command sequentially as a regression guard, which can exceed the default 2-minute Bash tool timeout on plans with several slow verify suites. Scope this note to fix-CLI finalize calls specifically (both `--nits-only` and full fix, both batch and holistic scope); review-CLI finalize calls don't run verify commands and aren't affected.
  Do not change the CLI invocation examples elsewhere in the file (e.g. lines 378, 393, 680, 696) — those already say `<args> = --scope batch --batch-name <batch_name> --review-file <review-file-abs-path> --round <N>` for the prepare-stage dispatch; the new note only clarifies what step 6's generic "same standard arguments" phrase means when the CLI is `millpy-fix.py`.
- **Commit:** `docs(mill-go): document review-file re-pass and extended timeout for fix-CLI finalize`

### Card 6: Force-load `mill:conversation` at mill-start Entry

- **Context:**
  - `plugins/mill/skills/mill-go/SKILL.md`
- **Edits:**
  - `plugins/mill/skills/mill-start/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In mill-start's `## Entry` section, insert a new "Step 0" before the existing "1. Resolve the wiki path via..." step, mirroring mill-go's `## Entry` "**Step 0: Verify `CLAUDE_PLUGIN_ROOT`.**" precedent in structure (bold step label, then instruction). The new Step 0 must: load the `mill:conversation` skill via the Skill tool, unconditionally, immediately, before any other Entry step or phase; state why — every operator-facing prompt in Phase: Discuss and Phase: Discussion Review depends on `mill:conversation`'s numbered-options rule (banning `AskUserQuestion`) being active. Renumber the existing three steps are untouched in content but now follow Step 0 (they may remain "1.", "2.", "3." — only a new "Step 0" is prepended, matching mill-go's own Step 0 + Step 1 numbering pattern where Step 0 is not part of the "1., 2., 3." sequence).
- **Commit:** `docs(mill-start): force-load mill:conversation at Entry Step 0`

### Card 7: Add Skill-tool same-session freshness anti-pattern to mill:workflow

- **Context:** none
- **Edits:**
  - `plugins/mill/skills/workflow/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In `## Anti-patterns`, add a third numbered item after the existing two (currently ending with "*Reason preserved from incident #19.*"). The new item states: if any prior step in the current session edited a `SKILL.md` file (via `Edit`/`Write` on any `plugins/*/skills/**/SKILL.md`), do not trust the Skill tool's served content for that skill for the rest of the session — `Read` the file directly to get the current on-disk content before following its instructions. Name the concrete trigger scenario: a batch inside a `mill-go` run edits a `SKILL.md` (e.g. `mill-finalize`, `git-pr`, `mill-merge`, `mill-cleanup`), and a later step in the *same* run invokes that skill via the Skill tool — the Skill tool can serve stale pre-edit content in that case. Follow the existing two items' style, including a closing italicized incident-reference line (e.g. "*Reason preserved from incident #596.*").
- **Commit:** `docs(workflow): add Skill-tool same-session freshness anti-pattern`

## Batch Tests

`verify: null` — all three cards are SKILL.md prose edits with no executable surface (see Shared Decision `documentation-only edits carry no test surface` in the overview). Verification is manual: re-read each edited section and confirm it accurately reflects the corresponding CLI's actual flag/behavior requirements (already cross-checked against source during discussion/planning).
