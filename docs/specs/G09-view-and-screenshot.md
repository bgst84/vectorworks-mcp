# G09 · View control and screenshot guard

Label: general · Size: S · Files: `vwlib.py`, `tools/generic.py`, `screenshot.py`, tests

## Problem seen

- Fitting the view needed `vs.DoMenuTextByName("Fit To Objects", 0)`, which
  depends on the UI language and on which layers are visible/gray.
- `vw_screenshot` silently returned garbage when Vectorworks was not
  frontmost.

## Proposed change

```python
vw_set_view(fit="layer" | "objects" | "bbox", layer=None, bbox=None,
            view="top_plan" | None)
```
using `vs` zoom/pan calls where available (find them live; record in
`docs/vs-notes.md`), menu commands only as fallback.

`vw_screenshot`: check whether Vectorworks is the frontmost app (JXA/osascript
read only, no Apple Event to Vectorworks) and, if not, return a ToolError that
recommends `vw_render_layers` (or an option `require_front=False` to capture
anyway).

## Acceptance

- Unit test of the frontmost check with a mocked osascript result.
- Live: `vw_set_view(fit="layer", layer="X")` shows the whole layer.
