#!/usr/bin/env bash
# Deploy all plugins from this source repo to the container's deploy directory,
# which is what Claude Code actually reads. Run from the millhouse repo root.
#
# Why a separate deploy directory rather than the plugin cache: the `millhouse`
# marketplace is a directory source, and Claude Code reads a directory-sourced
# plugin in place from <marketplace-dir>/<plugin source path> -- it never reads
# the copy under ~/.claude/plugins/cache/. Pointing the marketplace at the
# source repo therefore makes every session run the live dev tree, mid-edit,
# and makes whatever this script deploys dead weight.
#
# `claude plugin update` cannot do this job: it is version-gated and skips when
# marketplace.json's version is unchanged, so it cannot deploy in-place file
# edits without a version bump. rsync mirrors regardless of version.
#
# POSIX counterpart to update-plugins.ps1 -- same behavior, minus the Windows
# registry env-var step. Mill skills receive PYTHONPATH inline per invocation
# (see CLAUDE.md "Script invocation"), so no persistent global env var is
# needed on POSIX; MILL_PYTHON is updated in ~/.claude/settings.json instead,
# mirroring mill-setup Phase 4.8. CODEGUIDE_PLUGIN_ROOT has no POSIX
# equivalent here (no established settings.json convention for it yet) and is
# intentionally not set.
#
# Before deploying, refreshes scribe@scribe (mill's declared dependency) when
# installed and warns if it is older than mill requires.
# After deploying, prints an uninstall hint for each <name>@millhouse install
# whose plugin is no longer in marketplace.json, and warns if the marketplace
# is still registered against anything other than the deploy directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_PATH="$SCRIPT_DIR/.claude-plugin/marketplace.json"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
KNOWN_JSON="$HOME/.claude/plugins/known_marketplaces.json"
MILL_MANIFEST="$SCRIPT_DIR/plugins/mill/.claude-plugin/plugin.json"

# The repo lives at <container>/wts/<slug>; the deploy directory is a sibling of
# wts/, wiki/ and portals/, so it never sits inside a git checkout.
CONTAINER="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOY_ROOT="$CONTAINER/deploy"

# `python3` is a broken Microsoft Store alias under git-bash on Windows: it
# exits non-zero with an install prompt. Probe it, and fall back to `python`.
if command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1; then
    PY=python3
else
    PY=python
fi

MARKETPLACE=$("$PY" -c "import json; print(json.load(open('$MANIFEST_PATH'))['name'])")

# Refresh scribe@scribe (mill's dependency) and check it meets mill's minimum.
SCRIBE_INSTALLED=$("$PY" -c "
import json, os
path = '$INSTALLED_JSON'
installed = os.path.exists(path) and 'scribe@scribe' in json.load(open(path)).get('plugins', {})
print('yes' if installed else 'no')
")

if [ "$SCRIBE_INSTALLED" = "yes" ]; then
    if ! claude plugin marketplace update scribe; then
        echo "WARNING: 'claude plugin marketplace update scribe' failed -- continuing"
    fi
    if ! claude plugin update scribe@scribe; then
        echo "WARNING: 'claude plugin update scribe@scribe' failed -- continuing"
    fi

    "$PY" -c "
import json, re

def parse_version(text):
    # A directory-sourced install records its version with a '-<hash>' suffix; strip it before parsing.
    return tuple(int(part) for part in re.split(r'[-+]', text)[0].split('.'))

installed = json.load(open('$INSTALLED_JSON'))['plugins']['scribe@scribe']
lowest = min((parse_version(record['version']) for record in installed), default=None)

dependencies = json.load(open('$MILL_MANIFEST')).get('dependencies', [])
required = None
for entry in dependencies:
    if isinstance(entry, dict) and entry.get('name') == 'scribe' and entry.get('marketplace') == 'scribe':
        required = entry.get('version')

if lowest is not None and required:
    minimum = parse_version(re.sub(r'^(\\^|~|>=|=)', '', required))
    if lowest < minimum:
        found = '.'.join(map(str, lowest))
        needed = '.'.join(map(str, minimum))
        print(f\"WARNING: scribe@scribe is {found}, mill needs {needed} -- run 'claude plugin marketplace update scribe' and 'claude plugin update scribe@scribe'.\")
"
else
    echo "scribe@scribe is not installed -- mill fails to load without it. Add and install it: '/plugin marketplace add Knatte18/scribe', then '/plugin install scribe@scribe'."
fi

# The marketplace manifest is part of what gets deployed: the deploy directory
# IS the marketplace once it is registered, so it needs its own copy.
mkdir -p "$DEPLOY_ROOT/.claude-plugin"
rsync -a --delete "$SCRIPT_DIR/.claude-plugin/" "$DEPLOY_ROOT/.claude-plugin/"
echo "Deployed: .claude-plugin/marketplace.json"

while IFS=$'\t' read -r NAME VERSION; do
    SOURCE_DIR="$SCRIPT_DIR/plugins/$NAME"
    TARGET_DIR="$DEPLOY_ROOT/plugins/$NAME"
    mkdir -p "$TARGET_DIR"

    # Mirror source -> target. Exclude .venv because uv creates it in the
    # deploy tree at runtime; --exclude also protects it from --delete.
    rsync -a --delete --exclude='.venv' "$SOURCE_DIR/" "$TARGET_DIR/"
    echo "Deployed: $NAME@$MARKETPLACE ($VERSION)"

    if [ -f "$TARGET_DIR/pyproject.toml" ]; then
        echo "  -> Running uv sync for $NAME..."
        if ! uv sync --project "$TARGET_DIR" --quiet; then
            echo "  WARNING: uv sync failed for $NAME"
        fi
    fi
done < <("$PY" -c "
import json
data = json.load(open('$MANIFEST_PATH'))
for p in data['plugins']:
    print(f\"{p['name']}\t{p['version']}\")
")

# Point out installs whose plugin no longer exists in this marketplace.
"$PY" -c "
import json, os

path = '$INSTALLED_JSON'
if os.path.exists(path):
    current = {p['name'] for p in json.load(open('$MANIFEST_PATH'))['plugins']}
    for key in json.load(open(path)).get('plugins', {}):
        name, _, marketplace = key.partition('@')
        if marketplace == '$MARKETPLACE' and name not in current:
            print(f\"Orphaned: {key} is no longer in this marketplace -- run 'claude plugin uninstall {key}'.\")
"

# Update MILL_PYTHON in ~/.claude/settings.json so "$MILL_PYTHON" resolves to
# the newly deployed mill venv.
"$PY" -c "
import json
from pathlib import Path

mill_python = str(Path(r'$DEPLOY_ROOT') / 'plugins' / 'mill' / '.venv' / 'bin' / 'python')
settings_path = Path.home() / '.claude' / 'settings.json'

data = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
env_block = data.setdefault('env', {})
if env_block.get('MILL_PYTHON') == mill_python:
    print(f'  -> MILL_PYTHON already correct: {mill_python}')
else:
    env_block['MILL_PYTHON'] = mill_python
    settings_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f'  -> MILL_PYTHON set: {mill_python}')
"

# Deploying is pointless if the marketplace still points somewhere else: Claude
# Code would keep reading that other directory and ignore everything above.
"$PY" -c "
import json, os

path = '$KNOWN_JSON'
if os.path.exists(path):
    entry = json.load(open(path)).get('$MARKETPLACE')
    registered = entry and entry.get('installLocation')
    if registered and os.path.normcase(os.path.abspath(registered)) != os.path.normcase('$DEPLOY_ROOT'):
        plugins = ', '.join(f\"{p['name']}@$MARKETPLACE\" for p in json.load(open('$MANIFEST_PATH'))['plugins'])
        print()
        print(f\"WARNING: marketplace '$MARKETPLACE' is registered against {registered}, not $DEPLOY_ROOT.\")
        print('         Sessions read that directory, so this deploy has no effect. Re-register once:')
        print(f'           claude plugin marketplace remove $MARKETPLACE')
        print(f'           claude plugin marketplace add $DEPLOY_ROOT')
        print(f'         then reinstall each plugin: {plugins}')
"

echo ""
echo "Done."
