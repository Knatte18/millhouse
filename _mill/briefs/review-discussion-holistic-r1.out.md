MILL_REVIEW_BEGIN
# Review: mill-plan: Phase Plan Review's 4b/4c/4d re-validate gate says "7 kwargs", drops done_gate

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnethigh
reviewer_self_id: claude-sonnet-5
reviewed_file: /home/knatte/Code/millhouse/wts/mill-plan-done-gate-kwargs-count-drift/_mill/discussion.md
date: 2026-09-19
```

## Findings

### [BLOCKING:consistency] Testing section's "or true" verify: option contradicts actual enforcement
**Section:** `## Testing` **Issue:** Discussion offers bare `true` as a candidate `verify:` value for the doc-only batch, but `_plan_validate.py`'s `_check_verify_not_isolated` flags any non-`None` command lacking a `PYTHONPATH=` prefix whenever `_is_python_project()` is true — and this repo satisfies that via `plugins/mill/pyproject.toml`, so bare `true` fails, and CLAUDE.md's own convention mandates `PYTHONPATH= ` (literal, empty value) not bare `true`. **Fix:** State directly that the batch either omits `verify:` entirely (command=None, no check fires) or uses `PYTHONPATH= true`, not bare `true` — do not defer this to plan-writing time when the source already answers it.

### [NIT:consistency] Testing section's grep-count claim is arithmetically self-contradictory
**Section:** `## Testing`, bullet 2 **Issue:** "one more occurrence than before the fix (three new `done_gate` mentions added, one per site)" — adding three mentions is +3 occurrences, not +1; also unrelated pre-existing `done_gate` mentions already exist at lines 240-242 outside the four kwarg-enumeration sites, so "four sites" undercounts total file occurrences. **Fix:** Restate as "+3 occurrences (one new `done_gate` mention per corrected site)" and scope the count to the kwarg-enumeration sites only, not total file occurrences.

### [NIT:consistency] Decision's "verbatim" claim about line 251 doesn't match line 251's actual text
**Section:** `### Decision: Align 4b/4c/4d prose...` **Issue:** The decision states the target list matches line 251 "verbatim," including `skip_checks=plan_skip_checks`, but line 251 (confirmed by direct read) reads plain `skip_checks`, no `=plan_skip_checks` — that binding is Plan Review's own persisted-frontmatter variable (Path Setup, Plan Review), correctly reused in 4b/4c/4d's *existing* text, just not present in line 251 itself. **Fix:** Drop "verbatim" or clarify the decision preserves 4b/4c/4d's own existing `skip_checks=plan_skip_checks` naming (correct, since it's Plan Review's bound variable) while borrowing only the kwarg *set* and `done_gate`'s value expression from line 251/282.

## Verdict

REQUEST_CHANGES
Verify-command guidance contradicts actual validator enforcement; resolve before plan writing.
MILL_REVIEW_END
