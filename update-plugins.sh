#!/usr/bin/env bash
# Force-sync all plugins from the local source dir to the Claude Code plugin
# cache. `claude plugin update` is version-gated and skips when marketplace.json
# version is unchanged, so it cannot deploy in-place file edits without a
# version bump. We use rsync directly to mirror the current source into the
# cache regardless of version. Run from the millhouse repo root.
#
# POSIX counterpart to update-plugins.ps1 -- same behavior, minus the Windows
# registry env-var step. Mill skills receive PYTHONPATH inline per invocation
# (see CLAUDE.md "Script invocation"), so no persistent global env var is
# needed on POSIX; MILL_PYTHON is updated in ~/.claude/settings.json instead,
# mirroring mill-setup Phase 4.8. CODEGUIDE_PLUGIN_ROOT has no POSIX
# equivalent here (no established settings.json convention for it yet) and is
# intentionally not set.
#
# Before syncing, refreshes scribe@scribe (mill's declared dependency) when
# installed and warns if it is older than mill requires.
# After syncing, prints an uninstall hint for each <name>@millhouse install
# whose plugin is no longer in marketplace.json.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_PATH="$SCRIPT_DIR/.claude-plugin/marketplace.json"
INSTALLED_JSON="$HOME/.claude/plugins/installed_plugins.json"
MILL_MANIFEST="$SCRIPT_DIR/plugins/mill/.claude-plugin/plugin.json"

MARKETPLACE=$(python3 -c "import json; print(json.load(open('$MANIFEST_PATH'))['name'])")
CACHE_BASE="$HOME/.claude/plugins/cache/$MARKETPLACE"

# Refresh scribe@scribe (mill's dependency) and check it meets mill's minimum.
SCRIBE_INSTALLED=$(python3 -c "
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

    python3 -c "
import json, re

def parse_version(text):
    return tuple(int(part) for part in text.split('.'))

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

while IFS=$'\t' read -r NAME VERSION; do
    SOURCE_DIR="$SCRIPT_DIR/plugins/$NAME"
    TARGET_DIR="$CACHE_BASE/$NAME/$VERSION"

    if [ ! -d "$TARGET_DIR" ]; then
        echo "Skipped (not installed): $NAME@$MARKETPLACE -- run 'claude plugin install $NAME@$MARKETPLACE' first."
        continue
    fi

    # Mirror source -> target. Exclude .venv because uv creates it in the
    # cache at runtime; --exclude also protects it from --delete.
    rsync -a --delete --exclude='.venv' "$SOURCE_DIR/" "$TARGET_DIR/"
    echo "Force-synced: $NAME@$MARKETPLACE ($VERSION)"

    if [ -f "$TARGET_DIR/pyproject.toml" ]; then
        echo "  -> Running uv sync for $NAME..."
        if ! uv sync --project "$TARGET_DIR" --quiet; then
            echo "  WARNING: uv sync failed for $NAME"
        fi
    fi
done < <(python3 -c "
import json
data = json.load(open('$MANIFEST_PATH'))
for p in data['plugins']:
    print(f\"{p['name']}\t{p['version']}\")
")

# Point out installs whose plugin no longer exists in this marketplace.
python3 -c "
import json, os

path = '$INSTALLED_JSON'
if os.path.exists(path):
    current = {p['name'] for p in json.load(open('$MANIFEST_PATH'))['plugins']}
    for key in json.load(open(path)).get('plugins', {}):
        name, _, marketplace = key.partition('@')
        if marketplace == '$MARKETPLACE' and name not in current:
            print(f\"Orphaned: {key} is no longer in this marketplace -- run 'claude plugin uninstall {key}'.\")
"

# Update MILL_PYTHON in ~/.claude/settings.json so \"\$MILL_PYTHON\" resolves
# to the newly deployed mill cache venv.
MILL_VERSION=$(python3 -c "
import json
data = json.load(open('$MANIFEST_PATH'))
mill = next(p for p in data['plugins'] if p['name'] == 'mill')
print(mill['version'])
")
MILL_TARGET="$CACHE_BASE/mill/$MILL_VERSION"

python3 -c "
import json
from pathlib import Path

mill_python = str(Path(r'$MILL_TARGET') / '.venv' / 'bin' / 'python')
settings_path = Path.home() / '.claude' / 'settings.json'

data = json.loads(settings_path.read_text(encoding='utf-8')) if settings_path.exists() else {}
env_block = data.setdefault('env', {})
if env_block.get('MILL_PYTHON') == mill_python:
    print(f'MILL_PYTHON already correct: {mill_python}')
else:
    env_block['MILL_PYTHON'] = mill_python
    settings_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f'MILL_PYTHON set: {mill_python}')
"

echo ""
echo "Done."
