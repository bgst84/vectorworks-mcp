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

## Geometry read-back (Vectorworks 2027, live-tested)

- Vectorworks 2027 (32.1) embeds **Python 3.14**; 2026 embeds 3.9.
- `vs.GetBBox(h)` is the bounding box of the projection **on the screen
  plane**: with a rotated plan view the same object returns different,
  rotated coordinates. Don't use it for exact geometry.
- Exact geometry: lines `GetSegPt1/2`; polygons `GetVertNum` + `GetPolyPt(h, i)`
  (1-based); polylines `GetPolylineVertex(h, i)` → `(p, vertexType, arcRadius)`;
  texts `GetTextOrientation(h)` → `(origin, angle, mirrored)`, `GetText`,
  `GetTextSize(h, 0)`, `GetTextJust`; dimensions `GetDimText`.
- Arcs: `HCenter` is the arc's center, `GetSegPt1/2` its start and end
  points, `GetArc` → `(startAngle, sweep)` in degrees. Radius = distance
  center → start point.
- `vs.GetObjectUuid` + `vs.GetParent` over `ForEachObject(fn, "(ALL)")` gives
  a cheap before/after snapshot to find the objects a script created.

## Classes (Vectorworks 2027, live-tested)

- Attributes per class name: `GetClLW` (mils; mm = mils × 0.0254),
  `GetClLSN` (0 none, 2 solid, negative = line type resource:
  `Index2Name(-ls)`, set with `SetClLSN(name, -Name2Index(lineType))`),
  `GetClFPat` (0 none, 1 solid, negative = resource) plus
  `GetClVectorFill` → `(True, hatchName)` for hatches, `GetClPenFore/Back`,
  `GetClFillFore/Back` (0–65535; 8-bit = value // 257), `GetClUseGraphic`.
- **`GetClOpacityN(name)` returns `(pen, fill)`**, although its docstring says
  `(fill, pen)`. The class handle (`vs.GetObject(name)`, type 94) works with
  the object calls `GetOpacityN(h)` → `(ok, pen, fill)` and
  `SetOpacityN(h, pen, fill)`, which are documented correctly.
- `NameClass(name)` creates a class **and makes it active**: restore the
  active class afterwards. `RenameClass(old, new)` keeps the objects.
- PO4's earlier export script wrote pen opacity 100 for every class; the
  standard was regenerated from the template with `vw_class_export`.

## Embedded Python

- `open()` without `encoding=` uses **ASCII** in Vectorworks 2027: writing
  "ß" or "ä" fails with UnicodeEncodeError. Always pass `encoding="utf-8"`.
- A dimension standard name that doesn't exist (`SetObjectVariableString(d,
  27, name)`) silently falls back to another standard; read it back. The PO4
  template has "PO4 1:20"/"PO4 1:50"; "PO4" exists only where it was renamed.

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
with JXA `$.CGWindowListCopyWindowInfo` (owner contains "Vectorworks",
layer 0, title = document name), then `screencapture -x -o -l <id> out.png`.
That works even when the window is covered. It needs Screen Recording
permission for the calling app.

## AppleScript

See `architecture.md`: only `run VectorScript` calling
`DoMenuTextByName('MCP Run Job', 0)` is safe; `run Python script` writes,
and any script sent during launch or a modal dialog, crash Vectorworks.
The dictionary has no usable document list (`every document` → `missing value`).
