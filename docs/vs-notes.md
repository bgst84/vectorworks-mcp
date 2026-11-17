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
- **A new plug-in object's class is reset by its first regeneration**, which
  happens at the end of the creating job even after an explicit
  `ResetObject`. `SetClass` in the same job as `CreateCustomObjectN` is lost
  (TrussItem came back "None"); `SetClass` in a later job sticks through
  further resets and moves. Tools therefore assign the class in a second
  job (`set_objects_class`).

## Lighting devices (live 2026-11-17)

How to make a Lighting Device by script, found by experiment on the user's
plot (33 Martin MAC One devices on 4 Light Position Objs and a truss run):

- **`CreateCustomObjectN("Lighting Device", ...)` is a dead end.** It makes a
  plug-in object with no symbol geometry (`GetSymName` ""), `Inst Type`
  empty, `Device Type` "Light", `Num Channels` 1, nothing from the symbol.
- **What works:** `vs.Symbol(fixture, pt, rot)`, select only the new symbol
  instance(s) (`DSelectAll`, `SetSelect`), then
  `vs.DoMenuTextByName("Convert to Instrument", 0)`. The selection is
  replaced by Lighting Device objects (new uuids) with `Inst Type`,
  `Device Type` "Moving Light", `Wattage`, `Num Channels` 108, `GDTF Fixture
  Name`, `GDTF Type ID` filled from the symbol's **`Light Info Record`**.
  `Weight` shows "0" until the next reset, then "9.92 lb". Works for several
  selected symbols at once. The command needs a selection, so
  `vwlib.insert_lighting_devices` records and restores the user's selection.
- **Position does not hang the device.** Writing `Position` + `ResetObject`
  sets the name but leaves z at 0; Spotlight's insertion tool sets z itself.
  So read the position's z (`GetSymLoc3D` of the Light Position Obj /
  TrussItem / pipe with that name, `POSITION_PLUGINS`) and `Move3DObj` the
  device to it. Existing devices on "palm NE" sit at the position's z (118)
  on 17" centres; the Light Position Obj itself has `StartNum`, `Increment`,
  `Direction`, `Numbering Style`, `TotalHungWeight` fields.
- The `LDevice_*` functions (`LDevice_Reset`, `LDevice_GetActSym`,
  `LDevice_SetParamStr`, ...) and `HP_ConvertToHangPos`, `SL_Import`/`SL_Export`
  have **no docstrings** in 2026; still unused. Unit Number, Channel, Purpose,
  Position are set with plain `SetRField` + `ResetObject` and stick.
- Local fixture libraries on this Mac: only 3 files under
  `Entertainment/Lighting/Instruments` (incl. "Martin Lighting Moving
  Light.vwx"); the rest is download-on-demand.

## Truss runs (live 2026-11-17)

What Spotlight's Insert Truss tool leaves behind, read from a 5-piece
DJ truss on the user's plot, and reproduced by `vwlib.insert_truss_run`:

- One `TrussItem` per piece, `CenterBased`, `GetSymLoc3D` = piece centre
  with z = trim height in document units (120 = 10' on a feet-inches doc;
  `TrimHeight` field stays 0). Consecutive centres are one symbol length
  apart along the piece's rotation (`GetSymRot`).
- Dimensions come from the symbol definition's **`BrxTrussItemRecord`**
  (Length/Height/Width in mm, Weight in kg, Type, Section, Connection,
  ItemType). Writing `Length` as `"3000mm"` through `SetRField` parses
  correctly (reads back `9.84251968503937e00'`). Document units per mm =
  `GetUnits()[3] / 25.4`. The symbol also carries `Truss Record` (model,
  manufacturer, "3000mm" strings) and `EntEquipUniversal`.
- `Weight` on the TrussItem is grams (`19050` for 19.05 kg); `Distributed
  weight` is kg/m (`6.35`).
- Linking: each piece's `C_START_UUID` holds the uuid of the previous piece
  in the run (first piece empty). `TrussSystem` "T<n>", `TrussLine` "1",
  `TrussSystemLineIdent` "T<n>-1"; Insert Truss numbers systems T0, T2…
  with gaps, so pick the lowest unused. `ConStart`/`ConEnd` stayed 0.
  Whether Braceworks accepts the run as a system is still to be checked
  (run a Braceworks calculation on a test run).
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
