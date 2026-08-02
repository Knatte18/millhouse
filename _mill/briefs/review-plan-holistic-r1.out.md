MILL_REVIEW_BEGIN
# Review: _plan_validate false positives block plan authoring — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: Claude (Sonnet 5, per env header claude-sonnet-5)
reviewed_file: plan/
date: 2026-08-02
```

## Findings

### [NIT] Card 3 cites a nonexistent anchor comment for the quote-indent-drift function insertion
**Location:** batch 01-fix-plan-validate-false-positives, Card 3
**Issue:** The instruction "Insert the remaining two functions directly after `test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break` and before the `# skip_checks filtering (Card 7 / #188)` section comment" is wrong for the function-DEFINITION insertion point — that comment appears exactly once in the file, only inside the later `main()` `tests = [...]` registration list (correctly cited in the card's final paragraph), not adjacent to the function definitions (the next def there is `test_skip_checks_filters_wiki_config_mutation`, with no preceding comment).
**Fix:** Drop the "before the `# skip_checks filtering...` comment" clause from the function-definition insertion instruction (the "directly after `..._tie_break`" anchor alone is correct and sufficient); keep it only for the `tests = [...]` registration-list paragraph where it is accurate.

## Verdict

APPROVE
Both fixes are byte-verified against current source and both new-test scenarios trace correctly under the fixed logic; only a minor doc-anchor slip found.
MILL_REVIEW_END
