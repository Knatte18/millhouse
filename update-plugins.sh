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

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST_PATH="$SCRIPT_DIR/.claude-plugin/marketplace.json"

MARKETPLACE=$(python3 -c "import json; print(json.load(open('$MANIFEST_PATH'))['name'])")
CACHE_BASE="$HOME/.claude/plugins/cache/$MARKETPLACE"

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
