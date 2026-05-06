# Review: 4 (A) — mill-setup: --from-url for separate wiki repo

```yaml
verdict: APPROVE
reviewer_model: sonnetmax_tool
reviewed_file: discussion.md @ mill-setup-wiki-url
date: 2026-05-06
```

## Findings

### [NOTE] Phase 3.2 "via regex" claim is wrong for new-file path
**Section:** Persistence write — Phase 3.2 location and yaml handling
**Issue:** The decision states "Phase 4.9 still updates hub_relative_path in place (existing behavior — already handles 'file exists' case via regex)." When Phase 3.2 creates the file via yaml.safe_load+dump, all comments are stripped — the template's `# hub_relative_path: .` line is gone. Phase 4.9 then finds no `hub_relative_path:` in the file and takes the prepend branch, not the regex branch. The description "via regex" is wrong; correct path is prepend. Functionally fine, but a plan writer who relies on the regex description may try to preserve the template comment in Phase 3.2 (e.g., text-append instead of yaml-roundtrip for the "add block" step), which would cause the commented substring to match Phase 4.9's `if 'hub_relative_path:' in text` check while the regex silently fails — leaving hub_relative_path unset and Phase 8 failing.
**Fix:** Clarify that Phase 3.2 uses yaml.safe_load + set + yaml.dump for both the "file does not exist" and "file exists" cases (comments intentionally lost); note that Phase 4.9 takes the prepend branch (not regex) when Phase 3.2 created the file.

## Verdict

APPROVE  
Design is complete and consistent; one NOTE on a wrong-but-harmless mechanism description that could trap a plan writer.