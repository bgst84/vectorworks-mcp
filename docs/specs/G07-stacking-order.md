# G07 · Stacking order tool

Label: general · Size: S · Files: `vwlib.py`, `tools/generic.py`, tests

## Problem seen

Plans need heavy lines in front of thin ones, otherwise thin lines cut
through walls ("strange overlaps"). The agent appended a loop of
`vs.HMoveForward(h, True)` per class to its script. That is a common need.

## Proposed interface

```python
vw_stack(layer=None, uuids=None, classes=None, to="front")
# to: "front" | "back" | "forward" | "backward"

vw_order_by_class(layer=None, order=["bold", "medium"], match="contains")
# brings objects to the front class group by class, so the LAST entry ends on top;
# match: "exact" | "contains" | "prefix"
```

- Moving changes existing objects, so it is not revertible by the
  created-objects journal: record previous `stack` positions (G01) and restore
  them in a revert handler, or document that it is not revertible.

## Acceptance

- Unit test with the fake executor: order after `vw_order_by_class` matches the
  requested class order.
- Live: a light line drawn over a bold rectangle ends up behind it.
