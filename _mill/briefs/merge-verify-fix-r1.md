# Verify-Fix Brief

The verify command `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py test-brief-commit.py test-orch-review-scratch-path.py` failed after a merge.
Your job is to diagnose the failures and fix the code so the verify command passes.

## Verify Output

```
--- Card 3: orch-review .scratch/ path regression lock ---
Testing orch-review/orch-wait .scratch/orch-review.md path...
PASS: orch-review/SKILL.md and orch-wait/SKILL.md reference .scratch/orch-review.md with no stale _mill/orch-review.md references
All test-orch-review-scratch-path checks passed.
--- Card 5: Brief-commit regression lock ---
Testing mill-start brief commits...
PASS: mill-start SKILL.md references _mill/briefs/ in all required commit steps
Testing mill-merge-in brief commits...
FAIL: mill-merge-in/SKILL.md: _mill/briefs/ is present but not in an add command context
FAIL: 1 mill-merge-in brief-commit check(s) failed
PASS: build_wait_command contains the ready-phase grep pipeline
PASS: build_wait_command pipes every status_path grep through tr -d '\r'
PASS: build_wait_command renders the giveup_s timeout comparison
PASS: build_wait_command renders the poll_interval_s sleep/accumulate lines
PASS: build_wait_command emits exactly one echo/exit pair per outcome, no BLOCKED branch
PASS: build_wait_command double-quotes a status_path containing spaces
PASS: build_wait_command anchors the ready-phase grep pattern with a trailing $
PASS: matches_wait_trigger matches an exact-set member
PASS: matches_wait_trigger matches both regex patterns via full-match
PASS: matches_wait_trigger rejects non-matching phases
PASS: matches_wait_trigger matches with an empty regex list
PASS: matches_wait_trigger does not accidentally match mill-start's mid-loop phase value against a narrower trigger set
PASS: build_wait_command's tr -d '\r' pipe makes the trailing-$ anchor match a CRLF-terminated status.md line end-to-end
PASS: matches_wait_trigger matches all six widened Entry-gate phase values
PASS: matches_wait_trigger rejects non-matching phases and the unsuffixed 'approved' near-miss against the widened set
PASS: matches_wait_trigger matches the Entry-gate wait's widened discussion-fix-rN/discussion-gap-fix-rN patterns without accidentally matching a near-miss string
All _phase_wait unit tests passed.
Running 3 tests across 12 worker(s).
--- PASS test-orch-review-scratch-path.py (0.0s) ---
--- FAIL test-brief-commit.py (0.0s) ---
--- PASS test-phase-wait.py (0.0s) ---

Slowest 10:
     0.0s  test-phase-wait.py
     0.0s  test-brief-commit.py
     0.0s  test-orch-review-scratch-path.py

FAIL -- 1 of 3 in 0.0s: ['test-brief-commit.py']
```

## Merge Diff

```diff
diff --git a/CLAUDE.md b/CLAUDE.md
index 8982496c..2cfade8e 100644
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ -56,6 +56,8 @@ _mill/   ← status.md, discussion.md, plan/, reviews/
   reading stale cache content during plan-writing has previously produced an incorrect conclusion requiring mid-plan rework. `${CLAUDE_PLUGIN_ROOT}` remains correct for script invocation — this bullet narrows only the source-code-verification case, it does not revise the bullet above it.
 - **Working state never goes to wiki.** `_mill/` lives on the task branch.
   Wiki holds only `Home.md`.
+- **Never cite `_mill/discussion.md` (or any other `_mill/`-rooted path) from a permanent doc.**
+  A permanent/roadmap doc (e.g. a wiki Done entry or a module doc) that links to `_mill/discussion.md` is unsafe: `_mill/` is deleted or restored-from-base at merge time (`mill-finalize` Step 3 / `mill-merge` Step 4's cleanup commit), so the file no longer exists on the parent branch once the task merges.
 - **Fold only into unclaimed backlog tasks** (`status is None AND not deferred`).
   Claimed, terminal, blocked, or deferred tasks reject fold-ins — guard inlined in `millpy-fold.py` and the two fold SKILLs.
 
diff --git a/plugins/codeguide/scripts/resolve_scope.py b/plugins/codeguide/scripts/resolve_scope.py
index b9a22b4c..7d67863b 100644
--- a/plugins/codeguide/scripts/resolve_scope.py
+++ b/plugins/codeguide/scripts/resolve_scope.py
@@ -12,8 +12,8 @@ Scope-resolution chain
     --verify --quiet <token>^{commit}`` (a literal trailing ``..HEAD`` suffix is stripped before the
     check) uses ``git diff --name-only <resolved>..HEAD``.
     This subsumes hex SHAs, ``HEAD``, ``HEAD~N``, and branch/tag names.
-4. **Explicit paths** (anything else): treat each token as a path, resolve relative to git toplevel,
-    emit deduped absolute paths.
+4. **Explicit paths** (anything else): treat each token as a path, resolve relative to invocation
+    cwd, emit deduped absolute paths.
     No git invocation.
 
 Parent detection ----------------
@@ -196,8 +196,8 @@ def _head_rev_scope(toplevel: pathlib.Path, token: str) -> tuple[list[pathlib.Pa
     return paths, summary
 
 
-def _explicit_scope(toplevel: pathlib.Path, tokens: list[str]) -> tuple[list[pathlib.Path], dict]:
-    paths = _dedup([toplevel / token for token in tokens])
+def _explicit_scope(cwd_path: pathlib.Path, tokens: list[str]) -> tuple[list[pathlib.Path], dict]:
+    paths = _dedup([cwd_path / token for token in tokens])
     summary = {
         "mode": "explicit",
         "parent": None,
@@ -251,7 +251,7 @@ def enumerate_scope(
         if resolved is not None:
             return _head_rev_scope(toplevel, resolved)
 
-    return _explicit_scope(toplevel, args)
+    return _explicit_scope(cwd_path, args)
 
 
 def _cli(argv: list[str]) -> int:
diff --git a/plugins/codeguide/unit_tests/test-resolve-scope.py b/plugins/codeguide/unit_tests/test-resolve-scope.py
index 0176116f..c386849f 100644
--- a/plugins/codeguide/unit_tests/test-resolve-scope.py
+++ b/plugins/codeguide/unit_tests/test-resolve-scope.py
@@ -289,6 +289,29 @@ def main() -> int:
             assert summary["mode"] == "explicit", f"expected mode=explicit, got {summary['mode']}"
             print("PASS: single-token path with no colliding ref name still routes to explicit mode")
 
+        # Scenario 19: explicit paths in a nested-hub-root layout (hub root nested below git
+        # toplevel) must anchor to the invocation cwd, not the git toplevel. Uses a two-token
+        # call so the len(args) == 1 single-token ref-check dispatch in enumerate_scope is never
+        # reached, per the module docstring's note that multi-token calls never hit the ref check.
+        with tempfile.TemporaryDirectory() as tmpdir:
+            tmp = Path(tmpdir)
+            _make_repo(tmp, with_origin=False)
+            nested = tmp / "hub-root"
+            nested.mkdir()
+            _commit(tmp, {"hub-root/data.py": "x"}, "init")
+            paths, summary = enumerate_scope(["data.py", "extra.py"], cwd=nested)
+            path_names = {p.name for p in paths}
+            assert "data.py" in path_names, f"expected data.py in {path_names}"
+            assert "extra.py" in path_names, f"expected extra.py in {path_names}"
+            assert summary["mode"] == "explicit", f"expected mode=explicit, got {summary['mode']}"
+            data_path = [p for p in paths if p.name == "data.py"][0]
+            assert data_path == nested / "data.py", \
+                f"expected {nested / 'data.py'}, got {data_path}"
+            extra_path = [p for p in paths if p.name == "extra.py"][0]
+            assert extra_path == nested / "extra.py", \
+                f"expected {nested / 'extra.py'}, got {extra_path}"
+            print("PASS: explicit paths in nested-hub-root layout anchor to invocation cwd, not git toplevel")
+
         print("All resolve_scope unit tests passed.")
         return 0
 
diff --git a/plugins/mill/scripts/_implementer_common.py b/plugins/mill/scripts/_implementer_common.py
index 08e6b297..eef34b80 100644
--- a/plugins/mill/scripts/_implementer_common.py
+++ b/plugins/mill/scripts/_implementer_common.py
@@ -1636,6 +1636,7 @@ def finalize_from_output(
     cwd_override: Path | None = None,
     module_wide_cwd_override: Path | None = None,
     batch_verify_baseline: list[str] | None = None,
+    commit_sha_field_name: str = "commit_sha",
     batch_name: str | None = None,
 ) -> int:
     """Read sub-agent output and finalize.
@@ -1688,6 +1689,8 @@ def finalize_from_output(
         for the subset-diff waiver rule this enables.
             Defaults to None
         (run strictly, as before this parameter existed).
+        commit_sha_field_name: JSON key the corrective SHA is attached under on the success
+            fallback path; defaults to "commit_sha".
         batch_name: This batch's name, forwarded unchanged to _forward_output's _run_verify_gates
             calls.
             See _run_verify_gates for the self-healing persist this enables.
@@ -1729,6 +1732,7 @@ def finalize_from_output(
         cwd_override=cwd_override,
         module_wide_cwd_override=module_wide_cwd_override,
         batch_verify_baseline=batch_verify_baseline,
+        commit_sha_field_name=commit_sha_field_name,
         batch_name=batch_name,
     )
 
@@ -1786,6 +1790,7 @@ def _forward_output(
     cwd_override: Path | None = None,
     module_wide_cwd_override: Path | None = None,
     batch_verify_baseline: list[str] | None = None,
+    commit_sha_field_name: str = "commit_sha",
     batch_name: str | None = None,
 ) -> int:
     """Extract the last JSON object containing a 'status' key from output.
@@ -1842,6 +1847,11 @@ def _forward_output(
     cached, task-scoped stored signature set for this batch's own verify command, enabling the
     subset-diff waiver rule documented on _run_verify_gates.
     Defaults to None (run strictly, as before this parameter existed).
+    commit_sha_field_name is the JSON key the corrective SHA is attached under on the success
+    fallback block below (the unconditional `git rev-parse HEAD` correction); defaults to
+    "commit_sha", which preserves today's behavior for every existing caller. A non-default value
+    also pops any stale self-reported "commit_sha" key from parsed before attaching the corrected
+    SHA under the new key name, so the two never coexist.
     batch_name is forwarded unchanged to every _run_verify_gates call site below, alongside the
     already-present start_sha and status_path parameters, enabling the self-healing persist
     documented on _run_verify_gates.
@@ -2016,7 +2026,9 @@ def _forward_output(
                 cwd=project_root,
             )
             if result.returncode == 0 and _is_valid_commit_sha(result.stdout.strip()):
-                parsed["commit_sha"] = result.stdout.strip()
+                if commit_sha_field_name != "commit_sha":
+                    parsed.pop("commit_sha", None)
+                parsed[commit_sha_field_name] = result.stdout.strip()
                 violations = _cleanliness.compute_scope_violations(project_root, git_root)
                 if violations:
                     parsed["scope_violations"] = violations
diff --git a/plugins/mill/scripts/_plan_validate.py b/plugins/mill/scripts/_plan_validate.py
index 5ac7d2b9..46857c98 100644
--- a/plugins/mill/scripts/_plan_validate.py
+++ b/plugins/mill/scripts/_plan_validate.py
@@ -21,6 +21,8 @@ Checks performed (check keys):
     depends-on-unknown — (#10 check 4) depends-on entries referencing unknown batch names
     depends-on-batch-mismatch — per-batch file's depends-on disagrees with overview Batch Index
         depends-on for the same batch
+    verify-batch-mismatch — a batch's overview Batch Index verify: disagrees with that batch file's
+        own frontmatter verify: (command or cwd)
     parallel-modifies-overlap — (#10 check 5) Parallel-eligible batches both modifying the same file
         (includes Move endpoints)
     reads-not-backtick-path — (#10 check 6) Context:/Edits:/Creates: entries not in backtick-only
@@ -45,11 +47,12 @@ Checks performed (check keys):
         risk)
     plugin-manifest-context-missing — batch Creates:/Edits:/Deletes: touches plugins/mill/agents/
         but plugin.json is not in that batch's Context: or Edits:
-    context-completeness — a card's Requirements: references a resolvable file-path-shaped backtick
-        token absent from that card's own Context:/Edits:/Creates:/Deletes:/Moves:-source
+    context-completeness — a card's Requirements: references a resolvable file-path-shaped or
+        symbol-shaped backtick token absent from that card's own Context:/Edits:/Creates:/Deletes:/
+        Moves:-source
     requirements-quote-indent-drift — a card's Requirements: fenced block quoting exact source text
-        that only byte-matches its own Edits: file(s) after stripping a fixed per-line indent
-        (list-continuation-indentation bug signature)
+        that only byte-matches its own Edits: file(s) after stripping OR adding a fixed per-line
+        indent, in either direction (list-continuation-indentation bug signature)
     move-format — Moves: sub-bullet does not match the `src` -> `dst` grammar
     move-redundant — a path is both a Move endpoint and in Creates:/Deletes: of the same batch
     move-source-missing — Move source does not exist on disk and is not created/relocated by an
@@ -1318,6 +1321,107 @@ def _check_depends_on_batch_mismatch(
     return errors
 
 
+# ---------------------------------------------------------------------------
+# Check 5c — verify-batch-mismatch
+# ---------------------------------------------------------------------------
+
+def _check_verify_batch_mismatch(
+    batch_files: list[Path],
+    overview_text: str,
+    project_root: Path,
+) -> list[dict]:
+    """
+    Flag a batch whose overview Batch Index ``verify:`` disagrees with its own frontmatter ``verify:``.
+
+    Mirrors ``_check_depends_on_batch_mismatch``'s structure, but compares the ``verify:`` field
+    instead of ``depends-on:``. A malformed ``verify:`` mapping is reported by exactly one of the two
+    sides, never both:
+
+    - On the overview side, this check IS the sole reporter -- ``_check_verify_malformed_cwd``
+    inspects batch-file and overview *frontmatter* only, never Batch Index entries, so a malformed
+    ``verify:`` on an index entry would otherwise go unreported.
+    - On the batch-file side, ``_check_verify_malformed_cwd`` is already the documented sole
+    reporter, so this check silently skips a batch-side parse failure to avoid double-reporting.
+
+    Each side's raw ``cwd:`` key (the un-resolved string, not the normalizer's resolved ``Path``) is
+    compared independently of the normalized command, because both root arguments are passed as
+    ``project_root`` here -- passing the same value for both roots means ``cwd: hub`` and ``cwd:
+    git_root`` would otherwise resolve to the identical ``Path``, silently hiding a real drift between
+    the two spellings. Absent, explicit-null, and blank-string ``verify:`` all normalize to ``None``
+    through the shared normalizer, so those three spellings compare equal to one another and produce
+    no finding.
+
+    Error dict shape: ``{check, batch, card, path, message}``.
+
+    Args:
+        batch_files: Sorted list of batch file paths to validate.
+        overview_text: Full text of ``00-overview.md`` (source of the Batch Index DAG).
+        project_root: Root of the project;
+            passed as both the ``hub_root`` and ``git_root`` argument to
+                ``_plan_dag.parse_verify_field`` since only the command/cwd-key pair matters here,
+                never the resolved ``Path``.
+
+    Returns:
+        List of error dicts, one per batch whose two `verify:` sides disagree.
+    """
+    try:
+        batches = extract_batch_index(overview_text)
+    except PlanDAGError:
+        # Check 4 has already recorded the parse error; don't double-report.
+        return []
+
+    stem_to_path: dict[str, Path] = {bf.stem: bf for bf in batch_files}
+
+    errors: list[dict] = []
+    for entry in batches:
+        stem = Path(entry.get("file", "")).stem
+        batch_path = stem_to_path.get(stem)
+        if batch_path is None:
+            continue
+
+        try:
+            overview_command, _ = _plan_dag.parse_verify_field(entry, project_root, project_root)
+        except ValueError as exc:
+            errors.append({
+                "check": "verify-batch-mismatch",
+                "batch": entry["name"],
+                "card": None,
+                "path": None,
+                "message": f"overview Batch Index verify: is malformed: {exc}",
+            })
+            continue
+        raw_overview_verify = entry.get("verify")
+        overview_cwd_key = (
+            raw_overview_verify.get("cwd") if isinstance(raw_overview_verify, dict) else None
+        )
+
+        batch_frontmatter = _plan_dag._read_batch_frontmatter(batch_path)
+        try:
+            batch_command, _ = _plan_dag.parse_verify_field(
+                batch_frontmatter, project_root, project_root
+            )
+        except ValueError:
+            # _check_verify_malformed_cwd is the sole reporter for this.
+            continue
+        raw_batch_verify = batch_frontmatter.get("verify")
+        batch_cwd_key = raw_batch_verify.get("cwd") if isinstance(raw_batch_verify, dict) else None
+
+        if (overview_command, overview_cwd_key) != (batch_command, batch_cwd_key):
+            errors.append({
+                "check": "verify-batch-mismatch",
+                "batch": entry["name"],
+                "card": None,
+                "path": None,
+                "message": (
+                    f"per-batch file verify: command={batch_command!r} cwd={batch_cwd_key!r} "
+                    f"disagrees with overview Batch Index "
+                    f"verify: command={overview_command!r} cwd={overview_cwd_key!r}"
+                ),
+            })
+
+    return errors
+
+
 # ---------------------------------------------------------------------------
 # Check 6 — reads-not-backtick-path
 # ---------------------------------------------------------------------------
@@ -1606,7 +1710,7 @@ def _is_prohibition_exempt(lowered_line: str) -> bool:
         _PROHIBITION_VERB_RE.search(lowered_line)
     )
 
-# Citation-marker substrings: a Requirements: sentence containing one of these (lowercased) names a file as an illustrative example or citation, not as an unlisted read dependency, so a backtick token on that line is exempt from flagging.
+# Citation-marker substrings: a Requirements: sentence containing one of these (lowercased) names a file as an illustrative example or citation, not as an unlisted read dependency, so a backtick token on that line is exempt from flagging. "signature inlined" and "no file read needed" additionally cover the case where a Requirements: line inlines a cited symbol's full signature and therefore needs no file read, which is why naming the defining file on that line is not an unlisted read dependency.
 _CITATION_MARKERS = (
     "as an example",
     "as examples",
@@ -1615,11 +1719,25 @@ _CITATION_MARKERS = (
     "such as",
     "cited as",
     "citing",
+    "signature inlined",
+    "no file read needed",
 )
 
 # A backtick-quoted token counts as path-candidate-shaped when it contains a path separator or ends with one of these extensions; anything else (a JSON key, a function name, a sentinel string) is silently ignored.
 _PATH_CANDIDATE_EXTENSIONS = (".py", ".go", ".cs", ".ts", ".md", ".yaml", ".yml", ".json")
 
+# Source-code extensions searched when resolving a symbol-shaped (not path-shaped) backtick token.
+# A standalone tuple rather than a slice of _PATH_CANDIDATE_EXTENSIONS, so this list never silently
+# drifts if that constant's ordering or membership changes for unrelated (path-branch) reasons.
+_SYMBOL_SEARCH_EXTENSIONS = (".py", ".go", ".cs", ".ts")
+
+# Directory basenames pruned (never descended into) while walking a candidate root for symbol
+# resolution -- build artifacts and dependency trees that would otherwise dominate the search and
+# produce false ambiguous-matches.
+_SYMBOL_SEARCH_DENYLIST_DIRS = frozenset(
+    {".git", "node_modules", "vendor", "__pycache__", "dist", "build", ".venv"}
+)
+
 
 def _extract_requirements_text(card_text: str) -> str | None:
     """Return the body text of a card's ``Requirements:`` field, or ``None``.
@@ -1697,6 +1815,153 @@ def _card_own_reference_set(card_text: str) -> set[str]:
     return tokens
 
 
+# Trailing balanced-bracket groups stripped (repeatedly, from the end) when detecting a symbol-shaped
+# token's call/generic suffix -- e.g. "GetItems<T>()" strips to "GetItems" via two passes (the "()"
+# group, then the "<T>" group).
+_RE_TRAILING_PAREN_GROUP = re.compile(r"\([^()]*\)$")
+_RE_TRAILING_BRACKET_GROUP = re.compile(r"\[[^\[\]]*\]$")
+_RE_TRAILING_ANGLE_GROUP = re.compile(r"<[^<>]*>$")
+_RE_TRAILING_GROUPS = (
+    _RE_TRAILING_PAREN_GROUP,
+    _RE_TRAILING_BRACKET_GROUP,
+    _RE_TRAILING_ANGLE_GROUP,
+)
+
+# A bare-or-dotted identifier shape: one or two dot-separated `\w`-segments, each starting with a
+# letter or underscore. Matched AFTER line-range and call/generic-suffix stripping.
+_RE_SYMBOL_SHAPE = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)?$")
+
+
+def _symbol_candidate_shape(token: str) -> str | None:
+    """Return the symbol search key for a NOT-path-shaped Requirements: backtick token, or None.
+
+    ``token`` is an original backtick-quoted token the caller has already confirmed is not
+    path-shaped (no ``/``, doesn't end in a recognized source extension) -- this function does not
+    re-check that.
+    Strips a trailing ``:line-range`` suffix and any trailing call/generic suffix (one or more
+    trailing balanced ``()``/``[...]``/``<...>`` groups, e.g. ``GetItems<T>()`` -> ``GetItems``),
+    then requires what remains to look like a bare identifier (``SaveState``) or a dotted
+    qualifier.identifier pair (``reedengine.New``).
+    A bare or trailing-segment identifier only "qualifies" as a symbol candidate -- as opposed to an
+    ordinary lowercase English word like ``config`` -- when it is not entirely lowercase (contains an
+    uppercase letter, including possibly its first character) or contains an underscore;
+    for a dotted pair, only the trailing (second) segment's own qualification matters, since the
+    trailing segment is the only part ever used as the filesystem search key.
+
+    Returns:
+        The search key (the bare identifier, or the dotted pair's trailing segment) when the token
+        is symbol-shaped and qualifies, else None.
+    """
+    base = _RE_LINE_RANGE.sub("", token)
+    while True:
+        stripped_any = False
+        for group_re in _RE_TRAILING_GROUPS:
+            match = group_re.search(base)
+            if match:
+                base = base[: match.start()]
+                stripped_any = True
+                break
+        if not stripped_any:
+            break
+
+    if not _RE_SYMBOL_SHAPE.match(base):
+        return None
+
+    segments = base.split(".")
+
+    def qualifies(segment: str) -> bool:
+        return segment != segment.lower() or "_" in segment
+
+    if len(segments) == 1:
+        return base if qualifies(base) else None
+
+    trailing_segment = segments[-1]
+    return trailing_segment if qualifies(trailing_segment) else None
+
+
+def _resolve_symbol_files(
+    search_key: str,
+    project_root: Path,
+    root: str | None,
+    git_root: Path | None,
+    cache: dict[str, tuple[list[Path], Path | None]],
+) -> tuple[list[Path], Path | None]:
+    """Resolve ``search_key`` to its declaring file(s) via a first-match-wins filesystem walk.
+
+    Walks candidate roots in the same precedence order as ``resolve_existing_paths``
+    (``_review_common.py``'s "Resolution order (first match wins)"): (1) ``git_root / root`` when
+    both are set, (2) ``project_root / root`` (or bare ``project_root`` when ``root`` is None), (3)
+    bare ``git_root`` when set (tried unconditionally, mirroring that same precedence's own
+    unconditional trailing ``git_root`` candidate).
+    For each candidate root that exists on disk, recursively walks it -- pruning any directory whose
+    basename is in ``_SYMBOL_SEARCH_DENYLIST_DIRS`` -- and case-sensitive whole-word-matches
+    ``search_key`` against the text of every file whose suffix is in ``_SYMBOL_SEARCH_EXTENSIONS``.
+    Stops at the first candidate root that yields one or more matching files -- a later root in the
+    precedence order is never walked, even if the winning root had more than one match.
+
+    Memoized via ``cache`` (keyed by ``search_key``): a repeated call with the same key returns the
+    cached result without walking again, since a symbol name commonly recurs across many cards/
+    batches in one ``run()`` invocation.
+
+    Returns:
+        ``(matching_file_paths, winning_root)`` -- ``winning_root`` is the candidate root that
+        produced the match (needed by the caller to canonicalize the match back to a relative path);
+        ``([], None)`` when no candidate root yields any match.
+    """
+    if search_key in cache:
+        return cache[search_key]
+
+    candidate_roots: list[Path] = []
+    if root is not None and git_root is not None:
+        candidate_roots.append(git_root / root)
+    candidate_roots.append(project_root / root if root is not None else project_root)
+    if git_root is not None:
+        candidate_roots.append(git_root)
+
+    word_re = re.compile(r"\b" + re.escape(search_key) + r"\b")
+
+    for candidate_root in candidate_roots:
+        if not candidate_root.exists():
+            continue
+        matches: list[Path] = []
+        for dirpath, dirnames, filenames in os.walk(candidate_root):
+            dirnames[:] = [d for d in dirnames if d not in _SYMBOL_SEARCH_DENYLIST_DIRS]
+            for filename in filenames:
+                file_path = Path(dirpath) / filename
+                if file_path.suffix not in _SYMBOL_SEARCH_EXTENSIONS:
+                    continue
+                try:
+                    content = file_path.read_text(encoding="utf-8", errors="replace")
+                except OSError:
+                    # Broken symlink, permission-denied, or any other unreadable-file condition
+                    # under an arbitrary real-world project tree -- skip it, don't crash the run.
+                    continue
+                if word_re.search(content):
+                    matches.append(file_path)
+        if matches:
+            cache[search_key] = (matches, candidate_root)
+            return cache[search_key]
+
+    cache[search_key] = ([], None)
+    return cache[search_key]
+
+
+def _covered_by_own_refs(candidate: str, own_refs: set[str], moves_sources: set[str]) -> bool:
+    """Return True when ``candidate`` is already covered by a card's own declared refs.
+
+    Covered when ``candidate`` is in ``own_refs`` directly, is a plan-wide ``Moves:`` source, or (for
+    a bare filename with no ``/``) shares its basename with some entry in ``own_refs``.
+    """
+    return (
+        candidate in own_refs
+        or candidate in moves_sources
+        or (
+            "/" not in candidate
+            and any(Path(candidate).name == Path(entry).name for entry in own_refs)
+        )
+    )
+
+
 def _check_context_completeness(
     batch_files: list[Path],
     project_root: Path,
@@ -1710,28 +1975,53 @@ def _check_context_completeness(
     git_root: Path | None = None,
 ) -> list[dict]:
     """
-    Flag a card's Requirements: prose citing a file absent from its own refs.
+    Flag a card's Requirements: prose citing a file or symbol absent from its own refs.
 
-    A ``Requirements:`` field frequently prose-references a file the implementer must read or reason
-    about;
+    A ``Requirements:`` field frequently prose-references a file (or a symbol declared in exactly
+    one file) the implementer must read or reason about;
     when that file is a genuine dependency it belongs in the card's own ``Context:``/``Edits:`` (or
     ``Creates:``/``Deletes:``/``Moves:``) so a bulk-mode reviewer actually sees it.
-    This check heuristically detects the gap: for each card, every backtick-quoted, path-shaped
-    token in ``Requirements:`` that independently resolves to a real file (on disk, or a plan-wide
-    ``Creates:``/``Deletes:``/Moves-target reference) must also appear in that same card's own
+    This check heuristically detects the gap in two branches:
+
+    Path branch (unchanged): for each card, every backtick-quoted, path-shaped token in
+    ``Requirements:`` (contains ``/`` or ends with a recognized source extension) that
+    independently resolves to a real file (on disk, or a plan-wide ``Creates:``/``Deletes:``/
+    Moves-target reference) must also appear in that same card's own
     Context:/Edits:/Creates:/Deletes:/Moves:-source set.
-    Three exemptions prevent false positives:
+
+    Symbol branch: a backtick token that is NOT path-shaped is first gated by
+    ``_symbol_candidate_shape`` -- it must look like a bare or dotted identifier (``SaveState``,
+    ``reedengine.New``) that is not just an ordinary lowercase English word, else it is silently
+    ignored (same as today's behavior for non-path tokens).
+    A token that passes the shape gate is resolved via ``_resolve_symbol_files``: a first-match-wins
+    filesystem walk (memoized per ``run()`` call) that finds every file, under the highest-precedence
+    candidate root that has any match at all, whose text contains a case-sensitive whole-word
+    occurrence of the search key.
+    Zero or more-than-one matching file means the reference is unresolvable-with-confidence and is
+    never flagged;
+    exactly one match is canonicalized back to a root-relative path and checked against the card's
+    own refs exactly like the path branch.
+    The emitted ``message`` for a symbol-branch finding has a fixed format --
+    ``"...which resolves to '<path>' -- not in this card's ..."`` -- that a downstream fixer-doc
+    check (batch 2 of this task) parses to distinguish the symbol case from the path case;
+    this wording must not drift.
+
+    Three exemptions prevent false positives (apply to both branches):
 
     1. Prohibition-marker sentences (e.g. "forbid touching `x.py`") name a file the card must NOT
     act on, not an unlisted dependency.
     2. Citation-marker sentences (e.g. naming `x.py` as an example) cite a file for illustration,
     not as an unlisted read dependency.
+    This also covers a Requirements: line that inlines a cited symbol's full signature (e.g.
+    "signature inlined" or "no file read needed") -- naming the defining file on that line is not
+    an unlisted read dependency, since no file read is needed to act on the inlined signature.
     3. A token matching the plan-wide ``moves_sources`` set is exempt in any later card's
     ``Requirements:``, not just the declaring card's own -- mirrors how ``creates_union``/
     ``deletes_union`` are already plan-wide.
 
-    Non-path-shaped or unresolvable tokens (JSON keys, function names, sentinel strings) are never
-    flagged -- only genuine file references that this validator can independently confirm exist.
+    Not-shaped-at-all or unresolvable tokens (JSON keys, ordinary lowercase words, sentinel strings)
+    are never flagged -- only genuine file/symbol references that this validator can independently
+    confirm exist.
 
     Note: markdown's double-backtick-escape convention (`` `path` ``) is not detected by this regex;
     future citations needing that format should be aware they won't be checked by
@@ -1755,6 +2045,9 @@ def _check_context_completeness(
     """
     errors: list[dict] = []
     backtick_re = re.compile(r"`([^`]+)`")
+    # One symbol-resolution cache per run() call, shared across every batch/card, so a search key
+    # recurring across the plan is only walked once (see _resolve_symbol_files's memoization).
+    search_cache: dict[str, tuple[list[Path], Path | None]] = {}
 
     for batch_path in batch_files:
         text = batch_path.read_text(encoding="utf-8")
@@ -1770,9 +2063,13 @@ def _check_context_completeness(
 
             for line in requirements_lines:
                 for token in backtick_re.findall(line):
-                    # Path-candidate shape only: contains a separator or ends with a recognized source-file extension.
-                    if "/" not in token and not token.endswith(_PATH_CANDIDATE_EXTENSIONS):
-                        continue
+                    # Shape gate: path-shaped tokens fall through unconditionally; non-path tokens
+                    # fall through only when they look like a bare/dotted symbol candidate.
+                    is_path_shaped = "/" in token or token.endswith(_PATH_CANDIDATE_EXTENSIONS)
+                    if not is_path_shaped:
+                        search_key = _symbol_candidate_shape(token)
+                        if search_key is None:
+                            continue
 
                     # Prohibition-marker exemption: the line naming this token forbids acting on it, so it is not an unlisted read dependency.
                     lowered_line = line.lower()
@@ -1783,48 +2080,76 @@ def _check_context_completeness(
                     if any(marker in lowered_line for marker in _CITATION_MARKERS):
                         continue
 
-                    # Strip a trailing line-range suffix before testing resolvability and matching;
-                    # the ORIGINAL token is kept for the emitted error's "path" field.
-                    stripped_token = _RE_LINE_RANGE.sub("", token)
-
-                    existing = resolve_existing_paths(
-                        [stripped_token], project_root, root,
-                        wiki_root=wiki_root, git_root=git_root,
-                    )
-                    existing_files = [p for p in existing if p.is_file()]
-                    resolvable = (
-                        bool(existing_files)
-                        or stripped_token in creates_union
-                        or stripped_token in deletes_union
-                        or stripped_token in moves_targets
-                    )
-                    if not resolvable:
-                        continue
-
-                    if own_refs is None:
-                        own_refs = _card_own_reference_set(card_text)
+                    if is_path_shaped:
+                        # Strip a trailing line-range suffix before testing resolvability and matching;
+                        # the ORIGINAL token is kept for the emitted error's "path" field.
+                        stripped_token = _RE_LINE_RANGE.sub("", token)
+
+                        existing = resolve_existing_paths(
+                            [stripped_token], project_root, root,
+                            wiki_root=wiki_root, git_root=git_root,
+                        )
+                        existing_files = [p for p in existing if p.is_file()]
+                        resolvable = (
+                            bool(existing_files)
+                            or stripped_token in creates_union
+                            or stripped_token in deletes_union
+                            or stripped_token in moves_targets
+                        )
+                        if not resolvable:
+                            continue
+
+                        if own_refs is None:
+                            own_refs = _card_own_reference_set(card_text)
+
+                        if _covered_by_own_refs(stripped_token, own_refs, moves_sources):
+                            continue
 
-                    if stripped_token in own_refs:
-                        continue
-                    if stripped_token in moves_sources:
-                        continue
-                    if "/" not in stripped_token and any(
-                        Path(stripped_token).name == Path(entry).name for entry in own_refs
-                    ):
-                        continue
+                        errors.append({
+                            "check": "context-completeness",
+                            "batch": batch_path.stem,
+                            "card": card_num,
+                            "path": token,
+                            "message": (
+                                f"card {card_num}'s Requirements: references '{token}' "
+                                f"which is not in this card's "
+                                f"Context:/Edits:/Creates:/Deletes:/Moves:-source"
+                            ),
+                            "line": line.strip(),
+                        })
+                    else:
+                        # Check the shared cache before calling into _resolve_symbol_files at all --
+                        # a recurring search_key across cards/batches then costs one function call
+                        # (the actual filesystem walk), not one call per occurrence.
+                        if search_key in search_cache:
+                            matches, producing_root = search_cache[search_key]
+                        else:
+                            matches, producing_root = _resolve_symbol_files(
+                                search_key, project_root, root, git_root, search_cache
+                            )
+                        if len(matches) != 1:
+                            continue
+
+                        canonical = matches[0].relative_to(producing_root).as_posix()
+
+                        if own_refs is None:
+                            own_refs = _card_own_reference_set(card_text)
+
+                        if _covered_by_own_refs(canonical, own_refs, moves_sources):
+                            continue
 
-                    errors.append({
-                        "check": "context-completeness",
-                        "batch": batch_path.stem,
-                        "card": card_num,
-                        "path": token,
-                        "message": (
-                            f"card {card_num}'s Requirements: references '{token}' "
-                            f"which is not in this card's "
-                            f"Context:/Edits:/Creates:/Deletes:/Moves:-source"
-                        ),
-                        "line": line.strip(),
-                    })
+                        errors.append({
+                            "check": "context-completeness",
+                            "batch": batch_path.stem,
+                            "card": card_num,
+                            "path": token,
+                            "message": (
+                                f"card {card_num}'s Requirements: references symbol '{token}', "
+                                f"which resolves to '{canonical}' -- not in this card's "
+                                f"Context:/Edits:/Creates:/Deletes:/Moves:-source"
+                            ),
+                            "line": line.strip(),
+                        })
 
     return errors
 
@@ -1848,6 +2173,30 @@ def _strip_n_leading_spaces(text: str, n: int) -> str:
     return "\n".join(stripped_lines)
 
 
+def _add_n_leading_spaces(text: str, n: int, *, include_blank: bool = False) -> str:
+    """Prepend exactly ``n`` space characters to every line of ``text``.
+
+    This is the exact inverse of ``_strip_n_leading_spaces`` -- a fixed per-line add, not a
+    re-indent.
+    For each line (split via ``.splitlines()``), ``n`` space characters are prepended and the
+    lines are rejoined with ``"\\n"``.
+
+    When ``include_blank`` is ``False`` (the default), a line whose ``.strip()`` is empty is
+    emitted unchanged rather than padded: a real nested source excerpt usually has genuinely empty
+    separator lines, since editors strip trailing whitespace, so the default reproduces the true
+    source.
+    ``include_blank=True`` covers the less common case of a source that keeps whitespace-only
+    indented lines instead of collapsing them to empty ones.
+    """
+    added_lines = []
+    for line in text.splitlines():
+        if not include_blank and not line.strip():
+            added_lines.append(line)
+        else:
+            added_lines.append(" " * n + line)
+    return "\n".join(added_lines)
+
+
 def _card_edits_tokens(card_text: str) -> list[str]:
     """Return this card's own ``Edits:`` backtick tokens, in declaration order.
 
@@ -1937,23 +2286,35 @@ def _check_requirements_quote_indent_drift(
 ) -> list[dict]:
     """
     Flag a card's Requirements: fence that only byte-matches its own Edits: file(s) after stripping
-    a fixed per-line indent.
+    or adding a fixed per-line indent.
 
     This is the list-continuation-indentation bug's exact signature: a ``Requirements:`` fence meant
-    to quote exact source text as Edit-tool ``old_string`` bait silently picks up a uniform per-line
-    indent from the surrounding Markdown list-continuation nesting, so the quoted text no longer
-    byte-matches the real source file even though it "looks right" to a human or LLM reviewer.
+    to quote exact source text as Edit-tool ``old_string`` bait silently picks up (or loses) a
+    uniform per-line indent from the surrounding Markdown list-continuation nesting, so the quoted
+    text no longer byte-matches the real source file even though it "looks right" to a human or LLM
+    reviewer.
+    Drift can go either direction: the fence may carry MORE indent than the source (over-indent, the
+    strip case) or LESS indent than the source (under-indent, the add case).
 
     For each card with a non-empty Edits: field and a Requirements: field containing at least one
     fenced code block: for each fence, if the raw (unstripped) fence content is already a literal
     substring of some resolved Edits: file's content, the fence is clean -- no error.
-    If not, search ascending strip amounts N = 1..40 (a fixed per-line leading-space strip, NOT
-    textwrap.dedent's common-minimum-strip -- see _strip_n_leading_spaces) for the first N whose
-    stripped fence content IS a literal substring of some resolved Edits: file (walked in the card's
-    own Edits: declaration order, first match wins on ties).
-    The first match wins and stops the search;
-    a fence matching no N in range is an illustrative snippet showing new/desired-state code, not a
-    drifted quote, and is silently skipped -- never flagged.
+    Otherwise the strip pass runs first: search ascending strip amounts N = 1..40 (a fixed per-line
+    leading-space strip, NOT textwrap.dedent's common-minimum-strip -- see _strip_n_leading_spaces)
+    for the first N whose stripped fence content IS a literal substring of some resolved Edits: file
+    (walked in the card's own Edits: declaration order, first match wins on ties).
+    The strip pass runs before the add pass because a fence cannot legitimately match both
+    directions at once, so preserving the incumbent strip-first ordering keeps every
+    currently-emitted message byte-for-byte stable.
+    Only when the strip pass finds nothing does the add pass run, over the same ascending N = 1..40
+    range: for each N, ``_add_n_leading_spaces(fence_body, n)`` (blank lines left unpadded) is tried
+    first across every resolved Edits: file in declaration order, and only if that fails is
+    ``_add_n_leading_spaces(fence_body, n, include_blank=True)`` (blank lines padded too) tried the
+    same way -- the non-blank-then-all-lines ordering matches the common case (editors strip
+    trailing whitespace from blank lines) before the less common one.
+    Either pass's first match wins and stops the search;
+    a fence matching in neither direction at any N in range is an illustrative snippet showing
+    new/desired-state code, not a drifted quote, and is silently skipped -- never flagged.
 
     Per _mill/discussion.md's match-target-edits-only Decision, only a card's own Edits: files are
     compared against (never Context:, Creates:, or other cards' files) -- those files already exist
@@ -2021,6 +2382,7 @@ def _check_requirements_quote_indent_drift(
                 ):
                     continue
 
+                matched = False
                 for n in range(1, 41):
                     stripped = _strip_n_leading_spaces(fence_body, n)
                     matched_token = None
@@ -2040,6 +2402,38 @@ def _check_requirements_quote_indent_drift(
                                 f"leading spaces per line (found N={n})"
                             ),
                         })
+                        matched = True
+                        break
+                if matched:
+                    continue
+
+                # The strip pass found nothing: this fence may instead be under-indented relative
+                # to its source (the opposite drift direction), so run the symmetric add pass over
+                # the same ascending N range.
+                for n in range(1, 41):
+                    matched_token = None
+                    for candidate in (
+                        _add_n_leading_spaces(fence_body, n),
+                        _add_n_leading_spaces(fence_body, n, include_blank=True),
+                    ):
+                        for token in ordered_resolved_tokens:
+                            if candidate in resolved_contents[token]:
+                                matched_token = token
+                                break
+                        if matched_token is not None:
+                            break
+                    if matched_token is not None:
+                        errors.append({
+                            "check": "requirements-quote-indent-drift",
+                            "batch": batch_path.stem,
+                            "card": card_num,
+                            "path": matched_token,
+                            "message": (
+                                f"card {card_num}'s Requirements: fence {fence_idx} "
+                                f"matches '{matched_token}' after adding {n} "
+                                f"leading spaces per line (found N={n})"
+                            ),
+                        })
                         break
 
     return errors
@@ -2963,8 +3357,8 @@ def run(
     plugin-manifest-context-missing, verify-not-isolated, verify-full-suite, verify-malformed-cwd,
     verify-mixed-cwd, verify-unrelated-test-file, out-of-worktree-target, batch-oversized,
     commit-none-with-content, and five Move-specific checks (move-format, move-redundant,
-    move-source-missing, move-target-collision, move-mechanic-missing), and
-    cross-batch-creates-no-depends-on.
+    move-source-missing, move-target-collision, move-mechanic-missing),
+    cross-batch-creates-no-depends-on, and verify-batch-mismatch.
 
 
     Args:
@@ -3026,6 +3420,7 @@ def run(
     errors.extend(_check_card_numbering(batch_files))
     errors.extend(_check_depends_on_unknown(overview_text, overview_path))
     errors.extend(_check_depends_on_batch_mismatch(batch_files, overview_text))
+    errors.extend(_check_verify_batch_mismatch(batch_files, overview_text, project_root))
     errors.extend(_check_parallel_modifies_overlap(batch_files, overview_text))
     errors.extend(_check_cross_batch_creates_no_depends_on(batch_files, overview_text))
     errors.extend(_check_ref_not_backtick_path(batch_files))
diff --git a/plugins/mill/scripts/millpy-merge-in-subagent.py b/plugins/mill/scripts/millpy-merge-in-subagent.py
index 6740ee63..bad450b0 100644
--- a/plugins/mill/scripts/millpy-merge-in-subagent.py
+++ b/plugins/mill/scripts/millpy-merge-in-subagent.py
@@ -421,6 +421,7 @@ def main(argv=None) -> int:
             start_sha=None,
             snapshot_path=None,
             session_id=None,
+            commit_sha_field_name="pre_merge_head",
         )
 
     timeout = cfg.get("llm", {}).get("implementer_timeout", 1800)
@@ -487,7 +488,7 @@ def _run_conflicts(args, project_root: Path, plugin_root: Path, cfg: dict, timeo
             print(json.dumps(gate_result))
             return 0
 
-    return _forward_output(output, project_root)
+    return _forward_output(output, project_root, commit_sha_field_name="pre_merge_head")
 
 
 def _run_verify_fix(args, project_root: Path, plugin_root: Path, cfg: dict, timeout: int, impl_model: str, impl_effort: str | None, stage: str = "full") -> int:
diff --git a/plugins/mill/skills/git-commit/SKILL.md b/plugins/mill/skills/git-commit/SKILL.md
index 7cba3e69..8df32b2e 100644
--- a/plugins/mill/skills/git-commit/SKILL.md
+++ b/plugins/mill/skills/git-commit/SKILL.md
@@ -65,6 +65,13 @@ Either way, the `codeguide-update` skill re-resolves per file and handles inline
   Do not create the branch.
 - **If on `main`/`master` and `--onmain` is in the argument:** proceed normally.
 - Stage files individually: `git add file1 file2` — never `git add .` or `git add -A`.
+- **Verify the stage before committing.** After staging, run `git diff
+  --quiet -- <the same paths just staged>`. A non-zero exit means the
+  working tree still has changes beyond what was staged for those paths --
+  the add/edit race this step exists to catch (a `git mv`/edit not yet
+  reflected in the index at stage time). On a non-zero exit, re-run `git add`
+  for those exact paths once and re-check; if the second check is still
+  non-zero, halt and report the mismatch instead of committing.
 - Commit with title + bullet-point format (title summarizes the task, bullets explain key decisions).
 - Push to remote.
   Set upstream if needed: `git push --set-upstream origin <branch>`.
diff --git a/plugins/mill/skills/mill-finalize/SKILL.md b/plugins/mill/skills/mill-finalize/SKILL.md
index 8599d855..276aec35 100644
--- a/plugins/mill/skills/mill-finalize/SKILL.md
+++ b/plugins/mill/skills/mill-finalize/SKILL.md
@@ -79,6 +79,22 @@ otherwise remove it.
 This prevents PR diffs from being polluted with unrelated deletions on stacked-branch PRs.
 
 Call `_finalize_cleanup.base_tracks_task_dir(git_root, parent_branch, task_dir)`.
+
+**Citation scan (non-blocking).** Before either branch below runs, scan for permanent-doc citations of `_mill/discussion.md` that this cleanup is about to invalidate. A citation can live in either the worktree's own tracked tree or the wiki, so this is two separate greps, both read-only and neither one halts Step 3 under any outcome:
+
+```bash
+git -C <worktree> grep -InE '\]\([./]*_mill/discussion\.md\)' -- . \
+    ':!<task_dir>' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'
+```
+
+```bash
+git -C <wiki_path> grep -InE '\]\([./]*_mill/discussion\.md\)' -- .
+```
+
+Part 1 excludes `<task_dir>` itself and this plugin's own tooling docs/tests (`plugins/**/SKILL.md`, `plugins/**/unit_tests/**`, `plugins/**/integration_tests/**`) — those are self-referential mentions of the `_mill/discussion.md` convention, not citations of a real task's discussion file — and matches the markdown-link-context pattern rather than a bare literal-string match, since a bare-string scan would hit this repo's own tooling docs on effectively every run. Part 2 covers the wiki-board case (a Done/roadmap entry in the wiki's `Home.md`) that Part 1 structurally cannot reach: the wiki is a sibling clone resolved via `_paths.resolve_wiki_path` (bound in Entry step 1), never part of `<worktree>`'s own git repository, so `git -C <worktree> grep` cannot see wiki content. This wiki-path grep is read-only — it does not go through `_wiki.wiki_lock` or `_client`, since it performs no write.
+
+`git grep` exits 1 with empty stdout when nothing matches — that is the expected common case, not an error. If either part produces any output (non-zero line count), print a warning to the operator (ASCII-only) listing the citing files/wiki pages, worded according to which branch below is about to run: on the False branch (no base tracking), say the link "is about to go dead" — `<task_dir>` is genuinely removed. On the True branch (`base_tracks_task_dir`), say the link "is about to silently start pointing at a different task's `_mill/discussion.md` content" — `<task_dir>` is not deleted there, it is repopulated with `<parent_branch>`'s own tree at that path, so a citation does not 404, it silently resolves to whatever discussion file (if any) `<parent_branch>` happens to have at that same relative path. This scan never halts Step 3 in either case — it only warns.
+
 If True (base tracks task_dir): restore it from the base — but a bare checkout only adds/updates paths, it never deletes, so we delete-then-restore instead. `git rm -r --ignore-unmatch <task_dir>` first empties `task_dir` of everything on the current (child) branch tip — a no-op, not an error, when nothing matches — then `git checkout <parent_branch> -- <task_dir>` repopulates `task_dir` with exactly `<parent_branch>`'s tree at that path.
 Any file present in the child's `task_dir` but absent from `<parent_branch>`'s tree there is now removed rather than left behind — this closes the #653 orphaned-files gap a bare checkout left (it can only add/update paths present in the target ref, never delete paths that are exclusive to the current branch):
 
diff --git a/plugins/mill/skills/mill-merge-in/SKILL.md b/plugins/mill/skills/mill-merge-in/SKILL.md
index dbb5b152..72b1f567 100644
--- a/plugins/mill/skills/mill-merge-in/SKILL.md
+++ b/plugins/mill/skills/mill-merge-in/SKILL.md
@@ -13,20 +13,29 @@ This skill does not acquire the merge lock — only the calling `mill-merge` (or
 
 1. Read the slug via `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
    On `MarkerError` → halt with "this worktree was not created by mill-spawn".
-2. Resolve the parent branch.
-   **Source of truth is `_mill/status.md`'s `parent:` row** — call `_parent_branch.resolve(status_path, interactive=True, expected_slug=slug)` where `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")` and `slug` is already resolved in Entry step 1 via `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
-   Config does not carry a parent-branch override (YAGNI as of v2.0).
-   If `mill-merge-in` is being called from `mill-merge`'s auto-merge path, pass `interactive=False` and propagate the raised `ParentBranchError` -- `expected_slug=slug` applies in both the interactive and non-interactive forms of the call.
-
-   **Liveness check (#817):** after `resolve(...)` above returns a `parent_branch` successfully, first run the preflight guard `` import _preflight; exit(_preflight.check_helpers(['_parent_branch:check_liveness'])) `` , then verify it is still live: `_parent_branch.check_liveness(parent_branch, git_root)` (same call `mill-merge/SKILL.md` Entry Step 4 makes — see that step's own "Liveness check (#817)" paragraph for the exact bash invocation and the JSON shape returned).
+2. Bind `status_path = _paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")` unconditionally, before the branch check below.
+   This hoist is required because the "Liveness check (#817)" paragraph's dead-parent rebind (`_status.update_field(status_path, "parent", resolved_branch)`) needs `status_path` bound regardless of which of the two paths below is taken.
+3. Resolve the parent branch. Check whether the caller supplied the optional positional `<branch>` argument (the pre-existing ad-hoc override for syncing from some other branch than the task's declared parent, AND the caller-handoff use where a calling skill — e.g. `mill-merge` — passes its own already-resolved parent branch to avoid a redundant/unreachable `status.md` read):
+   - **If supplied:** bind `parent_branch` to that value directly and skip the `resolve(...)` call entirely.
+   - **If not supplied:** fall through exactly as today. **Source of truth is `_mill/status.md`'s `parent:` row** — call `_parent_branch.resolve(status_path, interactive=True, expected_slug=slug)`, reading the `status_path` hoisted in step 2 above (no longer computed inline here).
+     `slug` is already resolved in Entry step 1 via `_marker.slug_from_branch(git_root, wiki_path, cfg)`.
+     Config does not carry a parent-branch override (YAGNI as of v2.0).
+     `mill-merge` can no longer reach this fallback branch bare: as of the Card 1 fix (`mill-merge/SKILL.md` Step 2), `mill-merge` always passes its own already-resolved `<parent_branch>` as the positional override, landing in the "If supplied" branch above instead. The remaining bare (no-argument) caller is `mill-finalize`'s PR Step 1 ("Invoke the `mill-merge-in` skill (no arguments...)"), which does not currently override `interactive` -- it reaches this fallback branch with `interactive=True` as written above. If a future caller needs to invoke `mill-merge-in` bare from a non-interactive context, it must pass `interactive=False` explicitly and propagate the raised `ParentBranchError` -- `expected_slug=slug` applies in both the interactive and non-interactive forms of the call.
+
+   **Liveness check (#817):** in both branches above, once `parent_branch` is bound, first run the preflight guard `` import _preflight; exit(_preflight.check_helpers(['_parent_branch:check_liveness'])) `` , then verify it is still live: `_parent_branch.check_liveness(parent_branch, git_root)` (same call `mill-merge/SKILL.md` Entry Step 4 makes — see that step's own "Liveness check (#817)" paragraph for the exact bash invocation and the JSON shape returned).
+   This read-only liveness check (a `git ls-remote`) itself runs unconditionally in both branches and is harmless regardless of which branch produced `parent_branch` — this is a deliberately *broader* exemption than `mill-merge/SKILL.md` Entry Step 4's own precedent, not a mirror of it: Step 4 skips its liveness check *entirely* for its `status_path`-absent fallback branch ("This liveness check applies only to the `status_path.exists()` True branch"), whereas here the read-only check runs unconditionally in both branches and only the rebind *write* below is exempted.
    If alive, continue as before.
-   If dead, call `_parent_branch.resolve_dead_parent(parent_branch, git_root, cfg)` and apply the identical halt/report/confirm/rebind behavior documented in `mill-merge/SKILL.md` Entry Step 4's "Liveness check (#817)" paragraph: report the `resolved` or `fallback` outcome and require operator confirmation before continuing (the `cycle` outcome always halts outright, no confirmation prompt), then on confirmation rebind `status.md`'s `parent:` row via `_status.update_field(status_path, "parent", resolved_branch)`, commit, push, and use `resolved_branch` as `parent_branch` for the remainder of this run.
-   "Identical" above describes the operator-facing halt/report/confirm/rebind protocol, not the `status_path` derivation mechanism: this rebind reuses the same `status_path` already bound at the top of this Entry step (`_paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`) rather than deriving a fresh one, and that is safe here even though `mill-merge/SKILL.md` Entry Step 4 warns against the same `resolve_hub_path()` + literal-path pattern for its own rebind — that warning exists because `mill-merge` must reconcile cwd against a separately-tracked worktree location (its `mode == 'inplace'` vs `'worktree'` disambiguation, where cwd can legitimately be the main hub while the active slug's tracked worktree lives elsewhere).
+   If dead, call `_parent_branch.resolve_dead_parent(parent_branch, git_root, cfg)` and apply the identical halt/report/confirm operator-facing protocol documented in `mill-merge/SKILL.md` Entry Step 4's "Liveness check (#817)" paragraph: report the `resolved` or `fallback` outcome and require operator confirmation before continuing (the `cycle` outcome always halts outright, no confirmation prompt).
+   On confirmation, branch on `status_path.exists()` before writing the rebind:
+   - **If `status_path.exists()` is `False`:** this reordering is what newly makes the override branch reach the liveness check with a possibly-absent `status_path` (the exact #977 scenario: `mill-merge`'s Card 1 passes its own `status_path`-absent `cfg.git.base_branch` fallback, which `mill-merge` never liveness-checks itself). Skip the rebind write (and its commit/push) entirely — there is nothing to persist to — report the resolved/fallback outcome to the operator as informational only, and proceed using that resolved branch for the remainder of this run.
+   - **If `status_path.exists()` is `True`** (the pre-existing case, and the override-supplied case when a task's status.md still exists): rebind `status.md`'s `parent:` row via `_status.update_field(status_path, "parent", resolved_branch)`, commit, push, and use `resolved_branch` as `parent_branch` for the remainder of this run, exactly as documented today.
+
+   **Caller propagation (#977 follow-up):** whichever sub-case above ran, once the `if dead` branch above fires and the operator confirms, record `substituted_parent_branch = resolved_branch` (distinct from the ordinary `<parent-branch>` this file's own `## Steps` use) for this run. Step 6's Report below must surface this value. Resolving a successor here only ever affects `mill-merge-in`'s own remainder-of-run `parent_branch` (and, in the `True` sub-case, the persisted `status.md` row) — it never itself updates a calling skill's already-bound variables. When this skill is invoked as `mill-merge`'s own Step 2 (see `mill-merge/SKILL.md` Step 2), that caller's `parent_branch`/`<parent-path>` were resolved and bound before this call and are reused verbatim through its own Step 5 onward, so the caller must read `substituted_parent_branch` back out of this skill's Report and rebind its own variables from it before continuing past its Step 2 — this file cannot do that rebind on the caller's behalf.
+
+   This rebind reuses the same `status_path` hoisted in step 2 above (`_paths.resolve_task_path(_paths.resolve_hub_path(), "_mill/status.md")`) rather than deriving a fresh one, and that is safe here even though `mill-merge/SKILL.md` Entry Step 4 warns against the same `resolve_hub_path()` + literal-path pattern for its own rebind — that warning exists because `mill-merge` must reconcile cwd against a separately-tracked worktree location (its `mode == 'inplace'` vs `'worktree'` disambiguation, where cwd can legitimately be the main hub while the active slug's tracked worktree lives elsewhere).
    `mill-merge-in` has no such ambiguity: it always operates on "the current branch" from within that branch's own worktree (it is never dispatched against a different slug's worktree from some other cwd), so `resolve_hub_path()`'s cwd-walk necessarily lands on the same hub a slug-driven `resolve_active_hub()` lookup would return for that slug.
-   This mirrors the identical `resolve_hub_path()`-based derivation this file's own Step 4 (Verify) already uses (`hub_root = _paths.resolve_hub_path()`), so Card 7's rebind is consistent with the rest of this file, not a one-off exception to it.
-   This check runs identically whether `mill-merge-in` is invoked standalone or dispatched from `mill-merge`'s Step 2 — `mill-merge-in` reads the same `status_path` independently via its own `resolve()` call, and must not skip this check just because `mill-merge`'s own Entry Step 4 may have already performed it moments earlier for its own call site. The redundancy is harmless: `check_liveness` is a single read-only `git ls-remote`.
-3. Optional positional argument: `<branch>` from the user's invocation overrides both status.md and the prompt.
-   This is for ad-hoc syncing from some other branch than the task's declared parent.
+   This mirrors the identical `resolve_hub_path()`-based derivation this file's own Step 4 (Verify) already uses (`hub_root = _paths.resolve_hub_path()`), so this rebind is consistent with the rest of this file, not a one-off exception to it.
+   This check runs identically whether `mill-merge-in` is invoked standalone or dispatched from `mill-merge`'s Step 2 — `mill-merge-in` reads the same `status_path` independently, and must not skip this check just because `mill-merge`'s own Entry Step 4 may have already performed it moments earlier for its own call site. The redundancy is harmless: `check_liveness` is a single read-only `git ls-remote`.
 
 ## Steps
 
@@ -98,14 +107,29 @@ On `{"status":"stuck"}` from the sub-agent → roll back to checkpoint (`git res
 
 ### 3.5. Baseline recompute
 
-Runs unconditionally after step 3 completes successfully (including after any conflict-resolution sub-dispatch in step 3's table), before step 4's verify replay begins:
+Runs unconditionally after step 3 completes successfully (including after any conflict-resolution sub-dispatch in step 3's table), before step 4's verify replay begins.
+
+This call does not go through Agent-mode dispatch.
+Unlike steps 3/4's conflict/verify-fix sub-agent dispatches, `--recompute-baseline` runs the same deterministic computation `millpy-implement.py --stage baseline` uses, with no LLM session involved — it needs no `<cli>`/`<args>` Agent-mode dispatch pattern reference.
+Instead of a capped foreground call, it is background-dispatched and polled via the same `millpy-bg.py --slug <name> -- ...` pattern `mill-go-base/SKILL.md`'s `### 0.5. Baseline pre-flight` section uses:
+
+> **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree (this is the first `millpy-bg` call site in `mill-merge-in/SKILL.md` or `mill-merge/SKILL.md` — see `mill-go-base/SKILL.md`'s 0.5/0.6 sections for the callout's precedent). If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), this is the one deliberate divergence from the imported callout's wording: rather than halting the skill, log the reason (ASCII-only) and continue past this step -- the same log-and-continue *action* the `"dead"` branch below takes, but not its *detection mechanism*. The `"dead"` outcome below is discovered by polling `_bg.check_bg_status` against an already-created `<log-path>`; a cwd rejection here is discovered synchronously, from `millpy-bg.py`'s own stderr on the failed Bash call itself (it exits 1 before ever printing `pid=<N> log=<abs-path>`, so there is no log file yet to poll). Capture that stderr directly from the failed Bash call as the logged reason, rather than attempting a `_bg.check_bg_status` poll against a log path that was never created. Step 3.5 is fail-safe by design (an error here degrades to a `baseline: "error"` result, not a merge failure), so a cwd-mismatch on the dispatch attempt itself is scoped to the dispatch attempt only, not a new halt condition for this step.
+
+```bash
+PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-bg.py" \
+    --slug merge-in-baseline-recompute -- \
+    "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --recompute-baseline
+```
+
+This returns immediately with `pid=<N> log=<abs-path>`. Poll `cat <log-path>` until the line `[mill-bg] EXIT` appears, running the same `_bg.check_bg_status` liveness-check loop `mill-go-base/SKILL.md`'s 0.5 section uses:
 
 ```bash
-PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/millpy-merge-in-subagent.py" --recompute-baseline
+PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON" -c "import _bg, json; from pathlib import Path; print(json.dumps(_bg.check_bg_status(Path('<log-path>'))))"
 ```
 
-- This call is synchronous and does not go through Agent-mode dispatch.
-  Unlike steps 3/4's conflict/verify-fix sub-agent dispatches, `--recompute-baseline` runs the same deterministic computation `millpy-implement.py --stage baseline` uses, with no LLM session involved — it needs no `<cli>`/`<args>` Agent-mode dispatch pattern reference.
+Parse the JSON result and branch: `"running"` -> keep polling; `"exit"` -> proceed; `"dead"` -> log the reason (ASCII-only) and continue -- never halt, matching this step's own "It never blocks or fails the merge" contract below.
+Once `[mill-bg] EXIT` appears, run `grep '^{' <log-path>` to extract the result, exactly as `mill-go-base/SKILL.md`'s 0.5 section does.
+
 - It never blocks or fails the merge: on any internal error it prints a `baseline: "error"` result and returns exit 0 (fail-safe).
   This step never triggers the Rollback section.
 - If step 1's no-op check already exited early ("Nothing to merge"), this step never runs at all — the "## No-op guarantee" section's promise ("this skill touches nothing" when there was nothing to merge) continues to hold.
@@ -116,7 +140,7 @@ This mirrors the batch-1 pre-flight rule exactly: the parent's dependency manife
 ### 4. Verify
 
 Replay exactly the tests that ran during implementation.
-Resolve `hub_root = _paths.resolve_hub_path()` and `status_path = _paths.resolve_task_path(hub_root, "_mill/status.md")` (the same resolution Entry step 2 already uses).
+Resolve `hub_root = _paths.resolve_hub_path()` and `status_path = _paths.resolve_task_path(hub_root, "_mill/status.md")` (the same resolution Entry step 2 already uses to hoist `status_path`).
 Call `_plan_dag.iter_batch_verifies(plan_dir, hub_root, git_root, status_path=status_path)` where `plan_dir = _paths.resolve_task_path(hub_root, "_mill/plan/")`.
 That yields `(batch_name, verify_cmd, cwd)` triples in DAG order, skipping batches with `verify: null`, batches that have not reached `"approved"` state yet, and batches whose verify target a later-approved batch's `Deletes:`/`Moves:` declares removed.
 
@@ -171,17 +195,24 @@ This is the documented convention in `plugins/mill/skills/git-commit/SKILL.md` s
 
 ### 5.5. Commit dispatch briefs
 
-If any dispatch briefs exist and have changes (both the `merge/conflicts` brief written in step 3 and the `merge/verify-fix` brief written in step 4 after the `git merge --continue`), stage and commit them.
-Use a guarded `git status --porcelain` check to avoid an empty commit:
+If any dispatch briefs exist and have changes (both the `merge/conflicts` brief written in step 3 and the `merge/verify-fix` brief written in step 4 after the `git merge --continue`), stage and commit them alongside anything step 5 already staged.
+Staging is unconditional on `_mill/briefs` existing, but the commit is gated on whether anything is actually STAGED, never on unscoped `git status --porcelain`:
 
 ```bash
-if [ -d <worktree>/_mill/briefs ] && [ -n "$(git -C <worktree> status --porcelain -- _mill/briefs)" ]; then
-  git -C <worktree> add _mill/briefs/ && git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"
+if [ -d <worktree>/_mill/briefs ]; then
+  git -C <worktree> add <worktree>/_mill/briefs/
+fi
+if [ -n "$(git -C <worktree> diff --cached --name-only)" ]; then
+  git -C <worktree> commit -m "mill-merge-in: commit dispatch briefs"
 fi
 ```
 
-This step runs on the success path only: any failure in steps 2-5 triggers the Rollback (`git reset --hard "$CHK"`) before reaching this point, so the brief commit is intentionally outside rollback scope and captures successful state.
-Clean merges (no conflicts, no verify failures) skip steps 3 and 4 entirely, so this step gracefully handles the case where no briefs were written (the `git status --porcelain` guard returns empty).
+**Why staged-only, not unscoped porcelain:** `git status --porcelain` also reports unrelated unstaged/untracked worktree state that may already exist when `mill-merge-in` is invoked -- state this skill's own earlier steps had no part in creating -- and gating on that would either sweep foreign dirt into this commit or, worse, pass the non-empty check while nothing is actually staged, making `git commit` fail with "nothing to commit" even though the guard said there was something to commit. Checking `git diff --cached` (staged-only) avoids both failure modes, since briefs (if added above) and codeguide docs (already staged by `codeguide_commit.py --mode inline` in Step 5) are the only two things this step ever stages or expects to find staged.
+
+This also now picks up Step 5's inline-mode codeguide docs -- already `git add`-staged by `codeguide_commit.py --mode inline` back in Step 5, before this step runs -- which the prior `_mill/briefs`-scoped guard silently dropped whenever `_mill/briefs/` did not exist (#946).
+
+This step runs on the success path only: any failure in steps 2-5 triggers the Rollback (`git reset --hard "$CHK"`) before reaching this point, so the brief/codeguide-doc commit is intentionally outside rollback scope and captures successful state.
+Clean merges (no conflicts, no verify failures) skip steps 3 and 4 entirely, so this step gracefully handles the case where no briefs were written AND no codeguide docs were staged either -- the `git diff --cached --name-only` guard returns empty and the block no-ops.
 
 ### 6. Report
 
@@ -191,6 +222,12 @@ Verify: <ran> batch tests ran.
 Checkpoint: <CHK> (delete manually once you are confident the merge is stable).
 ```
 
+If `substituted_parent_branch` was recorded during this run (Entry's "Liveness check (#817)" paragraph, `if dead` branch), append one more line to the report, after the `Checkpoint:` line:
+
+```
+Substituted parent branch: <parent-branch> -> <substituted_parent_branch> (dead; not persisted to status.md unless status_path.exists() was True above). If this skill was called from mill-merge Step 2, that caller must rebind its own parent_branch/<parent-path> to <substituted_parent_branch> before continuing to Step 3.
+```
+
 Build the `Verify:` line by starting with `Verify: <ran> batch tests ran` and appending one clause per nonzero skip counter, in this fixed order -- allowlisted, not-approved, target-removed -- each included only when its own count is nonzero: `, <skipped> skipped (allowlisted as known-broken)` when `skipped >= 1`;
 `, <skipped_not_approved> skipped (batch not approved)` when `skipped_not_approved >= 1`;
 `, <skipped_target_removed> skipped (target removed by later batch)` when `skipped_target_removed >= 1`.
diff --git a/plugins/mill/skills/mill-merge/SKILL.md b/plugins/mill/skills/mill-merge/SKILL.md
index c1b15a48..cf536a88 100644
--- a/plugins/mill/skills/mill-merge/SKILL.md
+++ b/plugins/mill/skills/mill-merge/SKILL.md
@@ -246,11 +246,17 @@ If the lock already exists:
 
 ### 2. Invoke mill-merge-in
 
-Call the `mill-merge-in` skill (no arguments — it picks up the parent from status.md the same way).
+Call the `mill-merge-in` skill, passing `<parent_branch>` — the value already resolved and bound at Entry Step 4 (including that step's `status_path`-absent fallback and its liveness-check rebind) — as `mill-merge-in`'s optional positional `<branch>` argument (documented in `mill-merge-in/SKILL.md` Entry step 3 as "for ad-hoc syncing from some other branch than the task's declared parent"), rather than a bare invocation.
+Passing the value explicitly is what lets `mill-merge-in` skip its own independent `status.md` read — see Card 2 in this same batch for the corresponding `mill-merge-in`-side change this depends on.
+This applies to Step 2 itself, not any one route — both the `done` fresh-merge route and the `closed` PR-state-gate route (the only two routes that reach Step 2 via `## Entry`'s "In-place mode bypass" / PR-state-gate routing) pass the argument.
 If it reports failure → release the merge lock and halt.
 Capture the checkpoint branch name it prints;
 you may need it on rollback.
 
+**Rebind on dead-parent substitution (#977):** if `mill-merge-in`'s Step 6 report (see `mill-merge-in/SKILL.md` Step 6, "Substituted parent branch" line) includes a `Substituted parent branch: <old> -> <new>` line, rebind `parent_branch` (this skill's own variable, bound at Entry Step 4) to `<new>` before continuing to Step 3. This is required because `mill-merge-in`'s own dead-parent liveness check (its Entry section's "Liveness check (#817)" paragraph) only ever resolves a successor for its own run — it has no mechanism to reach back into this caller's already-bound `parent_branch`, and Step 5 below reuses `parent_branch`/`<parent-path>` verbatim from here through push/rollback.
+If `mode == 'worktree'`, also re-derive `<parent-path>` for the new branch: re-run `git worktree list --porcelain` and locate the entry whose branch matches `<new>`, the same lookup Step 1 above used for the original `parent_branch`.
+If `mode == 'inplace'`, there is no separate parent worktree to re-derive (Step 5 already omits `-C <parent-path>` in that mode per the "In-place mode bypass" note in `## Entry`) — rebinding `parent_branch` alone is sufficient.
+
 ### 3. Capture child branch
 
 ```bash
@@ -272,7 +278,20 @@ a failed step is reported with its name so the user can re-run from that step (S
 
 ### 4. Cleanup commit
 
-On the task branch (current cwd), remove the state directory that belongs to the task lifecycle, not to production code:
+On the task branch (current cwd), remove the state directory that belongs to the task lifecycle, not to production code.
+
+**Citation scan (non-blocking, #930).** Before removing `<task_dir>`, scan for permanent-doc citations of `_mill/discussion.md` that this deletion is about to invalidate. A citation can live in either the worktree's own tracked tree or the wiki, so this is two separate greps, both read-only and neither one halts this step under any outcome:
+
+```bash
+git -C <worktree> grep -InE '\]\([./]*_mill/discussion\.md\)' -- . \
+    ':!<task_dir>' ':!plugins/**/SKILL.md' ':!plugins/**/unit_tests/**' ':!plugins/**/integration_tests/**'
+```
+
+```bash
+git -C <wiki_path> grep -InE '\]\([./]*_mill/discussion\.md\)' -- .
+```
+
+`git grep` exits 1 with empty stdout when nothing matches — that is the expected common case, not an error. If either part produces any output (non-zero line count), print a warning to the operator (ASCII-only) listing the citing files/wiki pages: unlike `mill-finalize`'s Step 3 (which has a restore branch for stacked branches), `mill-merge`'s Step 4 always deletes `<task_dir>` outright — so the warning always says the link "is about to go dead", never the "silently repoints" variant. This scan never halts this step — it only warns.
 
 ```bash
 git -C <worktree> rm -r <task_dir>
diff --git a/plugins/mill/skills/mill-plan/SKILL.md b/plugins/mill/skills/mill-plan/SKILL.md
index be9fd45d..efeabc61 100644
--- a/plugins/mill/skills/mill-plan/SKILL.md
+++ b/plugins/mill/skills/mill-plan/SKILL.md
@@ -144,6 +144,7 @@ Report the current phase to the user at each transition.
 ### Phase: Plan
 
 Read `_mill/discussion.md` in full.
+Immediately capture `discussion_sha = git -C <git_root> rev-parse HEAD:_mill/discussion.md` (or the config-derived relative path from `cfg['paths']['discussion_file']` if it differs) — this pins the exact committed content this plan is written against, before any further reads, forks, or file writes that could race with a concurrent rewrite.
 Read `CONSTRAINTS.md` at the hub root if present (via `_constraints.read_if_exists()`).
 Then **think the plan through end-to-end before writing any file** — you are Opus and this is exactly where the planning budget pays off.
 
@@ -240,6 +241,8 @@ If the plan's batch-verify scopes do not cover the entire module tree (the commo
 Before defaulting `done_gate` to the target language's lint command (Go: `golangci-lint run`; Python: `ruff check .`), first run that candidate command against the current worktree tip (not the plan's own scoped changes) from `git_root` and confirm it exits 0. If it does, default `done_gate` to include it — e.g. `go test ./... && golangci-lint run` — applying even when a repo-wide *test* command is skipped as too slow: author `done_gate: golangci-lint run` (lint-only) rather than leaving it `null`, since linters are fast, unlike full regression suites. If the candidate command does NOT exit 0 (pre-existing repo-wide lint debt unrelated to this task), leave `done_gate: null` and record the finding in the plan overview's Shared Decisions instead of silently making every future task in the hub depend on unrelated debt being fixed first. `csharp-build` defines no lint command today, so C# projects are unaffected by this default.
 Leave `done_gate: null` only when the project has neither a meaningful repo-wide test nor a defined lint command.
 
+**Interpreter-naming note.** Every narrative Python call from this point through the end of Phase: Plan (`_plan_dag.extract_batch_index`/`_plan_dag.validate`, `_plan_validate.run`, `_status.update_field`/`_status.append_phase`, and any other `_<module>.<fn>(...)` reference in this phase) is executed by the orchestrator via `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}/scripts" "$MILL_PYTHON"` — never bare `python3` — matching CLAUDE.md's `## Script invocation` convention and the way every `millpy-bg`/`millpy-review-plan.py` invocation elsewhere in this file already names `$MILL_PYTHON` explicitly. A fresh orchestrator session with no other context has previously hit `ModuleNotFoundError: No module named 'pygit2'` here by reaching for the ambient `python3` instead.
+
 **Self-validate the DAG** before committing: call `_plan_dag.extract_batch_index(overview_text)` then `_plan_dag.validate(batches, sorted(p.name for p in plan_dir.glob("??-*.md") if p.name != "00-overview.md"))`.
 Any `PlanDAGError` → fix the plan files, then re-validate.
 Do not commit a plan that fails this check.
@@ -284,6 +287,8 @@ Fix any findings using the Step 1.5 fix table below, then re-run, before committ
 
 **Persist `skip_checks` for Phase: Plan Review.** When `skip_checks` (computed above, after applying the `wiki-config-mutation`, `verify-full-suite`, and `out-of-worktree-target` skip-check overrides) is non-empty, write it into `00-overview.md`'s fenced-yaml frontmatter as a new `skip_checks:` list field (parallel to the existing `approved:` field, e.g. `skip_checks: ["wiki-config-mutation"]`), via the same direct-`Edit` convention already used elsewhere in this file for the `approved:` field. Omit the field entirely (do not write `skip_checks: []`) when the frozenset is empty, matching the template's convention of omitting optional frontmatter keys that don't apply. Include this edit in the same 'Commit on the task branch' step below — no separate commit.
 
+**Persist `discussion_sha` for drift detection.** Write the `discussion_sha` captured above into `00-overview.md`'s fenced-yaml frontmatter as a new `discussion_sha:` field (parallel to `approved:`/`skip_checks:`), via the same direct-`Edit` convention already used elsewhere in this file for the `approved:` field. Unlike `skip_checks:`, this field is never optional — write it unconditionally on every Phase: Plan run, since every Phase: Plan Review dispatch site (see that phase's own drift-guard subsection, added in batch 1 card 3) depends on it being present. Include this edit in the same 'Commit on the task branch' step below — no separate commit.
+
 `signature: _status.read(status_path: Path) -> dict`
 
 **Update `_mill/status.md`.**
@@ -293,6 +298,8 @@ Fix any findings using the Step 1.5 fix table below, then re-run, before committ
 - `_status.update_field(status_path, "plan", cfg['paths']['plan_dir'].rstrip('/'))` — pointer to the plan dir (worktree-relative).
 - `_status.append_phase(status_path, "planning", _timestamp.now_utc_iso())`.
 
+**Pre-commit drift check.** Immediately before committing, re-run `git -C <git_root> rev-parse HEAD:_mill/discussion.md` and compare against the `discussion_sha` captured at the top of this phase. On a mismatch: discard the written-but-uncommitted plan files (`git -C <worktree> clean -fd <plan_dir>`, since nothing under `plan_dir` has been added/committed yet), halt via `_status.set_blocked(status_path, "discussion.md changed after Phase: Plan entry (blob sha drift)", timestamp=_timestamp.now_utc_iso())`, commit that status change alone on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (discussion.md blob sha drift) for {slug}"`), push, and halt with: `BLOCKED: discussion.md changed after Phase: Plan entry (blob sha drift). Delete _mill/plan/ and re-run /mill-plan for a fresh plan against the current discussion.md.` Do not proceed to commit the plan when this fires.
+
 **Commit on the task branch.** `git -C <worktree> add <plan_dir> <status_path> && git -C <worktree> commit -m "mill-plan: write plan for {slug}"`.
 Push.
 
@@ -304,6 +311,8 @@ Use this variable for all review file path references in this phase.
 
 **Read persisted `skip_checks` from Phase: Plan.** Parse `00-overview.md`'s fenced-yaml frontmatter (the same extraction pattern already used elsewhere in this file for the `approved:` field) and read `plan_skip_checks = <parsed skip_checks: list, or [] if the key is absent>`. This is the `skip_checks` frozenset Phase: Plan already justified via the `wiki-config-mutation` / `verify-full-suite` two-condition tests — thread it into every round's CLI dispatch below as `--skip-check <name>` per entry (repeatable flag, one `--skip-check` per list entry), so Phase: Plan Review's own validator gate does not re-flag a finding Phase: Plan already resolved and committed against.
 
+**Discussion drift guard (reused at every LLM-dispatch site in this phase).** Parse `00-overview.md`'s fenced-yaml frontmatter (same extraction pattern used for `approved:`/`skip_checks:`) and read `plan_discussion_sha = <parsed discussion_sha: field>`. Before every point in this phase where an LLM is actually dispatched or re-dispatched — in both Agent-mode and subprocess/psmux-mode, with no exception for a call that doesn't consume the round counter — re-run `git -C <git_root> rev-parse HEAD:_mill/discussion.md` and compare against `plan_discussion_sha`. Known dispatch points today (audit this file's current LLM-dispatch call sites at implementation time if this file has changed since this plan was written): step 2's initial per-round dispatch (both branches); Step 1.5's validator-fix re-invocation, in both its Agent-mode form ('Agent-mode prepare-envelope handling', the re-render-brief/call-Agent/finalize cycle) and its subprocess/psmux form (the `millpy-bg` re-run under slug `plan-validator-fix`); and step 3.5's ERROR-only-aggregate retry re-dispatch (both branches). On a mismatch at any of these: halt via `_status.set_blocked(status_path, "discussion.md changed after Phase: Plan entry (blob sha drift)", timestamp=_timestamp.now_utc_iso())`, commit that status change alone on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (discussion.md blob sha drift) for {slug}"`), push, and halt with: `BLOCKED: discussion.md changed after Phase: Plan entry (blob sha drift). Delete _mill/plan/ and re-run /mill-plan for a fresh plan against the current discussion.md.` Do not proceed with the dispatch about to happen. Recovery is manual, matching this file's own pattern for every non-max-rounds blocked state — neither a bare `/mill-plan` re-run (hard-stopped by the Entry table's `phase: blocked` row) nor `/mill-plan --revise` (which resumes the existing plan without recapturing `discussion_sha`) reaches Phase: Plan again on its own; the operator must delete `plan_dir` and start fresh.
+
 When `revise_from_blocked` is set (bound at Entry step 4's `--revise` pre-check), compute `blocked_resume_round = _review_common.discover_round(reviews_dir, "plan", "holistic")` against this plain, un-namespaced `reviews_dir`, before applying the namespacing override below.
 
 When `revise_requested` is set **and `revise_from_blocked` is not set** (carried forward from Step 0.5/step 4), compute a namespaced override before using `reviews_dir` for anything else in this phase: scan `<reviews_dir>/` for existing `revise-<N>` subdirectories (matching the literal pattern `revise-` followed by an integer), take the max `N` found (or `0` if none exist), and reassign `reviews_dir = reviews_dir / f"revise-{N+1}"` for the remainder of this phase.
@@ -348,7 +357,7 @@ Each round:
      No review file is written;
      no LLM token is spent;
      no review round is consumed.
-   - On validator-failure exit, mill-plan parses the JSON and applies one mechanical fix per error dict, per the mapping table below. After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then run `grep '^{' <log-path> | tail -1` to extract the JSON line.
+   - On validator-failure exit, mill-plan parses the JSON and applies one mechanical fix per error dict, per the mapping table below. Run the discussion drift guard (see 'Discussion drift guard' above) now, before this re-run. After fixes, mill-plan re-runs the review CLI via millpy-bg (slug `plan-validator-fix`; still no round consumed). Poll `cat <log-path>` until `[mill-bg] EXIT`, then run `grep '^{' <log-path> | tail -1` to extract the JSON line.
    - **Two-pass cap:** if the validator fails again on the second pass, immediately before halting, call `_status.set_blocked(status_path, "plan-validate non-progress", timestamp=_timestamp.now_utc_iso())`; commit on the task branch (`git -C <worktree> add <status_path> && git -C <worktree> commit -m "mill-plan: blocked (plan-validate non-progress) for {slug}"`) and push. Then mill-plan halts with `BLOCKED: plan-validate non-progress` and writes the unresolved errors to the user.
      Do NOT auto-retry beyond the second pass.
      The two-pass cap matches the `roles.implementer.self_fix_rounds` self-fix pattern.
@@ -373,8 +382,9 @@ Each round:
    | move-mechanic-missing          | Add the canonical `## Rename mechanic` section (copied from `plugins/mill/templates/plan-batch.md`) to the offending batch file, placed before `## Batch Scope`. |
    | all-files-touched-mismatch     | Update the overview's All Files Touched to match the union of every card's Edits: + Creates: + Moves: target paths (Move source paths are excluded — they disappear, like Deletes: tokens). (The overview list is derivative; the cards are the source of truth.) |
    | plugin-manifest-context-missing | Add `plugins/mill/.claude-plugin/plugin.json` to the offending batch's `Context:` list (unless the batch's own `Edits:` already includes it, in which case the check should not have fired — re-verify the check's `Creates:`/`Edits:`/`Deletes:` prefix match before editing the plan). |
-   | context-completeness           | Add the referenced file to the card's `Context:` list (unless the card's own `Edits:`/`Creates:`/`Deletes:`/`Moves:`-source already covers it, in which case re-verify the check's own-list cross-reference before editing — the "add to Context:" remedy applies only when the token is absent from all five fields; a token that legitimately belongs to `Deletes:`/`Moves:`-source means the check should not have fired at all). The error dict's `line` field carries the exact offending `Requirements:` line (stripped), so the fixer can locate it directly without re-deriving it from the batch file. |
-   | requirements-quote-indent-drift | Locate the card's `Requirements:` fence identified by the error payload's `message` (its fence index and the reported strip amount `N` — the message carries no content snippet). Strip exactly `N` leading space characters from each line of the fence body (not necessarily to column 0 — preserve whatever baseline indentation remains after the strip) so its content is a literal byte-exact substring of the target `Edits:` file named in the payload's `path` field. |
+   | context-completeness           | If the finding's `message` contains the substring `"which resolves to '"` (the symbol case — e.g. `"card 3's Requirements: references symbol 'SaveState()', which resolves to 'internal/state.go' -- not in this card's Context:/Edits:/Creates:/Deletes:/Moves:-source"`): extract the quoted text between `"which resolves to '"` and the next `"'"` (in the example, `internal/state.go`) and add that path to the card's `Context:` list — NOT the finding's `path` field, which holds the original symbol token text (e.g. `SaveState()`), never a file. Otherwise (the path case — `message` containing `"references '...' which is not in..."`, no `"which resolves to '"` substring): add the referenced file from the finding's `path` field to the card's `Context:` list (unless the card's own `Edits:`/`Creates:`/`Deletes:`/`Moves:`-source already covers it, in which case re-verify the check's own-list cross-reference before editing — the "add to Context:" remedy applies only when the token is absent from all five fields; a token that legitimately belongs to `Deletes:`/`Moves:`-source means the check should not have fired at all). In both cases, the error dict's `line` field carries the exact offending `Requirements:` line (stripped), so the fixer can locate it directly without re-deriving it from the batch file. When the cited file is large and the card needs only a symbol's exact signature rather than the file's contents, the escape hatch is to inline the full signature in the `Requirements:` prose and put the phrase `signature inlined` or `no file read needed` on the same physical line as the backtick-wrapped path — the check's citation-marker exemption then honours it — instead of adding a large file to `Context:` purely to satisfy this check and pushing the batch over the context cap. |
+   | requirements-quote-indent-drift | Locate the card's `Requirements:` fence identified by the error payload's `message` (its fence index and the reported direction and amount `N` — the message carries no content snippet). A message reading "after stripping N leading spaces per line" keeps today's remedy: strip exactly `N` leading space characters from each line of the fence body (not necessarily to column 0 — preserve whatever baseline indentation remains after the strip). A message reading "after adding N leading spaces per line" means the fence is flattened relative to its source: add exactly `N` leading space characters to each non-blank line of the fence body instead. In both cases the goal is identical: the fence body must end up a literal byte-exact substring of the target `Edits:` file named in the payload's `path` field. |
+   | verify-batch-mismatch          | The payload's `batch:` field names the batch whose per-batch file frontmatter `verify:` disagrees with the overview Batch Index entry for that same batch; the `message:` field shows both sides' command and `cwd:` key. Edit whichever side is stale so both name the identical command and the identical `cwd:` key — mirrors the `depends-on-batch-mismatch` row's "edit whichever side is stale" remedy. A message reading "overview Batch Index verify: is malformed" instead means the index entry's own `verify:` mapping is unparseable — fix that mapping per the `verify-malformed-cwd` row's guidance, then re-run. |
    | verify-not-isolated            | Open the per-batch file named by the error payload's `batch:` field (resolve `_mill/plan/<batch>.md`). Read the offending command from the payload's `path:` field. Replace the frontmatter line `verify: <original>` with `verify: PYTHONPATH= <original>` (literal `PYTHONPATH=`, single space, original command). One row, one prepend. |
    | verify-unrelated-test-file     | Remove the named token (the payload's `path:` field) from the offending batch's `verify:` command frontmatter (identified by the payload's `batch:` field). Log what was dropped and why in the validator-fix commit message, so the drop is auditable rather than silent. |
    | verify-excludes-edited-tagged-test | Open the offending batch's verify: command (payload's batch/path fields name the batch and the tagged test file; the payload's message field names the missing tag in its trailing "naming '<tag>'" fragment). If a `-tags` flag already exists on the command: do not comma-join `<tag>` into its value. Note this is a defense-in-depth choice, not a correction of broken Go semantics — Go's `-tags` set is satisfied by ANY-membership (each file's own `//go:build` line is checked independently against the full enabled-tag set, so a plain single-tag `//go:build scout` file is compiled/run whenever `scout` is enabled, regardless of what else is also enabled; `-tags integration,scout` does NOT exclude it). The real risk is project-specific: some repos deliberately give tagged suites mutually exclusive semantics (a suite's own constraint combines its tag with a negation of a sibling suite's tag, e.g. to keep suites isolated for cost/reporting reasons) — comma-joining silently breaks that convention if it's in use, and this check cannot tell whether a given project relies on it. Instead, append a new ` && `-chained invocation of the same base command (same verb and package pattern as the existing invocation) carrying its own `-tags <tag>` flag — strictly safer, since it never assumes either way. Otherwise (no `-tags` flag anywhere in the command yet): append `" -tags <tag>"` to the command in place, unchanged. |
@@ -382,7 +392,7 @@ Each round:
    | verify-mixed-cwd               | Each error dict's `message:` field states only that batch's own resolved cwd plus the sorted list of conflicting batch names; read all `verify-mixed-cwd` error dicts emitted for this plan together to see every batch's individual cwd. Change the outlier batch(es)' `verify:` mapping's `cwd:` value (or convert to the plain-string form, which implies `cwd: git_root`) so every batch in the plan resolves the `{cwd, command}` mapping form to the same root — all `hub` or all `git_root`. |
    | verify-full-suite              | The payload's `path:` field carries the offending `verify:` command; its `message:` field already names the runner-correct scoping flag (`-run <pattern>` for Go, `--filter` for dotnet, `-k <pattern>`/`--only <files>` for run-all.py, `-k <pattern>` for bare pytest — apply that flag directly. If instead the justification is already documented — the batch's own `## Batch Tests` section when `batch:` names a batch, or a `### Decision:` subsection under `00-overview.md`'s `## Shared Decisions` when `batch:` is `None` (see the `verify-full-suite` skip-check escape hatch in Phase: Plan) — re-run with `--skip-check verify-full-suite` instead of scoping. |
    | wiki-config-mutation           | This check cannot be fixed by editing plan files — the batch intentionally modifies `mill-config.yaml`. To proceed, verify one of two conditions: (a) a bootstrap card is present — a card whose body explains why the mill-config.yaml change is safe mid-flight for the currently-shipping task; or (b) the modified keys are provably unused — meaning key *removal or rename* where zero grep hits across `scripts/` and `skills/` confirm no existing code references them. (For key *addition* where consuming code is also being added in the same plan, zero grep hits does NOT satisfy condition (b); use (a) or halt.) If either condition holds: document the justification in the validator-fix commit message and re-run the CLI with `--skip-check wiki-config-mutation`. If `wiki-config-mutation` co-occurs with other fixable validator errors, fix those first per their rows, then re-run with `--skip-check wiki-config-mutation`. If neither condition holds: halt — the plan requires redesign. |
-   | batch-oversized                | Halt — the batch exceeds `pipeline.max_cards_per_batch` cards and/or the `pipeline.max_batch_context_tokens` context estimate. Splitting a batch is a structural change, not a mechanical fix; the planner must re-split at Phase: Plan. Not auto-fixable. |
+   | batch-oversized                | Before concluding a batch cannot be split, check whether a large `Context:` entry exists only to satisfy `context-completeness` for a signature citation — if so, the `context-completeness` row's inline-signature escape hatch (inline the signature, mark the citation `signature inlined` or `no file read needed`) removes the entry and the overage with it. For every other case: Halt — the batch exceeds `pipeline.max_cards_per_batch` cards and/or the `pipeline.max_batch_context_tokens` context estimate. Splitting a batch is a structural change, not a mechanical fix; the planner must re-split at Phase: Plan. Not auto-fixable. |
    | out-of-worktree-target         | If the plan's `discussion.md` records an explicit cross-worktree authorization and the target is itself a git worktree under legitimate task control (see the `out-of-worktree-target` skip-check override in Phase: Plan), re-run with `--skip-check out-of-worktree-target`. Otherwise: Halt — the operator must handle such edits manually; the implementer can never be pointed at them. Not auto-fixable. |
    | missing-overview               | Halt — the plan is structurally broken, not mechanically fixable.                                                                                                                                                       |
    | batch-index-parse              | Halt — the overview's fenced-yaml block is unparseable; not mechanically fixable.                                                                                                                                        |
@@ -413,6 +423,7 @@ converged = (round >= min_review_rounds)
 2. **Waiting is never a decision point.**
    Waiting on this dispatch — either branch — is never a decision point: state in one sentence what you're waiting for, then wait. `AskUserQuestion` (or any equivalent free-text operator prompt) is banned here unconditionally — both the max-rounds escape (step 6) and the non-progress check (step 5) resolve by halting via `_status.set_blocked`, never by prompting.
    **Dispatch mode:** Resolve dispatch mode via `_agent_dispatch.resolve_dispatch_mode(cfg)`.
+   Run the discussion drift guard (see 'Discussion drift guard' above) now, before this checkpoint.
    Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before the Agent-mode dispatch below.
    This does not apply to the subprocess/psmux branch, which keeps its existing worktree_snapshot_guard coverage unchanged.
 
@@ -435,6 +446,7 @@ converged = (round >= min_review_rounds)
      Parse the JSON and apply one mechanical fix per error dict, using the fix table in Step 1.5 below as the source of truth for all fix semantics.
      After fixes, commit on the task branch: `git -C <worktree> add <plan_dir> && git -C <worktree> commit -m "mill-plan: validator-fix pass for {slug}"`.
      Push.
+     Run the discussion drift guard (see 'Discussion drift guard' above) now, before this re-invocation.
      Then re-invoke the prepare stage via the same three-step Agent-mode dispatch (re-render brief, call Agent, finalize;
      the same cycle repeats).
      Use the two-pass cap: if the second prepare invocation also fails validator, halt with `BLOCKED: plan-validate non-progress` and write the unresolved errors to the user.
@@ -460,6 +472,8 @@ converged = (round >= min_review_rounds)
 
    **Subprocess/psmux branch — Invoke the CLI as a subprocess:**
 
+   Run the discussion drift guard (see 'Discussion drift guard' above) now, before invoking `millpy-bg`.
+
    > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.
 
    > Only when this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), append ` --max-rounds <local_max_review_rounds>` to the inner `millpy-review-plan.py` invocation below; omit it on every other round.
@@ -494,6 +508,7 @@ converged = (round >= min_review_rounds)
 
    When no entry in `reviews[]` is `error_kind: "usage"` (per the immediate halt above), and the JSON envelope from step 2 has a non-empty `reviews[]` array AND at least one remaining entry's `verdict` is `"ERROR"`, OR when no JSON line appears in the bg log (no `^{` summary line after `[mill-bg] EXIT`, indicating the worker died before printing — e.g. killed, OOM), skip steps 4a/4b/4c/4d entirely and immediately re-run:
 
+   Run the discussion drift guard (see 'Discussion drift guard' above) now, before this checkpoint.
    Tree-guard checkpoint (Agent-mode only, pre-dispatch): call _treeguard.check_and_restore(worktree_root, "_mill", git_root=git_root) — and, on trigger, _status.append_recovery_log(status_path, result["timestamp"], result["restored_paths"]) — immediately before this retry's Agent-mode dispatch.
    Does not apply to the Subprocess/psmux branch immediately below.
 
@@ -508,6 +523,8 @@ converged = (round >= min_review_rounds)
 
    **Subprocess/psmux branch:**
 
+   Run the discussion drift guard (see 'Discussion drift guard' above) now, before invoking `millpy-bg`.
+
    > **Before invoking `millpy-bg`**: verify `pwd` in the Bash terminal matches the task worktree. If `millpy-bg` rejects cwd with the parent-worktree error (`mill-bg: cwd appears to be a non-task worktree`), halt and instruct the operator to switch to the task-worktree terminal.
 
    > Only when this loop was entered via the Entry `blocked` re-entry row (see "Entry: resuming after a max-rounds block"), append ` --max-rounds <local_max_review_rounds>` to the inner `millpy-review-plan.py` invocation below; omit it on every other round.
diff --git a/plugins/mill/skills/mill-start/SKILL.md b/plugins/mill/skills/mill-start/SKILL.md
index 780ed5f6..4486aef5 100644
--- a/plugins/mill/skills/mill-start/SKILL.md
+++ b/plugins/mill/skills/mill-start/SKILL.md
@@ -194,7 +194,9 @@ and the right delegation mechanism depends on the shape of the question — this
 - **Small question** answerable in one or two tool calls — just explore inline;
   delegating either way is overhead.
 
-This is the one site in mill with no brief, no resume requirement, no per-role model tier, and no tool restriction to lose, which is exactly why none of the three fork disqualifiers (see "Why not fork?" in `mill-go-base/SKILL.md`'s "## Agent-mode dispatch") apply here.
+This is the one site in mill with no brief, no resume requirement, and no per-role model tier to lose from forking — but it is NOT a site with no tool restriction to lose: a fork inherits the parent's full tool access exactly as documented in `mill-go-base/SKILL.md`'s "Why not fork?" paragraph, and a live incident (#919) showed an in-context research fork, dispatched mid-`--auto` session for a narrowly-scoped read-only investigation, instead inherited the full session context and autonomously executed the entire downstream pipeline — writing and committing discussion.md, writing a full plan, running a plan-fix round, and dispatching a live reviewer, all pushed to origin before the operator noticed.
+
+**Fork scope guardrail.** Whenever a fork IS used under the guidance above, all of the following apply, mirroring `mill-plan/SKILL.md`'s own "Fork scope guardrail" (Phase: Plan) for the identical problem: (a) the fork's prompt must explicitly forbid Edit/Write calls, forbid mutating Bash commands, and forbid touching `discussion_path`, `status_path`, or any `mill-config.yaml`/`config.local.yaml` — and must explicitly state the fork is NOT the orchestrator and must not act on any active skill's phase instructions, only answer the narrow question it was dispatched with. (b) Immediately BEFORE dispatching the fork, capture a `git status --porcelain` snapshot (scoped to the worktree) as a baseline. (c) Immediately AFTER the fork returns, run `git status --porcelain` again and diff it against the pre-dispatch baseline. Treat only entries that are NEW in the post-return snapshot as a scope violation; the fork's report is not trusted until this diff is empty. (d) On a detected violation, revert the unauthorized changes (`git checkout --` / delete untracked files as appropriate) before proceeding, and never silently incorporate a fork's unauthorized writes into the discussion. (e) When multiple research investigations are needed, dispatch them serially, not in parallel — complete one dispatch and confirm a clean git-status diff before starting the next.
 
 **Fork echo caution.**
 A fork dispatched via `Agent(subagent_type: "fork")` shortly after the parent has just produced a similarly-shaped text block (e.g. the Step 2 scope digest) may, on its first turn, echo/restate that block instead of executing the assigned investigation directive.
diff --git a/plugins/mill/templates/implementer-brief.md b/plugins/mill/templates/implementer-brief.md
index 5bddf8ec..a786e99f 100644
--- a/plugins/mill/templates/implementer-brief.md
+++ b/plugins/mill/templates/implementer-brief.md
@@ -146,6 +146,11 @@ do not count them as part of the expected total when comparing your committed-ca
 Your free-text summary MUST state the real count honestly (e.g. "4 of 9 cards committed") — never write an unqualified "all complete"/"all done" claim without having actually verified the count this way.
 This applies regardless of which model is running this session: this check is what protects an operator who is only reading your chat summary from a false completion claim, independent of whatever the machine-readable JSON status line below says.
 
+**Never restate `commit_sha` in prose.** Your free-text summary may say the
+work is committed, but never write the SHA value (full or abbreviated)
+anywhere in prose -- the JSON line is the only place it appears. Restating it
+manually invites a transcription error the JSON line never has.
+
 Your last line of output (after all work and commits) MUST be a single JSON object:
 
 ```json
@@ -202,6 +207,13 @@ mill-go treats that as `stuck_type: logic` with reason "no structured report".
 To protect against this, emit the JSON line as the **first** non-tool content of your final assistant turn, before any optional commentary or further tool calls.
 Re-emit the JSON line at the end of the same turn as well — duplicate JSON is fine, `_implementer_common._forward_output` reads the last match.
 
+**Nothing follows the JSON line.** If you notice yourself starting a wrap-up
+paragraph after finishing implementation -- a "Note:", "Summary:", or any
+explanation of what you did or did not run -- stop and delete it before
+ending your turn. The JSON line above is the end of your turn; no prose,
+caveats, or notes may come after it, even ones that seem helpful to a human
+reader.
+
 ## On review resume
 
 If mill-go resumes this session with a new message pointing you at a code-review file, load the **mill-receiving-review** skill before reading any finding.
diff --git a/plugins/mill/unit_tests/test-implementer-common.py b/plugins/mill/unit_tests/test-implementer-common.py
index 4566d757..0bf16dc1 100644
--- a/plugins/mill/unit_tests/test-implementer-common.py
+++ b/plugins/mill/unit_tests/test-implementer-common.py
@@ -5455,6 +5455,100 @@ def main() -> int:
             print(f"FAIL: case 77 ({exc}) captured={captured!r}", file=sys.stderr)
             errors += 1
 
+    # Case 78: commit_sha_field_name="pre_merge_head" -> the corrective SHA is attached under
+    # the override key, and the default "commit_sha" key must not appear at all (#953).
+    with tempfile.TemporaryDirectory() as tmpdir:
+        project_root = Path(tmpdir)
+        base_sha = _setup_fixture(project_root)
+        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
+        _cleanliness.capture_snapshot(project_root, snapshot_path)
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
+            check=True,
+            capture_output=True,
+        )
+        new_head = subprocess.run(
+            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
+            check=True,
+            capture_output=True,
+            text=True,
+        ).stdout.strip()
+        agent_output = (
+            '{"status":"success","commit_sha":"abc","session_id":"test-session"}\n'
+        )
+        rc, captured = _capture_stdout(
+            lambda: _forward_output(
+                agent_output,
+                project_root,
+                start_sha=base_sha,
+                snapshot_path=snapshot_path,
+                verify_cmd=None,
+                commit_sha_field_name="pre_merge_head",
+            )
+        )
+        try:
+            data = json.loads(captured.strip())
+            assert data["status"] == "success", f"expected status=success, got {data}"
+            assert "commit_sha" not in data, (
+                f"expected no commit_sha key (renamed), got {data}"
+            )
+            assert data["pre_merge_head"] == new_head, (
+                f"expected pre_merge_head={new_head}, got {data}"
+            )
+            print(
+                "PASS: case 78 - commit_sha_field_name override renames the fallback"
+                " SHA field and drops the stale self-reported commit_sha key"
+            )
+        except Exception as exc:
+            print(f"FAIL: case 78 ({exc}) captured={captured!r}", file=sys.stderr)
+            errors += 1
+
+    # Case 79 (#932 regression): a truncated self-reported commit_sha (39 chars, one short of
+    # the real 40-char SHA) on the default field-name path must be discarded and replaced by the
+    # real git rev-parse HEAD value, not passed through.
+    with tempfile.TemporaryDirectory() as tmpdir:
+        project_root = Path(tmpdir)
+        base_sha = _setup_fixture(project_root)
+        snapshot_path = project_root / "_mill" / ".cleanliness-snapshot-test.txt"
+        _cleanliness.capture_snapshot(project_root, snapshot_path)
+        subprocess.run(
+            ["git", "-C", str(project_root), "commit", "--allow-empty", "-m", "second"],
+            check=True,
+            capture_output=True,
+        )
+        new_head = subprocess.run(
+            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
+            check=True,
+            capture_output=True,
+            text=True,
+        ).stdout.strip()
+        agent_output = (
+            '{"status":"success","commit_sha":"' + new_head[:-1]
+            + '","session_id":"test-session"}\n'
+        )
+        rc, captured = _capture_stdout(
+            lambda: _forward_output(
+                agent_output,
+                project_root,
+                start_sha=base_sha,
+                snapshot_path=snapshot_path,
+                verify_cmd=None,
+            )
+        )
+        try:
+            data = json.loads(captured.strip())
+            assert data["status"] == "success", f"expected status=success, got {data}"
+            assert data["commit_sha"] == new_head, (
+                f"expected commit_sha={new_head} (full, not truncated), got {data}"
+            )
+            print(
+                "PASS: case 79 - #932 truncated self-reported commit_sha is discarded and"
+                " replaced by the real git rev-parse HEAD value"
+            )
+        except Exception as exc:
+            print(f"FAIL: case 79 ({exc}) captured={captured!r}", file=sys.stderr)
+            errors += 1
+
     if errors:
         print(f"\n{errors} test(s) FAILED", file=sys.stderr)
         return 1
diff --git a/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py b/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
index 1bb85e72..4c31b9c6 100644
--- a/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
+++ b/plugins/mill/unit_tests/test-millpy-merge-in-subagent.py
@@ -591,6 +591,65 @@ class TestMillpyMergeInSubagent(unittest.TestCase):
             f"Expected no discarded field or empty list, got: {discarded!r}",
         )
 
+    def test_2x_conflicts_finalize_emits_pre_merge_head(self):
+        """--stage finalize conflicts mode: the corrective SHA is emitted as pre_merge_head, not
+        commit_sha (#953) -- HEAD at this point in the flow is still the pre-merge commit.
+        """
+        agent_output_path = self.tmp_path / "agent-output.txt"
+        agent_output_path.write_text(
+            '{"status":"success","commit_sha":"xyz"}\n',
+            encoding="utf-8"
+        )
+
+        with unittest.mock.patch.object(
+            millpy_merge_in_subagent._implementer_claude, "run"
+        ) as mock_run, \
+        unittest.mock.patch.object(
+            _implementer_common._subprocess_util, "run",
+            side_effect=_clean_gate_side_effect,
+        ):
+            rc, out = self._run_main([
+                "--mode", "conflicts",
+                "--files", "f.py",
+                "--stage", "finalize",
+                "--agent-output", str(agent_output_path),
+            ])
+
+        self.assertEqual(rc, 0)
+        mock_run.assert_not_called()
+        data = json.loads(out.strip())
+        self.assertEqual(data["status"], "success")
+        self.assertNotIn("commit_sha", data)
+        self.assertEqual(data["pre_merge_head"], "a" * 40)
+
+    def test_2x_conflicts_full_mode_emits_pre_merge_head(self):
+        """Full-mode conflicts success: the corrective SHA is emitted as pre_merge_head, not
+        commit_sha (#953), at the second conflicts-mode call site (_run_conflicts's own
+        _forward_output return).
+        """
+        with unittest.mock.patch.object(
+            millpy_merge_in_subagent._render, "render",
+            return_value="rendered",
+        ), \
+        unittest.mock.patch.object(
+            millpy_merge_in_subagent._implementer_claude, "run",
+            return_value=(
+                '{"status":"success"}\n',
+                "fake-session",
+            ),
+        ), \
+        unittest.mock.patch.object(
+            _implementer_common._subprocess_util, "run",
+            side_effect=_clean_gate_side_effect,
+        ):
+            rc, out = self._run_main(["--mode", "conflicts", "--files", "a.py"])
+
+        self.assertEqual(rc, 0)
+        data = json.loads(out.strip())
+        self.assertEqual(data["status"], "success")
+        self.assertNotIn("commit_sha", data)
+        self.assertEqual(data["pre_merge_head"], "a" * 40)
+
     def test_18_stage_finalize_verify_fix_reruns_verify(self):
         """--stage finalize verify-fix mode: re-runs verify, returns success if it passes."""
         agent_output_path = self.tmp_path / "agent-output.txt"
diff --git a/plugins/mill/unit_tests/test-plan-validate.py b/plugins/mill/unit_tests/test-plan-validate.py
index cdd10179..a50a789d 100644
--- a/plugins/mill/unit_tests/test-plan-validate.py
+++ b/plugins/mill/unit_tests/test-plan-validate.py
@@ -15,11 +15,13 @@ Check coverage:
   check 5 — parallel-modifies-overlap
   cross-batch-creates-no-depends-on (#887) — Context:/Edits: reference to a file another batch
       creates, with no depends-on edge to that creating batch
+  verify-batch-mismatch — a batch's overview Batch Index verify: disagrees with that batch file's
+      own frontmatter verify: (command or cwd)
   check 6 — reads-not-backtick-path (incl.
       none-exempt)
   check 8 — all-files-touched-mismatch
-  context-completeness (#742) — card Requirements: references a resolvable file-path-shaped token
-      absent from that card's own Context:/Edits:/Creates:/Deletes:/Moves:
+  context-completeness (#742) — card Requirements: references a resolvable file-path-shaped or
+      symbol-shaped token absent from that card's own Context:/Edits:/Creates:/Deletes:/Moves:
   verify cwd mapping form — verify-not-isolated/verify-full-suite accept the {cwd, command} mapping
       and the overview-level verify:;
       verify-malformed-cwd;
@@ -48,6 +50,13 @@ sys.path.insert(0, str(_UNIT_TESTS))
 # Fixture helpers
 # ---------------------------------------------------------------------------
 
+# Sentinel for _make_overview's per-entry `verify` override: signals "omit the verify: line
+# entirely from this Batch Index entry" (distinct from an explicit `verify: null`, even though both
+# normalize to the same `entry.get("verify") is None` result -- the two spellings are still tested
+# separately by the verify-batch-mismatch "absent" scenarios).
+_OMIT_VERIFY = object()
+
+
 def _make_overview(
     batches: list[dict],
     *,
@@ -56,12 +65,24 @@ def _make_overview(
 ) -> str:
     """Return 00-overview.md text.
 
-    Each batch dict: {name, file, number (optional), depends-on (optional, default [])}.
+    Each batch dict: {name, file, number (optional), depends-on (optional, default []),
+        verify (optional)}.
     all_files_touched: optional list of path strings for the section.
     overview_verify: optional module-wide verify: command string written into the overview's own
         frontmatter block (first fenced-yaml block, above the Batch Index).
         Omitted entirely when None, matching the plain real-world overview shape where module-wide
             verify: is optional.
+
+    Per-entry ``verify`` key (batch dict): when absent, the entry's ``verify:`` line renders as the
+    literal ``    verify: null`` exactly as before this override was added -- every existing caller
+    that omits this key is unaffected. When present, the caller controls the rendered line(s)
+    directly:
+      - ``_OMIT_VERIFY`` sentinel -> the ``verify:`` line is omitted entirely from this entry.
+      - ``None`` -> rendered as the literal ``verify: null`` (same text as the absent-key default,
+        provided for symmetry with the batch-file frontmatter's own explicit-null spelling).
+      - a plain string -> rendered verbatim as ``verify: <value>``.
+      - a ``{cwd: ..., command: ...}`` dict -> rendered as the nested mapping form, one sub-key per
+        dict key present (so a caller can omit ``cwd`` or ``command`` to test a malformed mapping).
     """
     entries = []
     for b in batches:
@@ -71,12 +92,27 @@ def _make_overview(
             first_line = f"  - number: {b['number']}\n    name: {b['name']}\n"
         else:
             first_line = f"  - name: {b['name']}\n"
-        entries.append(
+        base = (
             first_line
             + f"    file: {b['file']}\n"
-            + f"    depends-on: {deps_yaml}\n"
-            + "    verify: null"
-        )
+            + f"    depends-on: {deps_yaml}"
+        )
+        if "verify" not in b:
+            entries.append(base + "\n    verify: null")
+            continue
+        v = b["verify"]
+        if v is _OMIT_VERIFY:
+            entries.append(base)
+        elif isinstance(v, dict):
+            lines = ["    verify:"]
+            if "cwd" in v:
+                lines.append(f"      cwd: {v['cwd']}")
+            if "command" in v:
+                lines.append(f"      command: {v['command']}")
+            entries.append(base + "\n" + "\n".join(lines))
+        else:
+            rendered = "null" if v is None else v
+            entries.append(base + f"\n    verify: {rendered}")
     batch_list = "\n".join(entries)
     frontmatter = 'task: test\nslug: test-slug\nroot: ""\n'
     if overview_verify is not None:
@@ -233,6 +269,34 @@ def _make_verify_only_batch_text(
     )
 
 
+def _make_batch_verify_only_text(name: str, verify_block: str | None) -> str:
+    """Return a one-card batch file text with a caller-controlled own-frontmatter `verify:` block.
+
+    ``verify_block`` is the raw text spliced in place of the frontmatter's `verify:` value: e.g.
+    ``"null"``, a plain command string, or a multi-line mapping block (e.g.
+    ``"\\n  cwd: hub\\n  command: some cmd"``).
+    When ``None``, the `verify:` key is omitted from the frontmatter entirely -- the batch-file-side
+    counterpart to ``_make_overview``'s ``_OMIT_VERIFY`` "absent" case.
+    """
+    verify_line = "" if verify_block is None else f"verify: {verify_block}\n"
+    return (
+        f"# Batch: {name}\n\n"
+        "```yaml\n"
+        f"task: test\nbatch: {name}\ncards: 1\ndepends-on: []\n"
+        f"{verify_line}"
+        "```\n\n"
+        "## Cards\n\n"
+        "### Card 1: card 1\n\n"
+        "- **Context:** none\n"
+        "- **Edits:** none\n"
+        "- **Creates:** none\n"
+        "- **Deletes:** none\n"
+        "- **Moves:** none\n"
+        "- **Requirements:**\n  See scope.\n"
+        f"- **Commit:** feat({name}): card 1\n"
+    )
+
+
 def _git_commit_new_file(repo_root: Path, rel_path: str, content: str, message: str) -> None:
     """Write ``rel_path`` under ``repo_root`` and commit it onto the branch HEAD currently points to."""
     target = repo_root / rel_path
@@ -2472,6 +2536,118 @@ def test_check_context_completeness_dirty_citation_marker_absent() -> int:
             return 1
 
 
+def test_check_context_completeness_clean_signature_inlined_marker() -> int:
+    """Requirements: names a real, resolvable, backtick-wrapped file absent from the card's own refs, together with 'signature inlined' -> zero errors (inline-signature citation exemption)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
+        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/b.py"],
+            requirements=(
+                "  Call `helper()` (signature inlined from `src/a.py`: `def helper() -> int`).\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_clean_signature_inlined_marker")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_clean_signature_inlined_marker: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_clean_no_file_read_needed_marker() -> int:
+    """Same shape as the 'signature inlined' case, but the line instead carries 'no file read needed' -> zero errors (inline-signature citation exemption, second marker spelling)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
+        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/b.py"],
+            requirements=(
+                "  Call `helper()` (defined in `src/a.py` as `def helper() -> int`; "
+                "no file read needed).\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_clean_no_file_read_needed_marker")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_clean_no_file_read_needed_marker: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_dirty_inline_signature_marker_absent() -> int:
+    """Identical file reference and inlined signature, but with neither 'signature inlined' nor 'no file read needed' present -> one error, proving the exemption (not an unrelated change) is responsible."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "a.py").write_text("# placeholder", encoding="utf-8")
+        (project_root / "src" / "b.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/b.py"],
+            requirements=(
+                "  Call `helper()` (defined in `src/a.py` as `def helper() -> int`).\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 context-completeness error, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_dirty_inline_signature_marker_absent")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_dirty_inline_signature_marker_absent: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
 def test_check_context_completeness_clean_moves_source_plan_wide() -> int:
     """Requirements: token in a LATER batch names an EARLIER batch's Moves: source -> zero errors (plan-wide exemption)."""
     with tempfile.TemporaryDirectory() as tmpdir:
@@ -2867,256 +3043,960 @@ def test_check_context_completeness_dirty_prohibition_marker_verb_without_negati
             return 1
 
 
-def test_check_requirements_quote_indent_drift_clean_exact_match() -> int:
-    """Fence content is already a byte-exact substring of the target Edits: file -> no error."""
+# symbol-reference context-completeness (bare/dotted identifiers, not just paths)
+def test_check_context_completeness_symbol_clean_in_context() -> int:
+    """A bare symbol token (`SaveState`) resolves to exactly one fixture file, which IS in the
+    card's own Context: -> zero errors."""
     with tempfile.TemporaryDirectory() as tmpdir:
         tmp = Path(tmpdir)
         plan_dir = tmp / "plan"
         project_root = tmp / "project"
         project_root.mkdir()
-        (project_root / "src").mkdir()
-        (project_root / "src" / "target.py").write_text(
-            "def helper():\n    return 1\n", encoding="utf-8",
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nfunc SaveState() {}\n", encoding="utf-8"
         )
 
         overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
         batch = _make_batch_file(
             "alpha",
-            edits=["src/target.py"],
-            requirements=(
-                "  Quote:\n"
-                "```\n"
-                "def helper():\n"
-                "    return 1\n"
-                "```\n"
-            ),
+            context=["internal/state.go"],
+            requirements="  Call `SaveState` when the batch completes.\n",
         )
         _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
 
         result = _plan_validate.run(plan_dir, project_root)
-        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
         try:
             assert len(check_errors) == 0, (
-                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+                f"expected 0 context-completeness errors, got: {check_errors}"
             )
-            print("PASS test_check_requirements_quote_indent_drift_clean_exact_match")
+            print("PASS test_check_context_completeness_symbol_clean_in_context")
             return 0
         except AssertionError as exc:
             print(
-                f"FAIL test_check_requirements_quote_indent_drift_clean_exact_match: {exc}",
+                f"FAIL test_check_context_completeness_symbol_clean_in_context: {exc}",
                 file=sys.stderr,
             )
             return 1
 
 
-def test_check_requirements_quote_indent_drift_clean_illustrative_snippet() -> int:
-    """Fence shows plausible but different code, not a substring at any N in 1..40 -> no error."""
+def test_check_context_completeness_symbol_dirty_missing() -> int:
+    """A bare symbol token (`SaveState`) resolves to exactly one fixture file, absent from the
+    card's own refs -> one error naming the resolved path."""
     with tempfile.TemporaryDirectory() as tmpdir:
         tmp = Path(tmpdir)
         plan_dir = tmp / "plan"
         project_root = tmp / "project"
         project_root.mkdir()
-        (project_root / "src").mkdir()
-        (project_root / "src" / "target.py").write_text(
-            "def helper():\n    return 1\n", encoding="utf-8",
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nfunc SaveState() {}\n", encoding="utf-8"
         )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
 
         overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
         batch = _make_batch_file(
             "alpha",
-            edits=["src/target.py"],
-            requirements=(
-                "  Illustrative:\n"
-                "```\n"
-                "def other_func():\n"
-                "    return 999\n"
-                "```\n"
-            ),
+            edits=["other.py"],
+            requirements="  Call `SaveState` when the batch completes.\n",
         )
         _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
 
         result = _plan_validate.run(plan_dir, project_root)
-        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
         try:
-            assert len(check_errors) == 0, (
-                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+            assert len(check_errors) == 1, (
+                f"expected 1 context-completeness error, got: {check_errors}"
             )
-            print("PASS test_check_requirements_quote_indent_drift_clean_illustrative_snippet")
+            e = check_errors[0]
+            assert "which resolves to 'internal/state.go'" in e["message"], (
+                f"wrong message: {e['message']!r}"
+            )
+            assert e["path"] == "SaveState", f"wrong path: {e['path']!r}"
+            print("PASS test_check_context_completeness_symbol_dirty_missing")
             return 0
         except AssertionError as exc:
             print(
-                f"FAIL test_check_requirements_quote_indent_drift_clean_illustrative_snippet: {exc}",
+                f"FAIL test_check_context_completeness_symbol_dirty_missing: {exc}",
                 file=sys.stderr,
             )
             return 1
 
 
-def test_check_requirements_quote_indent_drift_clean_no_edits_field() -> int:
-    """Card's Edits: is none -> check is a no-op, nothing to compare against."""
+def test_check_context_completeness_symbol_clean_zero_matches() -> int:
+    """An identifier-shaped token that appears nowhere in the fixture project's source files ->
+    zero errors (unresolvable, not flagged)."""
     with tempfile.TemporaryDirectory() as tmpdir:
         tmp = Path(tmpdir)
         plan_dir = tmp / "plan"
         project_root = tmp / "project"
         project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nfunc SaveState() {}\n", encoding="utf-8"
+        )
 
         overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
         batch = _make_batch_file(
             "alpha",
-            edits=None,
-            requirements=(
-                "  Quote:\n"
-                "```\n"
-                "def helper():\n"
-                "    return 1\n"
-                "```\n"
-            ),
+            edits=["internal/state.go"],
+            requirements="  `RemapZone` is unrelated to any fixture file here.\n",
         )
         _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
 
         result = _plan_validate.run(plan_dir, project_root)
-        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
         try:
             assert len(check_errors) == 0, (
-                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+                f"expected 0 context-completeness errors, got: {check_errors}"
             )
-            print("PASS test_check_requirements_quote_indent_drift_clean_no_edits_field")
+            print("PASS test_check_context_completeness_symbol_clean_zero_matches")
             return 0
         except AssertionError as exc:
             print(
-                f"FAIL test_check_requirements_quote_indent_drift_clean_no_edits_field: {exc}",
+                f"FAIL test_check_context_completeness_symbol_clean_zero_matches: {exc}",
                 file=sys.stderr,
             )
             return 1
 
 
-def test_check_requirements_quote_indent_drift_dirty_list_continuation_indent() -> int:
-    """Flush-left source snippet, fence has a uniform 2-space list-continuation indent baked in."""
+def test_check_context_completeness_symbol_clean_ambiguous_matches() -> int:
+    """An identifier-shaped token appearing in two distinct fixture files -> zero errors
+    (ambiguous, not flagged)."""
     with tempfile.TemporaryDirectory() as tmpdir:
         tmp = Path(tmpdir)
         plan_dir = tmp / "plan"
         project_root = tmp / "project"
         project_root.mkdir()
-        (project_root / "src").mkdir()
-        (project_root / "src" / "target.py").write_text(
-            "alpha\nbeta\ngamma\n", encoding="utf-8",
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "a.go").write_text(
+            "package internal\n\nfunc RemapZone() {}\n", encoding="utf-8"
         )
+        (project_root / "internal" / "b.go").write_text(
+            "package internal\n\nfunc RemapZone() {}\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
 
         overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
         batch = _make_batch_file(
             "alpha",
-            edits=["src/target.py"],
-            requirements=(
-                "  Quote:\n"
-                "  ```\n"
-                "  alpha\n"
-                "  beta\n"
-                "  gamma\n"
-                "  ```\n"
-            ),
+            edits=["other.py"],
+            requirements="  `RemapZone` appears in two places here.\n",
         )
         _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
 
         result = _plan_validate.run(plan_dir, project_root)
-        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
         try:
-            assert len(check_errors) == 1, (
-                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
             )
-            e = check_errors[0]
-            assert e["card"] == 1, f"wrong card: {e['card']!r}"
-            assert e["path"] == "src/target.py", f"wrong path: {e['path']!r}"
-            assert "N=2" in e["message"], f"message missing N=2: {e['message']!r}"
-            print("PASS test_check_requirements_quote_indent_drift_dirty_list_continuation_indent")
+            print("PASS test_check_context_completeness_symbol_clean_ambiguous_matches")
             return 0
         except AssertionError as exc:
             print(
-                f"FAIL test_check_requirements_quote_indent_drift_dirty_list_continuation_indent: {exc}",
+                f"FAIL test_check_context_completeness_symbol_clean_ambiguous_matches: {exc}",
                 file=sys.stderr,
             )
             return 1
 
 
-def test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent() -> int:
-    """Source has its own 4-space baseline indent; fence adds a further uniform 2 spaces on top."""
+def test_check_context_completeness_symbol_call_site_phrasing() -> int:
+    """`SaveState()` behaves identically to bare `SaveState` -- suffix stripping does not change
+    the shape/resolution outcome, and a flagged finding's path preserves the call-suffix."""
     with tempfile.TemporaryDirectory() as tmpdir:
         tmp = Path(tmpdir)
         plan_dir = tmp / "plan"
         project_root = tmp / "project"
         project_root.mkdir()
-        (project_root / "src").mkdir()
-        (project_root / "src" / "target.py").write_text(
-            "    alpha\n    beta\n", encoding="utf-8",
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nfunc SaveState() {}\n", encoding="utf-8"
         )
 
-        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
-        batch = _make_batch_file(
+        overview = _make_overview(
+            [{"name": "alpha", "file": "01-alpha.md"}, {"name": "beta", "file": "02-beta.md"}]
+        )
+        clean_batch = _make_batch_file(
             "alpha",
-            edits=["src/target.py"],
-            requirements=(
-                "  Quote:\n"
-                "  ```\n"
-                "      alpha\n"
-                "      beta\n"
-                "  ```\n"
-            ),
+            context=["internal/state.go"],
+            requirements="  Call `SaveState()` when the batch completes.\n",
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+        dirty_batch = _make_batch_file(
+            "beta",
+            edits=["other.py"],
+            requirements="  Call `SaveState()` when the batch completes.\n",
+        )
+        _write_plan(
+            plan_dir, overview, [("01-alpha.md", clean_batch), ("02-beta.md", dirty_batch)]
         )
-        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
 
         result = _plan_validate.run(plan_dir, project_root)
-        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
         try:
             assert len(check_errors) == 1, (
-                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+                f"expected 1 context-completeness error, got: {check_errors}"
             )
             e = check_errors[0]
-            assert "N=2" in e["message"], f"message missing N=2: {e['message']!r}"
-            print("PASS test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent")
+            assert e["batch"] == "02-beta", f"wrong batch: {e['batch']!r}"
+            assert e["path"] == "SaveState()", f"wrong path: {e['path']!r}"
+            assert "which resolves to 'internal/state.go'" in e["message"], (
+                f"wrong message: {e['message']!r}"
+            )
+            print("PASS test_check_context_completeness_symbol_call_site_phrasing")
             return 0
         except AssertionError as exc:
             print(
-                f"FAIL test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent: {exc}",
+                f"FAIL test_check_context_completeness_symbol_call_site_phrasing: {exc}",
                 file=sys.stderr,
             )
             return 1
 
 
-def test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card() -> int:
-    """Two fences under one card; only the second has the drift bug -> exactly one error, fence 2."""
+def test_check_context_completeness_symbol_all_lowercase_not_candidate() -> int:
+    """An all-lowercase bare token (`config`) is never flagged, even when a fixture file contains
+    the literal text `config` exactly once (single unambiguous match) and it is absent from the
+    card's own refs -- the shape gate excludes it before resolution ever runs."""
     with tempfile.TemporaryDirectory() as tmpdir:
         tmp = Path(tmpdir)
         plan_dir = tmp / "plan"
         project_root = tmp / "project"
         project_root.mkdir()
-        (project_root / "src").mkdir()
-        (project_root / "src" / "target.py").write_text(
-            "first_line\nsecond_line\nthird_line\nfourth_line\n", encoding="utf-8",
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "config.go").write_text(
+            "package internal\n\nvar config = 1\n", encoding="utf-8"
         )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
 
         overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
         batch = _make_batch_file(
             "alpha",
-            edits=["src/target.py"],
-            requirements=(
-                "  Clean fence:\n"
-                "```\n"
-                "first_line\n"
-                "second_line\n"
-                "```\n"
-                "  Drifted fence:\n"
-                "  ```\n"
-                "   third_line\n"
-                "   fourth_line\n"
-                "  ```\n"
-            ),
+            edits=["other.py"],
+            requirements="  The `config` value is read at startup.\n",
         )
         _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
 
         result = _plan_validate.run(plan_dir, project_root)
-        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
         try:
-            assert len(check_errors) == 1, (
-                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
-            )
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_symbol_all_lowercase_not_candidate")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_symbol_all_lowercase_not_candidate: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_all_lowercase_dotted_not_candidate() -> int:
+    """A dotted, all-lowercase token (`config.example`) is never flagged, even when resolvable to
+    exactly one fixture file via its trailing segment."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "example.go").write_text(
+            "package internal\n\nvar example = 1\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  The `config.example` value is read at startup.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_symbol_all_lowercase_dotted_not_candidate")
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_context_completeness_symbol_all_lowercase_dotted_not_candidate: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_single_capitalized_is_candidate() -> int:
+    """A single-capitalized bare word (`New`) resolves to exactly one fixture file, absent from
+    own refs -> one error (the "not entirely lowercase" signal admits a single-capitalized bare
+    word, not only internally-capitalized CamelCase)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "factory.go").write_text(
+            "package internal\n\nfunc New() {}\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  Call `New` to construct the instance.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 context-completeness error, got: {check_errors}"
+            )
+            e = check_errors[0]
+            assert e["path"] == "New", f"wrong path: {e['path']!r}"
+            assert "which resolves to 'internal/factory.go'" in e["message"], (
+                f"wrong message: {e['message']!r}"
+            )
+            print("PASS test_check_context_completeness_symbol_single_capitalized_is_candidate")
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_context_completeness_symbol_single_capitalized_is_candidate: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_dotted_trailing_segment_only() -> int:
+    """A dotted token (`reedengine.New`) resolves via its trailing segment (`New`) even though the
+    fixture file's declaration line contains only the unqualified name, never the qualified dotted
+    form -- confirms resolution uses the trailing segment as the search key, not the literal
+    dotted text."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "factory.go").write_text(
+            "package reedengine\n\nfunc New(...) {}\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  Call `reedengine.New` to construct the engine.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 context-completeness error, got: {check_errors}"
+            )
+            e = check_errors[0]
+            assert e["path"] == "reedengine.New", f"wrong path: {e['path']!r}"
+            assert "which resolves to 'internal/factory.go'" in e["message"], (
+                f"wrong message: {e['message']!r}"
+            )
+            print("PASS test_check_context_completeness_symbol_dotted_trailing_segment_only")
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_context_completeness_symbol_dotted_trailing_segment_only: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_dotted_ambiguous_trailing_segment() -> int:
+    """The trailing segment of a dotted candidate (`Commit` in `batch.Commit`) appears in two
+    unrelated fixture files -> zero errors (ambiguous-skip)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "a.go").write_text(
+            "package internal\n\nfunc Commit() {}\n", encoding="utf-8"
+        )
+        (project_root / "internal" / "b.go").write_text(
+            "package internal\n\nfunc Commit() {}\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  Call `batch.Commit` to persist the batch.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_symbol_dotted_ambiguous_trailing_segment")
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_context_completeness_symbol_dotted_ambiguous_trailing_segment: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_dotted_qualifying_prefix_nonqualifying_trailing() -> int:
+    """A dotted token whose qualifier segment qualifies but whose trailing segment does not
+    (`Foo.bar` -- `Foo` is capitalized, `bar` is plain lowercase), resolvable to exactly one
+    fixture file containing the literal text `bar`, absent from own refs -> zero errors. The
+    qualifier's own capitalization never rescues a non-qualifying trailing segment."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "bar.go").write_text(
+            "package internal\n\nvar bar = 1\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  Read `Foo.bar` for the shared value.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print(
+                "PASS test_check_context_completeness_symbol_dotted_qualifying_prefix_nonqualifying_trailing"
+            )
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_context_completeness_symbol_dotted_qualifying_prefix_nonqualifying_trailing: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_first_match_wins_root_precedence() -> int:
+    """Regression test for the resolvability-gate's root-precedence design: a symbol resolvable
+    under both git_root/root and bare git_root must resolve to the git_root/root candidate only
+    (first-match-wins), never union across both roots.
+
+    Deliberately a dirty (flagged) case, not a clean one: correct first-match-wins behavior finds
+    exactly one match (under git_root/root, stopping before ever walking bare git_root) and flags
+    it; the rejected "union across all roots" behavior would instead find two matches across both
+    roots and skip as ambiguous (0 errors) -- a clean-only fixture could not distinguish the two
+    behaviors."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        git_root = tmp / "repo"
+        root = "subproject"
+        project_root = git_root / root
+        plan_dir = git_root / "plan"
+
+        project_root.mkdir(parents=True)
+        subproject_file = project_root / "internal" / "state.go"
+        subproject_file.parent.mkdir(parents=True)
+        subproject_file.write_text("package internal\n\nfunc New() {}\n", encoding="utf-8")
+
+        other_file = git_root / "other" / "somewhere.go"
+        other_file.parent.mkdir(parents=True)
+        other_file.write_text("package other\n\nfunc New() {}\n", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            requirements="  Call `New` to construct the instance.\n",
+        )
+        plan_dir.mkdir(parents=True)
+        (plan_dir / "00-overview.md").write_text(overview, encoding="utf-8")
+        (plan_dir / "01-alpha.md").write_text(batch, encoding="utf-8")
+
+        result = _plan_validate.run(plan_dir, project_root, root=root, git_root=git_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 context-completeness error, got: {check_errors}"
+            )
+            assert "which resolves to 'internal/state.go'" in check_errors[0]["message"], (
+                f"wrong message: {check_errors[0]['message']!r}"
+            )
+            print("PASS test_check_context_completeness_symbol_first_match_wins_root_precedence")
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_context_completeness_symbol_first_match_wins_root_precedence: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_cache_invoked_once_per_key() -> int:
+    """The same symbol (`SaveState`) is named in two different cards' Requirements:, each
+    resolvable via the same fixture file -> the shared search_cache means the underlying
+    filesystem walk for "SaveState" runs once, not once per occurrence."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nfunc SaveState() {}\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview(
+            [{"name": "alpha", "file": "01-alpha.md"}, {"name": "beta", "file": "02-beta.md"}]
+        )
+        batch_alpha = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  Call `SaveState` when the batch completes.\n",
+        )
+        batch_beta = _make_batch_file(
+            "beta",
+            edits=["other.py"],
+            requirements="  Call `SaveState` when the batch completes.\n",
+        )
+        _write_plan(
+            plan_dir, overview, [("01-alpha.md", batch_alpha), ("02-beta.md", batch_beta)]
+        )
+
+        original = _plan_validate._resolve_symbol_files
+        call_count = [0]
+
+        def counting_wrapper(*args, **kwargs):
+            call_count[0] += 1
+            return original(*args, **kwargs)
+
+        _plan_validate._resolve_symbol_files = counting_wrapper
+        try:
+            result = _plan_validate.run(plan_dir, project_root)
+        finally:
+            _plan_validate._resolve_symbol_files = original
+
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 2, (
+                f"expected 2 context-completeness errors, got: {check_errors}"
+            )
+            assert call_count[0] == 1, (
+                f"expected _resolve_symbol_files invoked once, got: {call_count[0]}"
+            )
+            print("PASS test_check_context_completeness_symbol_cache_invoked_once_per_key")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_symbol_cache_invoked_once_per_key: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_prohibition_marker_exempt() -> int:
+    """A resolvable, own-refs-absent symbol named inside a same-line prohibition -> zero errors,
+    mirroring the existing path-branch prohibition-exemption test."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nfunc SaveState() {}\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  Do not touch `SaveState`.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_symbol_prohibition_marker_exempt")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_symbol_prohibition_marker_exempt: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_citation_marker_exempt() -> int:
+    """A resolvable, own-refs-absent symbol named as an illustrative example -> zero errors,
+    mirroring the existing path-branch citation-exemption test."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nfunc SaveState() {}\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  For example, `SaveState` illustrates the pattern.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 context-completeness errors, got: {check_errors}"
+            )
+            print("PASS test_check_context_completeness_symbol_citation_marker_exempt")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_symbol_citation_marker_exempt: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_context_completeness_symbol_underscore_qualifies() -> int:
+    """An all-lowercase, underscore-containing bare token (`save_state`) resolves to exactly one
+    fixture file, absent from own refs -> one error. Confirms qualifies()'s "contains underscore"
+    OR-branch admits a candidate on its own, independent of the capitalization branch."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "internal").mkdir()
+        (project_root / "internal" / "state.go").write_text(
+            "package internal\n\nvar save_state = 1\n", encoding="utf-8"
+        )
+        (project_root / "other.py").write_text("# placeholder", encoding="utf-8")
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["other.py"],
+            requirements="  Read `save_state` before writing.\n",
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "context-completeness"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 context-completeness error, got: {check_errors}"
+            )
+            e = check_errors[0]
+            assert e["path"] == "save_state", f"wrong path: {e['path']!r}"
+            assert "which resolves to 'internal/state.go'" in e["message"], (
+                f"wrong message: {e['message']!r}"
+            )
+            print("PASS test_check_context_completeness_symbol_underscore_qualifies")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_context_completeness_symbol_underscore_qualifies: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_clean_exact_match() -> int:
+    """Fence content is already a byte-exact substring of the target Edits: file -> no error."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "def helper():\n    return 1\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "```\n"
+                "def helper():\n"
+                "    return 1\n"
+                "```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_clean_exact_match")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_clean_exact_match: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_clean_illustrative_snippet() -> int:
+    """Fence shows plausible but different code, not a substring at any N in 1..40 -> no error."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "def helper():\n    return 1\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Illustrative:\n"
+                "```\n"
+                "def other_func():\n"
+                "    return 999\n"
+                "```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_clean_illustrative_snippet")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_clean_illustrative_snippet: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_clean_no_edits_field() -> int:
+    """Card's Edits: is none -> check is a no-op, nothing to compare against."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=None,
+            requirements=(
+                "  Quote:\n"
+                "```\n"
+                "def helper():\n"
+                "    return 1\n"
+                "```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_clean_no_edits_field")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_clean_no_edits_field: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_dirty_list_continuation_indent() -> int:
+    """Flush-left source snippet, fence has a uniform 2-space list-continuation indent baked in."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "alpha\nbeta\ngamma\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "  ```\n"
+                "  alpha\n"
+                "  beta\n"
+                "  gamma\n"
+                "  ```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            )
+            e = check_errors[0]
+            assert e["card"] == 1, f"wrong card: {e['card']!r}"
+            assert e["path"] == "src/target.py", f"wrong path: {e['path']!r}"
+            assert "N=2" in e["message"], f"message missing N=2: {e['message']!r}"
+            print("PASS test_check_requirements_quote_indent_drift_dirty_list_continuation_indent")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_dirty_list_continuation_indent: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent() -> int:
+    """Source has its own 4-space baseline indent; fence adds a further uniform 2 spaces on top."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "    alpha\n    beta\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "  ```\n"
+                "      alpha\n"
+                "      beta\n"
+                "  ```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            )
+            e = check_errors[0]
+            assert "N=2" in e["message"], f"message missing N=2: {e['message']!r}"
+            print("PASS test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_dirty_nonzero_baseline_indent: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card() -> int:
+    """Two fences under one card; only the second has the drift bug -> exactly one error, fence 2."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "first_line\nsecond_line\nthird_line\nfourth_line\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Clean fence:\n"
+                "```\n"
+                "first_line\n"
+                "second_line\n"
+                "```\n"
+                "  Drifted fence:\n"
+                "  ```\n"
+                "   third_line\n"
+                "   fourth_line\n"
+                "  ```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            )
             e = check_errors[0]
             assert "fence 2" in e["message"], f"message missing fence 2: {e['message']!r}"
             print("PASS test_check_requirements_quote_indent_drift_dirty_multiple_fences_one_card")
@@ -3302,7 +4182,285 @@ def test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_clos
         project_root.mkdir()
         (project_root / "src").mkdir()
         (project_root / "src" / "target.py").write_text(
-            "value = compute(x, y) + offset\n", encoding="utf-8",
+            "value = compute(x, y) + offset\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "```\n"
+                "compute(x, y)\n"
+                "```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer() -> int:
+    """Byte-exact quoted content, closing fence carries list-continuation indentation -> clean (#754: previously fell through to the N-search and matched via incidental adjacent-content coincidence instead of the byte-exact pre-check)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "alpha\nbeta\ngamma\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "```\n"
+                "beta\n"
+                "gamma\n"
+                "  ```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 0, (
+                f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence() -> int:
+    """Source has a 2-space baseline indent, fence is flattened to column zero -> one finding, message states it matched after ADDING 2 leading spaces per line (the under-indent direction, #the add pass)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "  alpha\n  beta\n  gamma\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "```\n"
+                "alpha\n"
+                "beta\n"
+                "gamma\n"
+                "```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            )
+            e = check_errors[0]
+            assert e["path"] == "src/target.py", f"wrong path: {e['path']!r}"
+            assert "after adding 2 leading spaces per line" in e["message"], (
+                f"message should state the add direction: {e['message']!r}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence")
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line() -> int:
+    """Same under-indent shape, but the source excerpt's separator line is genuinely empty -> still detected via the default non-blank-only add variant."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "  alpha\n\n  beta\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "```\n"
+                "alpha\n"
+                "\n"
+                "beta\n"
+                "```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            )
+            assert "after adding 2 leading spaces per line" in check_errors[0]["message"], (
+                f"message should state the add direction: {check_errors[0]['message']!r}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line")
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line() -> int:
+    """Same under-indent shape, but the source's separator line is whitespace-only with its own indent (not genuinely empty) -> still detected, exercising the include_blank=True add variant."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "  alpha\n  \n  beta\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "```\n"
+                "alpha\n"
+                "\n"
+                "beta\n"
+                "```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            )
+            assert "after adding 2 leading spaces per line" in check_errors[0]["message"], (
+                f"message should state the add direction: {check_errors[0]['message']!r}"
+            )
+            print(
+                "PASS test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line"
+            )
+            return 0
+        except AssertionError as exc:
+            print(
+                "FAIL test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line: "
+                f"{exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen() -> int:
+    """An existing over-indented fence still produces the unchanged 'after stripping N leading spaces per line' message, asserted on the exact message text so a regression in the frozen wording fails the test."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "alpha\nbeta\ngamma\n", encoding="utf-8",
+        )
+
+        overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
+        batch = _make_batch_file(
+            "alpha",
+            edits=["src/target.py"],
+            requirements=(
+                "  Quote:\n"
+                "  ```\n"
+                "  alpha\n"
+                "  beta\n"
+                "  gamma\n"
+                "  ```\n"
+            ),
+        )
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        check_errors = [e for e in result if e["check"] == "requirements-quote-indent-drift"]
+        try:
+            assert len(check_errors) == 1, (
+                f"expected 1 requirements-quote-indent-drift error, got: {check_errors}"
+            )
+            expected = (
+                "card 1's Requirements: fence 1 matches 'src/target.py' after stripping 2 "
+                "leading spaces per line (found N=2)"
+            )
+            assert check_errors[0]["message"] == expected, (
+                f"frozen message wording regressed: {check_errors[0]['message']!r}"
+            )
+            print("PASS test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact() -> int:
+    """Fence content is already a byte-exact substring of the target Edits: file -> no error (regression guard: the byte-exact pre-check must still win before the add pass ever runs)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+        (project_root / "src").mkdir()
+        (project_root / "src" / "target.py").write_text(
+            "  alpha\n  beta\n", encoding="utf-8",
         )
 
         overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
@@ -3311,9 +4469,10 @@ def test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_clos
             edits=["src/target.py"],
             requirements=(
                 "  Quote:\n"
-                "```\n"
-                "compute(x, y)\n"
-                "```\n"
+                "  ```\n"
+                "  alpha\n"
+                "  beta\n"
+                "  ```\n"
             ),
         )
         _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
@@ -3324,18 +4483,18 @@ def test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_clos
             assert len(check_errors) == 0, (
                 f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
             )
-            print("PASS test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer")
+            print("PASS test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact")
             return 0
         except AssertionError as exc:
             print(
-                f"FAIL test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer: {exc}",
+                f"FAIL test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact: {exc}",
                 file=sys.stderr,
             )
             return 1
 
 
-def test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer() -> int:
-    """Byte-exact quoted content, closing fence carries list-continuation indentation -> clean (#754: previously fell through to the N-search and matched via incidental adjacent-content coincidence instead of the byte-exact pre-check)."""
+def test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match() -> int:
+    """Fence shows plausible but different code, not a substring at any N in 1..40 in either direction -> no error."""
     with tempfile.TemporaryDirectory() as tmpdir:
         tmp = Path(tmpdir)
         plan_dir = tmp / "plan"
@@ -3343,7 +4502,7 @@ def test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer(
         project_root.mkdir()
         (project_root / "src").mkdir()
         (project_root / "src" / "target.py").write_text(
-            "alpha\nbeta\ngamma\n", encoding="utf-8",
+            "  alpha\n  beta\n", encoding="utf-8",
         )
 
         overview = _make_overview([{"name": "alpha", "file": "01-alpha.md"}])
@@ -3351,11 +4510,11 @@ def test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer(
             "alpha",
             edits=["src/target.py"],
             requirements=(
-                "  Quote:\n"
+                "  Illustrative:\n"
                 "```\n"
-                "beta\n"
                 "gamma\n"
-                "  ```\n"
+                "delta\n"
+                "```\n"
             ),
         )
         _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
@@ -3366,11 +4525,14 @@ def test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer(
             assert len(check_errors) == 0, (
                 f"expected 0 requirements-quote-indent-drift errors, got: {check_errors}"
             )
-            print("PASS test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer")
+            print(
+                "PASS test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match"
+            )
             return 0
         except AssertionError as exc:
             print(
-                f"FAIL test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer: {exc}",
+                "FAIL test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match: "
+                f"{exc}",
                 file=sys.stderr,
             )
             return 1
@@ -5440,6 +6602,353 @@ def test_check_verify_mixed_cwd_single_cwd_clean() -> int:
         return 0
 
 
+# ---------------------------------------------------------------------------
+# verify-batch-mismatch check (Card 6)
+# ---------------------------------------------------------------------------
+
+def test_verify_batch_mismatch_clean_identical_string() -> int:
+    """Clean: identical plain-string verify: on both the overview entry and the batch file -> no finding."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "some cmd")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        if mismatch:
+            print(f"FAIL test_verify_batch_mismatch_clean_identical_string: unexpected: {mismatch}",
+                  file=sys.stderr)
+            return 1
+        print("PASS test_verify_batch_mismatch_clean_identical_string")
+        return 0
+
+
+def test_verify_batch_mismatch_dirty_null_vs_command() -> int:
+    """Dirty: overview names a real command, batch file's own verify: is null -> exactly one finding naming that batch."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "null")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        try:
+            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
+            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
+            print("PASS test_verify_batch_mismatch_dirty_null_vs_command")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_batch_mismatch_dirty_null_vs_command: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_batch_mismatch_dirty_trailing_clause() -> int:
+    """Dirty: overview and batch commands differ only by a trailing clause -> exactly one finding."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": "pytest test_foo.py"},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "pytest test_foo.py -k mytest")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        try:
+            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
+            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
+            print("PASS test_verify_batch_mismatch_dirty_trailing_clause")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_batch_mismatch_dirty_trailing_clause: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_batch_mismatch_clean_absent_vs_null() -> int:
+    """Clean: verify: absent from the overview entry, explicitly null on the batch file -> no finding."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": _OMIT_VERIFY},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "null")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        if mismatch:
+            print(f"FAIL test_verify_batch_mismatch_clean_absent_vs_null: unexpected: {mismatch}",
+                  file=sys.stderr)
+            return 1
+        print("PASS test_verify_batch_mismatch_clean_absent_vs_null")
+        return 0
+
+
+def test_verify_batch_mismatch_clean_both_absent() -> int:
+    """Clean: verify: key absent from both the overview entry and the batch file's own frontmatter -> no finding."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": _OMIT_VERIFY},
+        ])
+        batch = _make_batch_verify_only_text("alpha", None)
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        if mismatch:
+            print(f"FAIL test_verify_batch_mismatch_clean_both_absent: unexpected: {mismatch}",
+                  file=sys.stderr)
+            return 1
+        print("PASS test_verify_batch_mismatch_clean_both_absent")
+        return 0
+
+
+def test_verify_batch_mismatch_clean_both_null() -> int:
+    """Clean: verify: explicitly null on both the overview entry and the batch file -> no finding."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": None},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "null")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        if mismatch:
+            print(f"FAIL test_verify_batch_mismatch_clean_both_null: unexpected: {mismatch}",
+                  file=sys.stderr)
+            return 1
+        print("PASS test_verify_batch_mismatch_clean_both_null")
+        return 0
+
+
+def test_verify_batch_mismatch_dirty_string_vs_mapping_cwd() -> int:
+    """Dirty: overview has a plain-string verify:, batch file has the same command as a {cwd: git_root, ...} mapping -> one finding, because the raw cwd keys differ (None vs 'git_root')."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "\n  cwd: git_root\n  command: some cmd")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        try:
+            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
+            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
+            print("PASS test_verify_batch_mismatch_dirty_string_vs_mapping_cwd")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_batch_mismatch_dirty_string_vs_mapping_cwd: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_batch_mismatch_clean_matching_mapping() -> int:
+    """Clean: identical {cwd, command} mapping form on both sides -> no finding."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": {"cwd": "hub", "command": "some cmd"}},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "\n  cwd: hub\n  command: some cmd")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        if mismatch:
+            print(f"FAIL test_verify_batch_mismatch_clean_matching_mapping: unexpected: {mismatch}",
+                  file=sys.stderr)
+            return 1
+        print("PASS test_verify_batch_mismatch_clean_matching_mapping")
+        return 0
+
+
+def test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root() -> int:
+    """Dirty: identical command, but cwd: hub on the overview side vs cwd: git_root on the batch side -> one finding."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": {"cwd": "hub", "command": "some cmd"}},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "\n  cwd: git_root\n  command: some cmd")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        try:
+            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
+            assert mismatch[0]["batch"] == "alpha", f"wrong batch: {mismatch[0]['batch']!r}"
+            print("PASS test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_batch_mismatch_dirty_overview_malformed_mapping() -> int:
+    """Dirty: the overview entry's verify: mapping has no command: -> exactly one verify-batch-mismatch finding whose message contains the normalizer's error text, and no verify-malformed-cwd finding for that entry (the overview side is check-verify-batch-mismatch's sole reporter)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": {"cwd": "hub"}},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "null")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        malformed = [e for e in result if e["check"] == "verify-malformed-cwd"]
+        try:
+            assert len(mismatch) == 1, f"expected 1 finding, got {len(mismatch)}: {mismatch}"
+            assert "command" in mismatch[0]["message"], (
+                f"message should quote the normalizer's error text: {mismatch[0]['message']!r}"
+            )
+            assert len(malformed) == 0, f"expected no verify-malformed-cwd finding, got: {malformed}"
+            print("PASS test_verify_batch_mismatch_dirty_overview_malformed_mapping")
+            return 0
+        except AssertionError as exc:
+            print(f"FAIL test_verify_batch_mismatch_dirty_overview_malformed_mapping: {exc}", file=sys.stderr)
+            return 1
+
+
+def test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report() -> int:
+    """Clean (for this check): the batch file's own verify: mapping has no command: -> zero verify-batch-mismatch findings, exactly one verify-malformed-cwd finding (that check is the sole reporter for the batch-file side)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": "null"},
+        ])
+        batch = _make_batch_verify_only_text("alpha", "\n  cwd: hub")
+        _write_plan(plan_dir, overview, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        malformed = [e for e in result if e["check"] == "verify-malformed-cwd"]
+        try:
+            assert len(mismatch) == 0, f"expected 0 verify-batch-mismatch findings, got: {mismatch}"
+            assert len(malformed) == 1, f"expected 1 verify-malformed-cwd finding, got {len(malformed)}: {malformed}"
+            print("PASS test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report")
+            return 0
+        except AssertionError as exc:
+            print(
+                f"FAIL test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report: {exc}",
+                file=sys.stderr,
+            )
+            return 1
+
+
+def test_verify_batch_mismatch_clean_overview_batches_unparseable() -> int:
+    """Clean (for this check): the overview's Batch Index fenced yaml is unparseable -> zero verify-batch-mismatch findings (check 4 already records the parse error; this check silently defers)."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview_text = (
+            "# Overview\n\n"
+            "```yaml\n"
+            'task: test\nslug: test-slug\nroot: ""\n'
+            "```\n\n"
+            "## Batch Index\n\n"
+            "```yaml\n"
+            "batches: [this is not: valid: yaml: at all\n"
+            "```\n"
+        )
+        batch = _make_batch_verify_only_text("alpha", "some cmd")
+        _write_plan(plan_dir, overview_text, [("01-alpha.md", batch)])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        if mismatch:
+            print(
+                f"FAIL test_verify_batch_mismatch_clean_overview_batches_unparseable: unexpected: {mismatch}",
+                file=sys.stderr,
+            )
+            return 1
+        print("PASS test_verify_batch_mismatch_clean_overview_batches_unparseable")
+        return 0
+
+
+def test_verify_batch_mismatch_clean_missing_batch_file() -> int:
+    """Clean: the overview entry's file: names a batch file that does not exist on disk -> zero verify-batch-mismatch findings."""
+    with tempfile.TemporaryDirectory() as tmpdir:
+        tmp = Path(tmpdir)
+        plan_dir = tmp / "plan"
+        project_root = tmp / "project"
+        project_root.mkdir()
+
+        overview = _make_overview([
+            {"name": "alpha", "file": "01-alpha.md", "verify": "some cmd"},
+        ])
+        # Deliberately do not write 01-alpha.md -- _write_plan([]) writes only the overview.
+        _write_plan(plan_dir, overview, [])
+
+        result = _plan_validate.run(plan_dir, project_root)
+        mismatch = [e for e in result if e["check"] == "verify-batch-mismatch"]
+        if mismatch:
+            print(
+                f"FAIL test_verify_batch_mismatch_clean_missing_batch_file: unexpected: {mismatch}",
+                file=sys.stderr,
+            )
+            return 1
+        print("PASS test_verify_batch_mismatch_clean_missing_batch_file")
+        return 0
+
+
 # ---------------------------------------------------------------------------
 # git_root threading tests (Card 5)
 # ---------------------------------------------------------------------------
@@ -7214,6 +8723,10 @@ def main() -> int:
         test_check_context_completeness_dirty_odd_backtick_count_line_field,
         test_check_context_completeness_clean_citation_marker,
         test_check_context_completeness_dirty_citation_marker_absent,
+        # inline-signature citation markers (validator-tests batch, Card 8)
+        test_check_context_completeness_clean_signature_inlined_marker,
+        test_check_context_completeness_clean_no_file_read_needed_marker,
+        test_check_context_completeness_dirty_inline_signature_marker_absent,
         test_check_context_completeness_clean_moves_source_plan_wide,
         test_check_context_completeness_dirty_moves_target_plan_wide_still_flagged,
         test_check_context_completeness_message_includes_moves_source_qualifier,
@@ -7223,6 +8736,23 @@ def main() -> int:
         test_check_context_completeness_clean_prohibition_marker_write_irregular,
         test_check_context_completeness_dirty_prohibition_marker_unrelated_negation_not_exempted,
         test_check_context_completeness_dirty_prohibition_marker_verb_without_negation_not_exempted,
+        # symbol-reference context-completeness (bare/dotted identifiers, not just paths)
+        test_check_context_completeness_symbol_clean_in_context,
+        test_check_context_completeness_symbol_dirty_missing,
+        test_check_context_completeness_symbol_clean_zero_matches,
+        test_check_context_completeness_symbol_clean_ambiguous_matches,
+        test_check_context_completeness_symbol_call_site_phrasing,
+        test_check_context_completeness_symbol_all_lowercase_not_candidate,
+        test_check_context_completeness_symbol_all_lowercase_dotted_not_candidate,
+        test_check_context_completeness_symbol_single_capitalized_is_candidate,
+        test_check_context_completeness_symbol_dotted_trailing_segment_only,
+        test_check_context_completeness_symbol_dotted_ambiguous_trailing_segment,
+        test_check_context_completeness_symbol_dotted_qualifying_prefix_nonqualifying_trailing,
+        test_check_context_completeness_symbol_first_match_wins_root_precedence,
+        test_check_context_completeness_symbol_cache_invoked_once_per_key,
+        test_check_context_completeness_symbol_prohibition_marker_exempt,
+        test_check_context_completeness_symbol_citation_marker_exempt,
+        test_check_context_completeness_symbol_underscore_qualifies,
         # requirements-quote-indent-drift check (mill-plan-requirements-byte-exactness-gap)
         test_check_requirements_quote_indent_drift_clean_exact_match,
         test_check_requirements_quote_indent_drift_clean_illustrative_snippet,
@@ -7235,6 +8765,13 @@ def main() -> int:
         test_check_requirements_quote_indent_drift_dirty_multiple_edits_tie_break,
         test_check_requirements_quote_indent_drift_clean_midline_fragment_flush_closer,
         test_check_requirements_quote_indent_drift_clean_byte_exact_indented_closer,
+        # under-indented requirements fences (validator-tests batch, Card 7)
+        test_check_requirements_quote_indent_drift_dirty_under_indent_flattened_fence,
+        test_check_requirements_quote_indent_drift_dirty_under_indent_empty_separator_line,
+        test_check_requirements_quote_indent_drift_dirty_under_indent_whitespace_separator_line,
+        test_check_requirements_quote_indent_drift_dirty_over_indent_message_frozen,
+        test_check_requirements_quote_indent_drift_clean_under_indent_byte_exact,
+        test_check_requirements_quote_indent_drift_clean_under_indent_illustrative_no_match,
         # skip_checks filtering (Card 7 / #188)
         test_skip_checks_filters_wiki_config_mutation,
         test_skip_checks_does_not_suppress_other_checks,
@@ -7296,6 +8833,20 @@ def main() -> int:
         test_check_verify_malformed_cwd_bad_cwd_value_dirty,
         test_check_verify_mixed_cwd_dirty,
         test_check_verify_mixed_cwd_single_cwd_clean,
+        # verify-batch-mismatch check (Card 6)
+        test_verify_batch_mismatch_clean_identical_string,
+        test_verify_batch_mismatch_dirty_null_vs_command,
+        test_verify_batch_mismatch_dirty_trailing_clause,
+        test_verify_batch_mismatch_clean_absent_vs_null,
+        test_verify_batch_mismatch_clean_both_absent,
+        test_verify_batch_mismatch_clean_both_null,
+        test_verify_batch_mismatch_dirty_string_vs_mapping_cwd,
+        test_verify_batch_mismatch_clean_matching_mapping,
+        test_verify_batch_mismatch_dirty_mapping_cwd_hub_vs_git_root,
+        test_verify_batch_mismatch_dirty_overview_malformed_mapping,
+        test_verify_batch_mismatch_clean_batch_malformed_mapping_no_double_report,
+        test_verify_batch_mismatch_clean_overview_batches_unparseable,
+        test_verify_batch_mismatch_clean_missing_batch_file,
         # git_root threading (Card 5 / #471)
         test_git_root_threading_with_subfolder_cwd_clean,
         test_git_root_threading_without_git_root_default_none_documents_required,

```

## Instructions

1. Read the failing tests and the source files they exercise.
2. Fix the root cause of the failures.
   Do not modify tests unless they are genuinely wrong due to the merge (e.g. a test asserted against a value that the merge legitimately changed).
3. Re-run `PYTHONPATH= uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py --only test-phase-wait.py test-brief-commit.py test-orch-review-scratch-path.py` after each fix attempt using `git -C /home/knatte/Code/millhouse/wts/mill-start-discussion-review-timeline-and-orch-review-hygiene` for git commands.
4. Commit each fix attempt with a clear commit message.
5. Self-fix up to `3` times.
   If the verify command still fails after `3` attempts, stop and report stuck.

## Report

Your last output line MUST be a bare JSON object (no code fence, no backticks):

**`commit_sha` MUST be the full SHA from `git rev-parse HEAD` -- never the abbreviated form (`git rev-parse --short HEAD`) or a `git log --oneline` hash.**

On success:

{"status":"success","commit_sha":"<last-HEAD-sha>"}

After exhausting fix rounds:

{"status":"stuck","stuck_type":"verify","reason":"<one-line description of what still fails>","commit_sha":"<last-HEAD-sha>"}

Anything other than this JSON object on the last line is a protocol violation;
the merge-in dispatcher treats that as stuck_type: logic with reason "no structured report" — your work is lost.
Do not wrap the JSON in a code fence;
do not add commentary after it.

## Tools

Available: Read, Edit, Write, Bash, Grep, Glob.
Use `git -C /home/knatte/Code/millhouse/wts/mill-start-discussion-review-timeline-and-orch-review-hygiene` for git commands;
do not `cd`.
Worktree cwd is `/home/knatte/Code/millhouse/wts/mill-start-discussion-review-timeline-and-orch-review-hygiene`.
