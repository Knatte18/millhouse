# Layer 02 discussion — Review Round 5

```yaml
round: 5
reviewer: independent-reviewer
date: 2026-04-20
verdict: APPROVE
```

---

## Methodology

Evaluated `discussion.md` (r4) against three criteria:
1. **Internal consistency** — does the document contradict itself?
2. **Implementability** — can a plan writer produce unambiguous cards from this text alone?
3. **Technical correctness** — regex patterns, Python snippets, import directions, `_render.py` contract.

Legacy specs were not consulted as normative sources. `_render.py` was read directly.

---

## Findings

### [NOTE] Section: Path resolution comment vs. code — minor wording inconsistency

**Issue:** The "Path resolution" section (just before Task flows) says paths are resolved via `_render.render()` on the config path templates. The Config contract section and decision #29 say `resolve_path()` uses plain `str.replace`, NOT `_render.render()`. The body of `resolve_path`'s docstring in the `_review_common.py` block is unambiguous (simple string replace). The prose sentence is the only outlier.

**Severity:** Low. A careful implementer will follow the docstring and the decisions log. A careless implementer could be confused.

**Suggested fix:** In the "Path resolution" section, replace:
> "Resolved via `_render.render()` on the config path templates, substituting uppercase `<SLUG>`"

with:
> "Resolved via `resolve_path()` (plain `str.replace`), substituting uppercase `<SLUG>` — NOT via `_render.render()` (see decision #29)."

---

### [NOTE] Section: Plan review task flow — `mill_dir` not in scope for `load_task_title`

**Issue:** In the plan-review task flow, `load_task_title(mill_dir, slug)` and `read_constraints_md()` are called without `mill_dir` or `project_root` being established in the pseudocode. The discussion review flow has the same implicit dependency. The code-review flow also calls `load_task_title(mill_dir, slug)` with `mill_dir` undeclared in that snippet.

The API-layer snippet (`mill-review-plan.py`) shows only `cfg` and `slug` being established before calling `_review_plan.run(cfg, slug)`. `mill_dir` is presumably passed via `cfg` or derived from the script's own `__file__` location, but this is never stated.

**Severity:** Mild. A plan writer would need to decide: does `run(cfg, slug)` also receive `mill_dir`? Is it derived inside the backend from a well-known path? The discussion never declares how `mill_dir` enters the backend functions.

**Suggested fix:** Add one sentence to the "Contracts between layers / API → Review backend" section stating how `mill_dir` (and `project_root` for `read_constraints_md`) reach the backend — e.g., "The API script passes `mill_dir = Path('.millhouse').resolve()` as a third argument to the backend `run()` function" or "Derived inside the backend via `Path(__file__).parent.parent.parent / '.millhouse'`."

---

### [NOTE] Section: Code review task flow — `round_n` used but not computed

**Issue:** The code-review task flow pseudocode uses `round_n` (passed to `render_prompt`) but omits the `discover_round` call that produces it. The discussion review and plan review flows both show it explicitly. The omission is a copy-incomplete issue, not a conceptual gap — `discover_round` is fully specified — but a plan writer copying from the code-review diagram verbatim would miss it.

**Suggested fix:** Insert `round_n = discover_round(reviews_dir, "code")` in the code-review task flow, after `reviews_dir` is resolved.

---

### Regex correctness check

`RE_SIMPLE` and `RE_BATCH` are valid Python `re` patterns. The priority rule (match `RE_SIMPLE` first, exclude from `RE_BATCH`) correctly handles the holistic-vs-batch disambiguation. The batch-filename constraint (`[a-z0-9-]+`) is consistent with the example filename `20260418-143300-plan-review-01-setup-r1.md`. No issues.

---

### `_render.py` contract compatibility

`_render.render(template_path, values)` takes a `Path` and a `dict`. `render_prompt` in `_review_common.py` wraps this by building the path from `__file__` and auto-uppercasing kwarg keys before passing them as the `values` dict. This is fully compatible: `_render.py`'s `values` dict uses bare token names (no angle brackets), which matches the auto-uppercased keys the wrapper produces. No circular imports. Import direction is correct.

---

### Edge cases — all addressed

| Edge case | Addressed? |
|---|---|
| Empty batch_files | Yes — skip parallel section, proceed to holistic |
| Zero slug found | Yes — `ReviewError`, exit 1, stderr message defined |
| Multiple slugs found | Yes — `ReviewError`, exit 1, stderr message defined |
| Round > max | Yes — exit 1, stderr |
| All sub-reviews fail | Yes — exit 1, empty stdout, stderr lists errors |
| ≥1 sub-review fails | Yes — exit 0, `verdict: ERROR` in entry, aggregate = `REQUEST_CHANGES` |
| Round 1 / reviews_dir absent | Yes — `discover_round` returns 1 if dir does not exist |
| Missing `task_title` field | Yes — `load_task_title` falls back to slug |
| Incompatible reviewer MODE | Yes — error message defined verbatim |

---

## Summary of issues

| # | Type | Severity | One-liner |
|---|---|---|---|
| 1 | NOTE | Low | Prose says `_render.render()` for path substitution; correct answer is `resolve_path()` (str.replace) |
| 2 | NOTE | Mild | `mill_dir` used in task-flow pseudocode but never declared as a parameter or derivation in any backend `run()` signature |
| 3 | NOTE | Low | Code-review task flow omits `discover_round` call for `round_n` |

No GAPs. No blockers. All three are notes — clarifications that would make implementation smoother but do not prevent a careful implementer from proceeding correctly.

---

## Verdict

**APPROVE**

The spec is internally consistent, technically correct, and implementable from this document alone. The three notes above are editorial polish, not blockers. A plan writer can produce unambiguous implementation cards for all three review types.
