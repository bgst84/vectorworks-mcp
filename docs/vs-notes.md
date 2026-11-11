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
- Export scripts that read `GetClOpacityN` as one value get the pen opacity
  wrong (it returns pen and fill); check exported class data against the file.

## Embedded Python

- `open()` without `encoding=` uses **ASCII** in Vectorworks 2027: writing
  "ß" or "ä" fails with UnicodeEncodeError. Always pass `encoding="utf-8"`.
- A dimension standard name that doesn't exist (`SetObjectVariableString(d,
  27, name)`) silently falls back to another standard; read it back.

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

## Stories, levels and bounds (Vectorworks 2027, read-only live test)

- Story of a layer: `vs.GetStoryOfLayer(layer)`; `vs.GetName(story)`,
  `vs.GetStoryElevation(story)` (mm in a metre document: unlike geometry,
  this is not in document units), `vs.GetStorySuffix(story)`.
- `vs.GetLayerElevation(layer)` returns `(baseElev, thickness)`, also in mm.
- Story layer templates: `vs.GetNumStoryLayerTemplates()` and
  `vs.GetStoryLayerInfo(i)` (1-based) return
  `(ok, name, scale, levelType, elevationOffset, defaultWallHeight)`.
  A file can use story levels for bounds without setting a layer level type
  on any layer (`GetLayerLevelType` returns '').
- Levels of a story: `vs.GetLevelElevation(story, levelType)` (mm, relative
  to the story; returns 0 for a level the story doesn't have).
  Level type names: `vs.GetNumLayerLevelTypes()` + `vs.GetLevelTypeName(i)`
  (1-based). `vs.SetLevelElevation(story, levelType, mm)` moves every
  object bound to that level.
- Story bounds of walls and slabs: test `vs.HasObjStoryBound(obj, id)` for
  id 0 (bottom) and 1 (top), then
  `vs.GetObjStoryBound(obj, id)` → `(ok, boundType, boundStory, levelType,
  offset)`. boundType 2 = bound to a story level (`levelType` is the level
  name, `offset` in document units). 0 and 1 also occur (walls with fixed
  heights); their exact meaning is not verified yet.
  `boundStory` is a **relative story index** (0 = this story, 1 = the story
  above, -1 = below), not a handle. Passing a story handle to
  `SetWallOverallHeights` / `SetObjectStoryBound` pops a modal Script Errors
  dialog ("Invalid callback function parameter type").
  `GetObjStoryBoundsAt(obj, i)`
  returned id 0 for both i=0 and i=1; don't rely on it.
- `vs.JoinWalls(first, second, firstPick, secondPick, modifier, capped,
  showAlerts)`: modifier 1 T, 2 L, 3 X, 4 auto; the picks are points on each
  wall near the junction (like clicking with the Wall Join tool). For a T
  the wall that ends (the stem) must be `first`; the other order returns
  False. `vs.GetSegPt1/2(wall)` give the control line end points.
- `vs.GetWallOverallHeights(wall)` returns `(top, bottom)` as absolute Z in
  document units (note the order).
- `vs.CreateSlab(profile)` needs a polygon: a rectangle (`vs.Rect`) pops a
  modal "self-intersecting boundary" alert and leaves the rectangle.
  Bind with `vs.SetObjectStoryBound(slab, 0, 2, 0, level, offset)`; the
  slab style's datum component decides what sits on the level.
  `GetSlabHeight` shows the new bound only after the script has ended.
- Slabs are PIO type 86 with record "Slab" in this file (not type 147);
  `vs.GetSlabHeight(slab)` gives the datum elevation (document units),
  `vs.GetSlabStyle(slab)` a style index (`vs.Index2Name`).
- Components: `GetNumberOfComponents(obj)` → `(ok, n)`;
  `GetComponentName(obj, i)`, `GetComponentWidth(obj, i)` → `(ok, w)`,
  `GetComponentClass(obj, i)` → `(ok, classIndex)` (`vs.Index2Name`).
  Works for walls and slabs.

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

## Wall style Data tab (Vectorworks 2027, found by diffing two styles)

The "Data" tab of a wall style is not a record and not IFC data
(`NumRecords` 0, `IFC_GetNumPsets` False). It lives in ObjectVariables of the
wall style resource (`vs.GetObject(styleName)`, type 127):

| Selector | Kind | Field (German UI) |
|---|---|---|
| 1207 | string | Mark (Bezeichnung) |
| 1208 | string | Description (Beschreibung) |
| 1209 | int | Function (0 = custom / "Eigene Wand" seen) |
| 1210 | bool | Exterior (Außen) |
| 1211 | bool | Load bearing (Tragend) |
| 1212 | string | Fire rating (Feuerwiderstand) |
| 1213 | bool | Combustible construction (Brennbare Konstruktion) |
| 1214 | bool | Firewall (Brandmauer) |
| 1217 | string | Acoustic rating (Schalldämmung) |
| 1220 | string | Type (Typ) |
| 1221 | string | Manufacturer (Hersteller) |

1210/1211 confirmed on styles with only one of the two set. Wall styles of
the document: `vs.BuildResourceList(127, 0, '')` + `GetNameFromResourceList`;
skip names whose `vs.GetObject` is nil (library content). Components work on
the style handle like on walls. `vs.IFC_GetIFCEntity(h)` → `(ok, name)` and
`vs.IFC_GetNumPsets(h)` → `(ok, n)` are safe to call.

Component settings: "Join components butt" in the component dialog
("Schichten gestoßen verbinden") is `Get/SetCompAutoJoinCap(obj, i, flag)`.
Component function codes: 0 none, 1 load-bearing, 2 insulation, 3 interior
finish (confirmed in the German dialog: "Innenbekleidung"), 5 air gap (seen);
4 exterior finish and 6 other by list order. New style: `vs.CreateWallStyle`
returns the handle with one default component; add with
`InsertNewComponentN(h, n + 1, width, 0, 0, 0, 0, 0)`, then delete the
default. ObjectVariable 1195 on the style holds a class index (the wall
class); setting it read back 0, so it is not used yet.
