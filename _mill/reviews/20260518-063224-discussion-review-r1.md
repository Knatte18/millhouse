All key claims verified against source. Writing the review now.

# Review: 65 (A) — Config-load og mill-go helse-sjekk etter config-migrasjon

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-18
```

## Findings

### [GAP] No test for hub_relative_path warning suppression
**Section:** § Testing
**Issue:** The testing section specifies 6 new tests covering `deep_merge` None-overlay, `resolve_plugin_template_path` fallback, and `load_config` bare-roles, but omits a test verifying that `hub_relative_path` present in `config.local.yaml` does NOT produce a `[config] unknown key` warning — the primary symptom stated in the Problem section.
**Fix:** Add `test_load_config_hub_relative_path_no_warning` to `test-config.py` and a parallel test to `test-review-common.py`: write a `config.local.yaml` containing `hub_relative_path: subdir`; call `load_config`; assert no warning is emitted to stderr.

### [NOTE] Technical context line numbers are stale
**Section:** § Technical Context → Key locations
**Issue:** `_config.deep_merge` is cited at line 240 but is actually at line 283; `_config.load_config` warn call is cited at line 212 but is at line 217.
**Fix:** Update the line references to match current source before plan writing.

### [NOTE] "Rejected" entry in hub_relative_path stripping decision is self-contradictory
**Section:** § Decisions → hub_relative_path stripping: where to strip
**Issue:** The Rejected line reads "Keeping `hub_relative_path` in the returned cfg unchanged and only suppressing the warning — this is exactly what we want." — the phrase "this is exactly what we want" under a "Rejected:" heading contradicts the intent.
**Fix:** Reword: the intended meaning is that the approach being rejected is *removing* `hub_relative_path` from the returned cfg, not keeping it; the prose should say "Rejected: also removing `hub_relative_path` from the returned cfg — no caller uses it post-load but the behavior change is unnecessary."

## Verdict

GAPS_FOUND  
Primary bug fix (hub_relative_path warning) has no regression test.