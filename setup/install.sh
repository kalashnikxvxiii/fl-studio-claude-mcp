#!/usr/bin/env bash
# Installer for fl-studio-claude-mcp.
# - copies the FL controller script into FL's Settings/Hardware (path-patched)
# - sets up a Python venv with the mcp SDK
# - makes snd-virmidi persistent and loads it now
# - registers the MCP server with Claude Code
#
# Usage:  ./setup/install.sh [WINEPREFIX]
# WINEPREFIX defaults to ~/.local/share/wineprefixes/flstudio
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
WINEPREFIX="${1:-$HOME/.local/share/wineprefixes/flstudio}"
USER_NAME="$(whoami)"

FL_DATA="$WINEPREFIX/drive_c/users/$USER_NAME/Documents/Image-Line/FL Studio"
HW_DIR="$FL_DATA/Settings/Hardware/FLClaudeMCP"
WINE_DIR="C:\\users\\$USER_NAME\\Documents\\Image-Line\\FL Studio\\Settings\\Hardware\\FLClaudeMCP"

echo "==> FL data dir: $FL_DATA"
[ -d "$FL_DATA/Settings/Hardware" ] || { echo "ERROR: FL Hardware dir not found. Is FL installed in this prefix?"; exit 1; }

echo "==> Installing controller script -> $HW_DIR"
mkdir -p "$HW_DIR"
# patch the Wine path inside the script to match this user/prefix
sed "s|^_DIR = r\".*\"$|_DIR = r\"$WINE_DIR\"|" \
    "$REPO/fl_device/device_FLClaudeMCP.py" > "$HW_DIR/device_FLClaudeMCP.py"

echo "==> Python venv + mcp SDK"
python3 -m venv "$REPO/.venv"
"$REPO/.venv/bin/pip" -q install -r "$REPO/mcp_server/requirements.txt"

echo "==> snd-virmidi (needs sudo): persistent + load now"
sudo install -m644 "$REPO/setup/snd-virmidi.conf" /etc/modules-load.d/snd-virmidi.conf
sudo modprobe snd-virmidi || true

echo "==> Registering MCP server with Claude Code"
if command -v claude >/dev/null 2>&1; then
    claude mcp add fl-studio -- "$REPO/.venv/bin/python" "$REPO/mcp_server/fl_mcp_server.py" || \
        echo "   (already registered or 'claude mcp add' failed — register manually)"
else
    echo "   'claude' CLI not found — register manually:"
    echo "   claude mcp add fl-studio -- \"$REPO/.venv/bin/python\" \"$REPO/mcp_server/fl_mcp_server.py\""
fi

cat <<EOF

==> Done. Final manual step (one-time, in FL Studio):
    Options > MIDI settings > enable a "Virtual Raw MIDI" input,
    set its Controller type to "FLClaudeMCP".
    Then in Claude: ask it to run fl_ping.
EOF
