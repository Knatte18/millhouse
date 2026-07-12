MILL_REVIEW_BEGIN
# Review: Explore and adopt Claude Code fork-agents in mill orchestration — holistic

```yaml
verdict: REQUEST_CHANGES
reviewer_model: opushigh
reviewed_file: plan/
date: 2026-07-12
```

## Findings

### [BLOCKING] Batch 3 verify in overview contradicts the batch file
**Location:** `00-overview.md` Batch Index (batch 3) vs `03-prompt-surfaces.md` frontmatter + Batch Tests
**Issue:** The overview — declared "the authoritative DAG mill-go reads" — sets batch 3's verify to `test-agents-defs.py test-render.py`, while the batch file sets `test-agents-defs.py test-review-templates.py` and argues at length that `test-render.py` is worthless here (it renders only tempfile fixtures) and that card 18's new `test-review-templates.py` is the only gate on cards 15/16. As written, the gate that actually runs never executes the new file, and cards 15/16 ship uncovered.
**Fix:** Make the overview's batch-3 `verify:` byte-identical to `03-prompt-surfaces.md`'s: `... --only test-agents-defs.py test-review-templates.py`.

### [BLOCKING] Card 12 Context omits the three review backends it exercises
**Location:** Batch 2, card 12
**Issue:** Requirements name `_review_discussion.py:146-164`, `_review_code.py:547-559`, `_review_plan.py:568-575` and mandate running the **real** backend so its `except ReviewError -> return verdict "ERROR"` path is the thing under test — but `Context:` lists only the three CLIs plus `_agent_dispatch` / `_review_common` / `_review_cli`. The implementer may only read `Context:`/`Edits:` files, so the exact behaviour the card's most important assertions pin (exit 0 + ERROR envelope, not `print_error_envelope`) is unreadable without cold-start exploration.
**Fix:** Add `plugins/mill/scripts/_review_discussion.py`, `_review_code.py`, `_review_plan.py` to card 12's `Context:`.

### [NIT] Card 21 cross-references the wrong card
**Location:** Batch 4, card 21
**Issue:** It says "apply the same fix as card 19(b)" and "the fork guidance in card 19(a)"; the stale-rationale fix is card **20(b)** and the Explore fork guidance is card **20(a)**. Card 19(b) is mill-go's step-4(a) error-marker rewording — a different edit entirely.
**Fix:** Renumber both references to card 20(b) / 20(a).

### [NIT] Card 19(e) asserts config values with no config in Context
**Location:** Batch 4, card 19(e)
**Issue:** The "Why not fork?" prose must state `roles.fixer.model: haiku`, `roles.implementer.model: sonnethigh` and "discussion-review `opushigh`", but no config file is in `Context:`. The first two are correct in `plugins/mill/templates/mill-config.yaml`; the third conflates a reviewer **name** from `agents.yaml` with `roles.*.model` (only implementer / fixer / merge-in have a `model:` key) — the template ships `discussion-review.holistic.reviewer: sonnetmax`.
**Fix:** Add the config template to card 19's `Context:` and reword the third example to cite the reviewer's model tier resolved via `agents.yaml` + `model_to_tier`, not `roles.*.model`.

### [NIT] Deleting the template header strips the last Edit/git prohibition from the non-agent bulk prompt
**Location:** Batch 3, card 15(a) x Batch 1, card 3
**Issue:** `_TOOL_RULE_BULK` (frozen byte-identical by card 3) says only "Do NOT request tool calls" + "Do NOT use Write". Once the header's "MUST NOT call Edit, Write, Bash / MUST NOT make git commits" is deleted, a `--stage full` **bulk** reviewer is told nothing about Edit, Bash or commits. It is harmless only because `_llm_claude.py:80` maps bulk to an empty allowed-tools set, so the grant is zero by construction — but the plan never says so, and card 22's `--stage full` assertions will not catch it.
**Fix:** Record that mitigation in card 15 (or in the `--stage full` Shared Decision) so a later reader does not "restore" the prose into the shared template.

## Verdict

REQUEST_CHANGES
Two BLOCKING: batch-3 verify contradiction and card 12's missing backend Context.
MILL_REVIEW_END
