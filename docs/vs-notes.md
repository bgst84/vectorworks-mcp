# `vs.*` notes (Vectorworks 2026, macOS, live-tested)

Findings from building and using this server against Vectorworks 2026
Update 3 (build 846827) and, from 2026-11-17, 31.7. Embedded Python is **3.9.2**. Each run of the
menu command gets a fresh Python state (module globals don't persist).

## General

- `vs.GetName(h)` returns `"none"` for unnamed objects. A real object named
  "none" is the one `vs.GetObject("none")` returns, though that call can
  also match the class **None**, so compare handles.
- Layer names: `vs.GetLName(layer)`. `GetName` returns `""` for layers.
- Handles print as integers and are only valid during one script run. Use
  `vs.GetObjectUuid(h)` / `vs.GetObjectByUuid(uuid)` across calls.
- A nil handle compares as `str(h) == "0"`.
- `vs.ForEachObject(fn, "(ALL)")`, `"(T=RECT)"`, `"(PON='Lighting Device')"`,
  `"(T=86)"` (plug-in objects) all work.
- `vs.GetUnits()` → `(fraction, display, format, upi, name, sqName)`, e.g.
  `(25, 3, 2, 1.0, '"', ' sq ft')` for feet-and-inches documents.
- Most `vs` functions carry a docstring with a `Definition:` signature;
  `LDevice_*` don't.
- A call with the wrong number or type of arguments doesn't raise. It
  queues a modal **Script Errors** dialog shown when the script ends.
- `vs.NameUndoEvent(...)` neither names the Undo menu item nor stops
  Vectorworks merging consecutive scripted menu-command runs into one undo.

## Spotlight

- Lighting Device = plug-in object; parameters via
  `vs.GetRField(h, "Lighting Device", field)` / `SetRField`, then
  `vs.ResetObject(h)`. The reset takes effect when the script ends, so read
  back in a separate run.
- `UniverseAddress` (`"2/101"`) or `Absolute Address` are authoritative;
  `Universe` / `DMX Address` written on their own are overwritten on reset.
  Absolute = (universe-1)*512 + address.
- Useful fields: Unit Number, Channel, Dimmer, Purpose, Position, Inst Type,
  Wattage, Color, Template / Template2 (gobos), Focus, Circuit Number/Name,
  Symbol Name, Device Type, Num Channels, Fixture Mode, GDTF Fixture Name,
  User Field 1-6. Unit numbers repeat per position and may be blank.
- Positions: `Light Position Obj` (name in `Position Name`), `Lighting Pipe`,
  `Lighting Pipe Ladder` (`Name`). Devices reference positions by name.
- `LDevice_GetParamStr(h, 0, name)` is the wrong signature (Script Errors,
  returns `""`). Real signature unknown.

## Drawing and 3D

- Walls from `vs.Wall(...)` have one component; `SetWallThickness` and
  `SetWallHeights` silently do nothing (even after `ConvertToUnstyledWall`).
  Use `vs.SetComponentWidth(w, 1, t)` for thickness and
  `vs.SetWallCornerHeights(w, h, 0, h, 0)` for height.
- Doors: `vs.CreateCustomObjectN('Door', pt, rot, False)` (no dialog). Set
  both `Width` and `DoorWidth` (Width alone reverts). Local frame:
  `SwingDirection` Out → local +y, In → local -y; `SwingHingeSide` Right →
  hinge at local -x, Left → +x. `vs.GetBBox` on doors is unreliable; verify
  via the arc inside `FInGroup` (`HCenter` / `GetArc`).
- Extruded circles (`ArcByCenter` inside `BeginXtrd`) render as octagons at
  low 3D conversion resolution; build round things from 48-gon polygons.
- Top/Plan view: `vs.DoMenuTextByName('Standard Views', 1)`. Zoom to objects:
  select them, then `vs.DoMenuTextByName('Fit To Objects', 0)`.

## Screenshots (outside Vectorworks)

VectorScript can't save the viewport to a file (`ExportImageFile` only
exports existing image objects). From macOS: get the document window's id
from `CGWindowListCopyWindowInfo` (owner name "Vectorworks 2026", layer 0,
title = document name; palettes are layer 103), then
`screencapture -x -o -l <id> out.png`. That works even when the window is
covered. It needs Screen Recording permission for the calling app.
`src/vwmcp/screenshot.py` does this through ctypes; calling the same API
through JXA's ObjC bridge segfaulted `osascript` (2026-11-17).

## Drawing tools (live-tested 2026-11-17, VW 2026 build 31.7)

Call patterns first read from vicquick/vwx-mcp's `commands.py` (MIT), then
run here through the menu command on the user's sketch document
(solarplexia_dec2026.vwx), every step reverted afterwards.

- **Layer activation.** VW 2026 Python has **no `SetActiveLayerN`**; the only
  call is `vs.Layer(name)`. vwx-mcp found it hazardous from a palette callback
  or Windows timer (nested event loop), but from our menu-command context
  `CreateLayer` + `vs.Layer(previous)` ran cleanly and restored the active
  layer. Keep using it only from the menu command.
- Resources: `vs.BuildResourceListN(16, path)` → `(list_id, count)` lists the
  symbols of a library `.vwx` without opening it (49 names from Global Truss
  F34.vwx in ~0 s). `vs.GetNameFromResourceList(list_id, i)` is 1-based.
  **`vs.ImportResourceToCurrentFile(list_id, i)`** (two args, documented)
  imports one symbol; `ImportResToCurFileN` also exists but has no docstring
  and was not used. Importing a truss symbol brought only the 2D/hybrid
  definition, not a `_3d` companion like the ones Spotlight's Insert Truss
  tool had left in the file. `vs.GetObject(name)` finds a symbol definition;
  `vs.DelObject` on it removes it. `ForEachObject` with `T=SYMDEF` never sees
  resources; walk `FSymDef` / `NextSymDef` (as `list_symbols` does).
- **Truss objects are `TrussItem`**, not `Truss`. `vs.CreateCustomObjectN(
  'Truss', ...)` returns nil. `CreateCustomObjectN('TrussItem', (x, y), rot,
  False)` works; fields: `Symbol` (a truss symbol definition in the document),
  `Name`, `Type`, `PositionName`, `Length`, `Height`, `Width`, `Weight`,
  `TrussSystem`, `ItemType` ... Setting `Symbol` + `ResetObject` draws the
  truss, but `Length`/`Height`/`Width` stay 0 (Insert Truss reads them from
  the symbol's truss record); set them explicitly if Braceworks needs them.
  Existing plot: 13 TrussItem, 33 Lighting Device, 4 Light Position Obj.
- Right after `CreateCustomObjectN` the object reports an empty bbox and
  "not visible"; it regenerates by the next job. A regen can shift the
  insertion point slightly (observed 0.45 units), so a move + reverse move
  around a `ResetObject` doesn't land exactly on the start point.
- `vs.GetBBox` on the TrussItem returned coordinates ~2000 units from its
  `GetSymLoc` (0, 0): user origin vs internal origin. Use `GetSymLoc` for
  plug-in object positions.
- Layers: `vs.CreateLayer(name, 1)` design / `2` sheet (makes it active),
  `vs.SetLScale(h, 48)` (read back 48.0), `vs.DelObject(layer_handle)` deletes.
- Classes: `vs.NameClass(name)` creates **and activates**; calling it again
  with the previous name restores; `vs.DelClass(name)` removes.
- Views: `vs.SetViewVector((1, -1, 1), (0, 0, 0), (0, 0, 1))` gives Right
  Isometric; `vs.DoMenuTextByName('Fit To Objects', 0)` fits all (no
  selection needed) and VW 2026 has no `ZoomToSel`. `ReDrawAll` after.
- Moving: `vs.HMove(h, dx, dy)` on a plug-in object works and reverses.
- `vs.CombineIntoSurface` took 215 s on vwx-mcp's test; avoid in bulk.

Library files on this Mac: `/Applications/Vectorworks 2026/Libraries/`
(Entertainment/{Lighting, Stage, Audio, Rigging/Truss, Rigging/Truss Pickups},
Visualization/People, Defaults/Stage Deck; 60 `.vwx` under Entertainment) and
`~/Library/Application Support/Vectorworks/2026/Libraries/` (user, Favorites).
Some app libraries are download-on-demand (`*.db.proxy`); only present `.vwx`
files are listed.

## AppleScript

See `architecture.md`: only `run VectorScript` calling
`DoMenuTextByName('MCP Run Job', 0)` is safe; `run Python script` writes,
and any script sent during launch or a modal dialog, crash Vectorworks.
The dictionary has no usable document list (`every document` → `missing value`).
