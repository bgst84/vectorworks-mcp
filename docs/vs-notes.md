# `vs.*` notes (Vectorworks 2026, macOS, live-tested)

Findings from building and using this server against Vectorworks 2026
Update 3 (build 846827). Embedded Python is **3.9.2**. Each run of the
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

## Borrowed from vicquick/vwx-mcp (not yet verified here)

Call patterns read from vwx-mcp's `commands.py` (MIT; validated by them on
Vectorworks 2026/2027 for Windows). Used by `vwlib` for the drawing tools
added 2026-11-17; each needs one live check on this Mac on a throwaway doc.

- **`vs.Layer(name)` is dangerous.** On VW 2026 it parks the script in a
  nested event loop; vwx-mcp crashed VW from a web-palette callback, hung it
  from a Windows timer, and had it silently kill their pump from a menu
  command. Prefer `vs.SetActiveLayerN(layer_handle)` (`vwlib._activate_layer`
  falls back to `vs.Layer` only if that is missing). Our `insert_symbol` used
  `vs.Layer` since 2026-10-15 without visible harm from the menu-command
  context; now switched.
- Resources: `vs.BuildResourceListN(type, path)` → `(list_id, count)` over a
  saved `.vwx`; `vs.BuildResourceList(type, 0, '')` for the current document;
  `vs.GetNameFromResourceList(list_id, i)` (1-based);
  `vs.ImportResToCurFileN(list_id, i, callback)` imports one resource with
  Vectorworks' importer (plug-in style data included); the callback handles
  name conflicts, which `vwlib.import_resource` avoids by renaming first.
  Type 16 = symbol definition (plug-in styles are symbol definitions
  wrapping one plug-in object), 47 = record format, 97 = texture.
  `ForEachObject` with `T=SYMDEF` never sees resources; walk `FSymDef` /
  `NextSymDef` (as `list_symbols` does) or use `BuildResourceList`.
- Plug-in objects: `vs.CreateCustomObjectN(name, (x, y), rot, False)` with the
  plug-in's **internal** name ('Lighting Device', 'Truss', 'Soft Goods',
  'Stage Deck', 'Light Position Obj'); parameters are the fields of the record
  named like the plug-in (`GetParametricRecord`, `GetFldName`), set with
  `SetRField` then `vs.ResetObject(h)`. Same path our Door notes use.
- Layers: `vs.CreateLayer(name, 1)` design / `2` sheet (makes it active),
  `vs.SetLScale(h, denominator)`, `vs.DelObject(layer_handle)` deletes it.
- Classes: `vs.NameClass(name)` creates **and activates**; `vs.DelClass(name)`.
- Views: `vs.SetViewVector(camera_dir, (0, 0, 0), up)` for standard 3D views
  (iso = `(1, -1, 1)`, up `(0, 0, 1)`); `vs.SetView(xa, ya, za, dx, dy, dz)`
  for flyover angles. VW 2026 has no `ZoomToSel`; use `Fit To Objects`.
- Moving: `vs.HMove(h, dx, dy)` (2D/screen plane), `vs.Move3DObj(h, dx, dy, dz)`.
- `vs.CombineIntoSurface` took 215 s on their test; avoid in bulk.

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
