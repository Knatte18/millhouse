# Review: script-invocation-hygiene — Scripts: cwd not git-root, plugin cache not source repo — 02-simple-fixes

```yaml
verdict: REQUEST_CHANGES
reviewer_model: sonnetmax
reviewed_file: 02-simple-fixes
date: 2026-05-04
```

## Findings

### [BLOCKING] Card 5 omits resolve_hub_path from test stubs
**Step:** Card 5 — Fix millpy-claim.py cwd swaps
**Issue:** `test_smoke_import` uses `types.ModuleType("_paths")` and manually sets only the five symbols the current import line needs; adding `resolve_hub_path` to the `from _paths import ...` line causes `ImportError` at `spec.loader.exec_module` time because the stub has no `resolve_hub_path` attribute. Separately, `_make_stub_map` uses `MagicMock()` which auto-creates `resolve_hub_path` but its return value is `MagicMock()`, not a `Path`; `mill_dir = resolve_hub_path() / ".millhouse"` becomes a chained MagicMock, and `test_main_happy_path_calls_spawn_core_helpers` immediately fails its `rac_call.args[1] != expected_mill_dir` assertion.
**Fix:** Card 5 requirements must include: (a) add `paths_mod.resolve_hub_path = MagicMock(return_value=Path("/fake/repo"))` to the explicit attribute block in `test_smoke_import`; (b) add the same line to `_make_stub_map` so all harness-built tests see a real Path return value.

### [BLOCKING] Card 6 omits resolve_hub_path patch in existing color tests
**Step:** Card 6 — Fix millpy-color.py cwd swaps
**Issue:** The existing test writes `_write_settings(repo / ".vscode" / "settings.json", ...)` and patches only `mill_color.resolve_git_root`. After Card 6's change, `settings_path = resolve_hub_path() / ".vscode" / "settings.json"` calls the real `Path.cwd()`, which is not `repo`. `_read_existing_window_title(settings_path)` returns `None` (file absent at cwd), so window_title is derived from the config/slug fallback path, and the `window_title == "MY: existing-title"` assertion fails.
**Fix:** Card 6 requirements must include patching `mill_color.resolve_hub_path` to return `repo` in the existing "purple preserves title" test (and setting it to `repo` in any other existing test that writes files relative to the repo path).

## Verdict

REQUEST_CHANGES — two tests fail after batch implementation as written; stub updates required before approval.