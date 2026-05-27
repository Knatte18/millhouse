# Batch: safe-rmtree-chmod-retry

```yaml
task: V3 wiki adoption follow-up bugs
batch: safe-rmtree-chmod-retry
number: 3
cards: 3
verify: PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: [1]
```

## Batch Scope

Fixes `_safe_rmtree.safe_rmtree` so it can delete read-only files (git pack `.idx`/`.pack`) on Windows, and converts the three allowlisted test files (`test-wiki-daemon.py`, `test-wiki-store.py`, `test-wiki-sync.py`) to use `safe_rmtree` instead of bare `shutil.rmtree`. After conversion, removes those three files from the `ALLOWED_FILES` allowlist in `test-no-direct-rmtree.py`. Adds a regression test in `test-safe-rmtree.py` exercising the read-only path. Depends on Batch 1 because both batches edit `test-wiki-daemon.py`; the dependency lets Card 9 convert the rmtree call in the new test cases Batch 1 added.

External interface: `safe_rmtree(path, *, allowed_root, ignore_errors=False)` signature unchanged. Internal behaviour: failures on read-only files are now retried with the read-only bit cleared.

Batch-local decisions:

- Use a closure (`_readonly_handler`) defined inside `safe_rmtree`, capturing the outer `ignore_errors` variable. No module-level handler — the handler must see the call-site's `ignore_errors`, and closure capture is the cheapest implementation.
- Use `sys.version_info >= (3, 12)` to switch between `onexc` (3.12+) and `onerror` (3.11 and earlier). `onerror`'s 3-tuple signature `(func, path, exc_info)` differs from `onexc`'s `(func, path, exc)` — adapt with a wrapper.
- The chmod target is `stat.S_IWRITE` (clears the Windows read-only bit). The discussion considered `0o777` but settled on `stat.S_IWRITE` because it is the conventional value for this case and over-broad chmods on POSIX are gratuitous.

## Cards

### Card 8: Add chmod+retry handler to _safe_rmtree.safe_rmtree and update its kwargs test

- **Context:**
  - `plugins/mill/scripts/_junction.py`
  - `plugins/mill/scripts/_paths.py`
- **Edits:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/unit_tests/test-safe-rmtree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - At the top of `_safe_rmtree.py`, add `import stat` to the existing import block.
  - Inside `safe_rmtree` (`_safe_rmtree.py:69`), replace the existing `shutil.rmtree` call block (`_safe_rmtree.py:138-142`):
    ```python
    try:
        shutil.rmtree(str(original), ignore_errors=ignore_errors)
    except OSError:
        if not ignore_errors:
            raise
    ```
    with: define a nested `_readonly_handler(func, path, exc)` closure that does `try: os.chmod(path, stat.S_IWRITE); func(path)` and on `OSError` re-raises iff `not ignore_errors`. Then call `shutil.rmtree(str(original), onexc=_readonly_handler)` on Python 3.12+ and `shutil.rmtree(str(original), onerror=lambda func, path, exc_info: _readonly_handler(func, path, exc_info[1]))` on older Pythons. Wrap the rmtree call in `try: ... except OSError: if not ignore_errors: raise` so the outer `ignore_errors=True` contract is preserved even when the handler itself raises.
  - Use `sys.version_info >= (3, 12)` for the branch.
  - Update the function's docstring's "Step 8: rmtree with defense-in-depth for ignore_errors." comment to note the chmod+retry behaviour: "Step 8: rmtree with chmod+retry for read-only files (e.g. git pack idx/pack on Windows) and defense-in-depth for ignore_errors."
  - In `test-safe-rmtree.py`, replace the existing `# --- ignore_errors passes through to shutil.rmtree ---` test block (`test-safe-rmtree.py:261-282`). The prior block asserted that the `ignore_errors=` kwarg was forwarded directly to `shutil.rmtree`; after the prod change, `safe_rmtree` no longer passes `ignore_errors=` to `shutil.rmtree` (it uses `onexc` / `onerror` plus an outer `try/except OSError` to honour the `ignore_errors=True` contract). Rewrite the test as `# --- ignore_errors contract honoured via outer try/except ---`: still `patch("_safe_rmtree.shutil.rmtree", mock)` and call `safe_rmtree(scratch, allowed_root=scratch, ignore_errors=True)`; assert `mock.assert_called_once()`; assert that the call kwargs contain `"onexc"` if `sys.version_info >= (3, 12)` else `"onerror"` (whichever applies on the running interpreter); do NOT assert anything about `ignore_errors` being in the kwargs. Then in the `ignore_errors=False` branch, also patch `shutil.rmtree` and verify the same kwarg-name presence. Keep the existing `# --- ignore_errors=True swallows OSError from rmtree ---` test block at line 242 unchanged — it exercises the outer try/except contract end-to-end (it patches `shutil.rmtree` to raise `OSError` and expects `ignore_errors=True` to swallow, `ignore_errors=False` to propagate). That block must still pass after the prod change because the outer wrapper is exactly what preserves the contract.
- **Commit:** `fix(safe-rmtree): chmod+retry read-only files instead of silently leaving them (#366)`

### Card 9: Convert shutil.rmtree calls in wiki test files to safe_rmtree

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-wiki-daemon.py`
  - `plugins/mill/unit_tests/test-wiki-store.py`
  - `plugins/mill/unit_tests/test-wiki-sync.py`
  - `plugins/mill/unit_tests/test-no-direct-rmtree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - In `test-wiki-daemon.py`, `test-wiki-store.py`, and `test-wiki-sync.py`: replace every `shutil.rmtree(<var>, ignore_errors=True)` call with `_safe_rmtree.safe_rmtree(<var>, allowed_root=<var>, ignore_errors=True)`. The `<var>` varies per file (`tmp` in test-wiki-daemon, `tmp_dir` in test-wiki-store, `tmp` in test-wiki-sync) — preserve the original variable name in each replacement. The `allowed_root=<var>` argument deliberately mirrors `<var>` because the tests create their own tempdir as both the deletion target and its containment scope.
  - In each of the three files, add `import _safe_rmtree` immediately after the existing `sys.path.insert(0, str(HUB / "plugins" / "mill" / "scripts"))` line (or wherever the other `import _foo` mill-script imports live in that file). In all three files the `import shutil` statements appear ONLY as inline imports immediately above each `shutil.rmtree(...)` call (no top-level `import shutil`); after converting every callsite, remove the inline `import shutil` lines as well — `shutil` is not used elsewhere in any of the three files. Verify after editing that no `shutil.rmtree` call remains in any of the three files (`grep -n "shutil\.rmtree" <file>` returns no matches) AND no `import shutil` remains.
  - In `test-no-direct-rmtree.py`, remove the three entries `"plugins/mill/unit_tests/test-wiki-daemon.py"`, `"plugins/mill/unit_tests/test-wiki-store.py"`, `"plugins/mill/unit_tests/test-wiki-sync.py"` from the `ALLOWED_FILES` set. Leave the remaining entries unchanged. The `missing_whitelist` guard inside `test-no-direct-rmtree.py`'s `main()` will fail if any kept entry is missing on disk — manually verify each kept entry still resolves before committing.
- **Commit:** `refactor(tests): route wiki test rmtree through safe_rmtree and shrink allowlist (#366)`

### Card 10: Add regression test for safe_rmtree chmod+retry on read-only files

- **Context:**
  - `plugins/mill/scripts/_safe_rmtree.py`
  - `plugins/mill/scripts/_junction.py`
- **Edits:**
  - `plugins/mill/unit_tests/test-safe-rmtree.py`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  - Append a new test case to `test-safe-rmtree.py`'s `main()` using the existing `try/except` + `ok()` / `fail()` pattern. The case is labelled `safe_rmtree removes read-only files via chmod+retry`.
  - Setup: create `tmp = Path(tempfile.mkdtemp())`. Create `tmp / "sub"` directory. Create `tmp / "sub" / "readonly.idx"` file with `tmp.write_bytes(b"x")` semantics (use `(tmp / "sub" / "readonly.idx").write_bytes(b"x")`). Then `os.chmod(str(tmp / "sub" / "readonly.idx"), 0)` to clear all permission bits (mimics the Windows read-only git pack file).
  - Action: `safe_rmtree(tmp, allowed_root=tmp, ignore_errors=False)`. The call must succeed without raising.
  - Assertion: `assert not tmp.exists()` after the call — the entire tree must be gone.
  - Cleanup: wrap the test body in a `try/finally` that re-runs `safe_rmtree(tmp, allowed_root=tmp, ignore_errors=True)` for safety if the assertion fails. The handler must restore permissions itself if the test passes, so finally-cleanup is only a defensive net.
  - On POSIX the existing rmtree already handles `chmod(0)` files because `chmod 0` does not prevent unlinking on Linux when the parent dir has write+execute. The test is meaningful primarily on Windows; treat a POSIX pass as also exercising the version-branched `onexc`/`onerror` call site without exercising the read-only-bit path. Do NOT skip the test on POSIX — the closure path still executes.
- **Commit:** `test(safe-rmtree): cover chmod+retry path for read-only files (#366)`

## Batch Tests

Batch-level `verify:` runs the full unit-test suite. The `test-no-direct-rmtree.py` gate is the most sensitive — Card 9's allowlist shrink will fail that gate if any of the three converted files still has a `shutil.rmtree` callsite. The new regression case in Card 10 must pass on both Windows (real read-only-bit behaviour) and POSIX (closure path exercised, no read-only effect). The full `run-all.py` covers everything.
