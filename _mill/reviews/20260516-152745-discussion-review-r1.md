# Review: 57 (A) — Move config.yaml and agents.yaml from wiki to hub worktree

```yaml
verdict: GAPS_FOUND
reviewer_model: sonnetmax_tool
reviewed_file: _mill/discussion.md
date: 2026-05-16
```

## Findings

### [GAP] Machine layer omitted from new overlay spec
**Section:** § Scope — "Three-layer overlay in `_config.load_config`..."
**Issue:** Both current implementations include `~/.millhouse/config.machine.yaml` via `_machine.load_layer()` between the wiki layer and the local layer (`_config.py:66`, `_review_common.py:1036`). The new spec says "Three-layer: plugin template → `mill-config.yaml` → `.millhouse/config.local.yaml`" — the machine layer is absent. The `plugins/mill/templates/config.machine.yaml` template still exists and is not slated for removal, so the feature is almost certainly not being dropped. The implementer cannot know whether to preserve the machine layer (and where in the new ordering) or remove it.
**Fix:** Add an explicit decision: either the new overlay is four layers (plugin template → mill-config.yaml → machine → local) or the machine layer is intentionally removed (with rationale). Update the § Scope bullet and the § Overlay Precedence decision accordingly.

---

### [NOTE] `autonomous_mode` "never in Python" claim is imprecise
**Section:** § Technical context — "autonomous_mode is unread"
**Issue:** The discussion states the key is "referenced only in SKILL.md prose, never in Python." `mill-autofix/SKILL.md:124` runs inline Python that **writes** `pipeline.autonomous_mode = True` to `config.local.yaml`; `mill-go/SKILL.md:232` reads it to gate stuck escalation. After this task the key is removed from the schema and will produce unknown-key warnings when mill-autofix sets it — the discussion does not describe this intermediate broken-warning state or that mill-autofix/mill-go still function (because validation only warns, not fails).
**Fix:** Clarify that SKILL.md inline Python counts as an active callsite, and note explicitly that the intermediate state (schema key absent, warning emitted, skills not yet migrated to flag-file) is intentional and functionally non-breaking because unknown-key validation is warn-only.

---

## Verdict

GAPS_FOUND  
The machine layer omission is a concrete implementation ambiguity that the plan writer cannot resolve without a stated decision.