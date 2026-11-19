# P04 · Competition setup in a document

Label: po4 · Size: S · Files: `po4lib.py`, `docs/po4-setup.md` · Depends on: G05

## Goal

One call prepares an empty document (made from the PO4 template) for a
competition, so every project starts with the same structure.

## Rules

- Layer groups with separator layers: grundlagen → umgebung → grundrisse →
  ansichten → schnitte → details → 3D → schemas (E01); one "<Geschoss> boden"
  layer per storey (G28); base data on their own layers (E02).
- Draw in `-neu` classes; black is set per viewport/layout (decision 2026-11-18).

## Proposed API

```python
po4.setup_competition(storeys=["UG1", "EG", "OG1"], scale_plans=200,
                      scale_site=500, scale_details=50)
```
Creates the layers in order with scales, skips existing ones, returns the
list. Documents (no code) how to set class overrides to black in a viewport,
or implements it if a reliable `vs` call is found live.

## Acceptance

- Live on a throwaway document from the template: layer list matches E01/E02
  and is idempotent on a second call.
