# G08 · Checkpoint for scripts that redraw a layer

Label: general · Size: M · Files: `tools/generic.py`, `vwlib.py` (`exec_tracked`), `journal.py`, tests · Depends on: G05

## Problem seen

The recommended pattern for drawing scripts is idempotent: clear the layer,
draw everything again. Every run then reports
`"N pre-existing object(s) were deleted; vw_revert_last can't restore them"`.
One wrong run loses the previous state of the drawing.

## Proposed change

`vw_exec_python` / `vw_exec_file` gain `checkpoint_layers: list[str] | None`.
Before running, each listed layer is duplicated (reuse `duplicate_layer`) into
a hidden layer named `~checkpoint <layer> <timestamp>`. `vw_revert_last`
then restores: delete the redrawn layer content, move the checkpoint content
back, delete the checkpoint layer. Keep at most N checkpoints per layer
(default 3), oldest removed.

## Acceptance

- Live: run a script that clears and redraws a layer with `checkpoint_layers`,
  then `vw_revert_last`: the layer is identical to before (export diff empty).
- Checkpoint layers are hidden and do not appear in exports of other layers.
