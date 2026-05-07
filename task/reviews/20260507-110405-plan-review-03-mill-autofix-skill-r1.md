# Review: 16 (A) — Autonomous bug-fix pipeline (mill-autofix) — 03-mill-autofix-skill

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 03-mill-autofix-skill
date: 2026-05-07
```

## Findings

### [BLOCKING] `_autofix.py` absent from Card 8 Context
**Step:** Card 8 Context list
**Issue:** Requirements directly names `_autofix.slug_from_title(title, existing_home_slugs, issue_number)` from `_autofix.py`, but the file does not appear in Context. The implementer writing the SKILL.md may only read listed context files; `_autofix.py` is the source of truth for the invocation pattern even though the signature is sketched in Shared Decisions.
**Fix:** Add `plugins/mill/scripts/_autofix.py` to Card 8 Context. (The file will exist on disk by the time Batch 3 executes, because Batch 3 depends on Batch 1.)

### [NIT] Creates target repeated in Context
**Step:** Card 8 Context / Creates
**Issue:** `plugins/mill/skills/mill-autofix/SKILL.md` appears under both Context and Creates. Creates targets do not exist when the card runs; listing one in Context tells the implementer to read a file that will not be there.
**Fix:** Remove `plugins/mill/skills/mill-autofix/SKILL.md` from the Context list; keep it only in Creates.

### [NIT] Phase count off by one in Batch Scope
**Step:** Batch Scope paragraph, first sentence
**Issue:** "all five phases … Entry, Fetch, Pre-flight, Per-bug loop, Cleanup, Report" lists six phases.
**Fix:** Replace "five" with "six".

### [NIT] `_wiki.read_home_slugs` does not exist and is not being added
**Step:** Card 8 Requirements item (d)
**Issue:** The requirement says "parse via `_wiki.read_home_slugs` or equivalent", but `_wiki.py` has no such function and `_wiki.py` is absent from the All Files Touched list, meaning it will never be added.
**Fix:** Drop the named-function reference; replace with concrete guidance — e.g., "iterate `_TASK_HEADING_RE.finditer(home_text)` as shown in `millpy-add.py`'s `_slug_already_present`, collecting group(1) into a set".

## Verdict

REQUEST_CHANGES
One blocking context omission; three low-severity NITs.