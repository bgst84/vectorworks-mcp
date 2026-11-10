# PO4: Einrichtung und Updates

## Neuer Arbeitsplatz (einmal pro Mac, ca. 5 Minuten)

Voraussetzungen: Vectorworks installiert, Claude Desktop installiert und
angemeldet, PO4 Dropbox synchronisiert.

1. Terminal öffnen (Programme ▸ Dienstprogramme ▸ Terminal) und einfügen:

   ```bash
   curl -LsSf https://raw.githubusercontent.com/bgst84/vectorworks-mcp/stable/scripts/install-po4.sh | bash
   ```

2. Die Schritte ausführen, die der Installer am Schluss auflistet:
   Claude mit Cmd-Q neu starten, Vectorworks neu starten, einmalig den
   Arbeitsgruppenordner setzen (Programm-Einstellungen ▸ Benutzerordner):
   `~/PO4 Dropbox/PO4/00_Organisation/18_Vectorworks/arbeitsgruppe`
3. In Claude «Ping Vectorworks» schreiben und die macOS-Abfrage erlauben.

## Was wo liegt

| Teil | Ort | Update |
|---|---|---|
| MCP-Server (Tools, Logik) | GitHub, Branch `stable` | automatisch bei jedem Start von Claude |
| Bridge `vwmcp/` + Menübefehl `MCP Run Job.vsm` | lokaler Plug-ins-Ordner | Installer erneut ausführen (selten) |
| PO4-Arbeitsumgebung (Menü PO4) | Arbeitsgruppenordner (Dropbox) | automatisch über Dropbox |

## Updates verteilen (Yves)

Entwickeln auf eigenen Branches, lokal testen (Claude zeigt dafür auf den
lokalen Klon). Wenn eine Version gut ist:

```bash
git checkout stable && git merge --ff-only <branch> && git push origin stable
```

Alle bekommen sie beim nächsten Neustart von Claude. Nur wenn
`BRIDGE_VERSION` steigt, müssen alle den Installer noch einmal ausführen;
`vw_ping` warnt dann von selbst.

Updates von Giorgio übernehmen: `git fetch upstream && git merge upstream/main`.

## Fehlersuche

- Claude kennt keine Vectorworks-Tools: Claude ganz neu gestartet (Cmd-Q)?
  Einstellungen ▸ Entwickler sollte «vectorworks» als running zeigen.
- «did not pick up the job»: Datei offen, kein Dialog offen, «MCP Run Job»
  im Menü PO4 vorhanden? Steht dort «nicht im Ordner Plug-ins», Installer
  erneut ausführen.
- Log: `~/.vwmcp/vwmcp.log`
