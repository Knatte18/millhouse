# Batch: mill-plan-self-validate-fixes

```yaml
task: Self-discovered mill-go/mill-plan skill-doc and behavior gaps
batch: mill-plan-self-validate-fixes
number: 1
cards: 1
verify: null
depends-on: []
```

## Batch Scope

Fixes two documentation-only bugs in `plugins/mill/skills/mill-plan/SKILL.md`'s Phase: Plan "Self-run the validator gate" paragraph (closes #759 and #753). This is the prose describing mill-plan's own direct call to `_plan_validate.run(...)`, which mirrors — but has no CLI to inherit flags from — the CLI-driven Step 1.5 gate in `millpy-review-plan.py`. Both fixes touch the same paragraph, so they are one card: splitting them into two sequential text-mutations of the same few lines would only add risk of a bad merge, not add safety. This batch has no runnable surface of its own: `_plan_validate.run`'s `skip_checks` behavior is already exercised at the function level by `test-plan-validate.py`, and the paragraph itself is interpreted by the orchestrating LLM at plan-write time, not executed by any test harness.

## Cards

### Card 1: Fix mill-plan's self-validate call — add missing import, correct undefined names, add wiki-config-mutation skip-check override

- **Context:**
  - `mill-config.yaml`
- **Edits:**
  - `plugins/mill/skills/mill-plan/SKILL.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:**

  Locate the paragraph that begins with the bolded phrase **"Self-run the validator gate"** in the `### Phase: Plan` section (currently the paragraph directly above the `signature: _status.read(status_path: Path) -> dict` line). This paragraph currently states the self-validate call inline as prose, using two names that are never bound anywhere else in this file: `wiki_root=wiki_root` (only `wiki_path` is bound, at Entry step 1) and `project_root` as the positional second argument (only `worktree_root` is bound, at Path Setup — the hub-root equivalent). It also passes `skip_checks=frozenset()` unconditionally, with no override mechanism, unlike the CLI-driven Step 1.5 gate's `--skip-check` flag.

  Rewrite the paragraph as follows — same content and rationale, but restructured into prose plus two fenced Python snippets (mirroring the `quote_scalar` example's fenced-snippet-with-import convention documented earlier in this same file, at the paragraph beginning "**YAML-quoted tokens for fenced blocks.**"):

  1. Keep the opening bold label **"Self-run the validator gate"** and the sentence explaining this mirrors `millpy-review-plan.py`'s own step-1.5 gate (same seven keyword arguments: `root`, `git_root`, `wiki_root`, `skip_checks`, `parent_branch`, `max_cards_per_batch`, `max_batch_context_tokens`), and that `git_root`/`wiki_path` are already bound at mill-plan's Entry step and `worktree_root` at Path Setup, so this needs no new path resolution. Keep the closing sentence "There is no 'or invoke the standalone CLI' fallback for this self-run — call `_plan_validate.run` directly."
  2. Immediately after, insert a fenced ` ```python ` block containing exactly:
     ```
     from _review_common import _load_root_from_overview

     skip_checks = frozenset()
     ```
  3. Immediately after that snippet, add a new paragraph labeled **"`wiki-config-mutation` skip-check override."** stating: if any batch's `Edits:`/`Creates:` includes `mill-config.yaml`, apply the same two-condition test as Step 1.5's `wiki-config-mutation` fix-table row before calling `_plan_validate.run`: (a) a bootstrap card is present in the plan explaining why the `mill-config.yaml` change is safe mid-flight; or (b) the modified keys are provably unused — zero grep hits across `scripts/` and `skills/` for key *removal or rename* only; a key *addition* whose consuming code ships in this same plan never satisfies (b), even with zero grep hits. If either condition holds, set `skip_checks = frozenset({"wiki-config-mutation"})` and record the justification in the plan commit message (see "Commit on the task branch" later in this same section). If neither condition holds, leave `skip_checks` as the empty frozenset from step 2 — let the check fire and halt per the `wiki-config-mutation` fix-table row instead.
  4. Immediately after that paragraph, insert a second fenced ` ```python ` block containing exactly (note the corrected `worktree_root` positional argument and `wiki_root=wiki_path` keyword, replacing the two undefined names):
     ```
     errors = _plan_validate.run(
         plan_dir,
         worktree_root,
         root=_load_root_from_overview(plan_dir / "00-overview.md"),
         git_root=git_root,
         wiki_root=wiki_path,
         skip_checks=skip_checks,
         parent_branch=<_parent_branch.resolve(status_path, interactive=False), falling back to None on any exception>,
         max_cards_per_batch=cfg.get("pipeline", {}).get("max_cards_per_batch", 10),
         max_batch_context_tokens=cfg.get("pipeline", {}).get("max_batch_context_tokens", 120000),
     )
     ```
  5. Close with the existing sentence "Fix any findings using the Step 1.5 fix table below, then re-run, before committing the plan."

  The `<_parent_branch.resolve(...)>` placeholder in step 4 is copied verbatim from the paragraph's current text — it is an existing LLM-computed-value placeholder convention already used elsewhere in this file (e.g. the "Verify command shape" section), not new syntax.

- **Commit:** `docs(mill-plan): fix self-validate import/undefined-names/skip-check override (#759, #753)`

## Batch Tests

No runnable surface: this batch edits only `SKILL.md` prose consumed by the orchestrating LLM at plan-write time. `_plan_validate.run`'s `skip_checks` behavior (the conditional logic this batch now documents) is already covered at the function level by `plugins/mill/unit_tests/test-plan-validate.py`; no new unit test is warranted for a prose-only fix to how mill-plan's self-run *documents* invoking that already-tested function.
