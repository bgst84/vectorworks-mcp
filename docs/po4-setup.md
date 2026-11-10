# PO4: setup and updates

## New workstation (once per Mac, about 5 minutes)

Requirements: Vectorworks installed, Claude Desktop installed and signed in,
PO4 Dropbox synced.

1. Open Terminal (Applications ▸ Utilities ▸ Terminal) and paste:

   ```bash
   curl -LsSf https://raw.githubusercontent.com/bgst84/vectorworks-mcp/stable/scripts/install-po4.sh | bash
   ```

2. Do the steps the installer lists at the end: quit Claude with Cmd-Q and
   reopen it, restart Vectorworks, and set the workgroup folder once
   (Vectorworks Preferences ▸ User Folders):
   `~/PO4 Dropbox/PO4/00_Organisation/18_Vectorworks/arbeitsgruppe`
3. In Claude, write "Ping Vectorworks" and allow the macOS prompt.

## What lives where

| Part | Location | Update |
|---|---|---|
| MCP server (tools, logic) | GitHub, branch `stable` | automatic on every Claude start |
| Bridge `vwmcp/` + menu command `MCP Run Job.vsm` | local Plug-ins folder | re-run the installer (rare) |
| PO4 workspace (PO4 menu) | workgroup folder (Dropbox) | automatic via Dropbox |

Vectorworks does not load Python modules from the workgroup folder, so the
bridge has to be installed locally. Don't put a second copy of
`MCP Run Job.vsm` into the workgroup folder: duplicate commands conflict.

## Shipping updates (maintainer)

Develop on feature branches and test locally (Claude pointed at the local
checkout). When a version is good:

```bash
git checkout stable && git merge --ff-only <branch> && git push origin stable
```

Everyone gets it the next time they restart Claude. Only when
`BRIDGE_VERSION` goes up does everyone need to re-run the installer;
`vw_ping` warns about that by itself. Don't run the installer on your
development Mac: it switches Claude from the local checkout to `stable`.

Pulling in upstream changes: `git fetch upstream && git merge upstream/main`.

## Troubleshooting

- Claude has no Vectorworks tools: was Claude fully restarted (Cmd-Q)?
  Settings ▸ Developer should list "vectorworks" as running.
- "did not pick up the job": is a drawing open, no dialog open, and
  "MCP Run Job" in the PO4 menu? If the menu says it is not in the Plug-ins
  folder, re-run the installer.
- Log: `~/.vwmcp/vwmcp.log`; Claude's own log of the server:
  `~/Library/Logs/Claude/mcp-server-vectorworks.log`.
- Development Mac only (Claude pointed at the local checkout): if the log
  says `No module named 'vwmcp.server'`, macOS has marked the editable
  install's `.pth` file as hidden, and Python 3.13+ skips hidden `.pth`
  files. Check with `ls -lO .venv/lib/python3.14/site-packages/*.pth`, fix
  with `uv sync --reinstall-package vwmcp` (or `chflags nohidden` on it),
  then restart Claude. Office Macs install from GitHub without a `.pth`
  file and are not affected.
