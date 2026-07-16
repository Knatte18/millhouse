MILL_REVIEW_BEGIN
# Review: Agent-mode dispatch: envelope fields and session/runtime state are unreliable

```yaml
verdict: GAPS_FOUND
reviewer_model: opushigh
reviewed_file: _mill/discussion.md
date: 2026-07-16
```

## Findings

### [GAP] reviewer_model override lands in reviewer-authored text
**Section:** Decisions -> reviewer_model / audit-trail accuracy
**Issue:** The review file is `raw_text` written verbatim (`_review_common.write_review_file` / `finalize_scope:1690-1693`), and `reviewer_model` is a prompt token the reviewer echoes into its own YAML block (`review-code-batch.md:53`, `_review_code.py:362`) -- finalize never writes that field, so `--actual-model` cannot simply "record" it and the claim it "falls back to today's config-derived value" misdescribes the current write path.
**Fix:** State how finalize overrides a value embedded in reviewer-authored `raw_text` (e.g. regex-rewrite the `reviewer_model:` line before `write_review_file`) and correct the fallback description to "reviewer-echoed value" not "config-derived."

### [GAP] Batch count contradicts enumeration
**Section:** Q&A log (batch organization) / Scope
**Issue:** The answer says "Four batches by fix surface" but enumerates only three (implement-prepare `#625/#626/#635/#643/#636`, effort/audit `#628/#633/#644`, permission allowlist `#631`); the "Why" separately hints at an isolated SKILL.md-only doc batch, leaving the fourth boundary undefined.
**Fix:** Either list the fourth batch explicitly (e.g. SKILL.md doc-only) or change the count to three so a plan writer can partition the work unambiguously.

### [NOTE] #631 permission-allowlist fix has no test strategy
**Section:** Testing
**Issue:** The Testing section names unit coverage for the other five fixes but nothing for the `.claude/settings.json` allowlist, and the concrete allow-pattern list is deferred to the `fewer-permission-prompts` skill scan at implement time -- so the batch has no stated verification and no fixed acceptance target.
**Fix:** Add a testing note for the settings.json change (schema/parse assertion or explicit "config-only, verified by manual scan") and state how completeness of the allowlist is judged.

## Verdict

GAPS_FOUND
Two gaps: reviewer_model override mechanism and the four-vs-three batch count must be resolved before planning.
MILL_REVIEW_END
