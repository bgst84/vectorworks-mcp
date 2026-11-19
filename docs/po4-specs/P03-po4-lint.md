# P03 · `vw_po4_lint`: check a drawing against the PO4 rulebook

Label: po4 · Size: L · Files: new `src/vwmcp/po4lint.py` (pure Python), `tools/po4.py` (tool), `tests/test_po4lint.py`, `docs/po4-setup.md` · Depends on: G01, P02 (for G25), the rulebook CSV

## Goal

The rulebook stops being only a document: a tool reports which rules a
drawing breaks, with rule IDs, so the agent can fix them before showing the
result, and Yves sees which rules are actually checked.

## Input

- `docs/po4-regelwerk-wettbewerb.csv`: CSV export of the Sheet "PO4 Regelwerk
  Wettbewerb" (master stays the Sheet; Yves re-exports after changes).
  Columns: ID, Bereich, Thema, Regel, Status, Wert / Mass, VW-Klasse / Objekt,
  Gilt für, Quelle. Only rows with Status `gesetzt` or `entschieden` are active.
- The layer export from `vw_export_geometry` (G01 format, symbols expanded).

## Design

- Checks are code, keyed by rule ID: `CHECKS = {"A13": check_rounding, ...}`.
  The CSV supplies the active set, text and values; a rule without a check is
  reported as `manual` (listed once, not as a finding).
- A check returns findings `{rule, severity, uuid, message, where}`.
- Start with these automatable checks:

| ID | Check |
|---|---|
| A06 | all texts use GT Pressura (Light/Bold) |
| A07 | at most 4 distinct pen weights among `0 graphics-*` classes; no weight below superlight |
| A12 | no `-bestand` classes on layers of a new-build project (parameter `status="neu"`) |
| A13 | wall rectangles/polygons and openings on a 0.05 grid (tolerance 1e-3); façade posts excluded |
| A15 | no object of a thinner class lies above an overlapping object of a thicker class (uses `stack`) |
| G07/G08 | door arcs sweep 90° and are in the superlight class |
| G25 | every room label is a two-line text whose top-left corner is inside a room polygon (P02) |
| G27 | no dimension objects on competition plan layers |
| G29 | `7 nachweise-*` polygons exist on the plan layer, none on a separate area layer |

- Tool: `vw_po4_lint(layer=None, rules=None, status="neu")` exports the layer
  itself and returns `{"findings": [...], "checked": [...], "manual": [...]}`.

## Acceptance

- Unit tests on small synthetic exports for each check (one passing, one failing case).
- Running it on the Skizze 01 reference export (`_geometrie.json`) gives no
  findings for A13/A15/G07 and documents any remaining ones.
- `docs/po4-setup.md`: how to re-export the CSV and what each check does.
