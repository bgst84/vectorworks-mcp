# G06 · Browse and import resources from library files

Label: general · Size: M · Files: `vwlib.py`, `tools/generic.py`, tests, `docs/vs-notes.md`

## Problem seen

Placing a WC or a washbasin required: finding the office library file by
walking the filesystem from inside Vectorworks, `vs.BuildResourceListN(16, path)`,
matching names, `vs.ImportResourceToCurrentFile`, then reverse-engineering
each symbol's orientation (which side is the wall side) from its geometry.
`CLAUDE.md` already lists "Library access" as the top roadmap item.

## Proposed interface

```python
vw_list_library(path, resource_type="symbol", name_contains=None, limit=500)
# -> [{"name", "folder", "bbox_def": [[x0,y0],[x1,y1]], "insertion": "center|corner|other"}]

vw_import_resources(path, names, resource_type="symbol")
# -> {"imported": [...], "already_present": [...], "missing": [...]}
```

- `path` may be a .vwx file or a folder (then list .vwx files inside, depth 2).
- `bbox_def`: extent of the definition contents relative to the insertion
  point, so callers can place by edge ("back of the WC on the wall line").
- Journaled: revert removes resources that were imported by the call and are
  still unused.
- `vw_insert_symbol` gains `source_path=None`: import on the fly if the
  symbol is not in the document.
- Resource types beyond symbols (hatches, wall styles, textures) via the same
  `resource_type` argument where `BuildResourceListN` supports them; record the
  type codes in `docs/vs-notes.md`.

## Acceptance

- Live: list a library file, import two symbols, place one with
  `vw_insert_symbol`, revert the import of an unused one.
- `bbox_def` of a centered symbol is symmetric around 0.
