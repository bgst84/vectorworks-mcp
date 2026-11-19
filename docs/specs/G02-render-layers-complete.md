# G02 · `vw_render_layers`: symbols, texts, stacking order

Label: general · Size: M · Files: `render.py`, `tools/generic.py`, tests · Depends on: G01

## Goal

`vw_render_layers` becomes the default way for an agent to check its own
drawing: good enough to judge layout, collisions, line hierarchy and labels,
without Screen Recording and without Vectorworks being frontmost.

## Problem seen

- `vw_screenshot` returned distorted or wrong images whenever Vectorworks was
  not the frontmost app (Stage Manager / space switching). The agent wrote its
  own matplotlib renderer to continue.
- `vw_render_layers` exists but draws symbols as gray boxes (and with the
  current export, boxes of size 0), marks texts only with a cross, and paints
  all fills below all lines, so stacking problems (a light line over a bold
  wall) are not visible.

## Proposed interface

```python
vw_render_layers(layers=None, bbox=None, classes=None, max_size=1600,
                 fills=True, out_path=None, timeout=60,
                 symbols="expand",        # uses G01 expansion
                 texts="boxes",           # "cross" | "boxes" | "glyphs"
                 order="stack")           # "stack" (true drawing order) | "fills_first"
```

- Symbols drawn from their expanded children (G01).
- Texts: at least a box of the estimated text extent at the right anchor
  (font size × scale, line count from `\r`), better: simple stroke glyphs
  (a small built-in vector font is enough; no Pillow dependency).
- `order="stack"`: draw each object's fill then its outline in `stack` order,
  so the picture shows what overlaps what. Keep `fills_first` for area plans.
- Line widths from pen weight scaled to output size (today only 1/2/3 px);
  keep a minimum of 1 px.
- Return value: keep `Image`, and add the info dict (bbox, scale, counts) as
  text content or via `out_path` sidecar JSON.

## Acceptance

- Unit tests render small synthetic exports: a rotated symbol with nested
  children, a two-line text box, and a light line over a bold rectangle where
  `order="stack"` and `fills_first` give visibly different pixels.
- Live: rendering the fixture layer of a floor plan shows WC, washbasin,
  tables with chairs, beds, and room labels as boxes at the correct corner.
- Docstring of `vw_screenshot` points to `vw_render_layers` for checking work.

## As built (changes to the proposal)

- `texts` is `"boxes"` (default) or `"cross"`. Stroke glyphs are not built:
  the acceptance asks for boxes, and a vector font is a work item of its
  own. The box is an estimate (0.55 x font size per character of the longest
  line, 1.2 x font size per line), placed by justification and vertical
  alignment and turned with the text; a small x marks the origin. Exports
  without layer scale fall back to the cross.
- The info dict is returned as JSON text next to the image (no sidecar
  file); with `out_path` it also names the saved PNG.
- Solid fills are drawn with the object's opacity, so translucent area
  polygons no longer hide the plan in `order="stack"`.
- Pen weights use the layer scale and units of the export (G01); exports
  without them keep the three fixed steps.
- Objects without `stack` (old exports) are drawn in list order.
- Objects known only by a bounding box (plug-in objects, symbols that are
  not expanded, unknown types) are a gray outline and are never filled,
  whatever their own fill and pen are.
- The picture shows every object of the layer, also those of classes that
  are hidden in Vectorworks: the export has no class visibility.
- `exclude_classes` leaves out the objects of the named classes (a symbol
  of such a class with its contents). Its default comes from
  `app.register_render_excluded_classes`, an extension point that is empty
  upstream; `[]` draws everything. The info names what was left out.
  A name ending in `*` stands for all classes with that prefix.
