#!/bin/bash
# PO4: Vectorworks MCP für Claude einrichten oder aktualisieren.
#
#   curl -LsSf https://raw.githubusercontent.com/bgst84/vectorworks-mcp/stable/scripts/install-po4.sh | bash
#
# Erkennt die Vectorworks-Version selbst, installiert Bridge und Menübefehl
# «MCP Run Job» in den Plug-ins-Ordner und trägt den Server in Claude ein.
# Claude lädt den Server bei jedem Start frisch vom Branch «stable»:
# Updates kommen also automatisch, ein erneuter Aufruf ist nur nötig,
# wenn sich die Bridge ändert. Mehrfach ausführen schadet nicht.
#
# Optionen (Umgebungsvariablen): VW_VERSION=2027, VWMCP_BRANCH=stable,
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

say "1/5  Vectorworks suchen"
VW_YEAR="${VW_VERSION:-}"
if [ -z "$VW_YEAR" ]; then
  for d in /Applications/Vectorworks\ 20[0-9][0-9]; do
    y="${d##*Vectorworks }"
    [ -d "$d/Vectorworks $y.app" ] && VW_YEAR="$y"
  done
fi
[ -n "$VW_YEAR" ] || die "Kein Vectorworks unter /Applications gefunden."
APP="Vectorworks $VW_YEAR"
ok "$APP"
VW_RUNNING=0
if pgrep -f "/$APP.app/Contents/MacOS/Vectorworks$" >/dev/null 2>&1; then
  VW_RUNNING=1
  warn "Vectorworks läuft: nach der Installation einmal beenden und neu öffnen."
fi

say "2/5  uv (Python-Werkzeug) prüfen"
if command -v uvx >/dev/null 2>&1; then
  UVX="$(command -v uvx)"
elif [ -x "$HOME/.local/bin/uvx" ]; then
  UVX="$HOME/.local/bin/uvx"
else
  echo "  uv wird installiert ..."
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null
  UVX="$HOME/.local/bin/uvx"
fi
ok "$UVX"

say "3/5  Bridge und Menübefehl installieren"
"$UVX" --refresh --from "$SOURCE" vwmcp install-plugin --vw-version "$VW_YEAR" | sed 's/^/  /'

say "4/5  In Claude eintragen"
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
print("  ✓ Claude Desktop (Backup: claude_desktop_config.json.bak-vwmcp)")
PY
else
  warn "Claude Desktop nicht gefunden (claude.ai/download). Übersprungen."
fi
if command -v claude >/dev/null 2>&1; then
  claude mcp remove --scope user vectorworks >/dev/null 2>&1 || true
  claude mcp add --scope user -e VWMCP_APP="$APP" vectorworks -- "$UVX" --refresh --from "$SOURCE" vwmcp >/dev/null
  ok "Claude Code"
fi

say "5/5  Prüfen"
PLUGINS="$HOME/Library/Application Support/Vectorworks/$VW_YEAR/Plug-ins"
NEED_MANUAL_MENU=0
[ -f "$PLUGINS/vwmcp/vwmcp_bridge.py" ] && ok "Bridge in $PLUGINS/vwmcp" || warn "Bridge fehlt in $PLUGINS/vwmcp"
if [ -f "$PLUGINS/MCP Run Job.vsm" ]; then
  ok "Menübefehl «MCP Run Job»"
else
  NEED_MANUAL_MENU=1
  warn "Menübefehl «MCP Run Job» fehlt: einmal von Hand anlegen (siehe unten)."
fi
if [ -d "$WORKGROUP" ]; then
  ok "PO4-Arbeitsgruppenordner gefunden"
else
  warn "PO4-Arbeitsgruppenordner nicht gefunden (PO4 Dropbox synchronisiert?)"
fi

say "Fertig. Noch zu tun:"
echo "  1. Claude mit Cmd-Q ganz beenden und neu öffnen."
[ "$VW_RUNNING" = 1 ] && echo "  2. Vectorworks beenden und neu öffnen." \
                      || echo "  2. Vectorworks öffnen."
echo "     Einmalig: Programm-Einstellungen ▸ Benutzerordner ▸ Arbeitsgruppenordner:"
echo "     $WORKGROUP"
echo "     und die PO4-Arbeitsumgebung wählen (enthält «MCP Run Job» im Menü PO4)."
echo "  3. In Claude schreiben: «Ping Vectorworks» und die macOS-Abfrage erlauben."
echo "  4. Für Screenshots: Systemeinstellungen ▸ Datenschutz & Sicherheit ▸"
echo "     Bildschirm- & Systemaudioaufnahme ▸ Claude einschalten, Claude neu starten."
if [ "$NEED_MANUAL_MENU" = 1 ]; then
  cat <<'MSG'

  Menübefehl von Hand: Extras ▸ Plug-ins ▸ Plug-in-Manager ▸ Eigene Plug-ins ▸ Neu…
  Typ Befehl, Name exakt «MCP Run Job», Script-Sprache Python:
      from vwmcp import vwmcp_bridge
      vwmcp_bridge.run_pending()
MSG
fi
