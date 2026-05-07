---
name: cli
description: Shell command guidelines. Use when running shell commands.
---

# CLI Skill

Guidelines for shell commands executed by CC.

---

- Use **absolute paths** instead of `cd`. For git: `git -C /path/to/repo status` instead of `cd /path && git status`.
- Use **long flag names**: `--message` instead of `-m`, `--verbose` instead of `-v`.
- **Never use `rm -rf` or `rm -fr`.** Use `rm -r` (without `-f`). If a file is write-protected, the interactive prompt is intentional — stop and investigate rather than forcing deletion.

## Timestamps

When a timestamp is needed in filenames, frontmatter, or metadata, **always generate it via shell** — never guess or hallucinate a timestamp.

- **Filenames** (compact, no punctuation): `date -u +"%Y%m%d-%H%M%S"` → `20260408-143052`
- **Metadata / ISO 8601**: `date -u +"%Y-%m-%dT%H:%M:%SZ"` → `2026-04-08T14:30:52Z`

Store the result in a variable when the same timestamp is needed in multiple places within one operation.

## PowerShell

- The user's IDE terminal is **PowerShell 5** — bash commands fail at paste.
- **Commands for the user to copy/run:** write PowerShell syntax, not bash.
- **Commands CC executes via the Bash tool:** continue using bash syntax — unchanged.
- PS7-only features are forbidden in user-facing commands: `?:` ternary, `??` null-coalescing, `&&`/`||` chaining, `Get-Content -AsHashtable`.
- PS5 → bash equivalents: `$env:VAR` (not `export VAR=`), `Get-ChildItem` (not `ls`), `Resolve-Path` (not `realpath`), `Remove-Item` (not `rm`).
- **Commands CC executes via the Monitor tool:** use bash syntax — Monitor runs bash, not PowerShell. PS syntax in a Monitor command yields exit 127 with no warning.
- **`$CLAUDE_PLUGIN_ROOT` is a CC template token, not a Bash subshell variable.** CC substitutes it when loading SKILL.md, so the resolved literal path is visible in the loaded skill text. Autonomous agents (mill-plan, mill-go) constructing new Bash commands must use the resolved path verbatim — never reconstruct `${CLAUDE_PLUGIN_ROOT}` as a shell variable in new Bash commands, because it is empty in the Bash subshell on Windows.
