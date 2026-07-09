# Batch: implementer-brief-and-config-hardening

```yaml
task: Fix nit-enforcement gate marker gaps, NIT-dispatch wording, implementer liveness probe, and Haiku false-completion
batch: implementer-brief-and-config-hardening
number: 3
cards: 2
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-config.py
depends-on: []
```

## Batch Scope

Both halves of #616's remaining scope (the config-default half is already fixed — `roles.implementer.model` already resolves to `sonnethigh`, confirmed via `_config.load_config` and `git log` on the template, commit `410f8053`, 2026-06-23). This batch: (1) hardens `implementer-brief.md`'s final-report contract so the implementer's free-text chat summary states an honest card-count instead of an unqualified completion claim, independent of model tier; (2) adds a regression test locking the template's `roles.implementer.model` away from `haiku`, since it has already flip-flopped between `haiku` and `sonnethigh` twice in this file's git history. No dependency on batches 1/2 — different files (`implementer-brief.md`, `test-config.py`), no shared context.

## Cards

### Card 10: Add a card-count self-check to the implementer's free-text summary (#616)

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** In the `## Report` section, locate the existing "**Pre-report self-check (mandatory before emitting success JSON):**" paragraph. Its exact current text is:

  > **Pre-report self-check (mandatory before emitting success JSON):** Run `git -C <PROJECT_ROOT> status --porcelain --untracked-files=no`. If it shows ANY tracked in-scope modification, commit it via the `git-commit` skill (or report `stuck_type: logic`) -- never report `success` with an uncommitted tracked change. The finalize gate now mechanically rejects a success report when in-scope files are dirty, so an uncommitted change will demote your report to stuck regardless.

  Insert a new paragraph immediately after it (before the "Your last line of output (after all work and commits) MUST be a single JSON object:" sentence that follows):

  > **Card-count self-check (mandatory before writing your free-text turn summary):** Before stating anything about completion in your prose summary to the Builder/operator, count how many cards you actually committed versus how many the batch file declares. Determine the range start exactly as in "Resume-after-incomplete" above: use `<START_SHA>` when non-empty, else `git -C <PROJECT_ROOT> log --grep="^mill-go: start batch" -n 1 --format=%H`. Run `git -C <PROJECT_ROOT> log <range-start>..HEAD --oneline` and match commit subjects against the batch file's `## Cards` `Commit:` messages to get an exact count. Your free-text summary MUST state the real count honestly (e.g. "4 of 9 cards committed") — never write an unqualified "all complete"/"all done" claim without having actually verified the count this way. This applies regardless of which model is running this session: this check is what protects an operator who is only reading your chat summary from a false completion claim, independent of whatever the machine-readable JSON status line below says.

  Reuse the exact `<START_SHA>` / `--grep` fallback logic already described in this same file's "Resume-after-incomplete" paragraph (~line 52) — do not invent a different way to find the batch-start commit (per the overview's Shared Decision "reuse the existing START_SHA / `--grep` fallback for any new commit-range computation").
- **Commit:** `docs(implementer-brief): add card-count self-check to final report (#616)`

### Card 11: Regression test for the implementer model default (#616)

- **Context:**
  - `plugins/mill/templates/mill-config.yaml`
- **Edits:**
  - `plugins/mill/unit_tests/test-config.py`
- **Creates:** none
- **Deletes:** none
- **Moves:** none
- **Requirements:** This file already defines `HUB = Path(__file__).resolve().parent.parent.parent.parent` (~line 26) and imports `yaml` (~line 30). This card's test must read the REAL shipped template — not the synthetic fixture built by `_setup_plugin_template` used elsewhere in this file (that fixture tests `_config.load_config`'s merge logic, not the actual template's shipped defaults, and must not be modified). Add a new top-level test function `test_real_template_implementer_model_not_weak_tier` (placed after `test_load_config_no_hub_overlay_returns_template`, ~line 721) that:
  1. Resolves `template_path = HUB / "plugins" / "mill" / "templates" / "mill-config.yaml"`.
  2. Loads it directly: `real_cfg = yaml.safe_load(template_path.read_text(encoding="utf-8"))`.
  3. Defines `allowed_tiers = {"sonnet", "sonnethigh", "sonnetmax", "opus", "opushigh"}` (all confirmed present as entries in `plugins/mill/templates/mill-agents.yaml`).
  4. Asserts `real_cfg.get("roles", {}).get("implementer", {}).get("model") in allowed_tiers`, with a failure message that includes the actual value read.
  5. Prints `"PASS: real template -- roles.implementer.model is not a weak tier"` on success, following this file's existing print-on-pass convention (e.g. `test_load_config_no_hub_overlay_returns_template`'s trailing `print(...)` line).

  This test must NOT use `_config.load_config` or any of the `resolve_plugin_template_path` mocking machinery used by the rest of this file — it asserts on the actual on-disk template file directly, so a future edit to the real `mill-config.yaml` template (not a test fixture) is what this test catches.
- **Commit:** `test(config): guard implementer model default against regressing to a weak tier (#616)`

## Batch Tests

`verify:` runs `test-config.py` via `run-all.py --only test-config.py`, covering the new `test_real_template_implementer_model_not_weak_tier` test (card 11) alongside the file's existing `load_config`/`deep_merge` suite, confirming this batch does not disturb any existing config-loading test. Card 10 (`implementer-brief.md`) is a prompt template with no runnable surface — its correctness is established by the exact insertion text specified above and by review, not by `run-all.py` (mirrors the overview's Shared Decision on SKILL.md prose, applied here to a template file for the same reason: no Python entry point executes it as code).
