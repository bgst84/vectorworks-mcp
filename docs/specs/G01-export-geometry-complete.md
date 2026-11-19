# G01 · `vw_export_geometry`: symbols, walls, stacking order

Label: general · Size: M · Files: `vwlib.py` (`export_geometry`, `_geom`, `_attrs`), `tools/generic.py`, `docs/vs-notes.md`, tests

## Goal

The export is the ground truth for checking drawing work without the screen.
It must describe everything a plan contains, so that a renderer (G02) or a
linter can reproduce and judge the drawing.

## Problem seen

- Symbols come back as `{"type": "Symbol", "center": [0,0], "bbox_view": [[0,0],[0,0]]}`:
  no name, no insertion point, no rotation, no extent. The agent had to write
  its own walker over symbol definitions to see a WC or a table.
- Nested symbols (chairs inside a table symbol) are invisible even then.
- Wall objects (type 68) are only a view bbox; their outline is unknown.
- The order of objects (stacking) is implicit in list order but not stated,
  and groups lose their position in that order for consumers.
- Hatch / vector fill names are missing from `attrs` (only pattern 0/1/2).
- Text: `size_raw` has an unclear unit (values like 1200.0 for an 8 pt
  label at 1:200 were seen in other files), font name is missing.

## Proposed interface

New parameters, defaults keep today's output compatible:

```python
vw_export_geometry(layer=None, classes=None, out_path=None, limit=20000,
                   timeout=60, attributes=True,
                   symbols="instances",   # "instances" | "expand"
                   symbol_depth=3)
```

- Every Symbol entry gets `symbol` (name), `insert` [x, y], `rotation` (deg),
  `mirrored` (bool), `scale` [sx, sy] if available, and a correct
  `bbox` computed from the definition contents transformed to world space.
- `symbols="expand"`: additionally emit the definition's objects transformed
  to world coordinates, each with `"parent": <symbol entry uuid>` and
  `"depth": n`. Recurse into nested symbols and groups up to `symbol_depth`.
  Class/attrs are the child's own (resolve "by class" against the document).
- Walls: `points` = outline polygon in world coordinates (from start/end
  point, width and offset; check `vs` calls live and note them in
  `docs/vs-notes.md`), plus `wall_style` and `width`.
- Every entry gets `stack` (0 = backmost, increasing) over the whole layer,
  children of groups/symbols included in drawing order.
- `attrs.fill.hatch` = vector fill / hatch name when the fill is a hatch;
  `attrs.opacity` if obtainable.
- Texts: `font` (name) and `size_pt` (verified unit), `just`, `vertical_align`.

## Acceptance

- Unit tests with the fake executor cover: symbol transform (rotation 0/90/180/-90,
  mirror), nested expansion with depth limit, `stack` ordering through groups.
- Live check (throwaway doc, announce to user): a layer with a rotated library
  symbol containing a nested symbol exports children whose world coordinates
  match a manual calculation within 1e-4.
- `geometry_summary` and `vw_render_layers` keep working with old and new output.
- Findings about the `vs` calls used are recorded in `docs/vs-notes.md`.

## As built (changes to the proposal)

- The result also carries the layer `scale` and `units_per_inch` at the top
  level. G02 needs both to size texts and pen weights; a text of `size_pt`
  points is `size_pt / 72 * units_per_inch * scale` document units high.
- `depth` counts symbol nesting only: children of a top-level instance have
  depth 1, the children of a symbol nested in it depth 2. Groups inside a
  definition are flattened like groups on the layer (`group` = uuid).
  `symbol_depth=0` equals `symbols="instances"`. A nested symbol beyond the
  limit is still listed as an instance with its `bbox`.
- An expanded symbol entry has `children` (number of direct children).
  Expanded objects carry the uuid of the object in the definition, so one
  uuid repeats for every instance; tell them apart by `parent` and `stack`.
- `classes` filters layer objects by their own class. The contents of a
  symbol come with the instance and are not filtered. `stack` counts every
  object of the layer, so the numbers do not depend on the filter.
- `limit` counts expanded children.
- Symbols no longer report `bbox_view` (it was `[[0,0],[0,0]]`); `center`
  is the middle of `bbox`.
- Needed for transforming definition contents, and added on the layer too:
  rectangles and rounded rectangles have `points` (four corners, turned
  rectangles included) and `closed`; ovals have `center`, `radii` and
  `rotation`. `center` and `bbox_view` stay for old consumers. Objects
  without exact geometry inside a symbol (plug-in objects) get `bbox`, the
  box of their turned box.
- Under a non-uniform symbol scale, arcs and ovals use the mean scale
  (points, lines and polygons are exact).
- Coordinates read inside a symbol definition are shifted by the user
  origin of the document; the export adds `GetOrigin()` back (found on a
  real project, see `docs/vs-notes.md`).
- Walls: outline centered on the definition line, plus `line`, `width`,
  `wall_style`. Round walls are not covered.
- `attrs.opacity` is a top-level key of `attrs` (percent), not per fill/pen.

## Notes

`vs.GetBBox` depends on the view's plan rotation (see the comment in `_geom`);
compute symbol extents from the definition, not from `GetBBox` of the instance.
