# Review: codeguide sibling-mode + unified sibling-path convention — holistic r2

```yaml
verdict: APPROVE
reviewer_model: sonnet-4-6 (via Agent tool)
reviewed_file: specs/component/00-plan/
date: 2026-04-23
```

## Findings

### [NIT] `codeguide_commit.py` mode-detection is ambiguous
**Location:** Batch codeguide-plugin / Card 6
**Issue:** Card 6 says the helper should "call `resolve.py` (or directly import its logic) to determine mode," but `codeguide_commit.py`'s CLI only accepts `--file` and `-m` — it has no `--mode` or `--sibling-anchor` arg. The caller (`codeguide-update`) already holds the `resolve.py` result at that point; making the helper re-run resolution from cwd is fragile if cwd differs from the repo root.
**Fix:** Add `--mode inline|sibling` and `--sibling-anchor <path>` to the CLI args. The caller passes what it already knows; the helper trusts those args and never calls `resolve.py` itself.

### [NIT] `wiki/config.yaml` path never clarified for the implementer
**Location:** Batch mill-integration / Cards 10, 11, 12; overview "All Files Touched"
**Issue:** The plan consistently refers to `wiki/config.yaml` as if it is a path relative to the hub, but the file lives in the wiki repo (confirmed at `C:/Code/millhouse/wiki/config.yaml`). The `.millhouse/wiki` junction makes it reachable as `.millhouse/wiki/config.yaml` from hub root, but an implementer following the plan literally will not find `wiki/config.yaml` by path from cwd.
**Fix:** Add a one-line note to Card 12's "Reads" bullet: "Accessible as `.millhouse/wiki/config.yaml` from the hub root via the junction, or directly at `<container>/wiki/config.yaml`."

## Verdict

APPROVE
All three r1 BLOCKINGs are resolved; two minor NITs remain but do not block implementation.
