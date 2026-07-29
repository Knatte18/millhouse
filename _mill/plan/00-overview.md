# Plan: mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push

```yaml
task: "mill-plan/SKILL.md doc gaps: missing mill:conversation load, Phase: Plan commit step omits push"
slug: "mill-plan-skill-doc-gaps"
approved: false
started: "20260729-185355"
parent: "main"
root: ""
verify: null
```

## Batch Index

```yaml
batches:
  - number: 1
    name: skill-doc-gaps
    file: 01-skill-doc-gaps.md
    depends-on: []
    verify: null
```

## Shared Decisions

### Decision: SKILL.md em-dash prose stays as-is

- **Decision:** New/edited prose in `mill-plan/SKILL.md` and `mill-go/SKILL.md` may keep the existing em-dash-heavy style already used throughout both files.
- **Rationale:** CLAUDE.md's ASCII-only convention targets `print()`/`_log()` runtime output only, not SKILL.md prose (confirmed in `_mill/discussion.md`'s Constraints section). Matching existing file style avoids a jarring mid-document style deviation.
- **Applies to:** all batches (single batch in this plan)

## All Files Touched

- `plugins/mill/skills/mill-go/SKILL.md`
- `plugins/mill/skills/mill-plan/SKILL.md`
