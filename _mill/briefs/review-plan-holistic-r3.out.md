MILL_REVIEW_BEGIN
# Review: _config.py / _treeguard.py: silently-ignored config keys and unguarded str-vs-Path args — holistic

```yaml
verdict: APPROVE
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: plan/
date: 2026-09-19
```

## Findings

### [NIT:consistency] Card 1 cites a mismatched test fixture as its mirror pattern
**Location:** Batch 01-config-treeguard-guards, Card 1 (test-config.py additions)
**Issue:** The card tells the implementer to mirror `test_worktree_template_augments_template_cfg` (test-config.py:867-931) for the "local template with a `pipeline:` key + patch `resolve_plugin_template_path`" shape, but that test exercises a different mechanism entirely — the two-template cache/worktree-augmentation merge loop in `_config.load_config` (lines 250-266 of `_config.py`), requiring a separate `cache_templates` dir, a `wt_root/plugins/mill/templates/mill-config.yaml`, and a hub `mill-config.yaml`. The much closer existing precedent for "one local template with a `pipeline:` key, patched directly via `resolve_plugin_template_path`'s `return_value=`" is `test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning` (test-config.py:1389-1438), which is structurally identical to what Card 1's two new tests need.
**Fix:** Point the card's precedent citation at `test_pipeline_autonomous_mode_does_not_trigger_unknown_key_warning` instead of `test_worktree_template_augments_template_cfg`, to avoid nudging the implementer toward the unrelated, more complex augmentation-loop fixture shape.

## Verdict

APPROVE — both fixes are source-verified, decision-aligned, and test-complete; one non-blocking exemplar-citation mismatch noted.
MILL_REVIEW_END
