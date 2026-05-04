---
name: git-clone
description: "Clone a repo into the mill container layout (wts/<repo>/) ready for mill-setup"
argument-hint: "<url> [--linear]"
---

# Clone Git Repository

Clone a repo into the mill container layout (default), or as a standard clone (`--linear`).

## Usage

```
/git-clone https://github.com/user/repo.git          (hub — default)
/git-clone https://github.com/user/repo.git --linear  (standard clone)
/git-clone                                             (detect — inside existing repo)
```

## Hub Structure (container layout)

```text
<repo>/                  ← container, named after the repo
└── wts/                 ← all worktrees live here
    └── <repo>/          ← main worktree (regular clone — has its own .git/)
                         ← (task worktrees added by mill-spawn as siblings)
```

mill-setup later adds `<repo>/wiki/`, `<repo>/codeguide/`, and `<repo>/portals/` as siblings of `wts/`.

**No bare-clone strategy.** The main worktree is a normal clone with `.git/` inside it. Task worktrees are added via `git -C wts/<repo>/ worktree add ../<slug>` so they land at `<container>/wts/<slug>/` as siblings. Bare clones were tried previously but conflicted with VS Code's repo extension.

## Instructions

When the user invokes `/git-clone`, follow these steps exactly.

### 1. Parse arguments

Extract the URL (if present) and flags from the arguments.

- `--linear` flag → use the **Linear flow** (section below).
- No URL → use the **No-URL flow** (section below).
- URL without `--linear` → use the **Hub flow** (below).

### 2. Hub flow

**Steps are order-dependent — do not reorder.**

#### 2.1. Derive repo name

Take the last path segment of the URL and strip any `.git` suffix.

Examples:
- `https://github.com/user/my-repo.git` → `my-repo`
- `git@github.com:user/my-repo.git` → `my-repo`
- `https://github.com/user/my-repo` → `my-repo`

#### 2.2. Resolve absolute container path

```bash
container_path="$(pwd)/$name"
worktree_path="$container_path/wts/$name"
```

`$name` is both the container directory name AND the main worktree's directory name (they match — see `## Hub Structure`). All subsequent commands use absolute paths. Do not use relative paths.

#### 2.3. Check target doesn't exist

If `$container_path` already exists, report the error and stop:

> "Directory `<name>/` already exists. Remove it first or choose a different location."

#### 2.4. Create container scaffolding

```bash
mkdir -p "$container_path/wts"
```

#### 2.5. Clone into the main worktree path

```bash
git clone <url> "$worktree_path"
```

If the clone fails, report the error and stop.

#### 2.6. Detect default branch

```bash
git -C "$worktree_path" symbolic-ref --short HEAD 2>/dev/null
```

Returns the branch name that was checked out by `git clone` (e.g. `main`, `master`). If the result is empty (detached HEAD — rare), ask the user via `AskUserQuestion`.

#### 2.7. Report

Tell the user:

```
Hub created at <container_path>
Main worktree: <worktree_path> (branch: <default-branch>)

Next: cd <worktree_path> && /mill-setup
```

### 3. Linear flow

Standard clone — nothing special.

```bash
git clone <url>
```

Report:

```
Cloned to <name>/
```

### 4. No-URL flow (inside existing repo)

When invoked without a URL while inside a git repo.

#### 4.1. Find repo root

```bash
root=$(git rev-parse --show-toplevel)
```

#### 4.2. Detect container-form layout

Check whether the repo root sits under a `wts/` directory:

```bash
test "$(basename "$(dirname "$root")")" = "wts"
```

If true, this repo is already in container-form (mill-managed). Report:

> "This repo is already in container-form layout (`wts/<repo>/`)."

Stop.

If false, continue.

#### 4.3. Get remote URL

```bash
url=$(git remote get-url origin 2>/dev/null)
```

#### 4.4. Report

If URL was found:

> "This repo is not in container-form layout. To convert: delete this repo and run `/git-clone <url>`"

If no remote URL:

> "This repo is not in container-form layout and has no remote. Clone from a URL instead: `/git-clone <url>`"

### Error handling

- **Target directory exists:** abort with clear message (step 2.3)
- **Clone fails:** report git error output (step 2.5)
- **No default branch detected:** ask user (step 2.6)
- **Partial failure cleanup:** if any step after 2.5 fails (container partially created), advise the user: "Hub creation failed. Delete `<container_path>` before retrying."
