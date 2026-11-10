#!/bin/bash
# PO4: set up or update the Vectorworks MCP for Claude.
#
#   curl -LsSf https://raw.githubusercontent.com/bgst84/vectorworks-mcp/stable/scripts/install-po4.sh | bash
#
# Detects the Vectorworks version, installs the bridge and the "MCP Run Job"
# menu command into the Plug-ins folder and registers the server with Claude.
# Claude fetches the server from the "stable" branch on every start, so
# updates arrive automatically; re-running is only needed when the bridge
# changes. Safe to run repeatedly.
#
# Options (environment variables): VW_VERSION=2027, VWMCP_BRANCH=stable,
# VWMCP_REPO=https://github.com/bgst84/vectorworks-mcp
set -euo pipefail

REPO="${VWMCP_REPO:-https://github.com/bgst84/vectorworks-mcp}"
BRANCH="${VWMCP_BRANCH:-stable}"
SOURCE="git+${REPO}@${BRANCH}"
WORKGROUP="$HOME/PO4 Dropbox/PO4/00_Organisation/18_Vectorworks/arbeitsgruppe"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '\n\033[31m✗ %s\033[0m\n' "$*"; exit 1; }

say "1/5  Finding Vectorworks"
VW_YEAR="${VW_VERSION:-}"
if [ -z "$VW_YEAR" ]; then
  for d in /Applications/Vectorworks\ 20[0-9][0-9]; do
    y="${d##*Vectorworks }"
    [ -d "$d/Vectorworks $y.app" ] && VW_YEAR="$y"
  done
fi
[ -n "$VW_YEAR" ] || die "No Vectorworks found in /Applications."
APP="Vectorworks $VW_YEAR"
ok "$APP"
VW_RUNNING=0
if pgrep -f "/$APP.app/Contents/MacOS/Vectorworks$" >/dev/null 2>&1; then
  VW_RUNNING=1
  warn "Vectorworks is running: quit and reopen it after the install."
fi

say "2/5  Checking uv (Python tool runner)"
if command -v uvx >/dev/null 2>&1; then
  UVX="$(command -v uvx)"
elif [ -x "$HOME/.local/bin/uvx" ]; then
  UVX="$HOME/.local/bin/uvx"
else
  echo "  Installing uv ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
  UVX="$HOME/.local/bin/uvx"
fi
ok "$UVX"

say "3/5  Installing bridge and menu command"
"$UVX" --refresh --from "$SOURCE" vwmcp install-plugin --vw-version "$VW_YEAR" | sed 's/^/  /'

say "4/5  Registering with Claude"
CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
if [ -d "$(dirname "$CFG")" ]; then
  [ -f "$CFG" ] && cp "$CFG" "$CFG.bak-vwmcp"
  "$UVX" python - "$CFG" "$UVX" "$SOURCE" "$APP" <<'PY'
import json, pathlib, sys
path, uvx, source, app = pathlib.Path(sys.argv[1]), *sys.argv[2:]
text = path.read_text() if path.exists() else ""
cfg = json.loads(text) if text.strip() else {}
cfg.setdefault("mcpServers", {})["vectorworks"] = {
    "command": uvx,
    "args": ["--refresh", "--from", source, "vwmcp"],
    "env": {"VWMCP_APP": app},
}
path.write_text(json.dumps(cfg, indent=2) + "\n")
json.loads(path.read_text())  # still valid
print("  ✓ Claude Desktop (backup: claude_desktop_config.json.bak-vwmcp)")
PY
else
  warn "Claude Desktop not found (claude.ai/download). Skipped."
fi
if command -v claude >/dev/null 2>&1; then
  claude mcp remove --scope user vectorworks >/dev/null 2>&1 || true
  claude mcp add --scope user -e VWMCP_APP="$APP" vectorworks -- "$UVX" --refresh --from "$SOURCE" vwmcp >/dev/null
  ok "Claude Code"
fi

say "5/5  Checking"
PLUGINS="$HOME/Library/Application Support/Vectorworks/$VW_YEAR/Plug-ins"
NEED_MANUAL_MENU=0
[ -f "$PLUGINS/vwmcp/vwmcp_bridge.py" ] && ok "Bridge in $PLUGINS/vwmcp" || warn "Bridge missing in $PLUGINS/vwmcp"
if [ -f "$PLUGINS/MCP Run Job.vsm" ]; then
  ok "Menu command \"MCP Run Job\""
else
  NEED_MANUAL_MENU=1
  warn "Menu command \"MCP Run Job\" missing: create it once by hand (see below)."
fi
if [ -d "$WORKGROUP" ]; then
  ok "PO4 workgroup folder found"
else
  warn "PO4 workgroup folder not found (is the PO4 Dropbox synced?)"
fi

say "Done. Next steps:"
echo "  1. Quit Claude completely with Cmd-Q and reopen it."
[ "$VW_RUNNING" = 1 ] && echo "  2. Quit and reopen Vectorworks." \
                      || echo "  2. Open Vectorworks."
echo "     Once: Vectorworks Preferences ▸ User Folders ▸ workgroup folder:"
echo "     $WORKGROUP"
echo "     and choose the PO4 workspace (it has \"MCP Run Job\" in the PO4 menu)."
echo "  3. In Claude, write \"Ping Vectorworks\" and allow the macOS prompt."
echo "  4. For screenshots: System Settings ▸ Privacy & Security ▸"
echo "     Screen & System Audio Recording ▸ turn on Claude, then restart Claude."
if [ "$NEED_MANUAL_MENU" = 1 ]; then
  cat <<'MSG'

  Menu command by hand: Tools ▸ Plug-ins ▸ Plug-in Manager ▸ Custom Plug-ins ▸ New…
  Type Command, name exactly "MCP Run Job", script language Python:
      from vwmcp import vwmcp_bridge
      vwmcp_bridge.run_pending()
MSG
fi
