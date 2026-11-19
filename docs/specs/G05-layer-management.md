# G05 · Layer management tool

Label: general · Size: M · Files: `vwlib.py`, `tools/generic.py`, `journal.py` (revert handler), tests, `docs/vs-notes.md`

## Problem seen

The agent created a temporary layer to inspect symbols and could not remove
it: `vs.DelObject(layer_handle)` deleted nothing (layer empty but still
listed), `vs.SetLVis` does not exist. The user had to delete it by hand.
`CLAUDE.md` already lists `vw_create_layer` as a wanted generic helper.

## Proposed interface

```python
vw_layer(action, name, new_name=None, scale=None, visibility=None,
         after=None, force=False)
# action: "create" | "delete" | "rename" | "set" (scale/visibility) | "move" | "activate"
# visibility: "visible" | "hidden" | "gray" (reuse VISIBILITY in vwlib)
```

- `delete` refuses on a non-empty layer unless `force=True`; never deletes the
  active layer without first activating another one.
- Journaled: `vw_revert_last` undoes create (delete it), rename, set, move;
  delete is revertible only if it was empty (document this).
- Find the working `vs` calls live on a throwaway document and record them in
  `docs/vs-notes.md` (candidates to test: deleting a layer handle while it is
  not active, `vs.DeleteObjs` after selecting, a menu command as last resort).

## Acceptance

- Live: create → rename → set scale 100 → hide → delete works on a throwaway
  doc; `vw_list_layers` reflects each step; revert of create removes the layer.
- Unit tests for argument validation and journal entries.
