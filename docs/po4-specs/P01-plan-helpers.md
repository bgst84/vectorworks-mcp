# P01 · `po4` plan helpers from Skizze 01

Label: po4 · Size: L · Files: `po4lib.py` (module `po4`), `tests/test_po4lib.py`, `docs/po4-setup.md` · Uses G06/G07 when available, but can start with direct `vs` calls

## Goal

A floor plan script should consist of parameters and helper calls. The
Skizze 01 script (`tests/fixtures/po4_skizze_01/skizze_01_grundriss.py`,
~300 lines) re-implements glass façades, bathrooms, kitchens, labels and
stacking by hand. Move those into `po4` so the next sketch is ~80 lines.

## Rules these helpers must follow

From the PO4 rulebook (Sheet, CSV at `docs/po4-regelwerk-wettbewerb.csv`);
IDs in brackets. Defaults come from here; every default is a keyword argument.

- Dimensions rounded to 5 cm (A13); façade post spacing is the only exception
  (evenly distributed).
- Heavy lines in front of thin ones (A15).
- Doors 90°, leaf and arc superlight; flat entrance door 1.00 (G07, G08).
- Glass façade: glass axis 0.10 from the outer edge; posts 6.5×6.5 cm flush
  against solid walls, centered on the axes of abutting interior walls,
  evenly distributed in between at ~0.80; two light view lines per field (the
  post faces), like a door threshold; interior walls end at the post inner
  face; entrance door 1.00 is an exception in the grid.
- Vorwand as its own black rectangle in front of the wall, not part of the
  wall (G15). Depth: the Sheet now says **0.30**, Skizze 01 used 0.25 → use
  0.30 as default and confirm with Yves.
- WC/washbasin on the Vorwand, shower 0.90 wide (fixed), length variable,
  directly against the wall (G14, G16, G17).
- Kitchen 0.60 deep, 0.60 modules, directly against the wall (G20).
- Room label: name + area (m², no unit) on two lines, top left in the room (G25).
- Furniture in `4 elements-furniture`, drawn classes `-neu` (status classes of
  the template); black is set in the layout.

## Proposed API (all coordinates in document units, plan orientation)

```python
po4.walls2d(rects, openings=(), mode="poche")
#   rects: [(x1, y1, x2, y2), ...]; openings: [(x1, y1, x2, y2), ...] cut out;
#   mode "poche": union to one bold body (as Skizze 01);
#   mode "objects": real walls via po4.wall with competition wall styles
#   (style per thickness from a mapping argument). Returns handles.

po4.glass_facade(a0, a1, axis, outer, orient="h", wall_axes=(), doors=(),
                 grid=0.80, post=0.065, view_lines="double")
#   Pure function po4.facade_posts(a0, a1, wall_axes, doors, grid, post)
#   returns the post axes and field list (testable without vs).

po4.bath(origin, size, orient, vorwand=0.30, wc="toilet simplified 03",
         basin="waschtisch simplified 05", shower=(0.90, None), door=None)
#   Draws Vorwand (medium rectangle), places WC and basin against it,
#   shower at the short end; returns the free floor polygon (for G24 hatch).

po4.kitchen(origin, length, orient, depth=0.60, leg=None, sink=1, hob=3)
#   Straight or L-shaped (leg = length of the second run along the adjacent
#   wall); module lines every 0.60; sink and hob symbols from the office
#   library rotated with their back to the wall.

po4.symbol(name, x, y, rot=0, library=PO4_LIBRARY)
#   Imports from po4_symbole_2027.vwx if missing (convention of that
#   library: symbols centered, back/wall side = +y). Use G06 when available.

po4.label(x_left, y_top, name, area=None, pad=0.12)   # top-left anchored
po4.stack_by_weight(layer=None)                         # A15; G07 when available
po4.stair_two_flight(x0, y0, width, run, treads, tread=0.30, eye=0.10, landing=1.20)
po4.lift_shaft(x0, y0, inner=(1.55, 1.70), wall=0.15, door=(0.50, 0.85))
po4.door(...)  # unchanged, but document hinge/swing with a picture-like example:
#   o="h", wall from w0 to w1 (w1 > w0): swing=+1 opens toward w1 (up), -1 toward w0;
#   hinge=-1 hinge at a0, +1 at a1. Same for o="v" with x instead of y.
```

Keep geometry calculation in pure functions (post axes, kitchen modules,
bathroom fixture positions, stair treads) and the `vs` drawing in thin
wrappers, so `tests/test_po4lib.py` can test the geometry without Vectorworks.
`po4lib.py` must stay Python 3.9 compatible.

## Acceptance

1. Pure-function tests: post axes for the four façade segments of Skizze 01
   equal the reference (from `_geometrie.json`, rectangles in class
   `0 graphics-b medium-neu` on the glass axis), within 1e-4.
2. Rewrite the fixture script with the helpers as
   `tests/fixtures/po4_skizze_01/skizze_01_helpers.py`. Live (throwaway
   document, announce to Yves): its export compared with `_geometrie.json`
   has the same counts per class and type, and every reference object has a
   match within 0.005 m (write the comparison as a small script in
   `scripts/` so it can be reused).
3. `docs/po4-setup.md` documents each helper with one example.
