# Batch: templates

```yaml
task: 56 (A) -- Fix mill-go/start/plan/merge runtime behavioral bugs
batch: templates
number: 2
cards: 2
verify: uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py
depends-on: []
```

## Batch Scope

Fix two prompt templates. Card 3 removes the nested-fence ambiguity from `review-code-holistic.md` that causes the holistic code reviewer to drift into implementer voice (bug #278). Card 4 adds an explicit cross-worktree isolation rule to `implementer-brief.md` that bans `cd <parent-worktree>` with the cwd-corruption explanation (bug #287). Both cards are purely textual; no Python is touched.

## Cards

### Card 3: review-code-holistic -- fix nested triple-fence in output example

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/review-code-holistic.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  The current template has an anonymous code fence (` ``` ` with no language specifier, line 35) that opens an "example" block containing a ` ```yaml ` inner block. Because the outer fence has no language specifier, the model's parser closes the outer block at the inner yaml block's ` ``` ` closing fence (line 43), leaving lines 44–65 outside any block and line 66 as an orphaned closing fence. The model drifts into implementer mode as a result.

  Fix: remove the outer anonymous ` ``` ` fence entirely (line 35 and line 66). Keep the inner ` ```yaml ` block as-is (lines 38–43). Wrap the entire example (the yaml block and the surrounding scaffold lines 36–65) in a ` ~~~markdown ` tilde fence instead. Tilde fences allow inner backtick fences without nesting conflicts; the ` ```yaml ` block inside a `~~~markdown` outer fence is unambiguous to both the model's parser and to Markdown renderers. The key invariant: the ` ```yaml ` block and its ` ``` ` closing fence must be the ONLY backtick fences in the output-format section. Do not use blockquote (`>`) markers as the outer wrapper; prefer the tilde fence for unambiguity.

  Do not change any other part of the file. The criteria section (lines 16–28), source-grounding rule (lines 12–14), and severity/verdict rules reference (line 68) are unchanged.
- **Commit:** `fix(review-code-holistic): remove nested-fence ambiguity in output example (#278)`

### Card 4: implementer-brief -- add cross-worktree isolation rule

- **Context:** none
- **Edits:**
  - `plugins/mill/templates/implementer-brief.md`
- **Creates:** none
- **Deletes:** none
- **Requirements:**
  After the `## Tools` section at the end of the file (current last line: "Available: Read, Edit, Write, Bash, Grep, Glob. Banned: TodoWrite, WebFetch, WebSearch. Use `git -C <PROJECT_ROOT>` for commits; do not `cd`."), add a new `## Cross-worktree isolation` section with the following content (exact wording):

  ```
  ## Cross-worktree isolation

  You run inside a task worktree. The parent worktree (the repo's main branch checkout) is a sibling directory — do NOT change directory into it.

  - **Banned:** `cd <parent-worktree-path>` or any command that changes the process working directory to the parent. A single stray `cd` to the parent corrupts the shell cwd for every subsequent command in this session — the rest of the batch runs in the wrong directory with no error indicator.
  - **Allowed:** `git -C <parent-path> log/status/show/diff/ls-files` for read-only queries. Never `git -C <parent-path> commit/push/add` — those would mutate the parent's state.
  - **If you need a file from the parent:** use `git -C <PROJECT_ROOT> show <parent-branch>:<path>` to read it without changing cwd.
  ```

  The new section is appended at the very end of the file, after the `## Tools` section. No other edits.
- **Commit:** `fix(implementer-brief): add explicit cross-worktree isolation rule (#287)`

## Batch Tests

The verify command `uv run --project plugins/mill python plugins/mill/unit_tests/run-all.py` serves as a regression check that no Python code was accidentally broken. The template files themselves have no automated test coverage; correctness is verified by code review.
