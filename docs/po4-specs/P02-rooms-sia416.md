# P02 · Rooms, labels and SIA 416 areas from the drawing script

Label: po4 · Size: M · Files: `po4lib.py`, `tests/test_po4lib.py`, `docs/po4-setup.md` · Depends on: P01 (`po4.label`)

## Goal

Areas are computed, not typed. In Skizze 01 the script calculated room areas
by hand (`a_room = ROOM_W * ROOM_D`, ...) and rounded them for the labels.
Decision (2026-11-19): the drawing script declares the rooms; no automatic
detection from walls.

## Rules

- SIA 416 areas as polygons in the matching class `7 nachweise-sia416-*`,
  on the layer of the floor plan itself, no separate layer (G29).
- Room label: name + area, top left (G25); flat label: type + area, e.g.
  "3.5 Zi / 52.5" (G26). Areas rounded to 0.5 m² for labels.

## Proposed API

```python
r = po4.room(name, polygon, use="HNF", flat=None, label=True, label_at=None)
#   use: SIA 416 code (HNF, NNF, VF, FF, KF...) -> class 7 nachweise-sia416-<code...>
#   (map codes to the exact class names of the PO4 template; list them in docs)
#   Draws the polygon in that class, computes the area (shoelace, holes allowed),
#   places po4.label top-left unless label=False. Returns {"name", "area", "use", "flat"}.

po4.flat_label(flat, x_left, y_top)        # sums rooms of that flat
po4.area_table(layer=None)                 # list of rooms + totals per use and flat;
                                           # also written as CSV next to the script if a path is given
```

- Areas are net areas of the polygon given; the script decides where the
  polygon runs (inner faces). Document that convention.
- Rounding helper `po4.round_area(a, step=0.5)` (pure, tested).

## Acceptance

- Pure tests: shoelace with hole; rounding 0.25 → 0.5 rule documented and tested.
- Skizze 01 helper script (from P01) declares its rooms; the labels show the
  same numbers as today (9.5 / 27.5 / 24.5 / 4 / 2 / 1.5; flats 52.5 / 39.5)
  or the spec documents why they differ (e.g. inner faces vs. glass axis).
